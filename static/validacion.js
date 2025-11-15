// -------------------------
// VALIDACIÓN DEL FORMULARIO
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

    // Copiar dirección al input oculto
    document.getElementById('direccionInfo').value =
      document.getElementById('address-info').innerText.trim();

    if (!valid) event.preventDefault();
  });

});
