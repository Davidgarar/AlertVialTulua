let map, directionsService, directionsRenderer, geocoder;
let infoToast = null;

function mostrarNotificacion(texto) {
    if (!infoToast) infoToast = document.getElementById('route-toast');
    if (!infoToast) return;
    infoToast.textContent = texto;
    infoToast.classList.add('show');
    clearTimeout(infoToast.dismissTimeout);
    infoToast.dismissTimeout = setTimeout(() => {
        infoToast.classList.remove('show');
    }, 4000);
}

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 4.5409, lng: -75.6950 },
        zoom: 12
    });

    directionsService = new google.maps.DirectionsService();
    directionsRenderer = new google.maps.DirectionsRenderer();
    directionsRenderer.setMap(map);

    geocoder = new google.maps.Geocoder();
}

const rutasActivas = [];

function limpiarRutas() {
    rutasActivas.forEach((ruta) => ruta.setMap(null));
    rutasActivas.length = 0;
}

document.addEventListener('DOMContentLoaded', () => {
    const boton = document.getElementById('route-button');
    const modal = document.getElementById('route-modal');
    const send = document.getElementById('send-route');
    const closeModal = document.getElementById('close-modal');
    const startInput = document.getElementById('start-input');
    const endInput = document.getElementById('end-input');

    if (!boton || !modal || !send || !closeModal || !startInput || !endInput) {
        console.warn('No se encontraron los elementos necesarios para el modal de ruta.');
        return;
    }

    boton.addEventListener('click', () => {
        modal.style.display = 'block';
    });

    closeModal.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            modal.style.display = 'none';
        }
    });

    const geocodeAddress = (address) => new Promise((resolve, reject) => {
        geocoder.geocode({ address }, (results, status) => {
            if (status === "OK" && results[0]) {
                resolve(results[0]);
            } else {
                reject(new Error(`Dirección no encontrada: ${address}`));
            }
        });
    });

    const directionsRequest = (request) => new Promise((resolve, reject) => {
        directionsService.route(request, (result, status) => {
            if (status === "OK") {
                resolve(result);
            } else {
                reject(new Error(`Google Directions falló: ${status}`));
            }
        });
    });

    const obtenerRutasConAlternativas = async (baseRequest) => {
        const variantes = [
            { label: null, extra: {} },
            { label: 'evitando autopistas', extra: { avoidHighways: true } },
            { label: 'evitando peajes', extra: { avoidTolls: true } },
            { label: 'evitando transbordadores', extra: { avoidFerries: true } }
        ];
        let mejorResultado = null;
        for (const variante of variantes) {
            const request = { ...baseRequest, ...variante.extra };
            try {
                const result = await directionsRequest(request);
                if (!mejorResultado || (result.routes?.length || 0) > (mejorResultado.routes?.length || 0)) {
                    mejorResultado = result;
                }
                if (result.routes && result.routes.length >= 2) {
                    return { result, varianteAplicada: variante.label };
                }
            } catch (error) {
                console.warn('Intento de ruta alterna falló:', error);
            }
        }
        if (mejorResultado) {
            return { result: mejorResultado, varianteAplicada: null };
        }
        throw new Error('No se pudieron obtener rutas desde Google Maps.');
    };

    const calcularRuta = async () => {
        const start = startInput.value.trim();
        const end = endInput.value.trim();

        if (start === "" || end === "") {
            mostrarNotificacion("Debes escribir ambas direcciones.");
            return;
        }

        send.textContent = 'Calculando...';
        send.disabled = true;

        if (!geocoder) {
            mostrarNotificacion('El mapa todavía no está listo. Intenta de nuevo en unos segundos.');
            send.textContent = 'Calcular';
            send.disabled = false;
            return;
        }

        try {
            const origen = await geocodeAddress(`${start}, Tuluá, Valle del Cauca, Colombia`);
            const destino = await geocodeAddress(`${end}, Tuluá, Valle del Cauca, Colombia`);

            const baseRequest = {
                origin: origen.geometry.location,
                destination: destino.geometry.location,
                travelMode: google.maps.TravelMode.DRIVING,
                provideRouteAlternatives: true
            };

            const { result: directionsResult, varianteAplicada } = await obtenerRutasConAlternativas(baseRequest);
            const rutas = directionsResult.routes || [];

            if (rutas.length < 2) {
                mostrarNotificacion("Sólo se obtuvo una ruta incluso tras reintentos.");
            } else if (varianteAplicada) {
                mostrarNotificacion(`Rutas alternativas generadas ${varianteAplicada}.`);
            }

            const clima = await obtenerClima(
                destino.geometry.location.lat(),
                destino.geometry.location.lng()
            ).catch(err => {
                console.warn("No se pudo obtener el clima:", err);
                return null;
            });

            const accidentesPorRuta = await Promise.all(
                rutas.map((ruta) => obtenerAccidentalidadPromedio(ruta))
            );

            let menorRiesgo = Infinity;
            let mejorRuta = -1;
            // En la función donde calculas el riesgo, cambia esto:
            rutas.forEach((ruta, i) => {
                const tiempoMin = ruta.legs[0].duration.value / 60;

                let riesgoClima = 0;
                if (clima && clima.weather && clima.weather[0]) {
                    const main = clima.weather[0].main;
                    if (main === "Rain") riesgoClima = 40;
                    if (main === "Thunderstorm") riesgoClima = 60;
                }

                const riesgoAcc = Math.min(100, (accidentesPorRuta[i]?.nivel || 0.2) * 100);

                const total = Math.min(100, tiempoMin + riesgoClima + riesgoAcc);

                ruta.riesgo = total;
                ruta.detalleRiesgo = {
                    tiempo: Math.round(tiempoMin),
                    clima: riesgoClima,
                    accidentalidad: Math.round(riesgoAcc),
                    accidentes_cercanos: accidentesPorRuta[i]?.accidentes || 0
                };

                if (total < menorRiesgo) {
                    menorRiesgo = total;
                    mejorRuta = i;
                }
            });

            limpiarRutas();

            rutas.forEach((ruta, i) => {
                const stroke = i === mejorRuta ? "green" : "orange";
                const polyline = new google.maps.Polyline({
                    path: ruta.overview_path,
                    geodesic: true,
                    strokeColor: stroke,
                    strokeWeight: i === mejorRuta ? 6 : 4,
                    map,
                    zIndex: i === mejorRuta ? 2 : 1
                });
                polyline.addListener('click', () => {
                    const detalle = ruta.detalleRiesgo;
                    
                    // FORMATO MEJORADO - Mostrar datos exactos
                    let mensajeAccidentes;
                    if (detalle.accidentes_cercanos === 0) {
                        mensajeAccidentes = "0 accidentes reportados";
                    } else if (detalle.accidentes_cercanos === 1) {
                        mensajeAccidentes = "1 accidente reportado";
                    } else {
                        mensajeAccidentes = `${detalle.accidentes_cercanos} accidentes reportados`;
                    }
                    
                    mostrarNotificacion(
                        `Ruta ${i + 1}: Riesgo ${Math.round(ruta.riesgo)}% | ` +
                        `Tiempo: ${detalle.tiempo} min | ` +
                        `Impacto clima: ${detalle.clima}% | ` +
                        `Zonas de riesgo: ${Math.round(detalle.accidentalidad)}% | ` +
                        `${mensajeAccidentes}`
                    );
                });
                rutasActivas.push(polyline);
            });

            modal.style.display = 'none';
            if (mejorRuta >= 0) {
                mostrarNotificacion(`Ruta recomendada: #${mejorRuta + 1} (riesgo ${Math.round(menorRiesgo)}%)`);
            }
            startInput.value = '';
            endInput.value = '';
        } catch (error) {
            console.error('Error calculando ruta:', error);
            mostrarNotificacion(error.message || 'No fue posible calcular la ruta.');
        } finally {
            send.textContent = 'Calcular';
            send.disabled = false;
        }
    };

    send.addEventListener('click', calcularRuta);

    startInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            calcularRuta();
        }
    });

    endInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            calcularRuta();
        }
    });
});

