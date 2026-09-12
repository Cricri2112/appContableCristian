"""Instancia única de templates Jinja2, compartida por todas las rutas."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
