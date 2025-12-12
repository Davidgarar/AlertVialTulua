from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify, Response
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv
from security import encrypt_password, verify_password
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from geopy.geocoders import Nominatim
import requests
from data_filters import FiltroAccidentes
from risk_processor import ProcesadorRiesgo
from route_calculator import CalculadorRutaSegura
import json 
from datetime import datetime, timedelta
from export_utils import ExportUtils, PDFGenerator
import os
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor
import math

# --- IMPORTACIÓN NUEVA PARA LA IA ---
from ai_validator import AccidentAIValidator

# Configuración inicial
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' 
load_dotenv()

app = Flask(__name__)
app.secret_key = "secretSUPERT_key"

# Instancias de clases auxiliares
procesador_riesgo = ProcesadorRiesgo()
calculador_rutas = CalculadorRutaSegura(procesador_riesgo)

# --- INICIALIZACIÓN DE LA IA ---
ai_validator = AccidentAIValidator()

API_KEY = os.getenv("WEATHER_API_KEY") 

# Configuración de carpeta de subida
UPLOAD_FOLDER = 'static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Crear carpeta si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Conexión a PostgreSQL
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

# Configuración de OAuth para Google
google_bp = make_google_blueprint(
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    redirect_to="google_login_callback",
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
)   
app.register_blueprint(google_bp, url_prefix="/google_login")

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
app.config['MAIL_USE_TLS'] = True

mail = Mail(app)    
s = URLSafeTimedSerializer(app.secret_key)  


# ==========================================================
# 1. RUTAS DE AUTENTICACIÓN Y BÁSICAS
# ==========================================================

@app.route('/login_google')
def login_google():
    return redirect(url_for("google.login"))

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT contrasena FROM usuarios WHERE correo = %s", (correo,))
                user = cur.fetchone()

            if user and verify_password(user[0], contrasena):
                session['user'] = correo
                flash('Inicio de sesión exitoso', 'success')
                return redirect(url_for('alertv'))
            else:
                flash('Correo o contraseña incorrectos', 'error')

        except psycopg2.Error as e:
            print("Error al consultar la base de datos:", e)
            flash('Error en la base de datos', 'error')

    return render_template('index.html')

@app.route('/alertv')
def alertv():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('alertv.html', user=session['user'])

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/google_login/callback')
def google_login_callback():
    if not google.authorized or not google.token:
        flash("No se pudo autorizar con Google.", "error")
        return redirect(url_for('index'))

    try:
        resp = google.get('https://www.googleapis.com/oauth2/v3/userinfo')
        resp.raise_for_status()
        user_info = resp.json()
    except Exception:
        flash("No se pudo iniciar sesión con Google. Cancelado o error de autenticación.", "error")
        return redirect(url_for('index'))

    email = user_info.get('email')
    google_id = user_info.get('sub')
    if not email or not google_id:
        flash("No se obtuvo información suficiente de Google.", "error")
        return redirect(url_for('index'))

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE correo = %s", (email,))
            user = cur.fetchone()
            if not user:
                cur.execute(
                    "INSERT INTO usuarios (nombre_usuario, correo, contrasena, ciudad) VALUES (%s, %s, %s, %s)",
                    (user_info.get('name', 'usuario sin nombre'), email, google_id, 'ciudad no especificada')
                )
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        print("Error al insertar datos:", e)
        flash("Ocurrió un error al registrar el usuario.", "error")
        return redirect(url_for('index'))

    session['user'] = {'nombre': user_info.get('name', 'usuario sin nombre'), 'email': email}
    flash("Inicio de sesión con Google exitoso.", "success")
    return redirect(url_for('alertv'))

@app.route('/registrar', methods=['POST'])
def registrar():
    try:
        nombre = request.form['nombre']
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        ciudad = request.form['ciudad']

        with conn.cursor() as cur:
            contrasena_hash = encrypt_password(contrasena)
            cur.execute(
                "INSERT INTO usuarios (nombre_usuario, correo, contrasena, ciudad) VALUES (%s, %s, %s, %s)",
                (nombre, correo, contrasena_hash, ciudad)
            )
        conn.commit()
        return redirect('/')
    except psycopg2.Error as e:
        conn.rollback()
        print("Error al insertar datos:", e)
        return "Ocurrió un error al registrar el usuario."

