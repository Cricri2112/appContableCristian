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
MESES_CORTOS = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "set", "oct", "nov", "dic",
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


def mes_abreviado(valor: date) -> str:
    """Solo la abreviatura del mes: "ene" (celdas del mapa de períodos)."""
    return MESES_CORTOS[valor.month - 1]


def mes_corto(valor: date) -> str:
    """Ej.: "jun 2026" (formato de períodos del README de referencia)."""
    return f"{MESES_CORTOS[valor.month - 1]} {valor.year}"


def formato_periodo(desde: date | None, hasta: date | None) -> str:
    """Período cubierto por un cobro.

    - Sin período: —
    - Servicio único (ambas fechas iguales, la fecha real del trabajo): dd/mm/aaaa
    - Un solo mes: "jun 2026"
    - Rango de meses: "abr – may 2026"
    """
    if desde is None or hasta is None:
        return VACIO
    if desde == hasta:
        return formato_fecha(desde)
    if (desde.year, desde.month) == (hasta.year, hasta.month):
        return mes_corto(desde)
    if desde.year == hasta.year:
        return f"{MESES_CORTOS[desde.month - 1]} – {MESES_CORTOS[hasta.month - 1]} {desde.year}"
    return f"{mes_corto(desde)} – {mes_corto(hasta)}"


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
