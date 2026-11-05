"""F8 — Vencimientos: regla de aplicabilidad, día inexistente, vistas de
15/30 días, fecha límite y semáforo (Etapa 5, corte 5b)."""

from datetime import date

import pytest

from app.models import VencimientoCalendario
from app.services import fechas, vencimientos
from app.services.errores import ErrorValidacion
from tests.utilidades import crear_cliente_directo

HOY_FIJO = date(2026, 4, 10)


@pytest.fixture(autouse=True)
def fijar_hoy(monkeypatch):
    monkeypatch.setattr(fechas, "hoy", lambda: HOY_FIJO)


def _v(db, descripcion="Aportes", regimen="todos", organismo="bps", dia=15,
       mes=None, anio=None, activo=True):
    v = VencimientoCalendario(descripcion=descripcion, regimen=regimen, organismo=organismo,
                              dia_vencimiento=dia, mes=mes, anio=anio, activo=activo)
    db.add(v)
    db.commit()
    return v


# ---------- Reglas ----------

def test_dia_inexistente_toma_el_ultimo_dia_real(db_temporal):
    v = _v(db_temporal, dia=31)
    assert vencimientos.fecha_en_mes(v, date(2026, 4, 1)) == date(2026, 4, 30)
    assert vencimientos.fecha_en_mes(v, date(2026, 2, 1)) == date(2026, 2, 28)
    assert vencimientos.fecha_en_mes(v, date(2028, 2, 1)) == date(2028, 2, 29)
    assert vencimientos.fecha_en_mes(v, date(2026, 5, 1)) == date(2026, 5, 31)


def test_aplicabilidad_por_mes_anio_y_activo(db_temporal):
    junio = _v(db_temporal, mes=6)
    solo_2026 = _v(db_temporal, anio=2026)
    inactivo = _v(db_temporal, activo=False)
    assert vencimientos.fecha_en_mes(junio, date(2026, 5, 1)) is None
    assert vencimientos.fecha_en_mes(junio, date(2026, 6, 1)) == date(2026, 6, 15)
    assert vencimientos.fecha_en_mes(solo_2026, date(2027, 1, 1)) is None
    assert vencimientos.fecha_en_mes(inactivo, date(2026, 4, 1)) is None


def test_clientes_alcanzados_por_regimen(db_temporal):
    crear_cliente_directo(db_temporal, nombre="Mono", regimen="monotributo")
    crear_cliente_directo(db_temporal, nombre="General", regimen="regimen_general")
    crear_cliente_directo(db_temporal, nombre="Dormido", regimen="monotributo", activo=False)
    _v(db_temporal, "Solo monotributo", regimen="monotributo")
    _v(db_temporal, "Para todos", regimen="todos", dia=20)

    del_mes = vencimientos.ocurrencias_del_mes(db_temporal, date(2026, 4, 1))
    por_nombre = {o.descripcion: [c.nombre for c in o.clientes] for o in del_mes}
    assert por_nombre["Solo monotributo"] == ["Mono"]  # el inactivo no cuenta
    assert sorted(por_nombre["Para todos"]) == ["General", "Mono"]


def test_proximos_15_dias_cruza_de_mes(db_temporal):
    _v(db_temporal, "Abril", dia=20)        # 20/04 y 20/05
    _v(db_temporal, "Mayo", dia=2, mes=5)   # 02/05
    proximos = vencimientos.proximos_dias(db_temporal, 15)  # 10/04 → 25/04
    assert [(o.descripcion, o.fecha) for o in proximos] == [("Abril", date(2026, 4, 20))]
    proximos_30 = vencimientos.proximos_dias(db_temporal, 30)  # hasta 10/05
    assert [o.descripcion for o in proximos_30] == ["Abril", "Mayo"]


def test_proximos_del_cliente_30_dias(db_temporal):
    cliente = crear_cliente_directo(db_temporal, regimen="monotributo")
    _v(db_temporal, "Monotributo", regimen="monotributo", dia=18)
    _v(db_temporal, "Solo general", regimen="regimen_general", dia=19)
    # Hoy 10/04: entra el 18/04; el 18/05 queda fuera de los 30 días.
    proximos = vencimientos.proximos_del_cliente(db_temporal, cliente)
    assert [(o.descripcion, o.fecha) for o in proximos] == [("Monotributo", date(2026, 4, 18))]


