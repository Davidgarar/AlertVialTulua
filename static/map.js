let map, marker, geocoder, autocomplete;
let reportMarkers = [];
let markersVisible = false;


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


document.getElementById("toggle-markers").addEventListener("change", (e) => {
    markersVisible = e.target.checked;

    // Mostrar / ocultar marcadores existentes
    reportMarkers.forEach(m => m.setMap(markersVisible ? map : null));

    // Si se activan, recargar desde la base de datos
    if (markersVisible) {
        cargarMarkers();
    }
});



let currentAccidenteId = null;

// ---- Crear estrellas ----
function createRatingStars(container, initial = 0) {
  container.innerHTML = "";
  for (let i = 1; i <= 5; i++) {
    const s = document.createElement("span");
    s.className = "star";
    s.dataset.value = i;
    s.textContent = "★";

    if (i <= initial) {
        s.classList.add("active");
        container.dataset.value = initial; // <--- IMPORTANTE
    }

    s.onclick = () => {
        for (let st of container.children) {
            st.classList.toggle("active", Number(st.dataset.value) <= i);
        }
        container.dataset.value = i; // <--- GUARDA EL VALOR REAL
    };

    container.appendChild(s);
  }

}

// ---- Abrir modal ----
function openAccidenteModal(id) {
  currentAccidenteId = id;
  const modal = document.getElementById("accidente-modal");
  modal.setAttribute("aria-hidden", "false");

  document.getElementById("modal-id").textContent = id;
  document.getElementById("modal-meta").textContent = "Cargando...";
  document.getElementById("modal-main-data").innerHTML = "";
  document.getElementById("mini-gallery").innerHTML = "";
  createRatingStars(document.getElementById("rating"), 0);

  fetch(`/api/accidente/${id}`)
    .then(r => r.json())
    .then(data => {
      const meta = document.getElementById("modal-meta");
      const fecha = data.fecha ? new Date(data.fecha).toLocaleString() : "";
      meta.textContent = `${fecha} · ${data.barrio || ""} · ${data.gravedad || ""}`;

      document.getElementById("modal-main-data").innerHTML = `
        <p><strong>Área:</strong> ${data.area || "-"}</p>
        <p><strong>Dirección:</strong> ${data.direccion || "-"}</p>
        <p><strong>Clase:</strong> ${data.clase_accidente || "-"}</p>
        <p><strong>Servicio:</strong> ${data.clase_servicio || "-"}</p>
        <p><strong>Vehículo:</strong> ${data.clase_vehiculo || "-"}</p>
      `;

      // rating previo
      createRatingStars(document.getElementById("rating"), data.rating || 0);
      if (data.nota_interna)
        document.getElementById("nota-interna").value = data.nota_interna;

      // galería
      const g = document.getElementById("mini-gallery");
      if (data.fotos.length) {
        data.fotos.forEach(fn => {
          const img = document.createElement("img");
          img.src = `/static/img/${fn}`;
          img.onclick = () => window.open(img.src, "_blank");
          g.appendChild(img);
        });
      } else {
        g.innerHTML = "<p>No hay fotos.</p>";
      }
    });
}

// ---- Cerrar ----
document.getElementById("modal-close").onclick = () => {
  document.getElementById("accidente-modal")
    .setAttribute("aria-hidden", "true");
};

// ---- Guardar calificación ----
document.getElementById("btn-guardar-calificacion").onclick = () => {
  const rating = Number(document.getElementById("rating").dataset.value || 0);
  const nota = document.getElementById("nota-interna").value;

  fetch(`/api/accidente/${currentAccidenteId}/calificar`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ rating, nota })
  }).then(r => r.json()).then(res => {
    if (res.ok) {
      alert("Guardado");
      document.getElementById("accidente-modal")
        .setAttribute("aria-hidden", "true");
    }
  });
};

// ---- Cargar markers ----
function cargarMarkers() {
  // Borrar marcadores previos
  reportMarkers.forEach(m => m.setMap(null));
  reportMarkers = [];

  fetch("/api/accidentes_all")
    .then(r => r.json())
    .then(data => {
      data.accidentes.forEach(a => {
        const m = new google.maps.Marker({
          position: { lat: a.lat, lng: a.lng },
          title: "Reporte #" + a.id,
          map: markersVisible ? map : null   // <--- SOLO si está activado
        });

        m.addListener("click", () => openAccidenteModal(a.id));

        reportMarkers.push(m);
      });
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