const nombre = document.getElementById('name');
const correo = document.getElementById('email');
const contrasena = document.getElementById('password');
const ciudad = document.getElementById('city');
const form = document.getElementById('form');
const parrafo = document.getElementById('warnings');

form.addEventListener('submit', e => {
    e.preventDefault();
    let warnings = "";
    let entrar = false;
    parrafo.innerHTML = "";

    if (nombre.value.length < 6) {
        warnings += "El nombre no es válido <br>";
        entrar = true;
    }
    if (!correo.value.includes('@')) {
        warnings += "El correo no es válido <br>";
        entrar = true;
    }
    
    // VALIDACIÓN MEJORADA DE CONTRASEÑA
    const password = contrasena.value;
    if (password.length < 8) {
        warnings += "La contraseña debe tener al menos 8 caracteres <br>";
        entrar = true;
    }
    if (!/[a-zA-Z]/.test(password)) {
        warnings += "La contraseña debe contener al menos una letra <br>";
        entrar = true;
    }
    if (!/\d/.test(password)) {
        warnings += "La contraseña debe contener al menos un número <br>";
        entrar = true;
    }
    
    if (ciudad.value.length < 3) {
        warnings += "La ciudad no es válida <br>";
        entrar = true;
    }

    if (entrar) {
        parrafo.innerHTML = warnings;
    } else {
        parrafo.style.color = "green";
        parrafo.innerHTML = "Enviado correctamente ✅";
        setTimeout(() => form.submit(), 500);
    }
});