@app.route('/logout')
def logout():
    session.pop('user', None) 
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for('index'))


# ==========================================================
# 2. RUTAS DE REPORTE Y PROCESAMIENTO (CON IA)
# ==========================================================

@app.route('/reportar')
def reportar():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('report.html')

@app.route('/procesar', methods=['POST'])
def procesar():
    geolocator = Nominatim(user_agent="geoapi", timeout=10)

    # Obtener datos del formulario
    anio = request.form.get('anio')
    fecha = request.form.get('fecha')
    dia = request.form.get('dia')
    hora = request.form.get('hora')
    area = request.form.get('area')
    barrio = request.form.get('barrio')
    claseAccidente = request.form.get('claseAccidente')
    claseServicio = request.form.get('claseServicio')
    gravedadAccidente = request.form.get('gravedadAccidente')
    
    # 1. DEFINICIÓN SEGURA DE LA VARIABLE (Esto arregla el error "not defined")
    claseVehiculo_form = request.form.get('claseVehiculo', 'Desconocido')
    claseVehiculo = claseVehiculo_form # Valor por defecto inicial
    
    direccion = request.form.get('direccionInfo')
    controles = request.form.get('controles', 'NINGUNO')
    accion = request.form.get('accion')

    if accion == 'reportar':
        foto = request.files.get('foto')

        if not foto or foto.filename == "":
            flash("Debes adjuntar una foto del accidente.", "warning")
            return redirect('/reportar')

        filename = secure_filename(foto.filename)
        ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        foto.save(ruta_foto)

        # 2. ANÁLISIS DE IA
        print("🤖 IA Analizando imagen...")
        analisis_ia = ai_validator.analizar_imagen(ruta_foto)
        
        # Verificar autenticidad
        if not analisis_ia.get('es_real', True):
            # Es falsa: borramos y rechazamos
            try:
                os.remove(ruta_foto)
            except:
                pass
            razon = analisis_ia.get('razon', 'Imagen no válida')
            flash(f"⚠️ Reporte RECHAZADO por IA: {razon}", "error")
            return redirect('/reportar')

        # Si es real: Enriquecer datos
        vehiculos_detectados = analisis_ia.get('vehiculos', [])
        
        # Actualizamos la variable claseVehiculo SOLO si hay datos nuevos
        if vehiculos_detectados:
            vehiculos_str = ", ".join(vehiculos_detectados)
            claseVehiculo = f"{claseVehiculo_form} [IA: {vehiculos_str}]"
            flash(f"✅ Validación IA Exitosa: Se detectó {vehiculos_str}", "success")
        else:
            # Si no detectó nada específico, dejamos el valor del formulario
            claseVehiculo = claseVehiculo_form
            flash("✅ Reporte registrado exitosamente.", "success")

        # 3. Geocodificación
        ubicacion = geolocator.geocode(direccion)
        if ubicacion:
            latitud = ubicacion.latitude
            longitud = ubicacion.longitude
        else:
            latitud = None
            longitud = None
            
        # 4. Guardar en Base de Datos
        try:
            from datetime import datetime
            try:
                fecha_timestamp = datetime.strptime(fecha, "%Y-%m-%d")
            except ValueError:
                fecha_timestamp = datetime.now()

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO accidentes_completa (
                        ano, fecha, dia, hora, area, direccion_hecho, controles_transito,
                        barrio_hecho, clase_accidente, clase_servicio, gravedad_accidente,
                        clase_vehiculo, latitud, longitud
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    int(anio), fecha_timestamp, dia, hora, area, direccion,
                    controles, barrio, claseAccidente, claseServicio,
                    gravedadAccidente, claseVehiculo, latitud, longitud
                ))

                accidente_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO accidentes_fotos (accidente_id, nombre_archivo)
                    VALUES (%s, %s)
                """, (accidente_id, filename))

            conn.commit()

        except Exception as e:
            conn.rollback()
            print("❌ Error BD:", e)
            flash(f"Error técnico al guardar: {e}", "error")

        return redirect('/reportar')

    return redirect('/reportar')

# ==========================================================
# 3. APIs Y RUTAS DE DATOS (HEATMAP, RIESGO, DETALLES)
# ==========================================================

@app.route('/heatmap')
def heatmap():
    return render_template('heatmap.html')

@app.route('/api/accidentes')
def api_accidentes():
    with conn.cursor() as cur:
        cur.execute("SELECT latitud, longitud FROM accidentes_completa WHERE latitud IS NOT NULL AND longitud IS NOT NULL")
        data = cur.fetchall()
    return jsonify(data)

@app.route('/api/accidentes_all')
def api_accidentes_all():
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, ano, fecha, barrio_hecho, clase_accidente, gravedad_accidente,
                       latitud, longitud, direccion_hecho, area
                FROM accidentes_completa
                WHERE latitud IS NOT NULL AND longitud IS NOT NULL
            """)
            rows = c.fetchall()

        out = []
        for r in rows:
            out.append({
                'id': r[0],
                'ano': r[1],
                'fecha': r[2].isoformat() if r[2] else None,
                'barrio': r[3],
                'clase_accidente': r[4],
                'gravedad': r[5],
                'lat': float(r[6]),
                'lng': float(r[7]),
                'direccion': r[8],
                'area': r[9]
            })

        return jsonify({'accidentes': out})
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/accidente/<int:accidente_id>')
def api_accidente_detalle(accidente_id):
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, ano, fecha, dia, hora, area, direccion_hecho,
                       barrio_hecho, clase_accidente, clase_servicio,
                       gravedad_accidente, clase_vehiculo, latitud, longitud
                FROM accidentes_completa
                WHERE id = %s
            """, (accidente_id,))
            row = c.fetchone()

            if not row:
                return jsonify({'error': 'No encontrado'}), 404

            data = {
                'id': row[0],
                'ano': row[1],
                'fecha': row[2].isoformat() if row[2] else None,
                'dia': row[3],
                'hora': row[4],
                'area': row[5],
                'direccion': row[6],
                'barrio': row[7],
                'clase_accidente': row[8],
                'clase_servicio': row[9],
                'gravedad': row[10],
                'clase_vehiculo': row[11],
                'lat': float(row[12]),
                'lng': float(row[13])
            }

            c.execute("SELECT nombre_archivo FROM accidentes_fotos WHERE accidente_id = %s", (accidente_id,))
            data['fotos'] = [f[0] for f in c.fetchall()]

            c.execute("""
                SELECT rating, nota_interna
                FROM accidente_reviews
                WHERE accidente_id = %s
                ORDER BY actualizado_en DESC
                LIMIT 1
            """, (accidente_id,))
            r = c.fetchone()
            data['rating'] = r[0] if r else None
            data['nota_interna'] = r[1] if r else None

        return jsonify(data)

    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/accidente/<int:accidente_id>/calificar', methods=['POST'])
def api_accidente_calificar(accidente_id):
    try:
        data = request.get_json()
        rating = data.get('rating')
        nota = data.get('nota', '')

        with conn.cursor() as c:
            c.execute("""
                INSERT INTO accidente_reviews (accidente_id, rating, nota_interna)
                VALUES (%s, %s, %s)
            """, (accidente_id, rating, nota))

        conn.commit()
        return jsonify({'ok': True})

    except Exception as e:
        conn.rollback()
        print(e)
        return jsonify({'error': str(e)}), 500


# ==========================================================
# 4. RUTAS DE CÁLCULO DE RIESGO
# ==========================================================

def _accidentalidad_en_radio(lat, lng, cursor, filtros, radio_m=100): # <--- CAMBIO 1: 100 metros por defecto
    lat = float(lat)
    lng = float(lng)
    radio_m = float(radio_m or 100) # <--- Aseguramos 100m si viene vacío

    # Convertimos metros a grados (aproximación para lat/lng)
    delta_lat = radio_m / 111_320  
    delta_lng = radio_m / (111_320 * max(math.cos(math.radians(lat)), 0.0001))

    # Consulta SQL (Busca en un cuadrado alrededor del punto)
    sql = """
        SELECT latitud, longitud, gravedad_accidente, hora, clase_accidente
        FROM accidentes_completa
        WHERE latitud IS NOT NULL AND longitud IS NOT NULL
          AND latitud BETWEEN %s AND %s
          AND longitud BETWEEN %s AND %s
    """
    params = [lat - delta_lat, lat + delta_lat, lng - delta_lng, lng + delta_lng]

    # Aplicamos filtros dinámicos
    if filtros.get('gravedad'):
        sql += " AND gravedad_accidente = ANY(%s)"
        params.append(filtros['gravedad'])
    if filtros.get('ano'):
        sql += " AND ano = ANY(%s)"
        params.append(filtros['ano'])
    if filtros.get('hora'):
        rango = filtros['hora']
        if isinstance(rango, (list, tuple)) and len(rango) == 2:
            sql += " AND hora BETWEEN %s AND %s"
            params.extend(rango)

    cursor.execute(sql, params)
    accidentes = cursor.fetchall()

    conteo = 0
    puntaje = 0.0

    # Filtrado fino (Círculo exacto)
    for acc in accidentes:
        acc_lat = float(acc['latitud'])
        acc_lng = float(acc['longitud'])
        dist = procesador_riesgo.calcular_distancia(lat, lng, acc_lat, acc_lng)
        
        if dist > radio_m:
            continue # Si está fuera de los 100m, lo ignoramos

        conteo += 1
        gravedad = (acc['gravedad_accidente'] or '').lower()
        
        # Pesos: Muertos pesan más que heridos
        peso = 1.0
        if 'muert' in gravedad:
            peso = 3.0
        elif 'herid' in gravedad:
            peso = 2.0

        # Los accidentes más cercanos al punto pesan más
        puntaje += peso * (1 - dist / radio_m)

    if conteo == 0:
        return {'indice': 0.05, 'conteo': 0} # Riesgo mínimo base

    # --- CAMBIO 2: AJUSTE MATEMÁTICO PARA 100 METROS ---
    # Antes dividíamos por 12.0. Ahora dividimos por 4.0.
    # Esto significa que con 4 o 5 accidentes en esa cuadra ya se considera "Peligroso".
    densidad = 1 - math.exp(-conteo / 4.0)
    
    severidad_prom = min(1.0, (puntaje / max(conteo, 1)) / 3.0)
    indice = round(min(1.0, (densidad * 0.7) + (severidad_prom * 0.3)), 3)

    return {'indice': indice, 'conteo': conteo}

@app.route('/api/riesgo/calcular', methods=['POST'])
def calcular_riesgo():
    payload = request.get_json() or {}
    lat = payload.get('lat')
    lng = payload.get('lng')
    filtros = payload.get('filtros', {})
    if lat is None or lng is None:
        return jsonify(error="Coordenadas inválidas"), 400

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            stats = _accidentalidad_en_radio(lat, lng, cur, filtros, radio_m=filtros.get('radio', 300))
    except psycopg2.Error as e:
        conn.rollback()
        print("Error en calcular_riesgo:", e)
        return jsonify(error="No se pudo calcular el riesgo (consulta a BD)."), 500

    accidentes_cercanos = stats['conteo']
    nivel_accidentalidad = stats['indice']
    clima_penalizacion = min(0.2, filtros.get('clima_penalizacion', 0.0))
    nivel_riesgo = min(1.0, max(0.05, nivel_accidentalidad + clima_penalizacion))

    return jsonify({
        "nivel_riesgo": nivel_riesgo,
        "indice_accidentalidad": nivel_accidentalidad,
        "accidentes_cercanos": accidentes_cercanos,
        "lat": float(lat),
        "lng": float(lng),
        "filtros_aplicados": filtros
    })

@app.route('/api/riesgo/mapa-calor', methods=['POST'])
def generar_mapa_calor():
    try:
        data = request.get_json()
        if not data or 'bounds' not in data:
            return jsonify({'error': 'Se requieren bounds'}), 400
        
        filtros = data.get('filtros', {})
        resolucion = data.get('resolucion', 0.01)
        
        puntos_calor = procesador_riesgo.generar_mapa_calor(
            data['bounds'], 'accidentes_completa', filtros, resolucion, cur
        )
        return jsonify({'puntos_calor': puntos_calor, 'total_puntos': len(puntos_calor)})
    except Exception as e:
        print(f"Error en generar_mapa_calor: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rutas/calcular', methods=['POST'])
def calcular_ruta_segura():
    try:
        data = request.get_json()
        origen = data['origen']
        destino = data['destino']
        filtros = data.get('filtros', {})
        
        ruta = calculador_rutas.calcular_ruta_segura(
            origen, destino, 'accidentes_completa', filtros, cur
        )
        return jsonify(ruta)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/criterios-riesgo', methods=['GET', 'POST'])
def gestionar_criterios_riesgo():
    try:
        if request.method == 'POST':
            data = request.get_json()
            nombre = data.get('nombre')
            descripcion = data.get('descripcion', '')
            parametros = data.get('parametros', {})
            peso = data.get('peso', 1.0)
            
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO criterios_riesgo (nombre, descripcion, parametros, peso, activo)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (nombre) DO UPDATE SET
                    descripcion = EXCLUDED.descripcion,
                    parametros = EXCLUDED.parametros,
                    peso = EXCLUDED.peso,
                    activo = EXCLUDED.activo
                """, (nombre, descripcion, json.dumps(parametros), peso, True))
            conn.commit()
            return jsonify({'mensaje': 'Criterio guardado'})
        else:
            with conn.cursor() as cur:
                cur.execute("SELECT nombre, descripcion, parametros, peso FROM criterios_riesgo WHERE activo = TRUE")
                criterios = cur.fetchall()
            return jsonify({'criterios': criterios})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==========================================================
