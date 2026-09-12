"""Login: correcto, incorrecto, bloqueo y protección de rutas
(criterios de terminado 2, 3 y 4)."""

from datetime import timedelta

from app.models import Auditoria, UsuarioLogin
from app.models.base import ahora_montevideo


def _login(cliente_web, usuario, password):
    return cliente_web.post(
        "/login",
        data={"usuario": usuario, "password": password},
        follow_redirects=False,
    )


def _intentos_fallidos_auditados(db):
    return (
        db.query(Auditoria)
        .filter(Auditoria.accion == "login_fallido")
        .count()
    )


def test_login_correcto_redirige_y_deja_sesion(cliente_web, usuario_de_prueba):
    respuesta = _login(cliente_web, "contador", "clave-correcta")
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/"
    assert "sesion" in respuesta.cookies

    # Con la sesión activa, la página base responde con el cascarón
    pagina = cliente_web.get("/")
    assert pagina.status_code == 200
    assert "Cerrar sesión" in pagina.text


def test_login_incorrecto_muestra_error_y_se_audita(
    cliente_web, usuario_de_prueba, db_temporal
):
    respuesta = _login(cliente_web, "contador", "clave-mal")
    assert respuesta.status_code == 401
    assert "Usuario o contraseña incorrectos." in respuesta.text
    assert _intentos_fallidos_auditados(db_temporal) == 1

    db_temporal.refresh(usuario_de_prueba)
    assert usuario_de_prueba.intentos_fallidos == 1


def test_usuario_equivocado_tambien_cuenta_como_intento_fallido(
    cliente_web, usuario_de_prueba, db_temporal
):
    respuesta = _login(cliente_web, "otro-usuario", "clave-correcta")
    assert respuesta.status_code == 401
    db_temporal.refresh(usuario_de_prueba)
    assert usuario_de_prueba.intentos_fallidos == 1


def test_cinco_intentos_fallidos_bloquean_15_minutos(
    cliente_web, usuario_de_prueba, db_temporal
):
    for _ in range(5):
        _login(cliente_web, "contador", "clave-mal")

    db_temporal.refresh(usuario_de_prueba)
    assert usuario_de_prueba.intentos_fallidos == 5
    assert usuario_de_prueba.bloqueado_hasta is not None
    duracion = usuario_de_prueba.bloqueado_hasta - ahora_montevideo()
    assert timedelta(minutes=14) < duracion <= timedelta(minutes=15)

    # Los 5 intentos quedaron registrados en auditoría (enmienda A2)
    assert _intentos_fallidos_auditados(db_temporal) == 5

    # Bloqueado: ni siquiera la contraseña correcta entra
    respuesta = _login(cliente_web, "contador", "clave-correcta")
    assert respuesta.status_code == 401
    assert "bloqueado" in respuesta.text.lower()


def test_pasado_el_bloqueo_se_puede_entrar_de_nuevo(
    cliente_web, usuario_de_prueba, db_temporal
):
    for _ in range(5):
        _login(cliente_web, "contador", "clave-mal")

    # Se simula que el bloqueo ya venció
    db_temporal.refresh(usuario_de_prueba)
    usuario_de_prueba.bloqueado_hasta = ahora_montevideo() - timedelta(minutes=1)
    db_temporal.commit()

    respuesta = _login(cliente_web, "contador", "clave-correcta")
    assert respuesta.status_code == 303

    db_temporal.refresh(usuario_de_prueba)
    assert usuario_de_prueba.intentos_fallidos == 0
    assert usuario_de_prueba.bloqueado_hasta is None


def test_ruta_sin_sesion_redirige_al_login(cliente_web, usuario_de_prueba):
    respuesta = cliente_web.get("/", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/login"


def test_cookie_es_secure_y_httponly(cliente_web, usuario_de_prueba):
    respuesta = _login(cliente_web, "contador", "clave-correcta")
    set_cookie = respuesta.headers["set-cookie"].lower()
    assert "secure" in set_cookie
    assert "httponly" in set_cookie


def test_logout_cierra_la_sesion(cliente_web, usuario_de_prueba):
    _login(cliente_web, "contador", "clave-correcta")
    assert cliente_web.get("/").status_code == 200

    cliente_web.post("/logout", follow_redirects=False)
    respuesta = cliente_web.get("/", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/login"


def test_login_sin_usuario_creado_avisa(cliente_web, db_temporal):
    assert db_temporal.query(UsuarioLogin).count() == 0
    respuesta = _login(cliente_web, "contador", "clave-correcta")
    assert respuesta.status_code == 401
    assert "No hay usuario configurado" in respuesta.text
