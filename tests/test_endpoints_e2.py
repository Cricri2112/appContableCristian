"""Endpoints de la Etapa 2 — cobertura proporcional (Chat 4, decisión 9):
casos principales y validaciones de entrada, con los mensajes literales."""

from datetime import date

from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo


# ---------- F1: clientes ----------

def test_listado_separa_mensuales_y_eventuales(sesion, db_temporal):
    mensualero = crear_cliente_directo(db_temporal, nombre="Mensualero")
    crear_cliente_directo(db_temporal, nombre="Eventualero")
    servicio = crear_servicio_directo(db_temporal)
    contratar(db_temporal, mensualero, servicio)

    pagina = sesion.get("/clientes")
    assert pagina.status_code == 200
    seccion_mensuales = pagina.text.split("Clientes eventuales")[0]
    seccion_eventuales = pagina.text.split("Clientes eventuales")[1]
    assert "Mensualero" in seccion_mensuales
    assert "Eventualero" in seccion_eventuales


def test_filtro_de_inactivos_en_listado(sesion, db_temporal):
    crear_cliente_directo(db_temporal, nombre="Dormido", activo=False)

    assert "Dormido" not in sesion.get("/clientes").text
    assert "Dormido" in sesion.get("/clientes?inactivos=1").text


def test_crear_cliente_redirige_a_la_ficha(sesion, db_temporal):
    respuesta = sesion.post(
        "/clientes/nuevo",
        data={
            "nombre": "Cliente Web",
            "regimen": "monotributo",
            "fecha_inicio": "2026-01-15",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    ficha = sesion.get(respuesta.headers["location"])
    assert "Cliente Web" in ficha.text
    assert "Historial de regímenes" in ficha.text


def test_crear_cliente_con_rut_invalido_muestra_literal(sesion, db_temporal):
    respuesta = sesion.post(
        "/clientes/nuevo",
        data={
            "nombre": "Cliente Web",
            "regimen": "monotributo",
            "fecha_inicio": "2026-01-15",
            "rut": "123",
        },
    )
    assert respuesta.status_code == 422
    assert "El RUT debe tener 12 dígitos numéricos." in respuesta.text


def test_editar_con_cambio_de_regimen_desde_el_formulario(sesion, db_temporal):
    cliente = crear_cliente_directo(db_temporal, regimen="monotributo")

    respuesta = sesion.post(
        f"/clientes/{cliente.id}/editar",
        data={
            "nombre": cliente.nombre,
            "regimen": "regimen_general",
            "fecha_cambio_regimen": "2026-06-01",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    ficha = sesion.get(f"/clientes/{cliente.id}")
    assert "Régimen general" in ficha.text
    assert "vigente" in ficha.text


def test_desactivar_cliente_en_un_clic(sesion, db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    respuesta = sesion.post(f"/clientes/{cliente.id}/activo", follow_redirects=False)
    assert respuesta.status_code == 303
    db_temporal.refresh(cliente)
    assert cliente.activo is False


# ---------- F3: catálogo ----------

def test_crear_servicio_duplicado_muestra_literal(sesion, db_temporal):
    crear_servicio_directo(db_temporal, "Liquidación mensual", "mensual")
    respuesta = sesion.post(
        "/configuracion/servicios/nuevo",
        data={"nombre": "Liquidación mensual", "frecuencia": "mensual"},
    )
    assert respuesta.status_code == 422
    assert "Ya existe un servicio con ese nombre." in respuesta.text


def test_listado_de_servicios(sesion, db_temporal):
    crear_servicio_directo(db_temporal, "DDJJ FONASA", "anual")
    pagina = sesion.get("/configuracion/servicios")
    assert pagina.status_code == 200
    assert "DDJJ FONASA" in pagina.text


# ---------- F4: contratos ----------

def test_contratar_y_finalizar_desde_la_web(sesion, db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)

    respuesta = sesion.post(
        f"/clientes/{cliente.id}/servicios/contratar",
        data={
            "servicio_id": str(servicio.id),
            "fecha_inicio": "2026-02-01",
            "honorario": "5700",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    pestaña = sesion.get(f"/clientes/{cliente.id}/servicios")
    assert "Liquidación mensual" in pestaña.text
    assert "$ 5.700" in pestaña.text

    from app.services import contratos
    contrato = contratos.listar_contratos(db_temporal, cliente.id)[0]["contrato"]
    respuesta = sesion.post(
        f"/contratos/{contrato.id}/finalizar",
        data={"fecha_fin": "2026-08-31"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    db_temporal.refresh(contrato)
    assert contrato.activo is False


def test_contratar_duplicado_muestra_literal(sesion, db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contratar(db_temporal, cliente, servicio)

    respuesta = sesion.post(
        f"/clientes/{cliente.id}/servicios/contratar",
        data={
            "servicio_id": str(servicio.id),
            "fecha_inicio": "2026-02-01",
            "honorario": "5700",
        },
    )
    assert respuesta.status_code == 422
    assert "El cliente ya tiene ese servicio contratado activo." in respuesta.text


def test_toggle_finalizados_en_ficha(sesion, db_temporal):
    from app.services import contratos

    cliente = crear_cliente_directo(db_temporal)
    unico = crear_servicio_directo(db_temporal, "Gestión ante BPS", "unico")
    contrato = contratar(db_temporal, cliente, unico, fecha=date(2026, 1, 10))
    contratos.finalizar(db_temporal, contrato.id, date(2026, 1, 27))

    sin_toggle = sesion.get(f"/clientes/{cliente.id}/servicios")
    assert "Gestión ante BPS" not in sin_toggle.text

    con_toggle = sesion.get(f"/clientes/{cliente.id}/servicios?finalizados=1")
    assert "Gestión ante BPS" in con_toggle.text
    assert "27/01/2026" in con_toggle.text
