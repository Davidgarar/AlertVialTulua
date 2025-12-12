import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

class AccidentAIValidator:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            # CAMBIO AQUÍ: Usamos una versión más específica para evitar el error 404
            self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
        else:
            self.model = None
            print("⚠️ ADVERTENCIA: No se encontró GOOGLE_API_KEY en .env")

    def analizar_imagen(self, image_path):
        if not self.model:
            return {"es_real": True, "vehiculos": [], "razon": "Sin API Key"}

        try:
            print(f"🔍 Analizando imagen con IA: {image_path}")
            myfile = genai.upload_file(image_path)
            
            prompt = """
            Eres un perito de tráfico experto. Analiza esta imagen.
            Responde SOLO con un JSON válido (sin bloques de código markdown) con esta estructura exacta:
            {
                "es_real": boolean, (true si es un accidente de tráfico, una calle, vehículos chocados o situación vial. false si es un animal, comida, dibujo, paisaje natural sin calle, o videojuego),
                "vehiculos": [lista de strings con tipos de vehiculos detectados ej: "moto", "bus", "auto"],
                "razon": "breve texto explicativo de por qué se acepta o rechaza"
            }
            """

            result = self.model.generate_content([myfile, prompt])
            
            # Limpieza robusta de la respuesta
            texto_limpio = result.text.strip()
            if "```json" in texto_limpio:
                texto_limpio = texto_limpio.replace("```json", "").replace("```", "")
            elif "```" in texto_limpio:
                texto_limpio = texto_limpio.replace("```", "")
                
            datos = json.loads(texto_limpio)
            return datos

        except Exception as e:
            print(f"❌ Error IA: {e}")
            # En caso de error, devolvemos un diccionario seguro para no romper app.py
            return {"es_real": True, "vehiculos": [], "razon": "Error de conexión IA", "error": str(e)}