class CalculadorRutaSegura:
    def __init__(self, procesador_riesgo):
        self.procesador_riesgo = procesador_riesgo
    
    def calcular_ruta_segura(self, origen, destino, tabla_accidentes, filtros=None, cursor=None):
        """
        Calcular ruta segura entre origen y destino
        origen/destino: {'lat': x, 'lng': y}
        """
        if cursor is None:
            return self._ruta_por_defecto(origen, destino)
        
        # Generar puntos intermedios
        waypoints = self._generar_waypoints(origen, destino, 3)
        
        # Evaluar riesgo en cada waypoint
        ruta_con_riesgo = []
        riesgo_total = 0
        
        for punto in [origen] + waypoints + [destino]:
            riesgo = self.procesador_riesgo.calcular_riesgo_punto(
                punto['lat'], punto['lng'], tabla_accidentes, filtros, cursor
            )
            
            ruta_con_riesgo.append({
                'lat': punto['lat'],
                'lng': punto['lng'],
                'riesgo': round(riesgo, 3)
            })
            riesgo_total += riesgo
        
        riesgo_promedio = riesgo_total / len(ruta_con_riesgo) if ruta_con_riesgo else 0
        
        return {
            'ruta': ruta_con_riesgo,
            'riesgo_promedio': round(riesgo_promedio, 3),
            'puntos_riesgo_alto': [p for p in ruta_con_riesgo if p['riesgo'] > 0.7],
            'distancia_estimada_km': round(self._calcular_distancia_ruta(ruta_con_riesgo), 2),
            'filtros_aplicados': filtros
        }
    
    def _generar_waypoints(self, origen, destino, cantidad):
        """Generar puntos intermedios entre origen y destino"""
        waypoints = []
        
        for i in range(1, cantidad + 1):
            factor = i / (cantidad + 1)
            lat = origen['lat'] + (destino['lat'] - origen['lat']) * factor
            lng = origen['lng'] + (destino['lng'] - origen['lng']) * factor
            
            waypoints.append({'lat': round(lat, 6), 'lng': round(lng, 6)})
        
        return waypoints
    
    def _calcular_distancia_ruta(self, ruta):
        """Calcular distancia total de la ruta en km"""
        distancia_total = 0
        
        for i in range(len(ruta) - 1):
            punto_actual = ruta[i]
            punto_siguiente = ruta[i + 1]
            
            distancia = self.procesador_riesgo.calcular_distancia(
                punto_actual['lat'], punto_actual['lng'],
                punto_siguiente['lat'], punto_siguiente['lng']
            )
            
            distancia_total += distancia
        
        return distancia_total / 1000  # Convertir a km
    
    def _ruta_por_defecto(self, origen, destino):
        """Ruta por defecto cuando no hay cursor disponible"""
        waypoints = self._generar_waypoints(origen, destino, 2)
        ruta = [origen] + waypoints + [destino]
        
        return {
            'ruta': [{'lat': p['lat'], 'lng': p['lng'], 'riesgo': 0.1} for p in ruta],
            'riesgo_promedio': 0.1,
            'puntos_riesgo_alto': [],
            'distancia_estimada_km': round(self._calcular_distancia_ruta(ruta), 2),
            'filtros_aplicados': {},
            'nota': 'Ruta estimada - datos limitados'
        }