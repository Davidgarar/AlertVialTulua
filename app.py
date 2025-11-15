from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv
from security import encrypt_password, verify_password
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from geopy.geocoders import Nominatim
# AGREGAR ESTOS IMPORTS DESPUÉS DE LOS EXISTENTES
from data_filters import FiltroAccidentes
from risk_processor import ProcesadorRiesgo
from route_calculator import CalculadorRutaSegura
import json 
from datetime import datetime, timedelta
from export_utils import ExportUtils, PDFGenerator
import os
from werkzeug.utils import secure_filename
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' 

import psycopg2
from flask import request, jsonify
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "secretSUPERT_key"
procesador_riesgo = ProcesadorRiesgo()
calculador_rutas = CalculadorRutaSegura(procesador_riesgo)
load_dotenv()

API_KEY = os.getenv("WEATHER_API_KEY") 

# Conexión a PostgreSQL
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

#configuración de OAuth para Google
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

# Ruta para iniciar sesión con Google
@app.route('/login_google')
def login_google():
    return redirect(url_for("google.login"))

## Ruta principal (login)
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



# Ruta para la página de alerta después del login
@app.route('/alertv')
def alertv():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('alertv.html', user=session['user'])

# Ruta para la página de registro
@app.route('/register')
def register():
    return render_template('register.html')

# Ruta de callback para Google OAuth
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

    # Aquí se puede agregar la lógica para registrar al usuario
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


# Ruta para registrar un nuevo usuario
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

# Ruta para la página de reporte  
@app.route('/reportar')
def reportar():
    # Verificamos si el usuario está logueado
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('report.html')



# --- ENDPOINT: lista completa de accidentes ---
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



# --- ENDPOINT: detalle de un accidente ---
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

            # fotos
            c.execute("SELECT nombre_archivo FROM accidentes_fotos WHERE accidente_id = %s", (accidente_id,))
            data['fotos'] = [f[0] for f in c.fetchall()]

            # rating + nota
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



# --- ENDPOINT: guardar calificación y nota ---
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


UPLOAD_FOLDER = 'static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
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
    claseVehiculo = request.form.get('claseVehiculo')
    direccion = request.form.get('direccionInfo')
    controles = request.form.get('controles', 'NINGUNO')

    accion = request.form.get('accion')

    if accion == 'reportar':
            # Obtener archivo de foto
            foto = request.files.get('foto')

            # Validar que exista foto
            if not foto or foto.filename == "":
                flash("Debes adjuntar una foto del accidente.", "warning")
                return redirect('/reportar')

            # Asegurar nombre seguro para el archivo
            filename = secure_filename(foto.filename)

            # Guardar archivo en carpeta /static/img
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Obtener coordenadas con geopy
            ubicacion = geolocator.geocode(direccion)
            if ubicacion:
                latitud = ubicacion.latitude
                longitud = ubicacion.longitude
            else:
                latitud = None
                longitud = None
                

            try:
                from datetime import datetime
                try:
                    fecha_timestamp = datetime.strptime(fecha, "%Y-%m-%d")
                except ValueError:
                    fecha_timestamp = datetime.now()

                with conn.cursor() as cur:
                    # Insertar accidente y obtener ID generado
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

                    # Guardar referencia de la foto en su tabla
                    cur.execute("""
                        INSERT INTO accidentes_fotos (accidente_id, nombre_archivo)
                        VALUES (%s, %s)
                    """, (accidente_id, filename))

                conn.commit()
                

            except Exception as e:
                conn.rollback()
                print("❌ Error:", e)
                

            return redirect('/reportar')


    
# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.pop('user', None)  # elimina al usuario de la sesión
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for('index'))

#configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
app.config['MAIL_USE_TLS'] = True


mail = Mail(app)    
s = URLSafeTimedSerializer(app.secret_key)  

#ruta para solicitar restablecimiento de contraseña
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
                msg.body = f'Para restablecer su contraseña, haga clic en el siguiente enlace: {link}'
                mail.send(msg)
                flash("Se ha enviado un correo electrónico para restablecer la contraseña.", "info")
                
            else:
                flash("El correo electrónico no está registrado.", "error") 
    return render_template('forgot_password.html')


