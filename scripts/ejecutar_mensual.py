"""Dispara el proceso mensual a demanda (herramienta de desarrollo, Chat 5).

Uso, desde la raíz del proyecto:

    python scripts/ejecutar_mensual.py

Genera las tareas del mes en curso y registra la ejecución en
`scheduler_ejecuciones`, igual que el scheduler el día 1. Es seguro
ejecutarlo varias veces: la generación tiene anti-duplicados.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Tarea  # noqa: E402
from app.services import fechas, scheduler  # noqa: E402


def main():
    db = SessionLocal()
    try:
        periodo = fechas.primer_dia_mes(fechas.hoy())
        antes = db.query(func.count(Tarea.id)).filter(Tarea.periodo == periodo).scalar()
        resultado = scheduler.ejecutar_proceso_mensual(db)
        despues = db.query(func.count(Tarea.id)).filter(Tarea.periodo == periodo).scalar()
        print(f"Período {periodo:%m/%Y} — resultado: {resultado}")
        print(f"Tareas creadas en esta ejecución: {despues - antes} (total del período: {despues})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
