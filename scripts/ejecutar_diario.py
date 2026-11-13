"""Dispara el proceso diario a demanda (herramienta de desarrollo, Chat 5).

Uso, desde la raíz del proyecto:

    python scripts/ejecutar_diario.py

Evalúa los recordatorios, manda el email resumen (si hay activos y el
email está configurado) y hace el respaldo de la base, igual que el
scheduler a las 06:00. A diferencia del scheduler, corre aunque ya haya
corrido hoy (sirve para probar). La generación tiene anti-duplicados.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.services import scheduler  # noqa: E402


def main():
    db = SessionLocal()
    try:
        print(scheduler.ejecutar_proceso_diario(db, forzar=True))
    finally:
        db.close()


if __name__ == "__main__":
    main()
