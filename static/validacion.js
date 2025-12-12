// -------------------------
// VALIDACIÓN DEL FORMULARIO (MEJORADO)
// -------------------------

document.addEventListener("DOMContentLoaded", () => {

  const form = document.getElementById('report-form');

  form.addEventListener('submit', function(event) {
    let valid = true;

    // Campos
    const anio = document.getElementById('anio');
    const fecha = document.getElementById('fecha');
    const dia = document.getElementById('dia');
    const hora = document.getElementById('hora');
    const foto = document.getElementById('foto'); // <--- NUEVO

    // Spans de error
    const eAnio = document.getElementById('error-anio');
    const eFecha = document.getElementById('error-fecha');
    const eDia = document.getElementById('error-dia');
    const eHora = document.getElementById('error-hora');

    // Validaciones
    if (anio.value.trim() === '') {
      eAnio.innerText = "Ingrese el año.";
      valid = false;
    } else eAnio.innerText = "";

    if (fecha.value.trim() === '') {
      eFecha.innerText = "Seleccione una fecha.";
      valid = false;
    } else eFecha.innerText = "";

    if (dia.value.trim() === '') {
      eDia.innerText = "Seleccione un día.";
      valid = false;
    } else eDia.innerText = "";

    if (hora.value.trim() === '') {
      eHora.innerText = "Ingrese una hora.";
      valid = false;
    } else eHora.innerText = "";

    // --- NUEVA VALIDACIÓN DE FOTO ---
    if (foto.files.length === 0) {
      alert("⚠️ Debes adjuntar una foto obligatoriamente para la validación con IA.");
      valid = false;
    }

    // Copiar dirección al input oculto
    // Aseguramos que si address-info está vacío, no mande basura
    const direccionTexto = document.getElementById('address-info').innerText.trim();
    document.getElementById('direccionInfo').value = direccionTexto;

    if (direccionTexto === "Selecciona una ubicación o busca una dirección." || direccionTexto === "") {
        alert("Por favor selecciona una ubicación en el mapa.");
        valid = false;
    }

    if (!valid) event.preventDefault();
  });

});