"""Alta del usuario único de la app (se ejecuta una sola vez).

Uso, desde la raíz del proyecto y con la migración ya aplicada:

    python scripts/crear_usuario.py

Pide usuario y contraseña por consola (la contraseña no se ve al tipearla)
y guarda el hash bcrypt en `usuario_login`. No hay pantalla de registro.
"""

import getpass
import sys
from pathlib import Path

# Permite ejecutar el script desde la raíz del proyecto sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect

from app.database import SessionLocal, engine
from app.models import UsuarioLogin
from app.services.autenticacion import hashear_password


def main():
    # La tabla debe existir: primero hay que correr `alembic upgrade head`.
    if not inspect(engine).has_table("usuario_login"):
        print("ERROR: la base no está migrada. Ejecutá primero: alembic upgrade head")
        sys.exit(1)

    db = SessionLocal()
    try:
        if db.query(UsuarioLogin).first() is not None:
            print("Ya existe el usuario de la app. No se puede crear otro.")
            sys.exit(1)

        usuario = input("Usuario: ").strip()
        if not usuario:
            print("ERROR: el usuario no puede estar vacío.")
            sys.exit(1)

        password = getpass.getpass("Contraseña: ")
        confirmacion = getpass.getpass("Repetir contraseña: ")
        if password != confirmacion:
            print("ERROR: las contraseñas no coinciden.")
            sys.exit(1)
        if not password:
            print("ERROR: la contraseña no puede estar vacía.")
            sys.exit(1)

        db.add(UsuarioLogin(usuario=usuario, password_hash=hashear_password(password)))
        db.commit()
        print(f"Usuario '{usuario}' creado correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