# ---------- Fecha límite y semáforo ----------

def _ocurrencias(db, regimen, periodo=date(2026, 4, 1)):
    return vencimientos.vencimientos_del_cliente_en_periodo(db, regimen, periodo)


def test_fecha_limite_es_el_proximo_que_no_paso(db_temporal):
    _v(db_temporal, "BPS", organismo="bps", dia=5)    # ya pasó (hoy 10/04)
    _v(db_temporal, "DGI", organismo="dgi", dia=24)
    limite = vencimientos.fecha_limite(_ocurrencias(db_temporal, "monotributo"))
    assert limite.fecha == date(2026, 4, 24)
    assert limite.organismo == "DGI"
    assert limite.dias_restantes == 14


def test_fecha_limite_vencida_si_todos_pasaron(db_temporal):
    _v(db_temporal, "BPS", dia=5)
    limite = vencimientos.fecha_limite(_ocurrencias(db_temporal, "monotributo"))
    assert limite.dias_restantes == -5
    assert limite.texto_dias == "vencida"


def test_sin_vencimientos_no_hay_fecha_limite_ni_semaforo(db_temporal):
    _v(db_temporal, "Solo general", regimen="regimen_general")
    limite = vencimientos.fecha_limite(_ocurrencias(db_temporal, "monotributo"))
    assert limite is None
    assert vencimientos.semaforo(limite, tareas_abiertas=3) is None


@pytest.mark.parametrize("dias, abiertas, esperado", [
    (14, 0, "verde"),     # todo completado o cancelado
    (14, 2, "amarillo"),  # más de 5 días
    (6, 2, "amarillo"),
    (5, 2, "rojo"),       # 5 días o menos
    (0, 1, "rojo"),
    (-3, 1, "rojo"),      # vencido
    (-3, 0, "verde"),
])
def test_semaforo(dias, abiertas, esperado):
    limite = vencimientos.FechaLimite(date(2026, 4, 20), "DGI", dias)
    assert vencimientos.semaforo(limite, abiertas) == esperado


# ---------- Administración ----------

def test_validaciones_de_vencimiento(db_temporal):
    with pytest.raises(ErrorValidacion) as error:
        vencimientos.crear_vencimiento(db_temporal, {
            "descripcion": " ", "organismo": "dgi", "regimen": "todos",
            "mes": "", "dia_vencimiento": "32", "anio": "",
        })
    assert set(error.value.errores) == {"descripcion", "dia_vencimiento"}

    v = vencimientos.crear_vencimiento(db_temporal, {
        "descripcion": "IVA mínimo", "organismo": "dgi", "regimen": "pequena_empresa",
        "mes": "", "dia_vencimiento": "22", "anio": "",
    })
    assert v.mes is None and v.anio is None  # todos los meses, recurrente


def test_no_se_valida_duplicado_exacto(db_temporal):
    datos = {"descripcion": "Aportes", "organismo": "bps", "regimen": "todos",
             "mes": "", "dia_vencimiento": "15", "anio": ""}
    vencimientos.crear_vencimiento(db_temporal, datos)
    vencimientos.crear_vencimiento(db_temporal, datos)
    assert db_temporal.query(VencimientoCalendario).count() == 2


def test_filtro_anio_actual_incluye_recurrentes(db_temporal):
    _v(db_temporal, "Recurrente")
    _v(db_temporal, "De 2026", anio=2026)
    _v(db_temporal, "De 2025", anio=2025)
    nombres = [v.descripcion for v in vencimientos.listar_vencimientos(db_temporal, "actual")]
    assert sorted(nombres) == ["De 2026", "Recurrente"]
    assert len(vencimientos.listar_vencimientos(db_temporal, "todos")) == 3


def test_semanas_del_mes_empiezan_en_lunes():
    semanas = vencimientos.semanas_del_mes(date(2026, 9, 1))  # 1/9/2026 es martes
    assert semanas[0][0] is None
    assert semanas[0][1] == date(2026, 9, 1)
    assert all(len(s) == 7 for s in semanas)
