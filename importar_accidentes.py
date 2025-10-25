import psycopg2
import csv
from dotenv import load_dotenv
from datetime import datetime
import os
import re

load_dotenv()

# Conexión a PostgreSQL
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

# Leer archivo CSV
with open('Accidentalidad_Vehicular_en_el_Municipio_de_Tuluá_20251023.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=',', quotechar='"')
    count = 0
    for row in reader:
        try:
            # Extraer coordenadas (columna tiene un espacio al final)
            coords = row['Cordenada Geografica '].strip()
            match = re.search(r'POINT\s*\(([-\d\.]+)\s+([-\d\.]+)\)', coords)
            if not match:
                continue

            lon, lat = float(match.group(1)), float(match.group(2))

            # Extraer fecha
            fecha_str = row['FECHA']
            try:
                fecha = datetime.strptime(fecha_str, "%Y/%m/%d")
            except:
                fecha = None

            # Tipo de accidente
            tipo = row['CLASE DE ACCIDENTE'].strip().capitalize()

            # Insertar datos
            cur.execute("""
                INSERT INTO accidentes (latitud, longitud, fecha, tipo)
                VALUES (%s, %s, %s, %s)
            """, (lat, lon, fecha, tipo))
            count += 1
        except Exception as e:
            print("Error en fila:", e)

conn.commit()
cur.close()
conn.close()

print(f"✅ Datos importados correctamente: {count} registros insertados.")