#ruta para restablecer la contraseña
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):  
    try:
        email = s.loads(token, salt='password-recovery', max_age=3600)
    except SignatureExpired:
        flash("El enlace para restablecer la contraseña ha expirado.", "error")
        return redirect(url_for('forgot_password'))
    except BadSignature:
        flash("El enlace para restablecer la contraseña no es válido.", "error")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        # CAMBIADO: Usar los nombres del HTML actual
        new_password = request.form['nueva_contrasena']
        confirm_password = request.form['confirmar_contrasena']
        
        # Validar que las contraseñas coincidan
        if new_password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")
            return render_template('reset_password.html')
        
        hashed_password = encrypt_password(new_password)

        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET contrasena = %s WHERE correo = %s", (hashed_password, email))
        conn.commit()
        flash("Su contraseña ha sido restablecida exitosamente.", "success")
        return redirect(url_for('index'))  # Cambié a 'login' en vez de 'index'

    return render_template('reset_password.html')

@app.route('/heatmap')
def heatmap():
    return render_template('heatmap.html')


@app.route('/api/accidentes')
def api_accidentes():
    with conn.cursor() as cur:
        cur.execute("SELECT latitud, longitud FROM accidentes_completa WHERE latitud IS NOT NULL AND longitud IS NOT NULL")
        data = cur.fetchall()
    # Devuelve los puntos en formato JSON
    return jsonify(data)

# =================================================================
# NUEVAS RUTAS PARA PROCESAMIENTO DE RIESGO - SIN AFECTAR EXISTENTES
# =================================================================

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
            sql = """
                SELECT gravedad_accidente, clase_accidente
                FROM accidentes_completa
                WHERE ST_DWithin(
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(longitud, latitud), 4326)::geography,
                    %s
                )
            """
            params = [lng, lat, 2000]
            if filtros.get('gravedad'):
                sql += " AND gravedad_accidente = ANY(%s)"
                params.append(filtros['gravedad'])
            cur.execute(sql, params)
            accidentes = cur.fetchall()
    except psycopg2.Error as e:
        conn.rollback()
        print("Error en calcular_riesgo:", e)
        return jsonify(error="No se pudo calcular el riesgo. Verifica que PostGIS esté instalado y que lat/long sean válidos."), 500

    conteo = len(accidentes)
    gravedad_puntos = sum(30 if acc['gravedad_accidente'] == 'Con muertos' else 15 for acc in accidentes)
    nivel_accidentalidad = min(1.0, (conteo * 0.05) + (gravedad_puntos / 100))

    tiempo_base = 0.3
    clima_penalizacion = 0.2 if filtros.get('clima') == 'lluvia' else 0
    nivel_riesgo = min(1.0, tiempo_base + clima_penalizacion + nivel_accidentalidad)

    return jsonify({
        "nivel_riesgo": nivel_riesgo,
        "lat": lat,
        "lng": lng,
        "accidentes_cercanos": conteo,
        "filtros_aplicados": filtros
    })

