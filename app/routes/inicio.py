"""Dashboard (F9, vista 01): pantalla inicial de la app."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.plantillas import templates
from app.services import cuentas, fechas, finanzas, tareas, vencimientos

router = APIRouter()

# Prioridad para ordenar los clientes en el bloque de tareas: lo urgente primero.
URGENCIA = {"rojo": 0, "amarillo": 1, "verde": 2, None: 3}


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    hoy = fechas.hoy()
    mes = fechas.primer_dia_mes(hoy)
    resumen = finanzas.resumen_mes(db, mes)

    # Bloque 3 — accesos rápidos.
    grupos = tareas.grupos_del_periodo(db, mes)
    vencimientos.completar_grupos_con_limite(db, grupos, mes)
    grupos.sort(key=lambda g: (URGENCIA[g["semaforo"]], g["cliente"].nombre.lower()))
    completadas, total = tareas.progreso_periodo(db, mes)
    deudores = [
        fila for fila in cuentas.saldos_de_clientes_activos(db)["filas"] if fila["saldo"] > 0
    ]

    return templates.TemplateResponse(request, "dashboard.html", {
        "seccion": "dashboard",
        "mes": mes,
        "dia": hoy.day,
        "dias_mes": fechas.ultimo_dia_mes(mes).day,
        "resumen": resumen,
        "detalle_gastos": finanzas.detalle_gastos(resumen),
        "proximos": vencimientos.proximos_dias(db, 15)[:6],
        "grupos": grupos[:6],
        "tareas_abiertas": total - completadas,
        "tareas_total": total,
        "deudores": deudores[:5],
    })