# 5. ANALYTICS (ESTADÍSTICAS Y EXPORTACIÓN) - RESTAURADO
# ==========================================================

@app.route('/analytics')
def analytics():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('analytics.html')

@app.route('/api/analytics/filtros')
def obtener_filtros_analytics():
    """Obtener opciones para los filtros"""
    try:
        with conn.cursor() as cur:
            # Obtener zonas únicas
            cur.execute("SELECT DISTINCT barrio_hecho FROM accidentes_completa WHERE barrio_hecho IS NOT NULL ORDER BY barrio_hecho")
            zonas = [row[0] for row in cur.fetchall()]
            
            # Obtener tipos de accidente únicos
            cur.execute("SELECT DISTINCT clase_accidente FROM accidentes_completa WHERE clase_accidente IS NOT NULL ORDER BY clase_accidente")
            tipos_accidente = [row[0] for row in cur.fetchall()]
            
        return jsonify({
            'zonas': zonas,
            'tipos_accidente': tipos_accidente
        })
        
    except Exception as e:
        print(f"Error obteniendo filtros: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/estadisticas', methods=['POST'])
def obtener_estadisticas():
    """Obtener estadísticas y gráficos con filtros"""
    try:
        data = request.get_json()
        filtros = data.get('filtros', {})
        
        # CONSULTA CORREGIDA (Incluye 'dia')
        query = """
            SELECT 
                fecha, dia, hora, barrio_hecho, clase_accidente, gravedad_accidente,
                latitud, longitud, area, direccion_hecho
            FROM accidentes_completa 
            WHERE 1=1
        """
        params = []
        
        # Aplicar filtros
        if filtros.get('fecha_inicio'):
            query += " AND fecha >= %s"
            params.append(filtros['fecha_inicio'])
        
        if filtros.get('fecha_fin'):
            query += " AND fecha <= %s"
            params.append(filtros['fecha_fin'])
        
        if filtros.get('gravedad'):
            query += " AND gravedad_accidente = %s"
            params.append(filtros['gravedad'])
        
        if filtros.get('zona'):
            query += " AND barrio_hecho = %s"
            params.append(filtros['zona'])
        
        if filtros.get('tipo_accidente'):
            query += " AND clase_accidente = %s"
            params.append(filtros['tipo_accidente'])
        
        if filtros.get('hora'):
            # Filtrar por rango de horas
            if filtros['hora'] == 'madrugada':
                query += " AND (hora < '06:00' OR hora >= '00:00')"
            elif filtros['hora'] == 'mañana':
                query += " AND hora BETWEEN '06:00' AND '11:59'"
            elif filtros['hora'] == 'tarde':
                query += " AND hora BETWEEN '12:00' AND '17:59'"
            elif filtros['hora'] == 'noche':
                query += " AND hora BETWEEN '18:00' AND '23:59'"
        
        # Ejecutar consulta
        with conn.cursor() as cur:
            cur.execute(query, params)
            datos = cur.fetchall()
            
            # Obtener nombres de columnas
            column_names = [desc[0] for desc in cur.description]
            
            # Convertir a lista de diccionarios
            datos_dict = []
            for row in datos:
                datos_dict.append(dict(zip(column_names, row)))
            
            # Calcular estadísticas
            estadisticas = calcular_estadisticas(datos_dict)
            
            # Generar datos para gráficos
            graficos = generar_datos_graficos(datos_dict)
            
        return jsonify({
            'estadisticas': estadisticas,
            'graficos': graficos,
            'datos': datos_dict,
            'total_registros': len(datos_dict)
        })
        
    except Exception as e:
        print(f"Error obteniendo estadísticas: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/exportar/csv', methods=['POST'])
def exportar_csv():
    """Exportar datos a CSV"""
    try:
        data = request.get_json()
        datos = data.get('datos', [])
        
        csv_content = ExportUtils.generar_csv(datos)
        
        if not csv_content:
            return jsonify({'error': 'No hay datos para exportar'}), 400
        
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=accidentes_export.csv"}
        )
        
    except Exception as e:
        print(f"Error exportando CSV: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/exportar/pdf', methods=['POST'])
def exportar_pdf():
    """Exportar reporte a PDF"""
    try:
        data = request.get_json()
        filtros = data.get('filtros', {})
        datos = data.get('datos', {})
        
        pdf_file = PDFGenerator.generar_pdf_simple(datos, filtros, datos.get('estadisticas', {}))
        
        return Response(
            pdf_file.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment;filename=reporte_accidentes.pdf"}
        )
        
    except Exception as e:
        print(f"Error exportando PDF: {e}")
        return jsonify({'error': str(e)}), 500


# ==========================================================
# 6. RECUPERACIÓN DE CONTRASEÑA
# ==========================================================

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['correo']
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE correo = %s", (email,))
            user = cur.fetchone()

            if user:
                token = s.dumps(email, salt='password-recovery')
                link = url_for('reset_password', token=token, _external=True)
                msg = Message("Restablecimiento de contraseña", sender=app.config['MAIL_USERNAME'], recipients=[email])
                msg.body = f'Para restablecer su contraseña, haga clic: {link}'
                mail.send(msg)
                flash("Correo enviado.", "info")
            else:
                flash("Correo no registrado.", "error") 
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):  
    try:
        email = s.loads(token, salt='password-recovery', max_age=3600)
    except SignatureExpired:
        flash("El enlace ha expirado.", "error")
        return redirect(url_for('forgot_password'))
    except BadSignature:
        flash("El enlace no es válido.", "error")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_pass = request.form['nueva_contrasena']
        conf_pass = request.form['confirmar_contrasena']
        if new_pass != conf_pass:
            flash("Las contraseñas no coinciden.", "error")
            return render_template('reset_password.html')
        
        hashed = encrypt_password(new_pass)
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET contrasena = %s WHERE correo = %s", (hashed, email))
        conn.commit()
        flash("Contraseña restablecida.", "success")
        return redirect(url_for('index'))

    return render_template('reset_password.html')


# ==========================================================
# 7. FUNCIONES AUXILIARES (Estadísticas y Gráficos)
# ==========================================================

def calcular_estadisticas(datos):
    """Calcular estadísticas principales desde los datos"""
    if not datos:
        return {
            'total_accidentes': 0,
            'con_heridos': 0,
            'con_muertos': 0,
            'porcentaje_heridos': 0,
            'porcentaje_muertos': 0,
            'zona_mas_peligrosa': 'N/A',
            'max_accidentes_zona': 0  # <--- FALTABA ESTO PARA EVITAR EL UNDEFINED
        }
    
    total = len(datos)
    
    # 1. CONTEO INTELIGENTE (Detecta mayúsculas/minúsculas)
    # Buscamos que la palabra "herid" o "muert" esté contenida en el texto, sin importar si es mayúscula
    con_heridos = sum(1 for d in datos if d.get('gravedad_accidente') and 'herid' in d.get('gravedad_accidente').lower())
    con_muertos = sum(1 for d in datos if d.get('gravedad_accidente') and 'muert' in d.get('gravedad_accidente').lower())
    
    # 2. ZONA MÁS PELIGROSA (Ignorando "No informa")
    zonas_validas = [
        d.get('barrio_hecho') for d in datos 
        if d.get('barrio_hecho') and d.get('barrio_hecho').lower() not in ['no informa', 'sin informacion', 'desconocido', '']
    ]
    
    if zonas_validas:
        zona_mas_peligrosa = max(set(zonas_validas), key=zonas_validas.count)
        cantidad_en_zona = zonas_validas.count(zona_mas_peligrosa)
    else:
        zona_mas_peligrosa = "Sin datos suficientes"
        cantidad_en_zona = 0
    
    return {
        'total_accidentes': total,
        'con_heridos': con_heridos,
        'con_muertos': con_muertos,
        'porcentaje_heridos': round((con_heridos/total)*100, 1) if total > 0 else 0,
        'porcentaje_muertos': round((con_muertos/total)*100, 1) if total > 0 else 0,
        'zona_mas_peligrosa': zona_mas_peligrosa,
        'max_accidentes_zona': cantidad_en_zona 
    }

def generar_datos_graficos(datos):
    """Generar estructuras de datos para Chart.js (CORREGIDO)"""
    if not datos:
        # Estructura vacía para evitar "undefined" en JS
        empty_struct = {'labels': [], 'data': []}
        return {
            'por_hora': empty_struct,
            'por_dia': empty_struct,
            'por_gravedad': empty_struct,
            'por_tipo': empty_struct,
            'por_zona': empty_struct
        }
    
    # 1. Por Hora
    horas_counts = {}
    for d in datos:
        h = str(d.get('hora', ''))
        # Tomar solo la hora (ej: "14:30" -> "14")
        if h and ':' in h:
            h_simple = h.split(':')[0]
            horas_counts[h_simple] = horas_counts.get(h_simple, 0) + 1
    
    # Ordenar horas numéricamente
    horas_sorted = sorted(horas_counts.items())

    # 2. Por Día de la Semana
    dias_counts = {}
    for d in datos:
        dia = d.get('dia') or 'Desconocido'
        dias_counts[dia] = dias_counts.get(dia, 0) + 1
        
    # 3. Por Gravedad
    gravedad_counts = {}
    for d in datos:
        g = d.get('gravedad_accidente') or 'Desconocido'
        gravedad_counts[g] = gravedad_counts.get(g, 0) + 1
        
    # 4. Por Tipo de Accidente
    tipo_counts = {}
    for d in datos:
        t = d.get('clase_accidente') or 'Otros'
        tipo_counts[t] = tipo_counts.get(t, 0) + 1
        
    # 5. Por Zona (Barrio) - Top 10
    zona_counts = {}
    for d in datos:
        z = d.get('barrio_hecho') or 'Desconocido'
        zona_counts[z] = zona_counts.get(z, 0) + 1
    
    top_zonas = sorted(zona_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Retornar con las claves EXACTAS que pide analytics.js
    return {
        'por_hora': {
            'labels': [x[0] + ":00" for x in horas_sorted],
            'data': [x[1] for x in horas_sorted]
        },
        'por_dia': {
            'labels': list(dias_counts.keys()),
            'data': list(dias_counts.values())
        },
        'por_gravedad': {
            'labels': list(gravedad_counts.keys()),
            'data': list(gravedad_counts.values())
        },
        'por_tipo': {
            'labels': list(tipo_counts.keys()),
            'data': list(tipo_counts.values())
        },
        'por_zona': {
            'labels': [x[0] for x in top_zonas],
            'data': [x[1] for x in top_zonas]
        }
    }

if __name__ == '__main__':
    app.run(debug=True)