"""Error de validación de negocio.

Las rutas lo atrapan y re-renderizan el formulario con los mensajes
debajo de cada campo (los literales exactos del Chat 3).
"""


class ErrorValidacion(Exception):
    """Errores de validación por campo: {nombre_de_campo: mensaje}."""

    def __init__(self, errores: dict[str, str]):
        self.errores = errores
        super().__init__("; ".join(errores.values()))