@app.route('/api/riesgo/mapa-calor', methods=['POST'])
def generar_mapa_calor():
    """Generar datos para mapa de calor con filtros"""
    try:
        data = request.get_json()
        
        if not data or 'bounds' not in data:
            return jsonify({'error': 'Se requieren bounds [lat_min, lng_min, lat_max, lng_max]'}), 400
        
        filtros = data.get('filtros', {})
        resolucion = data.get('resolucion', 0.01)
        
        puntos_calor = procesador_riesgo.generar_mapa_calor(
            data['bounds'], 'accidentes_completa', filtros, resolucion, cur
        )
        
        return jsonify({
            'puntos_calor': puntos_calor,
            'total_puntos': len(puntos_calor),
            'resolucion': resolucion,
            'filtros_aplicados': filtros
        })
        
    except Exception as e:
        print(f"Error en generar_mapa_calor: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rutas/calcular', methods=['POST'])
def calcular_ruta_segura():
    """Calcular ruta segura entre dos puntos"""
    try:
        data = request.get_json()
        
        if not data or 'origen' not in data or 'destino' not in data:
            return jsonify({'error': 'Se requieren origen y destino'}), 400
        
        origen = data['origen']  # {'lat': x, 'lng': y}
        destino = data['destino']  # {'lat': x, 'lng': y}
        filtros = data.get('filtros', {})
        
        ruta = calculador_rutas.calcular_ruta_segura(
            origen, destino, 'accidentes_completa', filtros, cur
        )
        
        return jsonify(ruta)
        
    except Exception as e:
        print(f"Error en calcular_ruta_segura: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/filtros/aplicar', methods=['POST'])
def aplicar_filtros():
    """Aplicar filtros y obtener accidentes filtrados"""
    try:
        data = request.get_json()
        filtros = data.get('filtros', {})
        
        filtro_obj = FiltroAccidentes()
        
        # Aplicar filtros dinámicamente
        for key, value in filtros.items():
            if hasattr(filtro_obj, f'por_{key}'):
                getattr(filtro_obj, f'por_{key}')(value)
        
        # Aplicar filtros a la consulta
        query = "SELECT * FROM accidentes_completa WHERE 1=1"
        params = []
        query, params = filtro_obj.aplicar_sql(query, params)
        
        with conn.cursor() as cur:
            cur.execute(query, params)
            accidentes_filtrados = cur.fetchall()
        
        # Obtener nombres de columnas
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'accidentes_completa' ORDER BY ordinal_position")
        columnas = [col[0] for col in cur.fetchall()]
        
        # Convertir a lista de diccionarios
        accidentes_dict = []
        for acc in accidentes_filtrados:
            acc_dict = {}
            for i, columna in enumerate(columnas):
                acc_dict[columna] = acc[i]
            accidentes_dict.append(acc_dict)
        
        return jsonify({
            'total_accidentes': len(accidentes_filtrados),
            'accidentes': accidentes_dict,
            'filtros_aplicados': filtros
        })
        
    except Exception as e:
        print(f"Error en aplicar_filtros: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/estadisticas/riesgo', methods=['GET'])
def obtener_estadisticas_riesgo():
    """Obtener estadísticas generales de riesgo"""
    try:
        # Puedes aceptar filtros por query parameters
        filtros = request.args.to_dict()
        
        estadisticas = procesador_riesgo.obtener_estadisticas_riesgo('accidentes_completa', filtros, cur)
        
        return jsonify(estadisticas)
        
    except Exception as e:
        print(f"Error en obtener_estadisticas_riesgo: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/criterios-riesgo', methods=['GET', 'POST'])
def gestionar_criterios_riesgo():
    """Gestionar criterios de riesgo (guardar/recuperar de base de datos)"""
    try:
        if request.method == 'POST':
            data = request.get_json()
            
            nombre = data.get('nombre')
            descripcion = data.get('descripcion', '')
            parametros = data.get('parametros', {})
            peso = data.get('peso', 1.0)
            
            # Guardar en base de datos
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
            
            return jsonify({'mensaje': 'Criterio guardado exitosamente', 'criterio': data})
        
        else:  # GET
            with conn.cursor() as cur:
                cur.execute("SELECT nombre, descripcion, parametros, peso FROM criterios_riesgo WHERE activo = TRUE")
                criterios = cur.fetchall()
            
            criterios_dict = []
            for criterio in criterios:
                criterios_dict.append({
                    'nombre': criterio[0],
                    'descripcion': criterio[1],
                    'parametros': json.loads(criterio[2]) if criterio[2] else {},
                    'peso': criterio[3]
                })
            
            return jsonify({'criterios': criterios_dict})
            
    except Exception as e:
        print(f"Error en gestionar_criterios_riesgo: {e}")
        return jsonify({'error': str(e)}), 500

# ================================================
# ENDPOINTS PARA ANALYTICS Y ESTADÍSTICAS
# ================================================

@app.route('/analytics')
def analytics():
    """Página de estadísticas para administradores"""
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
        
        # Construir consulta base
        query = """
            SELECT 
                fecha, hora, barrio_hecho, clase_accidente, gravedad_accidente,
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
        
        from flask import Response
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
        
        from flask import Response
        return Response(
            pdf_file.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment;filename=reporte_accidentes.pdf"}
        )
        
    except Exception as e:
        print(f"Error exportando PDF: {e}")
        return jsonify({'error': str(e)}), 500

# ================================================
# FUNCIONES AUXILIARES PARA ESTADÍSTICAS
# ================================================

def calcular_estadisticas(datos):
    """Calcular estadísticas principales desde los datos"""
    if not datos:
        return {
            'total_accidentes': 0,
            'con_heridos': 0,
            'con_muertos': 0,
            'porcentaje_heridos': 0,
            'porcentaje_muertos': 0,
            'zona_mas_peligrosa': 'No hay datos suficientes',
            'max_accidentes_zona': 0
        }
    
    total = len(datos)
    con_heridos = sum(1 for acc in datos if acc.get('gravedad_accidente') and 'HERIDO' in str(acc['gravedad_accidente']).upper())
    con_muertos = sum(1 for acc in datos if acc.get('gravedad_accidente') and 'MUERTO' in str(acc['gravedad_accidente']).upper())
    
    # Calcular zona más peligrosa - FILTRANDO "NO INFORMA"
    zonas = {}
    for acc in datos:
        zona = acc.get('barrio_hecho')
        
        # Filtrar valores no informativos
        if (zona and 
            str(zona).strip() != '' and 
            str(zona).upper() not in ['NO INFORMA', 'NO INFORMA', 'NONE', 'NULL', '', 'NO INFORMADO', 'NO INFORMA'] and
            not str(zona).startswith('No informa')):
            
            zonas[zona] = zonas.get(zona, 0) + 1
    
    # Encontrar la zona con más accidentes (que no sea "No informa")
    zona_mas_peligrosa = 'No informada en la mayoría de casos'
    max_accidentes_zona = 0
    
    if zonas:
        # Ordenar por cantidad de accidentes y tomar la primera que no sea "No informa"
        zonas_ordenadas = sorted(zonas.items(), key=lambda x: x[1], reverse=True)
        
        for zona, cantidad in zonas_ordenadas:
            if (zona and 
                str(zona).strip() != '' and 
                str(zona).upper() not in ['NO INFORMA', 'NO INFORMA', 'NONE', 'NULL', '', 'NO INFORMADO'] and
                not str(zona).startswith('No informa')):
                
                zona_mas_peligrosa = zona
                max_accidentes_zona = cantidad
                break
    
    return {
        'total_accidentes': total,
        'con_heridos': con_heridos,
        'con_muertos': con_muertos,
        'porcentaje_heridos': round((con_heridos / total) * 100, 1) if total > 0 else 0,
        'porcentaje_muertos': round((con_muertos / total) * 100, 1) if total > 0 else 0,
        'zona_mas_peligrosa': zona_mas_peligrosa,
        'max_accidentes_zona': max_accidentes_zona
    }

def generar_datos_graficos(datos):
    """Generar datos para los gráficos"""
    if not datos:
        return generar_graficos_vacios()
    
    # Gráfico por hora
    horas = [0] * 24
    for acc in datos:
        if acc.get('hora'):
            try:
                hora = int(acc['hora'].split(':')[0])
                if 0 <= hora < 24:
                    horas[hora] += 1
            except:
                pass
    
    # Gráfico por día de la semana
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    dias = {dia: 0 for dia in dias_semana}
    for acc in datos:
        dia = acc.get('dia')
        if dia and dia in dias:
            dias[dia] += 1
    
    # Gráfico por gravedad
    gravedades = {'Solo daños': 0, 'Con heridos': 0, 'Con muertos': 0}
    for acc in datos:
        gravedad = acc.get('gravedad_accidente', '')
        if 'HERIDO' in gravedad.upper():
            gravedades['Con heridos'] += 1
        elif 'MUERTO' in gravedad.upper():
            gravedades['Con muertos'] += 1
        else:
            gravedades['Solo daños'] += 1
    
    # Gráfico por tipo de accidente
    tipos = {}
    for acc in datos:
        tipo = acc.get('clase_accidente')
        if tipo:
            tipos[tipo] = tipos.get(tipo, 0) + 1
    
    # Gráfico por zona (top 10)
    zonas = {}
    for acc in datos:
        zona = acc.get('barrio_hecho')
        if zona:
            zonas[zona] = zonas.get(zona, 0) + 1
    
    top_zonas = dict(sorted(zonas.items(), key=lambda x: x[1], reverse=True)[:10])
    
    return {
        'por_hora': {
            'labels': [f'{h:02d}:00' for h in range(24)],
            'data': horas
        },
        'por_dia': {
            'labels': dias_semana,
            'data': [dias[dia] for dia in dias_semana]
        },
        'por_gravedad': {
            'labels': list(gravedades.keys()),
            'data': list(gravedades.values())
        },
        'por_tipo': {
            'labels': list(tipos.keys()),
            'data': list(tipos.values())
        },
        'por_zona': {
            'labels': list(top_zonas.keys()),
            'data': list(top_zonas.values())
        }
    }

def generar_graficos_vacios():
    """Generar estructura de gráficos vacíos"""
    return {
        'por_hora': {'labels': [], 'data': []},
        'por_dia': {'labels': [], 'data': []},
        'por_gravedad': {'labels': [], 'data': []},
        'por_tipo': {'labels': [], 'data': []},
        'por_zona': {'labels': [], 'data': []}
    }


@app.route('/rutas')
def rutas():
    return render_template('rutas.html')

@app.route('/clima')
def clima():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=es"

    response = request.get(url)
    return response.json()


# Ejecutar la aplicación
if __name__ == '__main__':
    app.run(debug=True)