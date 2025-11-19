import math
import json

class ProcesadorRiesgo:
    def __init__(self, radio_zona=100):  # metros por defecto
        self.radio_zona = radio_zona
        self.riesgo_maximo_teorico = 5.0  # Límite máximo para normalización
    
    def calcular_distancia(self, lat1, lon1, lat2, lon2):
        """Calcular distancia entre dos puntos en metros usando Haversine"""
        R = 6371000  # Radio de la Tierra en metros
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon/2) * math.sin(delta_lon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def calcular_riesgo_punto(self, lat, lng, tabla_accidentes, filtros=None, cursor=None, conn=None):
        """Calcular nivel de riesgo para un punto específico usando criterios de la BD"""
        if cursor is None:
            return 0.0
        
        from data_filters import FiltroAccidentes
        filtro_obj = FiltroAccidentes()
        
        if filtros:
            for key, value in filtros.items():
                if hasattr(filtro_obj, f'por_{key}'):
                    getattr(filtro_obj, f'por_{key}')(value)
        
        # Consulta base para accidentes
        query = f"SELECT latitud, longitud, gravedad_accidente, hora, clase_accidente FROM {tabla_accidentes} WHERE latitud IS NOT NULL AND longitud IS NOT NULL"
        params = []
        
        # Aplicar filtros
        query, params = filtro_obj.aplicar_sql(query, params)
        
        try:
            cursor.execute(query, params)
            accidentes = cursor.fetchall()
        except Exception as e:
            print(f"Error en consulta de accidentes: {e}")
            return 0.0
        
        if not accidentes:
            return 0.0
        
        # OBTENER CRITERIOS DE RIESGO DE LA BASE DE DATOS
        criterios = self.obtener_criterios_riesgo(cursor)
        
        # Calcular riesgo basado en accidentes cercanos y criterios
        riesgo_total = 0.0
        accidentes_cercanos = 0
        
        for accidente in accidentes:
            acc_lat = accidente[0]
            acc_lng = accidente[1]
            gravedad = accidente[2] if accidente[2] else 'SOLO DANOS'
            hora = accidente[3] if accidente[3] else ''
            clase_accidente = accidente[4] if accidente[4] else ''
            
            if acc_lat is None or acc_lng is None:
                continue
                
            distancia = self.calcular_distancia(lat, lng, acc_lat, acc_lng)
            
            if distancia <= self.radio_zona:
                # Calcular peso base basado en gravedad
                peso_base = self.calcular_peso_base(gravedad)
                
                # APLICAR CRITERIOS DE RIESGO (sumar en lugar de multiplicar)
                peso_adicional = self.aplicar_criterios_riesgo(peso_base, criterios, {
                    'hora': hora,
                    'gravedad': gravedad,
                    'clase_accidente': clase_accidente,
                    'distancia': distancia
                })
                
                # Factor de distancia (más cercano = más riesgo)
                factor_distancia = 1 - (distancia / self.radio_zona)
                
                riesgo_total += (peso_base + peso_adicional) * factor_distancia
                accidentes_cercanos += 1
        
        if accidentes_cercanos == 0:
            return 0.0
        
        riesgo_promedio = riesgo_total / accidentes_cercanos
        
        # NORMALIZACIÓN CORREGIDA - Usar límite máximo
        riesgo_normalizado = min(riesgo_promedio / self.riesgo_maximo_teorico, 1.0)
        
        print(f"DEBUG - Riesgo: promedio={riesgo_promedio:.2f}, normalizado={riesgo_normalizado:.2f}, accidentes={accidentes_cercanos}")
        
        return riesgo_normalizado
    
    def obtener_criterios_riesgo(self, cursor):
        """Obtener criterios de riesgo activos de la base de datos"""
        try:
            cursor.execute("""
                SELECT nombre, parametros, peso 
                FROM criterios_riesgo 
                WHERE activo = TRUE
                ORDER BY peso DESC
            """)
            criterios = cursor.fetchall()
            
            criterios_procesados = []
            for criterio in criterios:
                nombre = criterio[0]
                parametros = json.loads(criterio[1]) if criterio[1] else {}
                peso = float(criterio[2])
                
                criterios_procesados.append({
                    'nombre': nombre,
                    'parametros': parametros,
                    'peso': peso
                })
            
            print(f"Criterios de riesgo cargados: {len(criterios_procesados)}")
            return criterios_procesados
            
        except Exception as e:
            print(f"Error al cargar criterios de riesgo: {e}")
            return []
    
    def calcular_peso_base(self, gravedad):
        """Calcular peso base según la gravedad del accidente"""
        gravedad_upper = gravedad.upper() if gravedad else ''
        
        if 'MUERTO' in gravedad_upper:
            return 3.0
        elif 'HERIDO' in gravedad_upper:
            return 2.0
        else:
            return 1.0
    
    def aplicar_criterios_riesgo(self, peso_base, criterios, contexto):
        """Aplicar todos los criterios de riesgo - SUMAR en lugar de multiplicar"""
        peso_adicional = 0.0
        
        for criterio in criterios:
            adicional = self.evaluar_criterio(criterio, contexto)
            peso_adicional += adicional
            print(f"Aplicado criterio {criterio['nombre']}: +{adicional:.2f}")
        
        # Limitar el peso adicional para evitar valores excesivos
        return min(peso_adicional, 2.0)  # Máximo 2.0 adicional
    
    def evaluar_criterio(self, criterio, contexto):
        """Evaluar un criterio específico contra el contexto del accidente"""
        nombre = criterio['nombre']
        parametros = criterio['parametros']
        peso_base = criterio['peso']
        
        if nombre == 'riesgo_nocturno':
            return self.evaluar_riesgo_nocturno(contexto['hora'], parametros, peso_base)
        elif nombre == 'riesgo_lluvia':
            return self.evaluar_riesgo_clima(contexto.get('clima', ''), parametros, peso_base)
        elif nombre == 'riesgo_heridos_muertos':
            return self.evaluar_riesgo_gravedad(contexto['gravedad'], parametros, peso_base)
        else:
            return 0.0  # Sin efecto adicional
    
    def evaluar_riesgo_nocturno(self, hora, parametros, peso_base):
        """Evaluar riesgo nocturno"""
        if not hora:
            return 0.0
            
        try:
            hora_inicio = parametros.get('hora_inicio', '18:00')
            hora_fin = parametros.get('hora_fin', '06:00')
            factor = parametros.get('factor_nocturno', 0.5)  # REDUCIDO
            
            # Conversión simple de hora
            if ':' in hora:
                hora_num = int(hora.split(':')[0])
            else:
                return 0.0
            
            # Verificar si está en rango nocturno
            hora_inicio_num = int(hora_inicio.split(':')[0])
            hora_fin_num = int(hora_fin.split(':')[0])
            
            if hora_inicio_num <= hora_fin_num:
                # Rango normal (ej: 18:00-23:00)
                if hora_inicio_num <= hora_num <= hora_fin_num:
                    return factor * peso_base
            else:
                # Rango que cruza medianoche (ej: 18:00-06:00)
                if hora_num >= hora_inicio_num or hora_num <= hora_fin_num:
                    return factor * peso_base
                    
        except Exception as e:
            print(f"Error evaluando riesgo nocturno: {e}")
            
        return 0.0
    
    def evaluar_riesgo_gravedad(self, gravedad, parametros, peso_base):
        """Evaluar riesgo por gravedad"""
        if not gravedad:
            return 0.0
            
        gravedades_riesgo = parametros.get('gravedades', ['Con heridos', 'Con muertos'])
        factor = parametros.get('factor_gravedad', 0.3)  # REDUCIDO
        
        if any(g in gravedad for g in gravedades_riesgo):
            return factor * peso_base
            
        return 0.0
    
    def evaluar_riesgo_clima(self, clima, parametros, peso_base):
        """Evaluar riesgo por condiciones climáticas"""
        if not clima:
            return 0.0
            
        climas_riesgo = parametros.get('climas', ['Lluvia', 'Niebla'])
        factor = parametros.get('factor_clima', 0.2)  # REDUCIDO
        
        if any(c in clima for c in climas_riesgo):
            return factor * peso_base
            
        return 0.0
    
    def generar_mapa_calor(self, bounds, tabla_accidentes, filtros=None, resolucion=0.01, cursor=None, conn=None):
        """Generar puntos para mapa de calor"""
        if cursor is None:
            return []
        
        lat_min, lng_min, lat_max, lng_max = bounds
        puntos_calor = []
        
        # Reducir resolución para mejor performance en producción
        lat_actual = lat_min
        while lat_actual <= lat_max:
            lng_actual = lng_min
            while lng_actual <= lng_max:
                riesgo = self.calcular_riesgo_punto(lat_actual, lng_actual, tabla_accidentes, filtros, cursor, conn)
                
                if riesgo > 0.01:  # Reducir umbral para incluir más puntos
                    puntos_calor.append({
                        'lat': round(lat_actual, 6),
                        'lng': round(lng_actual, 6),
                        'intensidad': round(riesgo, 3)
                    })
                
                lng_actual += resolucion * 2  # Aumentar paso para mejor performance
            lat_actual += resolucion * 2
        
        return puntos_calor
    
    def obtener_estadisticas_riesgo(self, tabla_accidentes, filtros=None, cursor=None, conn=None):
        """Obtener estadísticas generales de riesgo"""
        if cursor is None:
            return {'total_accidentes': 0, 'riesgo_promedio': 0}
        
        from data_filters import FiltroAccidentes
        filtro_obj = FiltroAccidentes()
        
        if filtros:
            for key, value in filtros.items():
                if hasattr(filtro_obj, f'por_{key}'):
                    getattr(filtro_obj, f'por_{key}')(value)
        
        query = f"SELECT COUNT(*) FROM {tabla_accidentes} WHERE 1=1"
        params = []
        query, params = filtro_obj.aplicar_sql(query, params)
        
        try:
            cursor.execute(query, params)
            total_accidentes = cursor.fetchone()[0]
        except Exception as e:
            print(f"Error en consulta estadísticas: {e}")
            total_accidentes = 0
        
        return {
            'total_accidentes': total_accidentes,
            'filtros_aplicados': filtros
        }
    
    def calcular_riesgo_area(self, lat, lng, radio_m, accidentes):
        """Calcular índice de riesgo para un área basada en accidentes conocidos"""
        conteo = 0
        puntaje = 0.0

        for acc in accidentes:
            acc_lat = float(acc['latitud'])
            acc_lng = float(acc['longitud'])
            dist = self.calcular_distancia(lat, lng, acc_lat, acc_lng)
            if dist > radio_m:
                continue

            conteo += 1
            gravedad = (acc['gravedad_accidente'] or '').lower()
            peso = 1.0
            if 'muert' in gravedad:
                peso = 3.0
            elif 'herid' in gravedad:
                peso = 2.0

            puntaje += peso * (1 - dist / radio_m)

        if conteo == 0:
            return {'indice': 0.05, 'conteo': 0}  # leve riesgo base

        densidad = 1 - math.exp(-conteo / 6.0)          # 0..1 según cantidad
        severidad_prom = min(1.0, (puntaje / conteo) / 3.5)
        indice = round(min(1.0, (densidad * 0.7) + (severidad_prom * 0.3)), 3)

        return {'indice': indice, 'conteo': conteo}