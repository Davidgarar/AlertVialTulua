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
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' 

import psycopg2

app = Flask(__name__)
app.secret_key = "secretSUPERT_key"
procesador_riesgo = ProcesadorRiesgo()
calculador_rutas = CalculadorRutaSegura(procesador_riesgo)
load_dotenv()

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

@app.route('/procesar', methods=['POST'])
def procesar():
    geolocator = Nominatim(user_agent="geoapi")

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
        # Obtener coordenadas con geopy
        ubicacion = geolocator.geocode(direccion)
        if ubicacion:
            latitud = ubicacion.latitude
            longitud = ubicacion.longitude
        else:
            latitud = None
            longitud = None
            flash("⚠️ No se pudo obtener la ubicación de la dirección.", "warning")

        try:
            # Conversión de fecha a formato TIMESTAMP (YYYY-MM-DD HH:MM:SS)
            # Si el campo `fecha` solo tiene día, usa hora vacía.
            from datetime import datetime
            try:
                fecha_timestamp = datetime.strptime(fecha, "%Y-%m-%d")
            except ValueError:
                fecha_timestamp = datetime.now()

            # Insertar en la tabla
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO accidentes_completa (
                        ano,
                        fecha,
                        dia,
                        hora,
                        area,
                        direccion_hecho,
                        controles_transito,
                        barrio_hecho,
                        clase_accidente,
                        clase_servicio,
                        gravedad_accidente,
                        clase_vehiculo,
                        latitud,
                        longitud
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    int(anio),                # ano INTEGER
                    fecha_timestamp,     # fecha TIMESTAMP
                    dia,                 # dia VARCHAR(20)
                    hora,                # hora VARCHAR(10)
                    area,                # area VARCHAR(100)
                    direccion,           # direccion_hecho TEXT
                    controles,           # controles_transito VARCHAR(100)
                    barrio,              # barrio_hecho VARCHAR(100)
                    claseAccidente,      # clase_accidente VARCHAR(100)
                    claseServicio,   # clase_servicio VARCHAR(100)
                    gravedadAccidente,   # gravedad_accidente VARCHAR(100)
                    claseVehiculo,       # clase_vehiculo VARCHAR(100)
                    latitud,             # latitud DOUBLE PRECISION
                    longitud             # longitud DOUBLE PRECISION
                ))
            conn.commit()
            flash("✅ Accidente reportado correctamente.", "success")
        except Exception as e:
            conn.rollback()
            print("❌ Error al insertar accidente:", e)
            flash("Ocurrió un error al guardar el reporte.", "error")

        return redirect('/reportar')

    # Si no se presionó "reportar", vuelve al inicio
    return redirect('/')

    
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
    """Calcular nivel de riesgo en un punto específico"""
    try:
        data = request.get_json()
        
        if not data or 'lat' not in data or 'lng' not in data:
            return jsonify({'error': 'Se requieren lat y lng'}), 400
        
        filtros = data.get('filtros', {})
        
        # Calcular riesgo usando la tabla accidentes_completa que ya tienes
        riesgo = procesador_riesgo.calcular_riesgo_punto(
            data['lat'], data['lng'], 'accidentes_completa', filtros, cur, conn
        )
        
        return jsonify({
            'lat': data['lat'],
            'lng': data['lng'],
            'nivel_riesgo': round(riesgo, 3),
            'radio_metros': procesador_riesgo.radio_zona,
            'filtros_aplicados': filtros
        })
        
    except Exception as e:
        print(f"Error en calcular_riesgo: {e}")
        return jsonify({'error': str(e)}), 500

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


# Ejecutar la aplicación
if __name__ == '__main__':
    app.run(debug=True)   