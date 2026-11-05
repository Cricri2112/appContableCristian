"""F2 — Vault de credenciales: cifrado, validaciones, auditoría [cifrado]
y comportamiento sin clave / con clave equivocada (criterios de la Etapa 4)."""

from datetime import date

import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.models import Auditoria, Credencial
from app.services import cifrado, vault
from app.services.errores import ErrorValidacion
from tests.utilidades import crear_cliente_directo

USUARIO = "218855430017"
PASSWORD = "elsol1979-secreta"
NOTAS = "la contraseña es el nombre más el año"


def _crear(db, cliente, **cambios):
    datos = {"tipo": "bps", "usuario": USUARIO, "password": PASSWORD, "notas": NOTAS}
    datos.update(cambios)
    return vault.crear_credencial(db, cliente.id, **datos)


def _fila_cruda(db, credencial_id):
    """Lee la fila directo de la base, sin pasar por el servicio."""
    db.expire_all()
    return db.get(Credencial, credencial_id)


# ---------- Cifrado ----------

def test_cifrar_y_descifrar_ida_y_vuelta():
    cifrado_texto = cifrado.cifrar("hola")
    assert cifrado_texto != "hola"
    assert cifrado.descifrar(cifrado_texto) == "hola"
    assert cifrado.cifrar(None) is None


def test_en_la_base_los_tres_campos_son_ilegibles(db_temporal):
    """Criterio 1: consulta directa → texto cifrado ilegible."""
    cliente = crear_cliente_directo(db_temporal)
    credencial = _crear(db_temporal, cliente)

    fila = _fila_cruda(db_temporal, credencial.id)
    for campo, claro in (("usuario", USUARIO), ("password", PASSWORD), ("notas", NOTAS)):
        valor = getattr(fila, campo)
        assert valor is not None
        assert claro not in valor
        assert cifrado.descifrar(valor) == claro


# ---------- Validaciones ----------

