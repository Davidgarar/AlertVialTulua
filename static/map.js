let map, marker, geocoder, autocomplete;

function initMap() {
  const defaultLocation = { lat: 4.7110, lng: -74.0721 }; // Bogotá

  // Crear mapa
  map = new google.maps.Map(document.getElementById("map"), {
    zoom: 12,
    center: defaultLocation,
  });

  geocoder = new google.maps.Geocoder();

  // Crear marcador
  marker = new google.maps.Marker({
    position: defaultLocation,
    map: map,
    draggable: true,
    title: "Ubicación seleccionada"
  });

  // Mostrar dirección inicial
  getAddress(defaultLocation);

  // Evento al hacer clic en el mapa
  map.addListener("click", (event) => {
    const clickedLocation = event.latLng;
    marker.setPosition(clickedLocation);
    getAddress(clickedLocation);
  });

  // Evento al mover el marcador manualmente
  marker.addListener("dragend", () => {
    const pos = marker.getPosition();
    getAddress(pos);
  });

  // Activar el autocompletado en la barra de búsqueda
  const input = document.getElementById("search-input");
  autocomplete = new google.maps.places.Autocomplete(input);
  autocomplete.bindTo("bounds", map);

  // Cuando el usuario selecciona una dirección
  autocomplete.addListener("place_changed", () => {
    const place = autocomplete.getPlace();
    if (!place.geometry || !place.geometry.location) {
      alert("No se encontró información para esta dirección.");
      return;
    }

    // Mover el mapa al lugar seleccionado
    map.panTo(place.geometry.location);
    map.setZoom(15);

    // Mover el marcador
    marker.setPosition(place.geometry.location);

    // Mostrar la dirección
    document.getElementById("address-info").innerText = place.formatted_address || place.name;
  });
}

// Función para obtener dirección a partir de coordenadas
function getAddress(latlng) {
  geocoder.geocode({ location: latlng }, (results, status) => {
    if (status === "OK" && results[0]) {
      document.getElementById("address-info").innerText = results[0].formatted_address;
    } else {
      document.getElementById("address-info").innerText = "No se pudo obtener la dirección.";
    }
  });
}

window.onload = initMap;
