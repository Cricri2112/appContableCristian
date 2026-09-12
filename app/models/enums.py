"""Enums del dominio, según Chat 2 + cambios del Chat 3 y enmiendas A2/A4.

SQLite no valida enums de forma nativa: la validación real vive en la capa
de aplicación (servicios + Pydantic), según el requisito transversal 3.
"""

import enum


class Regimen(str, enum.Enum):
    """Régimen tributario del cliente (enmienda A4: se agrega pequena_empresa)."""

    unipersonal_prof = "unipersonal_prof"
    unipersonal_no_prof = "unipersonal_no_prof"
    monotributo = "monotributo"
    pequena_empresa = "pequena_empresa"
    regimen_general = "regimen_general"
    persona_fisica = "persona_fisica"


class RegimenAplicable(str, enum.Enum):
    """Mismo enum que Regimen más el valor `todos`.

    Lo usan `tarea_templates` y `vencimientos_calendario`.
    """

    unipersonal_prof = "unipersonal_prof"
    unipersonal_no_prof = "unipersonal_no_prof"
    monotributo = "monotributo"
    pequena_empresa = "pequena_empresa"
    regimen_general = "regimen_general"
    persona_fisica = "persona_fisica"
    todos = "todos"


class FrecuenciaServicio(str, enum.Enum):
    mensual = "mensual"
    anual = "anual"
    unico = "unico"


class FormaPago(str, enum.Enum):
    efectivo = "efectivo"
    transferencia = "transferencia"
    otro = "otro"


class TipoComprobante(str, enum.Enum):
    e_ticket = "e_ticket"
    no_gravado = "no_gravado"
    sin_comprobante = "sin_comprobante"


class TipoCredencial(str, enum.Enum):
    """Chat 3, cambio 2: `pin` se reemplaza por `clave_dgi`."""

    dgi = "dgi"
    bps = "bps"
    facturador = "facturador"
    clave_dgi = "clave_dgi"
    otro = "otro"


class EstadoTarea(str, enum.Enum):
    pendiente = "pendiente"
    en_proceso = "en_proceso"
    completada = "completada"
    cancelada = "cancelada"


class TipoRecordatorio(str, enum.Enum):
    tarea_pendiente = "tarea_pendiente"
    vencimiento_proximo = "vencimiento_proximo"
    cobro_pendiente = "cobro_pendiente"


class EstadoRecordatorio(str, enum.Enum):
    """Chat 3, cambio 5: se agrega el valor `cerrado`."""

    pendiente = "pendiente"
    enviado = "enviado"
    silenciado = "silenciado"
    cerrado = "cerrado"


class Organismo(str, enum.Enum):
    dgi = "dgi"
    bps = "bps"
    otro = "otro"


class TipoMovimientoPropio(str, enum.Enum):
    ingreso = "ingreso"
    gasto = "gasto"


class CategoriaMovimientoPropio(str, enum.Enum):
    cjppu = "cjppu"
    aportes_bps = "aportes_bps"
    gasto_operativo = "gasto_operativo"
    otro = "otro"


class AccionAuditoria(str, enum.Enum):
    """Enmienda A2: se agrega `login_fallido`."""

    creacion = "creacion"
    edicion = "edicion"
    eliminacion = "eliminacion"
    login_fallido = "login_fallido"


class ProcesoScheduler(str, enum.Enum):
    diario = "diario"
    mensual = "mensual"
