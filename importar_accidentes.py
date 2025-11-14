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

with open("Accidentalidad_Vehicular_en_el_Municipio_de_Tuluá_20251023.csv", 'r', encoding='utf-8') as f:

    reader = csv.DictReader(f, delimiter=',', quotechar='"')
    count = 0
    for row in reader:
        try:
            ano_str = row.get("AÑO", "").strip()
            ano = int(ano_str.replace(",", "")) if ano_str.replace(",", "").isdigit() else None

            fecha_str = row.get("FECHA", "").strip()
            dia = row.get("DIA", "").strip()
            hora = row.get("HORA", "").strip()
            area = row.get("AREA", "").strip()
            direccion = row.get("DIRECCION HECHO", "").strip()
            controles = row.get("CONTROLES DE TRANSITO", "").strip()
            barrio = row.get("BARRIO HECHO", "").strip()
            clase_accidente = row.get("CLASE DE ACCIDENTE", "").strip()
            clase_servicio = row.get("CLASE DE SERVICIO", "").strip()
            gravedad = row.get("GRAVEDAD DEL ACCIDENTE", "").strip()
            clase_vehiculo = row.get("CLASE DE VEHICULO", "").strip()

            # Fecha segura
            try:
                fecha = datetime.strptime(fecha_str, "%Y/%m/%d")
            except:
                fecha = None

            # Coordenadas
            coords = row.get("Cordenada Geografica ", "").strip()
            latitud = None
            longitud = None
            match = re.search(r'POINT\s*\(([-\d\.]+)\s+([-\d\.]+)\)', coords)
            if match:
                longitud = float(match.group(1))
                latitud = float(match.group(2))

            # Insert individual
            cur.execute("""
                INSERT INTO accidentes_completa (
                    ano, fecha, dia, hora, area, direccion_hecho, 
                    controles_transito, barrio_hecho, clase_accidente, 
                    clase_servicio, gravedad_accidente, clase_vehiculo,
                    latitud, longitud
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ano, fecha, dia, hora, area, direccion, controles, barrio,
                clase_accidente, clase_servicio, gravedad, clase_vehiculo,
                latitud, longitud
            ))

            conn.commit()
            count += 1

        except Exception as e:
            print(f" Error en fila: {e}")
            conn.rollback()  # limpia la transacción para continuar

cur.close()
conn.close()

print(f" Datos importados correctamente: {count} registros insertados.")
