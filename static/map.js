let map, marker, geocoder, autocomplete;

function initMap() {
    const defaultLocation = { lat: 4.0847, lng: -76.1954 }; // Tuluá

    map = new google.maps.Map(document.getElementById("map"), {
        zoom: 12,
        center: defaultLocation,
    });

    geocoder = new google.maps.Geocoder();

    marker = new google.maps.Marker({
        position: defaultLocation,
        map,
        draggable: true,
        title: "Ubicación seleccionada"
    });

    // GEOLOCALIZACIÓN MEJORADA CON MÁS PRECISIÓN
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const userLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                };

                // Centrar el mapa en la ubicación del usuario
                map.setCenter(userLocation);
                map.setZoom(18); // Zoom más cercano para mejor precisión
                marker.setPosition(userLocation);
                getAddress(userLocation);

            },
            (error) => {
                console.log("Error obteniendo ubicación:", error);
                handleLocationError(true, map.getCenter());
            },
            {
                enableHighAccuracy: true, // Forzar alta precisión
                timeout: 15000, // Aumentar tiempo de espera
                maximumAge: 0 // No usar caché de ubicación
            }
        );

        // OPCIONAL: Usar watchPosition para actualizaciones en tiempo real
        navigator.geolocation.watchPosition(
            (position) => {
                const updatedLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                };
                
                // Actualizar marcador si la posición cambia significativamente
                const currentPos = marker.getPosition();
                const distance = calculateDistance(
                    currentPos.lat(), currentPos.lng(),
                    updatedLocation.lat, updatedLocation.lng
                );
                
                if (distance > 10) { // Solo actualizar si se movió más de 10 metros
                    marker.setPosition(updatedLocation);
                    map.setCenter(updatedLocation);
                }
            },
            (error) => {
                console.log("Error en watchPosition:", error);
            },
            {
                enableHighAccuracy: true,
                maximumAge: 30000,
                timeout: 10000
            }
        );

    } else {
        // El navegador no soporta geolocalización
        handleLocationError(false, map.getCenter());
    }

    // Click en el mapa
    map.addListener("click", (event) => {
        const clickedLocation = event.latLng;
        marker.setPosition(clickedLocation);
        getAddress(clickedLocation);
    });

    // Arrastrar marcador
    marker.addListener("dragend", () => {
        const pos = marker.getPosition();
        getAddress(pos);
    });

    // Autocompletado
    const input = document.getElementById("search-input");
    autocomplete = new google.maps.places.Autocomplete(input);
    autocomplete.bindTo("bounds", map);

    autocomplete.addListener("place_changed", () => {
        const place = autocomplete.getPlace();
        if (!place.geometry || !place.geometry.location) {
            alert("No se encontró información para esta dirección.");
            return;
        }

        map.panTo(place.geometry.location);
        map.setZoom(17);
        marker.setPosition(place.geometry.location);
        document.getElementById("address-info").innerText = place.formatted_address || place.name;
    });
}

function handleLocationError(browserHasGeolocation, pos) {
    console.log(browserHasGeolocation ?
                        "Error: El servicio de geolocalización falló." :
                        "Error: Tu navegador no soporta geolocalización.");
    getAddress(pos);
}

function getAddress(latlng) {
    geocoder.geocode({ location: latlng }, (results, status) => {
        if (status === "OK" && results[0]) {
            document.getElementById("address-info").innerText = results[0].formatted_address;
        } else {
            document.getElementById("address-info").innerText = "No se pudo obtener la dirección.";
        }
    });
}

// Función para calcular distancia entre dos puntos (Haversine)
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371e3; // Radio de la Tierra en metros
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c; // Distancia en metros
}

// Función para obtener coordenadas actuales
function getCurrentCoordinates() {
    return marker ? {
        lat: marker.getPosition().lat(),
        lng: marker.getPosition().lng()
    } : null;
}

window.onload = initMap;