async function obtenerClima(lat, lon) {
    const res = await fetch(`/clima?lat=${lat}&lon=${lon}`);
    const data = await res.json();
    return data;
}

async function obtenerAccidentalidadPromedio(ruta) {
    const puntos = sampleRoutePoints(ruta.overview_path, 6);
    if (!puntos.length) {
        return { nivel: 0.2, accidentes: 0 };
    }

    const respuestas = await Promise.all(
        puntos.map(async (punto) => {
            try {
                const resp = await fetch('/api/riesgo/calcular', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ lat: punto.lat, lng: punto.lng })
                });
                if (!resp.ok) throw new Error('Error consultando accidentalidad');
                const data = await resp.json();
                
                // Asegúrate de que la API devuelve estos campos
                return {
                    nivel_riesgo: data.nivel_riesgo || data.riesgo || 0.2,
                    accidentes_cercanos: data.accidentes_cercanos || data.accidentes || 0
                };
            } catch (error) {
                console.warn('Error consultando accidentalidad:', error);
                return { nivel_riesgo: 0.2, accidentes_cercanos: 0 };
            }
        })
    );

    const nivelPromedio = respuestas.reduce((acc, item) => acc + item.nivel_riesgo, 0) / respuestas.length;
    const accidentesTotales = respuestas.reduce((acc, item) => acc + item.accidentes_cercanos, 0);

    return { 
        nivel: nivelPromedio, 
        accidentes: Math.round(accidentesTotales) // Asegurar número entero
    };
}

function sampleRoutePoints(path, desiredSamples = 5) {
    if (!path || !path.length) return [];
    if (path.length <= desiredSamples) {
        return path.map((p) => ({ lat: p.lat(), lng: p.lng() }));
    }

    const step = Math.max(1, Math.floor(path.length / desiredSamples));
    const puntos = [];

    for (let i = 0; i < path.length && puntos.length < desiredSamples; i += step) {
        const punto = path[i];
        puntos.push({ lat: punto.lat(), lng: punto.lng() });
    }

    if (!puntos.length && path.length) {
        const puntoMedio = path[Math.floor(path.length / 2)];
        puntos.push({ lat: puntoMedio.lat(), lng: puntoMedio.lng() });
    }

    return puntos;
}

