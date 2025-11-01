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

  // Mostrar dirección inicial
  getAddress(defaultLocation);

  // Click en mapa
  map.addListener("click", (event) => {
    const clickedLocation = event.latLng;
    marker.setPosition(clickedLocation);
    getAddress(clickedLocation);
  });

  // Mover marcador
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
    map.setZoom(15);
    marker.setPosition(place.geometry.location);
    document.getElementById("address-info").innerText = place.formatted_address || place.name;
  });
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



window.onload = initMap;
