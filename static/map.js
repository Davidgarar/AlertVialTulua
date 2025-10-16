document.addEventListener("DOMContentLoaded", function () {
  // Crear mapa centrado en Tuluá
  const map = L.map("map").setView([4.0847, -76.1954], 13);

  // Capa base de OpenStreetMap
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors"
  }).addTo(map);

  // Proveedor de búsqueda
  const provider = new window.GeoSearch.OpenStreetMapProvider();

  // Control de búsqueda
  const searchControl = new window.GeoSearch.GeoSearchControl({
    provider: provider,
    style: "bar",
    showMarker: true,
    showPopup: true,
    marker: {
      icon: new L.Icon.Default(),
      draggable: false,
    },
    retainZoomLevel: false,
    animateZoom: true,
    autoClose: true,
    searchLabel: "Buscar dirección..."
  });

  map.addControl(searchControl);

  // Referencia al div donde se mostrará la dirección
  const infoDiv = document.getElementById("address-info");
  let marker;

  // Cuando el usuario selecciona una ubicación del buscador
  map.on("geosearch/showlocation", function (result) {
    const location = result.location;
    infoDiv.innerText = `Dirección seleccionada: ${location.label}`;
  });

  // Cuando el usuario hace clic en el mapa
  map.on("click", async function (e) {
    const { lat, lng } = e.latlng;

    if (marker) {
      map.removeLayer(marker);
    }

    marker = L.marker([lat, lng]).addTo(map);

    // Petición a OpenStreetMap (reverse geocoding)
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}`
      );
      const data = await response.json();

      if (data.display_name) {
        infoDiv.innerText = `Dirección seleccionada: ${data.display_name}`;
        marker.bindPopup(data.display_name).openPopup();
      } else {
        infoDiv.innerText = `Coordenadas seleccionadas: ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      }
    } catch (error) {
      console.error("Error al obtener dirección:", error);
      infoDiv.innerText = `Coordenadas seleccionadas: ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    }
  });

  // Centrar en ubicación actual si está disponible
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      const { latitude, longitude } = pos.coords;
      map.setView([latitude, longitude], 14);
      marker = L.marker([latitude, longitude]).addTo(map)
        .bindPopup("Tu ubicación actual").openPopup();
    });
  }
});
