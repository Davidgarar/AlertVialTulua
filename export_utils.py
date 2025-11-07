# export_utils.py - Utilidades para exportar datos
import csv
import io
import json
from datetime import datetime

class ExportUtils:
    @staticmethod
    def generar_csv(datos):
        """Generar archivo CSV desde los datos"""
        if not datos:
            return None
            
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Escribir headers
        if datos:
            headers = datos[0].keys()
            writer.writerow(headers)
            
            # Escribir datos
            for fila in datos:
                writer.writerow([fila.get(header, '') for header in headers])
        
        return output.getvalue()
    
    @staticmethod
    def generar_json(datos):
        """Generar archivo JSON desde los datos"""
        return json.dumps(datos, indent=2, ensure_ascii=False, default=str)
    
    @staticmethod
    def formatear_filtros(filtros):
        """Formatear filtros para el reporte"""
        if not filtros:
            return "Sin filtros aplicados"
            
        texto_filtros = []
        if filtros.get('fecha_inicio'):
            texto_filtros.append(f"Desde: {filtros['fecha_inicio']}")
        if filtros.get('fecha_fin'):
            texto_filtros.append(f"Hasta: {filtros['fecha_fin']}")
        if filtros.get('gravedad'):
            texto_filtros.append(f"Gravedad: {filtros['gravedad']}")
        if filtros.get('zona'):
            texto_filtros.append(f"Zona: {filtros['zona']}")
        if filtros.get('tipo_accidente'):
            texto_filtros.append(f"Tipo: {filtros['tipo_accidente']}")
        if filtros.get('hora'):
            texto_filtros.append(f"Horario: {filtros['hora']}")
            
        return ", ".join(texto_filtros) if texto_filtros else "Sin filtros aplicados"

class PDFGenerator:
    """Generador básico de PDF (usando reportlab si está disponible)"""
    
    @staticmethod
    def generar_pdf_simple(datos, filtros, estadisticas):
        """Generar un PDF simple usando texto formateado"""
        from io import BytesIO
        
        output = BytesIO()
        
        # Encabezado del reporte
        contenido = [
            "REPORTE DE ACCIDENTES - AlertViaTulua",
            "=" * 50,
            f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Filtros aplicados: {ExportUtils.formatear_filtros(filtros)}",
            "",
            "ESTADÍSTICAS PRINCIPALES:",
            f"Total de accidentes: {estadisticas.get('total_accidentes', 0)}",
            f"Accidentes con heridos: {estadisticas.get('con_heridos', 0)}",
            f"Accidentes con muertos: {estadisticas.get('con_muertos', 0)}",
            f"Zona más peligrosa: {estadisticas.get('zona_mas_peligrosa', 'N/A')}",
            "",
            "DETALLE DE ACCIDENTES:",
            "-" * 50
        ]
        
        # Agregar datos
        for i, accidente in enumerate(datos.get('datos', [])[:100]):  # Limitar a 100 registros
            contenido.append(
                f"{i+1}. {accidente.get('fecha', 'N/A')} {accidente.get('hora', 'N/A')} - "
                f"{accidente.get('barrio_hecho', 'N/A')} - {accidente.get('gravedad_accidente', 'N/A')}"
            )
        
        contenido.extend([
            "",
            f"Total de registros mostrados: {len(datos.get('datos', []))}",
            "=" * 50,
            "Fin del reporte"
        ])
        
        # Convertir a bytes
        output.write("\n".join(contenido).encode('utf-8'))
        output.seek(0)
        
        return output