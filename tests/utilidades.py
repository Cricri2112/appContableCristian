"""Ayudantes para armar datos de prueba en los tests de la Etapa 2."""

from datetime import date

from app.models import Cliente, Servicio
from app.schemas.clientes import FormularioCliente
from app.services import contratos as servicio_contratos


def datos_cliente(**cambios) -> FormularioCliente:
    """Formulario de cliente válido; se ajusta con kwargs."""
    base = {
        "nombre": "Cliente Prueba",
        "regimen": "monotributo",
        "fecha_inicio": date(2026, 1, 15),
    }
    base.update(cambios)
    return FormularioCliente(**base)


def crear_cliente_directo(db, **cambios) -> Cliente:
    """Inserta un cliente directo en la base (sin pasar por el servicio)."""
    base = {
        "nombre": "Cliente Prueba",
        "regimen": "monotributo",
        "fecha_inicio": date(2026, 1, 15),
        "activo": True,
    }
    base.update(cambios)
    cliente = Cliente(**base)
    db.add(cliente)
    db.commit()
    return cliente


def crear_servicio_directo(db, nombre="Liquidación mensual", frecuencia="mensual",
                           activo=True) -> Servicio:
    servicio = Servicio(nombre=nombre, frecuencia=frecuencia, activo=activo)
    db.add(servicio)
    db.commit()
    return servicio


def contratar(db, cliente, servicio, fecha=date(2026, 2, 1), honorario="5000"):
    return servicio_contratos.contratar(db, cliente.id, servicio.id, fecha, honorario)
