"""Cifrado Fernet de los campos sensibles del vault (Chat 4, decisión 6).

Fernet es cifrado simétrico (una sola clave cifra y descifra) con
verificación de integridad. La clave vive SOLO en la variable de entorno
FERNET_KEY: nunca en el código, en GitHub ni en la base.

Sin la clave correcta, los datos cifrados son irrecuperables. Por diseño.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

MENSAJE_SIN_CLAVE = (
    "ERROR: falta configurar FERNET_KEY (clave de cifrado del vault).\n"
    "Generala UNA SOLA VEZ con:\n"
    '  python -c "from cryptography.fernet import Fernet; '
    'print(Fernet.generate_key().decode())"\n'
    "agregala al archivo .env como FERNET_KEY=... y guardá una copia en tu "
    "gestor de contraseñas ANTES de cargar credenciales reales."
)

MENSAJE_CLAVE_INVALIDA = (
    "ERROR: FERNET_KEY tiene un formato inválido. Debe ser la clave generada "
    "con Fernet.generate_key() (44 caracteres terminados en '=')."
)


class ClaveNoConfigurada(RuntimeError):
    """FERNET_KEY falta o tiene un formato inválido."""


class DatoIndescifrable(Exception):
    """El texto no se puede descifrar con la clave actual (clave cambiada
    o perdida, o dato corrupto)."""


def _fernet() -> Fernet:
    """Construye el objeto Fernet con la clave del entorno."""
    clave = settings.fernet_key
    if not clave:
        raise ClaveNoConfigurada(MENSAJE_SIN_CLAVE)
    try:
        return Fernet(clave.encode("utf-8"))
    except ValueError as error:
        raise ClaveNoConfigurada(MENSAJE_CLAVE_INVALIDA) from error


def verificar_clave() -> None:
    """Se llama al arrancar la app: si la clave falta o es inválida, la app
    no arranca (criterio de terminado 5 de la Etapa 4)."""
    _fernet()


def cifrar(texto: str | None) -> str | None:
    """Cifra un texto. None se mantiene None (campo vacío)."""
    if texto is None:
        return None
    return _fernet().encrypt(texto.encode("utf-8")).decode("utf-8")


def descifrar(texto_cifrado: str | None) -> str | None:
    """Descifra un texto. Lanza DatoIndescifrable si la clave no coincide."""
    if texto_cifrado is None:
        return None
    try:
        return _fernet().decrypt(texto_cifrado.encode("utf-8")).decode("utf-8")
    except InvalidToken as error:
        raise DatoIndescifrable(
            "No se puede descifrar: la clave FERNET_KEY no es la que se usó al guardar."
        ) from error
