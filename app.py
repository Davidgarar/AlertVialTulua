from flask import Flask, render_template, request, redirect
import psycopg2

app = Flask(__name__)

# Conexión a PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    database="usuarios_app",
    user="postgres",
    password="DDDavidggg"
)
cur = conn.cursor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register')
def register():
    return render_template('register.html')


@app.route('/registrar', methods=['POST'])
def registrar():
    try:
        nombre = request.form['nombre']
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        ciudad = request.form['ciudad']

        cur = conn.cursor()
        cur.execute(
            "INSERT INTO usuarios (nombre_usuario, correo, contrasena, ciudad) VALUES (%s, %s, %s, %s)",
            (nombre, correo, contrasena, ciudad)
        )
        conn.commit()
        cur.close()
        return redirect('/')
    
    except psycopg2.Error as e:
        conn.rollback()  # 👈 Esto evita el “current transaction is aborted”
        print("Error al insertar datos:", e)
        return "Ocurrió un error al registrar el usuario."
       
if __name__ == '__main__':
    app.run(debug=True)
