"""F2 — Vault de credenciales (Chat 3 + Chat 5, Etapa 4).

- `usuario`, `password` y `notas` se cifran ANTES de escribir en la base
  y nunca se guardan en texto plano.
- El listado muestra el usuario en claro; la contraseña solo se descifra
  cuando se pide revelar (la contraseña en claro no viaja al navegador antes).
- La auditoría registra estos campos como "[cifrado]" (services/auditoria.py).
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import Credencial
from app.models.base import ahora_montevideo
from app.models.enums import TipoCredencial
from app.services import cifrado
from app.services.errores import ErrorValidacion

# Orden del enum (Chat 3, cambio 2): es el orden "ascendente" por tipo.
ORDEN_TIPOS = [t.value for t in TipoCredencial]

TIPOS_LEGIBLES = {
    "dgi": "DGI",
    "bps": "BPS",
    "facturador": "Facturador",
    "clave_dgi": "Clave DGI",
    "otro": "Otro",
}

# Texto que se muestra cuando un dato no se puede descifrar.
INDESCIFRABLE = "⚠ indescifrable"


def hoy() -> date:
    return ahora_montevideo().date()


@dataclass
class CredencialVisible:
    """Credencial lista para mostrar: tipo y usuario en claro, SIN contraseña."""

    credencial: Credencial
    usuario: str | None
    usuario_ok: bool  # False si no se pudo descifrar


def _descifrar_para_mostrar(texto_cifrado: str | None) -> tuple[str | None, bool]:
    """Descifra sin romper la vista: devuelve (texto, ok)."""
    try:
        return cifrado.descifrar(texto_cifrado), True
    except cifrado.DatoIndescifrable:
        return INDESCIFRABLE, False


def listar_credenciales(db: Session, cliente_id: int) -> list[CredencialVisible]:
    """Credenciales del cliente: tipo ascendente, luego última actualización
    descendente (Chat 3). La contraseña no se descifra acá."""
    credenciales = (
        db.query(Credencial).filter(Credencial.cliente_id == cliente_id).all()
    )
    credenciales.sort(
        key=lambda c: (
            ORDEN_TIPOS.index(c.tipo.value),
            -c.ultima_actualizacion.toordinal(),
            -c.id,
        )
    )
    visibles = []
    for credencial in credenciales:
        usuario, ok = _descifrar_para_mostrar(credencial.usuario)
        visibles.append(CredencialVisible(credencial, usuario, ok))
    return visibles


def contar_credenciales(db: Session, cliente_id: int) -> int:
    return db.query(Credencial).filter(Credencial.cliente_id == cliente_id).count()


def obtener_credencial(db: Session, credencial_id: int) -> Credencial | None:
    return db.get(Credencial, credencial_id)


def detalle(db: Session, credencial_id: int) -> dict:
    """Datos del panel de detalle: usuario y notas en claro, contraseña NO."""
    credencial = db.get(Credencial, credencial_id)
    usuario, usuario_ok = _descifrar_para_mostrar(credencial.usuario)
    notas, notas_ok = _descifrar_para_mostrar(credencial.notas)
    return {
        "credencial": credencial,
        "usuario": usuario,
        "notas": notas,
        "ok": usuario_ok and notas_ok,
        "tiene_password": credencial.password is not None,
    }


def revelar_password(db: Session, credencial_id: int) -> str | None:
    """Descifra la contraseña. Solo se llama cuando el usuario pide revelar."""
    credencial = db.get(Credencial, credencial_id)
    texto, _ = _descifrar_para_mostrar(credencial.password)
    return texto


def _limpiar(texto: str | None) -> str | None:
    """Campo de formulario vacío → None (no se cifra un string vacío)."""
    if texto is None:
        return None
    texto = texto.strip()
    return texto or None


def _validar(tipo: str, usuario: str | None, password: str | None) -> dict:
    errores = {}
    if tipo not in ORDEN_TIPOS:
        errores["tipo"] = "Elegí el tipo de credencial."
    if usuario is None and password is None:
        errores["general"] = "Ingresá al menos usuario o contraseña."
    return errores


def crear_credencial(
    db: Session,
    cliente_id: int,
    tipo: str,
    usuario: str | None,
    password: str | None,
    notas: str | None,
) -> Credencial:
    usuario, password, notas = _limpiar(usuario), _limpiar(password), _limpiar(notas)
    errores = _validar(tipo, usuario, password)
    if errores:
        raise ErrorValidacion(errores)

    credencial = Credencial(
        cliente_id=cliente_id,
        tipo=tipo,
        usuario=cifrado.cifrar(usuario),
        password=cifrado.cifrar(password),
        notas=cifrado.cifrar(notas),
        ultima_actualizacion=hoy(),
    )
    db.add(credencial)
    db.commit()
    return credencial


def editar_credencial(
    db: Session,
    credencial_id: int,
    tipo: str,
    usuario: str | None,
    password_nueva: str | None,
    notas: str | None,
) -> Credencial:
    """Edita y recifra. `ultima_actualizacion` pasa a hoy.

    La contraseña actual no se precarga en el formulario (no viaja en claro
    al navegador): si `password_nueva` llega vacía, se mantiene la actual.
    """
    credencial = db.get(Credencial, credencial_id)
    usuario, notas = _limpiar(usuario), _limpiar(notas)
    password_nueva = _limpiar(password_nueva)

    # Para validar "al menos usuario o contraseña" cuenta la que queda.
    queda_password = password_nueva is not None or credencial.password is not None
    errores = _validar(tipo, usuario, "x" if queda_password else None)
    if errores:
        raise ErrorValidacion(errores)

    credencial.tipo = tipo
    credencial.usuario = cifrado.cifrar(usuario)
    if password_nueva is not None:
        credencial.password = cifrado.cifrar(password_nueva)
    credencial.notas = cifrado.cifrar(notas)
    credencial.ultima_actualizacion = hoy()
    db.commit()
    return credencial


def eliminar_credencial(db: Session, credencial_id: int) -> None:
    """Eliminación física; en auditoria queda con los campos como [cifrado]."""
    credencial = db.get(Credencial, credencial_id)
    db.delete(credencial)
    db.commit()
