// analytics.js - Lógica para el panel de estadísticas

let chartInstances = {};
let currentData = null;

// Cargar datos iniciales
document.addEventListener('DOMContentLoaded', function() {
    cargarFiltros();
    cargarEstadisticas();
});

// Cargar opciones de filtros desde la API
async function cargarFiltros() {
    try {
        const response = await fetch('/api/analytics/filtros');
        const data = await response.json();
        
        // Llenar filtro de zonas
        const filtroZona = document.getElementById('filtro-zona');
        data.zonas.forEach(zona => {
            if (zona) {
                const option = document.createElement('option');
                option.value = zona;
                option.textContent = zona;
                filtroZona.appendChild(option);
            }
        });
        
        // Llenar filtro de tipos
        const filtroTipo = document.getElementById('filtro-tipo');
        data.tipos_accidente.forEach(tipo => {
            if (tipo) {
                const option = document.createElement('option');
                option.value = tipo;
                option.textContent = tipo;
                filtroTipo.appendChild(option);
            }
        });
        
    } catch (error) {
        console.error('Error cargando filtros:', error);
    }
}

// Cargar estadísticas con filtros aplicados
async function cargarEstadisticas() {
    const filtros = obtenerFiltros();
    
    try {
        mostrarLoading(true);
        
        const response = await fetch('/api/analytics/estadisticas', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ filtros })
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        currentData = data;
        actualizarUI(data);
        
    } catch (error) {
        console.error('Error cargando estadísticas:', error);
        mostrarError('Error al cargar las estadísticas: ' + error.message);
    } finally {
        mostrarLoading(false);
    }
}

// Obtener valores de los filtros
function obtenerFiltros() {
    return {
        fecha_inicio: document.getElementById('fecha-inicio').value,
        fecha_fin: document.getElementById('fecha-fin').value,
        gravedad: document.getElementById('filtro-gravedad').value,
        zona: document.getElementById('filtro-zona').value,
        tipo_accidente: document.getElementById('filtro-tipo').value,
        hora: document.getElementById('filtro-hora').value
    };
}

// Limpiar todos los filtros
function limpiarFiltros() {
    document.getElementById('fecha-inicio').value = '';
    document.getElementById('fecha-fin').value = '';
    document.getElementById('filtro-gravedad').value = '';
    document.getElementById('filtro-zona').value = '';
    document.getElementById('filtro-tipo').value = '';
    document.getElementById('filtro-hora').value = '';
    
    cargarEstadisticas();
}

// Actualizar la interfaz con los datos
function actualizarUI(data) {
    actualizarEstadisticasPrincipales(data.estadisticas);
    actualizarGraficos(data.graficos);
    actualizarTabla(data.datos);
}

// Actualizar tarjetas de estadísticas principales
function actualizarEstadisticasPrincipales(stats) {
    const container = document.getElementById('stats-cards');
    
    container.innerHTML = `
        <div class="stat-card">
            <div class="stat-label">Total Accidentes</div>
            <div class="stat-number">${stats.total_accidentes}</div>
            <div>En período seleccionado</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Accidentes con Heridos</div>
            <div class="stat-number">${stats.con_heridos}</div>
            <div>${stats.porcentaje_heridos}% del total</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Accidentes con Muertos</div>
            <div class="stat-number">${stats.con_muertos}</div>
            <div>${stats.porcentaje_muertos}% del total</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Zona más Peligrosa</div>
            <div class="stat-number">${stats.zona_mas_peligrosa || 'N/A'}</div>
            <div>${stats.max_accidentes_zona} accidentes</div>
        </div>
    `;
}

