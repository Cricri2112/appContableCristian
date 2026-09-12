"""Conversión de importes ingresados en formularios a Decimal.

Formato local (Uruguay): el punto es separador de miles y la coma es el
separador decimal. Ej.: "5.700" → 5700 ; "5.700,50" → 5700.50.
"""

from decimal import Decimal, InvalidOperation


def parsear_importe(
    texto: str, nombre: str = "importe"
) -> tuple[Decimal | None, str | None]:
    """Devuelve (valor, None) o (None, mensaje_de_error)."""
    limpio = texto.strip().replace("$", "").replace(" ", "")
    limpio = limpio.replace(".", "").replace(",", ".")
    if not limpio:
        return None, f"Ingresá el {nombre}."
    try:
        valor = Decimal(limpio)
    except InvalidOperation:
        return None, f"Ingresá un {nombre} válido."
    if valor <= 0:
        return None, f"El {nombre} debe ser mayor a cero."
    return valor, None
