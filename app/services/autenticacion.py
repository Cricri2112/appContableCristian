"""Autenticación de usuario único (Chat 4, decisión 8 + Chat 5, Etapa 0).

- Contraseña hasheada con bcrypt (irreversible; solo se verifica).
- Sesión por cookie firmada, expiración 7 días sin uso.
- Anti fuerza bruta: 5 intentos fallidos → bloqueo 15 minutos.
- Cada intento fallido se registra en `auditoria` con accion=login_fallido,
  tabla='usuario_login', registro_id=id del usuario, datos null (enmienda A2).
"""

from dataclasses import dataclass
from datetime import timedelta

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Auditoria, UsuarioLogin
from app.models.base import ahora_montevideo

INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 15
DIAS_EXPIRACION_SESION = 7

# Firma y verifica el contenido de la cookie de sesión.
_firmador = URLSafeTimedSerializer(settings.secret_key, salt="sesion-app-contable")


@dataclass
class ResultadoLogin:
    """Resultado de un intento de login, para que la ruta arme la respuesta."""

    exitoso: bool
    mensaje: str | None = None       # mensaje de error para mostrar en el form
    usuario_id: int | None = None    # solo si exitoso


def hashear_password(password: str) -> str:
    """Genera el hash bcrypt de una contraseña (usado por el script CLI)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _registrar_intento_fallido(db: Session, usuario: UsuarioLogin):
    """Escribe el intento fallido en `auditoria` según la enmienda A2."""
    db.add(
        Auditoria(
            fecha=ahora_montevideo(),
            tabla="usuario_login",
            registro_id=usuario.id,
            accion="login_fallido",
            datos_antes=None,
            datos_despues=None,
        )
    )


def iniciar_sesion(db: Session, usuario_ingresado: str, password: str) -> ResultadoLogin:
    """Valida las credenciales aplicando el bloqueo anti fuerza bruta."""
    ahora = ahora_montevideo()

    # Usuario único: hay a lo sumo un registro en la tabla.
    usuario = db.query(UsuarioLogin).first()
    if usuario is None:
        return ResultadoLogin(
            exitoso=False,
            mensaje="No hay usuario configurado. Crealo con el script de alta.",
        )

    # ¿Está bloqueado?
    if usuario.bloqueado_hasta is not None:
        if ahora < usuario.bloqueado_hasta:
            _registrar_intento_fallido(db, usuario)
            db.commit()
            minutos = int((usuario.bloqueado_hasta - ahora).total_seconds() // 60) + 1
            return ResultadoLogin(
                exitoso=False,
                mensaje=f"Usuario bloqueado por intentos fallidos. "
                        f"Probá de nuevo en {minutos} minutos.",
            )
        # El bloqueo ya venció: se limpia y el contador arranca de cero.
        usuario.bloqueado_hasta = None
        usuario.intentos_fallidos = 0

    credenciales_ok = (
        usuario_ingresado == usuario.usuario
        and _verificar_password(password, usuario.password_hash)
    )

    if not credenciales_ok:
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= INTENTOS_MAXIMOS:
            usuario.bloqueado_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
        _registrar_intento_fallido(db, usuario)
        db.commit()
        if usuario.bloqueado_hasta is not None:
            return ResultadoLogin(
                exitoso=False,
                mensaje=f"Usuario bloqueado por intentos fallidos. "
                        f"Probá de nuevo en {MINUTOS_BLOQUEO} minutos.",
            )
        return ResultadoLogin(exitoso=False, mensaje="Usuario o contraseña incorrectos.")

    # Login correcto: se resetea el contador de intentos.
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    db.commit()
    return ResultadoLogin(exitoso=True, usuario_id=usuario.id)


def generar_token_sesion(usuario_id: int) -> str:
    """Crea el valor firmado que viaja en la cookie de sesión."""
    return _firmador.dumps({"usuario_id": usuario_id})


def verificar_token_sesion(token: str | None) -> int | None:
    """Devuelve el usuario_id si el token es válido y no expiró; si no, None."""
    if not token:
        return None
    try:
        datos = _firmador.loads(
            token, max_age=DIAS_EXPIRACION_SESION * 24 * 60 * 60
        )
    except (BadSignature, SignatureExpired):
        return None
    return datos.get("usuario_id")
