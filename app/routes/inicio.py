"""Página base de la app (Etapa 0: HTML mínimo, sin funcionalidad de negocio)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.plantillas import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def pagina_inicio(request: Request, db: Session = Depends(get_db)):
    # `db` se pide para que el menú lateral muestre el progreso de tareas.
    return templates.TemplateResponse(request, "inicio.html", {})
