"""Envío de email transaccional por API (Chat 4, decisión 7).

Proveedor: Brevo (candidato principal del Chat 4: permite verificar una
dirección individual como remitente, sin dominio propio). El envío es una
llamada HTTPS a su API, no SMTP. La clave vive en BREVO_API_KEY.

Para cambiar de proveedor (ej. Resend) alcanza con reescribir `enviar_email`.
"""

import json
import urllib.error
import urllib.request

from app.config import settings

URL_API_BREVO = "https://api.brevo.com/v3/smtp/email"
NOMBRE_REMITENTE = "Estudio Contable"
TIMEOUT_SEGUNDOS = 20


class ErrorEmail(Exception):
    """El email no se pudo enviar (configuración faltante o error del proveedor)."""


def configurado() -> bool:
    return bool(settings.brevo_api_key and settings.email_remitente)


def enviar_email(destino: str, asunto: str, html: str) -> None:
    """Envía un email HTML. Lanza ErrorEmail si algo falla."""
    if not configurado():
        raise ErrorEmail("email no configurado (faltan BREVO_API_KEY o EMAIL_REMITENTE)")
    if not destino:
        raise ErrorEmail("falta el email de destino (Configuración → Notificaciones)")

    cuerpo = json.dumps({
        "sender": {"name": NOMBRE_REMITENTE, "email": settings.email_remitente},
        "to": [{"email": destino}],
        "subject": asunto,
        "htmlContent": html,
    }).encode("utf-8")
    pedido = urllib.request.Request(
        URL_API_BREVO,
        data=cuerpo,
        method="POST",
        headers={
            "api-key": settings.brevo_api_key,
            "content-type": "application/json",
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            if not 200 <= respuesta.status < 300:
                raise ErrorEmail(f"Brevo respondió {respuesta.status}")
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")[:200]
        raise ErrorEmail(f"Brevo respondió {error.code}: {detalle}") from error
    except urllib.error.URLError as error:
        raise ErrorEmail(f"no se pudo conectar con Brevo: {error.reason}") from error
