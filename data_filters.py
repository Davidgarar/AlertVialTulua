import json
from datetime import datetime

class FiltroAccidentes:
    def __init__(self):
        self.filtros = {}
    
    def por_hora(self, hora_inicio=None, hora_fin=None):
        """Filtrar por rango de horas"""
        if hora_inicio and hora_fin:
            self.filtros['hora'] = (hora_inicio, hora_fin)
        return self
    
    def por_clima(self, condiciones_clima):
        """Filtrar por condiciones climáticas"""
        if condiciones_clima:
            if isinstance(condiciones_clima, str):
                condiciones_clima = [condiciones_clima]
            self.filtros['clima'] = condiciones_clima
        return self
    
    def por_tipo_accidente(self, tipos_accidente):
        """Filtrar por tipos de accidente"""
        if tipos_accidente:
            if isinstance(tipos_accidente, str):
                tipos_accidente = [tipos_accidente]
            self.filtros['tipo_accidente'] = tipos_accidente
        return self
    
    def por_fecha(self, fecha_inicio=None, fecha_fin=None):
        """Filtrar por rango de fechas"""
        if fecha_inicio and fecha_fin:
            self.filtros['fecha'] = (fecha_inicio, fecha_fin)
        return self
    
    def por_gravedad(self, gravedades):
        """Filtrar por gravedad de accidente"""
        if gravedades:
            if isinstance(gravedades, str):
                gravedades = [gravedades]
            self.filtros['gravedad'] = gravedades
        return self
    
    def por_barrio(self, barrios):
        """Filtrar por barrios"""
        if barrios:
            if isinstance(barrios, str):
                barrios = [barrios]
            self.filtros['barrio'] = barrios
        return self
    
    def por_ano(self, anos):
        """Filtrar por años"""
        if anos:
            if isinstance(anos, (str, int)):
                anos = [str(anos)]
            elif isinstance(anos, list):
                anos = [str(ano) for ano in anos]
            self.filtros['ano'] = anos
        return self
    
    def aplicar_sql(self, query_base, params):
        """Aplicar filtros a consulta SQL"""
        query = query_base
        params_list = params
        
        if 'hora' in self.filtros:
            hora_inicio, hora_fin = self.filtros['hora']
            query += " AND hora BETWEEN %s AND %s"
            params_list.extend([hora_inicio, hora_fin])
        
        if 'clima' in self.filtros:
            # Asumiendo que hay un campo 'condiciones_climaticas' o similar
            placeholders = ','.join(['%s'] * len(self.filtros['clima']))
            query += f" AND condiciones_climaticas IN ({placeholders})"
            params_list.extend(self.filtros['clima'])
        
        if 'tipo_accidente' in self.filtros:
            placeholders = ','.join(['%s'] * len(self.filtros['tipo_accidente']))
            query += f" AND clase_accidente IN ({placeholders})"
            params_list.extend(self.filtros['tipo_accidente'])
        
        if 'fecha' in self.filtros:
            fecha_inicio, fecha_fin = self.filtros['fecha']
            query += " AND fecha BETWEEN %s AND %s"
            params_list.extend([fecha_inicio, fecha_fin])
        
        if 'gravedad' in self.filtros:
            placeholders = ','.join(['%s'] * len(self.filtros['gravedad']))
            query += f" AND gravedad_accidente IN ({placeholders})"
            params_list.extend(self.filtros['gravedad'])
        
        if 'barrio' in self.filtros:
            placeholders = ','.join(['%s'] * len(self.filtros['barrio']))
            query += f" AND barrio_hecho IN ({placeholders})"
            params_list.extend(self.filtros['barrio'])
        
        if 'ano' in self.filtros:
            placeholders = ','.join(['%s'] * len(self.filtros['ano']))
            query += f" AND ano IN ({placeholders})"
            params_list.extend(self.filtros['ano'])
        
        return query, params_list
    
    def limpiar(self):
        """Limpiar todos los filtros"""
        self.filtros = {}
        return self