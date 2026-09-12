"""Página base de la app (Etapa 0: HTML mínimo, sin funcionalidad de negocio)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.plantillas import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def pagina_inicio(request: Request):
    return templates.TemplateResponse(request, "inicio.html", {})
