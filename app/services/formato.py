"""Formatos de presentación (referencia/README.md, punto 5).

- Importes: `$ 6.190` — punto de miles, sin decimales salvo que existan,
  `−` para negativos.
- Fechas: `dd/mm/aaaa`. Fecha larga en español para la barra superior.
- Vacíos: `—`.
"""

from datetime import date, datetime
from decimal import Decimal

# Nombres en español sin depender del locale del sistema operativo.
# "setiembre" es la forma usada en Uruguay.
DIAS_SEMANA = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre",
]

VACIO = "—"

# Etiquetas legibles de los enums (los valores nunca se muestran crudos).
REGIMENES_LEGIBLES = {
    "unipersonal_prof": "Unipersonal profesional",
    "unipersonal_no_prof": "Unipersonal no profesional",
    "monotributo": "Monotributo",
    "pequena_empresa": "Pequeña empresa",
    "regimen_general": "Régimen general",
    "persona_fisica": "Persona física",
    "todos": "Todos",
}
FRECUENCIAS_LEGIBLES = {
    "mensual": "Mensual",
    "anual": "Anual",
    "unico": "Único",
}


def _valor_enum(valor) -> str:
    """Acepta tanto el enum como su valor string."""
    return valor.value if hasattr(valor, "value") else valor


def regimen_legible(valor) -> str:
    return REGIMENES_LEGIBLES.get(_valor_enum(valor), _valor_enum(valor))


def frecuencia_legible(valor) -> str:
    return FRECUENCIAS_LEGIBLES.get(_valor_enum(valor), _valor_enum(valor))


def formato_fecha(valor: date | None) -> str:
    """dd/mm/aaaa; vacío como —."""
    if valor is None:
        return VACIO
    return valor.strftime("%d/%m/%Y")


def fecha_larga(valor: date | datetime) -> str:
    """Ej.: "jueves 11 de setiembre de 2026" (barra superior)."""
    return (
        f"{DIAS_SEMANA[valor.weekday()]} {valor.day} "
        f"de {MESES[valor.month - 1]} de {valor.year}"
    )


def formato_importe(valor: Decimal | int | float | None) -> str:
    """`$ 6.190` con punto de miles; decimales solo si existen; `−` negativo."""
    if valor is None:
        return VACIO
    numero = Decimal(str(valor))
    negativo = numero < 0
    numero = abs(numero)

    entera = int(numero)
    decimales = numero - entera
    # Punto de miles: se formatea con coma y se cambia por punto.
    texto = f"{entera:,}".replace(",", ".")
    if decimales:
        # Dos decimales, con coma decimal (uso local).
        texto += f",{int(decimales * 100):02d}"
    signo = "−" if negativo else ""
    return f"$ {signo}{texto}"
