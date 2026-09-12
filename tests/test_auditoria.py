"""Auditoría automática por event listeners (criterio de terminado 5)."""

import json
from datetime import date

from app.models import Auditoria, Cliente, Credencial


def _registros(db, tabla, accion):
    return (
        db.query(Auditoria)
        .filter(Auditoria.tabla == tabla, Auditoria.accion == accion)
        .all()
    )


def _cliente_de_prueba():
    return Cliente(
        nombre="Cliente Prueba",
        regimen="monotributo",
        rut="123456789012",
        fecha_inicio=date(2026, 1, 15),
    )


def test_creacion_queda_auditada(db_temporal):
    cliente = _cliente_de_prueba()
    db_temporal.add(cliente)
    db_temporal.commit()

    registros = _registros(db_temporal, "clientes", "creacion")
    assert len(registros) == 1
    registro = registros[0]
    assert registro.registro_id == cliente.id
    assert registro.datos_antes is None
    despues = json.loads(registro.datos_despues)
    assert despues["nombre"] == "Cliente Prueba"
    assert despues["regimen"] == "monotributo"
    assert despues["fecha_inicio"] == "2026-01-15"


def test_edicion_queda_auditada_con_antes_y_despues(db_temporal):
    cliente = _cliente_de_prueba()
    db_temporal.add(cliente)
    db_temporal.commit()

    cliente.nombre = "Nombre Nuevo"
    db_temporal.commit()

    registros = _registros(db_temporal, "clientes", "edicion")
    assert len(registros) == 1
    antes = json.loads(registros[0].datos_antes)
    despues = json.loads(registros[0].datos_despues)
    assert antes["nombre"] == "Cliente Prueba"
    assert despues["nombre"] == "Nombre Nuevo"
    # Los campos no modificados se conservan iguales en ambos snapshots
    assert antes["rut"] == despues["rut"] == "123456789012"


def test_eliminacion_queda_auditada_con_datos_antes(db_temporal):
    cliente = _cliente_de_prueba()
    db_temporal.add(cliente)
    db_temporal.commit()
    id_cliente = cliente.id

    db_temporal.delete(cliente)
    db_temporal.commit()

    registros = _registros(db_temporal, "clientes", "eliminacion")
    assert len(registros) == 1
    assert registros[0].registro_id == id_cliente
    assert registros[0].datos_despues is None
    antes = json.loads(registros[0].datos_antes)
    assert antes["nombre"] == "Cliente Prueba"


def test_campos_sensibles_de_credenciales_se_auditan_como_cifrado(db_temporal):
    """Chat 4: usuario, password y notas de `credenciales` nunca aparecen
    en la auditoría con su valor (regla verificada a fondo en la Etapa 4)."""
    cliente = _cliente_de_prueba()
    db_temporal.add(cliente)
    db_temporal.commit()

    credencial = Credencial(
        cliente_id=cliente.id,
        tipo="dgi",
        usuario="usuario-secreto",
        password="password-secreta",
        notas="nota secreta",
        ultima_actualizacion=date(2026, 9, 1),
    )
    db_temporal.add(credencial)
    db_temporal.commit()

    registros = _registros(db_temporal, "credenciales", "creacion")
    assert len(registros) == 1
    despues = json.loads(registros[0].datos_despues)
    assert despues["usuario"] == "[cifrado]"
    assert despues["password"] == "[cifrado]"
    assert despues["notas"] == "[cifrado]"
    # El registro completo tampoco contiene los valores reales
    assert "secreto" not in registros[0].datos_despues
    assert "secreta" not in registros[0].datos_despues
    # Los campos no sensibles sí se auditan normalmente
    assert despues["tipo"] == "dgi"


def test_la_auditoria_no_se_audita_a_si_misma(db_temporal):
    cliente = _cliente_de_prueba()
    db_temporal.add(cliente)
    db_temporal.commit()

    assert db_temporal.query(Auditoria).filter(
        Auditoria.tabla == "auditoria"
    ).count() == 0
