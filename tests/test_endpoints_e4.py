"""Endpoints de la Etapa 4 (vault) — cobertura proporcional."""

from app.services import vault
from tests.utilidades import crear_cliente_directo

PASSWORD = "clave-super-secreta"


def _credencial(db):
    cliente = crear_cliente_directo(db)
    credencial = vault.crear_credencial(
        db, cliente.id, tipo="dgi", usuario="218855430017",
        password=PASSWORD, notas="nota visible en el detalle",
    )
    return cliente, credencial


def test_listado_no_envia_la_contrasena_al_navegador(sesion, db_temporal):
    cliente, _ = _credencial(db_temporal)
    pagina = sesion.get(f"/clientes/{cliente.id}/credenciales")
    assert pagina.status_code == 200
    assert "218855430017" in pagina.text  # usuario en claro
    assert PASSWORD not in pagina.text    # contraseña nunca, antes de revelar
    assert "••••••••" in pagina.text


def test_detalle_muestra_notas_pero_no_la_contrasena(sesion, db_temporal):
    cliente, credencial = _credencial(db_temporal)
    pagina = sesion.get(f"/clientes/{cliente.id}/credenciales?detalle={credencial.id}")
    assert "nota visible en el detalle" in pagina.text
    assert PASSWORD not in pagina.text


def test_revelar_y_ocultar_por_htmx(sesion, db_temporal):
    _, credencial = _credencial(db_temporal)

    revelada = sesion.get(f"/credenciales/{credencial.id}/password?mostrar=1")
    assert revelada.status_code == 200
    assert PASSWORD in revelada.text
    assert "ph-eye-slash" in revelada.text

    oculta = sesion.get(f"/credenciales/{credencial.id}/password?mostrar=0")
    assert PASSWORD not in oculta.text
    assert "ph-eye" in oculta.text


def test_crear_sin_usuario_ni_contrasena_muestra_literal(sesion, db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    respuesta = sesion.post(
        f"/clientes/{cliente.id}/credenciales/nueva",
        data={"tipo": "dgi", "usuario": "", "password": "", "notas": ""},
    )
    assert respuesta.status_code == 422
    assert "Ingresá al menos usuario o contraseña." in respuesta.text


def test_crear_desde_la_web(sesion, db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    respuesta = sesion.post(
        f"/clientes/{cliente.id}/credenciales/nueva",
        data={"tipo": "bps", "usuario": "u", "password": PASSWORD, "notas": ""},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert vault.contar_credenciales(db_temporal, cliente.id) == 1


def test_editar_no_precarga_la_contrasena(sesion, db_temporal):
    _, credencial = _credencial(db_temporal)
    pagina = sesion.get(f"/credenciales/{credencial.id}/editar")
    assert pagina.status_code == 200
    assert PASSWORD not in pagina.text
    assert "Dejá vacío para mantener la actual" in pagina.text


def test_eliminar_pide_confirmacion_con_literal(sesion, db_temporal):
    cliente, credencial = _credencial(db_temporal)
    confirmacion = sesion.get(f"/credenciales/{credencial.id}/eliminar")
    assert (
        "¿Confirmás que querés eliminar esta credencial? "
        "Esta acción no se puede deshacer." in confirmacion.text
    )
    respuesta = sesion.post(f"/credenciales/{credencial.id}/eliminar",
                            follow_redirects=False)
    assert respuesta.status_code == 303
    assert vault.contar_credenciales(db_temporal, cliente.id) == 0
