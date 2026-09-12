"""Endpoints de la Etapa 3 — cobertura proporcional."""

from datetime import date
from decimal import Decimal

from app.services import cuentas, honorarios
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo


def _contrato_con_deuda(db, honorario="5000"):
    cliente = crear_cliente_directo(db)
    servicio = crear_servicio_directo(db)
    contrato = contratar(db, cliente, servicio, fecha=date(2026, 8, 1),
                         honorario=honorario)
    return cliente, contrato


# ---------- F5 ----------

def test_vista_global_muestra_saldos_y_totales(sesion, db_temporal):
    cliente, _ = _contrato_con_deuda(db_temporal)

    pagina = sesion.get("/cobros")
    assert pagina.status_code == 200
    assert cliente.nombre in pagina.text
    assert "Total adeudado" in pagina.text
    assert "Aumento global de honorarios" in pagina.text


def test_registrar_cobro_desde_la_web(sesion, db_temporal):
    cliente, contrato = _contrato_con_deuda(db_temporal)

    respuesta = sesion.post(
        f"/clientes/{cliente.id}/cobros/nuevo",
        data={
            "cliente_id": str(cliente.id),
            "servicio_contratado_id": str(contrato.id),
            "periodo_desde": "2026-08-01",
            "periodo_hasta": "2026-08-31",
            "fecha_cobro": "2026-09-01",
            "importe": "5.000",
            "forma_pago": "transferencia",
            "tipo_comprobante": "e_ticket",
            "notas": "",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    saldo = cuentas.calcular_saldo(db_temporal, cliente.id)
    assert saldo["cobros"] == Decimal("5000")

    cuenta = sesion.get(f"/clientes/{cliente.id}/cuenta")
    assert "ago 2026" in cuenta.text  # el período del cobro


def test_cobro_con_un_solo_periodo_muestra_error(sesion, db_temporal):
    cliente, _ = _contrato_con_deuda(db_temporal)
    respuesta = sesion.post(
        f"/clientes/{cliente.id}/cobros/nuevo",
        data={
            "cliente_id": str(cliente.id),
            "periodo_desde": "2026-08-01",
            "fecha_cobro": "2026-09-01",
            "importe": "5.000",
            "forma_pago": "transferencia",
            "tipo_comprobante": "e_ticket",
        },
    )
    assert respuesta.status_code == 422
    assert "van juntos" in respuesta.text


def test_eliminar_cobro_con_confirmacion(sesion, db_temporal):
    from app.services import cobros as servicio_cobros

    cliente, _ = _contrato_con_deuda(db_temporal)
    cobro = servicio_cobros.registrar_cobro(db_temporal, {
        "cliente_id": cliente.id, "servicio_contratado_id": None,
        "periodo_desde": None, "periodo_hasta": None,
        "fecha_cobro": date(2026, 9, 1), "importe": "5.000",
        "forma_pago": "transferencia", "tipo_comprobante": "e_ticket", "notas": "",
    })

    confirmacion = sesion.get(f"/cobros/{cobro.id}/eliminar")
    assert (
        "¿Confirmás que querés eliminar este registro? "
        "Esta acción no se puede deshacer." in confirmacion.text
    )

    respuesta = sesion.post(f"/cobros/{cobro.id}/eliminar", follow_redirects=False)
    assert respuesta.status_code == 303
    assert cuentas.calcular_saldo(db_temporal, cliente.id)["cobros"] == Decimal("0")


def test_registrar_descuento_desde_la_web(sesion, db_temporal):
    cliente, _ = _contrato_con_deuda(db_temporal)
    respuesta = sesion.post(
        f"/clientes/{cliente.id}/descuentos/nuevo",
        data={"fecha": "2026-09-01", "importe": "1.500", "motivo": "Bonificación"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert cuentas.calcular_saldo(db_temporal, cliente.id)["descuentos"] == Decimal("1500")


# ---------- F6 ----------

def test_cambio_de_honorario_igual_muestra_literal(sesion, db_temporal):
    _, contrato = _contrato_con_deuda(db_temporal, honorario="5700")
    respuesta = sesion.post(
        f"/contratos/{contrato.id}/honorario",
        data={"honorario": "5.700", "fecha_vigencia": "2026-10-01"},
    )
    assert respuesta.status_code == 422
    assert "El nuevo honorario es igual al vigente." in respuesta.text


def test_wizard_de_aumento_global_completo(sesion, db_temporal):
    _, contrato = _contrato_con_deuda(db_temporal, honorario="5.700")

    # Paso 1 → 2: candidatos con el nuevo calculado ($6.190).
    paso2 = sesion.post(
        "/aumento-global/paso2",
        data={"porcentaje": "8,5", "fecha_vigencia": "2026-10-01"},
    )
    assert paso2.status_code == 200
    assert "6190" in paso2.text

    # Paso 2 → 3 sin selección: error.
    sin_seleccion = sesion.post(
        "/aumento-global/paso3",
        data={"porcentaje": "8,5", "fecha_vigencia": "2026-10-01"},
    )
    assert sin_seleccion.status_code == 422
    assert "Seleccioná al menos un servicio." in sin_seleccion.text

    # Paso 2 → 3 con selección: resumen.
    paso3 = sesion.post(
        "/aumento-global/paso3",
        data={
            "porcentaje": "8,5",
            "fecha_vigencia": "2026-10-01",
            "seleccion": str(contrato.id),
            f"nuevo_{contrato.id}": "6190",
        },
    )
    assert paso3.status_code == 200
    assert "Confirmar aumento" in paso3.text

    # Confirmar: se aplica la mecánica.
    listo = sesion.post(
        "/aumento-global/confirmar",
        data={
            "porcentaje": "8,5",
            "fecha_vigencia": "2026-10-01",
            "seleccion": str(contrato.id),
            f"nuevo_{contrato.id}": "6190",
        },
    )
    assert listo.status_code == 200
    assert "Aumento aplicado" in listo.text

    vigente = honorarios.honorario_vigente(db_temporal, contrato.id)
    assert vigente.honorario == Decimal("6190")
    assert vigente.fecha_desde == date(2026, 10, 1)


def test_historial_consolidado_en_la_ficha(sesion, db_temporal):
    cliente, contrato = _contrato_con_deuda(db_temporal)
    honorarios.cambiar_honorario(db_temporal, contrato.id, "6.200", date(2026, 9, 1))

    pagina = sesion.get(f"/clientes/{cliente.id}/honorarios")
    assert pagina.status_code == 200
    assert "$ 6.200" in pagina.text
    assert "vigente" in pagina.text
