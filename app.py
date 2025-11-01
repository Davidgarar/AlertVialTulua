from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv
from security import encrypt_password, verify_password
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from geopy.geocoders import Nominatim

import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' 

import psycopg2

app = Flask(__name__)
app.secret_key = "secretSUPERT_key"

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

# Ruta principal
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
                    
            # if user is None:
            #     flash('El usuario no existe', 'error')
            # elif verify_password(contrasena, user[0]):
            #     session['user'] = correo
            #     flash('Inicio de sesión exitoso', 'success')
            #     return redirect(url_for('alertv'))
            # else:
            #     flash('Contraseña incorrecta', 'error')

        except psycopg2.Error as e:
            print("Error al consultar la base de datos:", e)
            flash('Error en la base de datos', 'error')

    return render_template('index.html')

# Ruta para el login tradicional
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM usuarios WHERE correo = %s AND contrasena = %s",
                    (correo, contrasena)
                )
                user = cur.fetchone()
        except psycopg2.Error as e:
            print("Error al consultar usuario:", e)
            return "Ocurrió un error en el login."

        if user:
            session['user'] = {'nombre': user[1], 'email': user[2]}  # Ajusta los índices según tu tabla
            return redirect(url_for('alertv'))
        else:
            return "Credenciales inválidas. Por favor, intenta de nuevo."
    return render_template('login.html')

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


# Ejecutar la aplicación
if __name__ == '__main__':
    app.run(debug=True)    