def test_exige_usuario_o_contrasena(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    with pytest.raises(ErrorValidacion) as error:
        _crear(db_temporal, cliente, usuario="  ", password="")
    assert error.value.errores["general"] == "Ingresá al menos usuario o contraseña."


def test_puede_haber_dos_del_mismo_tipo(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    _crear(db_temporal, cliente, tipo="dgi")
    _crear(db_temporal, cliente, tipo="dgi")
    assert vault.contar_credenciales(db_temporal, cliente.id) == 2


def test_tipo_invalido(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    with pytest.raises(ErrorValidacion) as error:
        _crear(db_temporal, cliente, tipo="pin")  # reemplazado por clave_dgi
    assert "tipo" in error.value.errores


# ---------- Listado ----------

def test_listado_orden_y_usuario_en_claro(db_temporal, monkeypatch):
    cliente = crear_cliente_directo(db_temporal)
    monkeypatch.setattr(vault, "hoy", lambda: date(2026, 1, 1))
    _crear(db_temporal, cliente, tipo="facturador", usuario="factu")
    vieja_dgi = _crear(db_temporal, cliente, tipo="dgi", usuario="dgi-vieja")
    monkeypatch.setattr(vault, "hoy", lambda: date(2026, 6, 1))
    nueva_dgi = _crear(db_temporal, cliente, tipo="dgi", usuario="dgi-nueva")

    lista = vault.listar_credenciales(db_temporal, cliente.id)
    # Orden del enum (dgi antes que facturador), y dentro del tipo la más nueva primero.
    assert [item.credencial.id for item in lista[:2]] == [nueva_dgi.id, vieja_dgi.id]
    assert lista[2].credencial.tipo.value == "facturador"
    assert lista[0].usuario == "dgi-nueva"


# ---------- Edición ----------

def test_editar_recifra_y_actualiza_fecha(db_temporal, monkeypatch):
    cliente = crear_cliente_directo(db_temporal)
    monkeypatch.setattr(vault, "hoy", lambda: date(2026, 1, 1))
    credencial = _crear(db_temporal, cliente)
    usuario_cifrado_antes = _fila_cruda(db_temporal, credencial.id).usuario

    monkeypatch.setattr(vault, "hoy", lambda: date(2026, 9, 1))
    vault.editar_credencial(
        db_temporal, credencial.id, tipo="bps", usuario=USUARIO,
        password_nueva="otra-clave", notas=NOTAS,
    )

    fila = _fila_cruda(db_temporal, credencial.id)
    assert fila.ultima_actualizacion == date(2026, 9, 1)
    assert fila.usuario != usuario_cifrado_antes  # recifrado (Fernet usa IV aleatorio)
    assert vault.revelar_password(db_temporal, credencial.id) == "otra-clave"


def test_editar_con_password_vacia_mantiene_la_actual(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    credencial = _crear(db_temporal, cliente)
    vault.editar_credencial(
        db_temporal, credencial.id, tipo="dgi", usuario=USUARIO,
        password_nueva="", notas=None,
    )
    assert vault.revelar_password(db_temporal, credencial.id) == PASSWORD
    assert _fila_cruda(db_temporal, credencial.id).notas is None


# ---------- Auditoría: [cifrado], nunca el valor ----------

def _auditorias(db, credencial_id):
    return (
        db.query(Auditoria)
        .filter(Auditoria.tabla == "credenciales", Auditoria.registro_id == credencial_id)
        .all()
    )


def test_auditoria_nunca_guarda_valores_ni_cifrados_ni_en_claro(db_temporal):
    """Excepción del listener genérico: test obligatorio de la Etapa 4."""
    cliente = crear_cliente_directo(db_temporal)
    credencial = _crear(db_temporal, cliente)
    id_credencial = credencial.id
    cifrados = [getattr(_fila_cruda(db_temporal, id_credencial), c)
                for c in ("usuario", "password", "notas")]

    vault.editar_credencial(
        db_temporal, id_credencial, tipo="bps", usuario=USUARIO,
        password_nueva="nueva-secreta", notas=NOTAS,
    )
    vault.eliminar_credencial(db_temporal, id_credencial)

    registros = _auditorias(db_temporal, id_credencial)
    assert [r.accion.value for r in registros] == ["creacion", "edicion", "eliminacion"]

    textos_prohibidos = [USUARIO, PASSWORD, NOTAS, "nueva-secreta", *cifrados]
    for registro in registros:
        for contenido in (registro.datos_antes, registro.datos_despues):
            if contenido is None:
                continue
            assert '"password": "[cifrado]"' in contenido
            assert '"usuario": "[cifrado]"' in contenido
            for prohibido in textos_prohibidos:
                assert prohibido not in contenido


def test_eliminar_es_fisico(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    credencial = _crear(db_temporal, cliente)
    id_credencial = credencial.id
    vault.eliminar_credencial(db_temporal, id_credencial)
    assert _fila_cruda(db_temporal, id_credencial) is None


# ---------- Sin clave / clave equivocada ----------

def test_sin_fernet_key_la_app_no_arranca(monkeypatch):
    """Criterio 5: arrancar sin FERNET_KEY → falla con mensaje claro."""
    monkeypatch.setattr(settings, "fernet_key", None)
    with pytest.raises(cifrado.ClaveNoConfigurada) as error:
        cifrado.verificar_clave()
    assert "FERNET_KEY" in str(error.value)

    monkeypatch.setattr(settings, "fernet_key", "no-es-una-clave")
    with pytest.raises(cifrado.ClaveNoConfigurada):
        cifrado.verificar_clave()


def test_con_otra_clave_los_datos_son_indescifrables(db_temporal, monkeypatch):
    """Criterio 6: sin la clave correcta no hay datos, pero la vista no se rompe."""
    cliente = crear_cliente_directo(db_temporal)
    credencial = _crear(db_temporal, cliente)

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())

    with pytest.raises(cifrado.DatoIndescifrable):
        cifrado.descifrar(_fila_cruda(db_temporal, credencial.id).password)
    lista = vault.listar_credenciales(db_temporal, cliente.id)
    assert lista[0].usuario == vault.INDESCIFRABLE
    assert lista[0].usuario_ok is False
    assert vault.revelar_password(db_temporal, credencial.id) == vault.INDESCIFRABLE
