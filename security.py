from werkzeug.security import generate_password_hash, check_password_hash

def encrypt_password(password):
    """Genera un hash seguro para la contraseña proporcionada."""
    return generate_password_hash(password)

def verify_password(stored_password, provided_password):
    """Verifica si la contraseña proporcionada coincide con el hash almacenado."""
    return check_password_hash(stored_password, provided_password)  