// Actualizar todos los gráficos
function actualizarGraficos(graficos) {
    // Destruir gráficos existentes
    Object.values(chartInstances).forEach(chart => {
        if (chart) chart.destroy();
    });
    
    // Gráfico de horas
    chartInstances.horas = new Chart(document.getElementById('chart-horas'), {
        type: 'bar',
        data: {
            labels: graficos.por_hora.labels,
            datasets: [{
                label: 'Accidentes por Hora',
                data: graficos.por_hora.data,
                backgroundColor: 'rgba(54, 162, 235, 0.8)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Cantidad de Accidentes'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Hora del Día'
                    }
                }
            }
        }
    });
    
    // Gráfico de días de la semana
    chartInstances.dias = new Chart(document.getElementById('chart-dias'), {
        type: 'bar',
        data: {
            labels: graficos.por_dia.labels,
            datasets: [{
                label: 'Accidentes por Día',
                data: graficos.por_dia.data,
                backgroundColor: 'rgba(255, 99, 132, 0.8)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 1
            }]
        }
    });
    
    // Gráfico de gravedad
    chartInstances.gravedad = new Chart(document.getElementById('chart-gravedad'), {
        type: 'pie',
        data: {
            labels: graficos.por_gravedad.labels,
            datasets: [{
                data: graficos.por_gravedad.data,
                backgroundColor: [
                    'rgba(255, 99, 132, 0.8)',
                    'rgba(255, 159, 64, 0.8)',
                    'rgba(75, 192, 192, 0.8)'
                ]
            }]
        }
    });
    
    // Gráfico de tipos de accidente
    chartInstances.tipo = new Chart(document.getElementById('chart-tipo'), {
        type: 'doughnut',
        data: {
            labels: graficos.por_tipo.labels,
            datasets: [{
                data: graficos.por_tipo.data,
                backgroundColor: [
                    'rgba(54, 162, 235, 0.8)',
                    'rgba(255, 206, 86, 0.8)',
                    'rgba(75, 192, 192, 0.8)',
                    'rgba(153, 102, 255, 0.8)',
                    'rgba(255, 159, 64, 0.8)'
                ]
            }]
        }
    });
    
    // Gráfico de zonas
    chartInstances.zonas = new Chart(document.getElementById('chart-zonas'), {
        type: 'bar',
        data: {
            labels: graficos.por_zona.labels,
            datasets: [{
                label: 'Accidentes por Zona',
                data: graficos.por_zona.data,
                backgroundColor: 'rgba(40, 167, 69, 0.8)',
                borderColor: 'rgba(40, 167, 69, 1)',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true
        }
    });
}

// Actualizar tabla de datos
function actualizarTabla(datos) {
    const tbody = document.getElementById('tabla-body');
    
    if (datos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="padding: 20px; text-align: center;">No hay datos para mostrar con los filtros aplicados</td></tr>';
        return;
    }
    
    tbody.innerHTML = datos.map(accidente => `
        <tr>
            <td style="padding: 10px; border: 1px solid #dee2e6;">${accidente.fecha || 'N/A'}</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">${accidente.hora || 'N/A'}</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">${accidente.barrio_hecho || 'N/A'}</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">${accidente.clase_accidente || 'N/A'}</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">${accidente.gravedad_accidente || 'N/A'}</td>
        </tr>
    `).join('');
}

// Exportar a CSV
async function exportarCSV() {
    if (!currentData) {
        alert('No hay datos para exportar');
        return;
    }
    
    try {
        const response = await fetch('/api/analytics/exportar/csv', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                filtros: obtenerFiltros(),
                datos: currentData.datos 
            })
        });
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `accidentes_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
    } catch (error) {
        console.error('Error exportando CSV:', error);
        alert('Error al exportar CSV');
    }
}

// Exportar a PDF
async function exportarPDF() {
    if (!currentData) {
        alert('No hay datos para exportar');
        return;
    }
    
    try {
        const response = await fetch('/api/analytics/exportar/pdf', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                filtros: obtenerFiltros(),
                datos: currentData 
            })
        });
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `reporte_accidentes_${new Date().toISOString().split('T')[0]}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
    } catch (error) {
        console.error('Error exportando PDF:', error);
        alert('Error al exportar PDF');
    }
}

// Mostrar/ocultar loading
function mostrarLoading(mostrar) {
    const elements = document.querySelectorAll('.loading');
    elements.forEach(el => {
        el.style.display = mostrar ? 'block' : 'none';
    });
}


// Mostrar error
function mostrarError(mensaje) {
    const container = document.getElementById('stats-cards');
    container.innerHTML = `<div class="no-data">${mensaje}</div>`;
    
    // Limpiar gráficos y tabla
    Object.values(chartInstances).forEach(chart => {
        if (chart) chart.destroy();
    });
    document.getElementById('tabla-body').innerHTML = '<tr><td colspan="5" style="padding: 20px; text-align: center;">Error al cargar datos</td></tr>';
}