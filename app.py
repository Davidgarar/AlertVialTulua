from flask import Flask, flash, render_template, request, redirect, url_for, session
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv
from security import encrypt_password, verify_password

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

    
# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.pop('user', None)  # elimina al usuario de la sesión
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for('index'))



# Ejecutar la aplicación
if __name__ == '__main__':
    app.run(debug=True)    




