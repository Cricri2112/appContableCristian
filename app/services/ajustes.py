"""Ajustes editables desde la app (tabla `configuracion`, clave/valor).

Hoy solo guarda el email de destino del resumen diario (F10:
"Dirección de destino configurable — cambiar de casilla no toca código").
"""

from sqlalchemy.orm import Session

from app.models import Configuracion
from app.services.errores import ErrorValidacion

CLAVE_EMAIL_DESTINO = "email_destino"


def _leer(db: Session, clave: str) -> str | None:
    fila = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    return fila.valor if fila else None


def _guardar(db: Session, clave: str, valor: str | None) -> None:
    fila = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if fila is None:
        db.add(Configuracion(clave=clave, valor=valor))
    else:
        fila.valor = valor
    db.commit()


def email_destino(db: Session) -> str | None:
    return _leer(db, CLAVE_EMAIL_DESTINO)


def guardar_email_destino(db: Session, email: str) -> str:
    """Valida lo mínimo (no vacío, con @ y un punto en el dominio)."""
    email = email.strip()
    usuario, arroba, dominio = email.partition("@")
    if not (usuario and arroba and "." in dominio and " " not in email):
        raise ErrorValidacion({"email_destino": "Ingresá una dirección de email válida."})
    _guardar(db, CLAVE_EMAIL_DESTINO, email)
    return email
