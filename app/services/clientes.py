"""F1 — Ficha de clientes unificada (Chat 3).

Listado con derivación mensual/eventual, alta con primer registro de
régimen, edición con flujo de cambio de régimen, desactivar. Los mensajes
de validación son los literales exactos del Chat 3.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Cliente, ClienteRegimenHistorial, Servicio, ServicioContratado
from app.models.base import ahora_montevideo
from app.models.enums import Regimen
from app.schemas.clientes import FormularioCliente
from app.services.errores import ErrorValidacion


def hoy() -> date:
    return ahora_montevideo().date()


def ids_clientes_mensuales(db: Session) -> set[int]:
    """Un cliente es mensual si tiene al menos un contrato activo de un
    servicio con frecuencia mensual. Derivado, nunca almacenado (F1)."""
    filas = (
        db.query(ServicioContratado.cliente_id)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(
            ServicioContratado.activo.is_(True),
            Servicio.frecuencia == "mensual",
        )
        .distinct()
        .all()
    )
    return {cliente_id for (cliente_id,) in filas}


def es_mensual(db: Session, cliente_id: int) -> bool:
    return cliente_id in ids_clientes_mensuales(db)


def listar_clientes(db: Session, incluir_inactivos: bool = False) -> dict:
    """Dos secciones: mensuales y eventuales, con el orden del Chat 3.

    - Mensuales: por régimen (orden alfabético del valor del enum), luego id.
    - Eventuales: por id ascendente.
    """
    consulta = db.query(Cliente)
    if not incluir_inactivos:
        consulta = consulta.filter(Cliente.activo.is_(True))
    clientes = consulta.all()

    mensuales_ids = ids_clientes_mensuales(db)
    mensuales = [c for c in clientes if c.id in mensuales_ids]
    eventuales = [c for c in clientes if c.id not in mensuales_ids]

    mensuales.sort(key=lambda c: (c.regimen.value, c.id))
    eventuales.sort(key=lambda c: c.id)
    return {"mensuales": mensuales, "eventuales": eventuales}


def obtener_cliente(db: Session, cliente_id: int) -> Cliente | None:
    return db.get(Cliente, cliente_id)


def historial_regimenes(db: Session, cliente_id: int) -> list[ClienteRegimenHistorial]:
    """Ordenado por fecha_desde descendente (solo lectura en la ficha)."""
    return (
        db.query(ClienteRegimenHistorial)
        .filter(ClienteRegimenHistorial.cliente_id == cliente_id)
        .order_by(ClienteRegimenHistorial.fecha_desde.desc())
        .all()
    )


def _regimen_vigente(db: Session, cliente_id: int) -> ClienteRegimenHistorial | None:
    return (
        db.query(ClienteRegimenHistorial)
        .filter(
            ClienteRegimenHistorial.cliente_id == cliente_id,
            ClienteRegimenHistorial.fecha_hasta.is_(None),
        )
        .first()
    )


def _validar_datos(
    db: Session, datos: FormularioCliente, excluir_id: int | None
) -> dict:
    """Validaciones de F1. Los mensajes con unicidad y RUT son literales."""
    errores = {}

    if not datos.nombre:
        errores["nombre"] = "El nombre no puede estar vacío."

    if datos.regimen not in [r.value for r in Regimen]:
        errores["regimen"] = "Elegí un régimen."

    if datos.rut is not None:
        if not (len(datos.rut) == 12 and datos.rut.isdigit()):
            errores["rut"] = "El RUT debe tener 12 dígitos numéricos."
        else:
            consulta = db.query(Cliente).filter(Cliente.rut == datos.rut)
            if excluir_id is not None:
                consulta = consulta.filter(Cliente.id != excluir_id)
            # Unicidad contra TODOS los clientes, incluidos inactivos.
            if consulta.first() is not None:
                errores["rut"] = "Ya existe un cliente con ese RUT."

    if datos.ci is not None:
        consulta = db.query(Cliente).filter(Cliente.ci == datos.ci)
        if excluir_id is not None:
            consulta = consulta.filter(Cliente.id != excluir_id)
        if consulta.first() is not None:
            errores["ci"] = "Ya existe un cliente con esa CI."

    return errores


def crear_cliente(db: Session, datos: FormularioCliente) -> Cliente:
    errores = _validar_datos(db, datos, excluir_id=None)

    if datos.fecha_inicio is None:
        errores["fecha_inicio"] = "Ingresá la fecha de inicio."
    elif datos.fecha_inicio > hoy():
        errores["fecha_inicio"] = "La fecha de inicio no puede ser futura."

    if errores:
        raise ErrorValidacion(errores)

    cliente = Cliente(
        nombre=datos.nombre,
        regimen=datos.regimen,
        rut=datos.rut,
        ci=datos.ci,
        fecha_nacimiento=datos.fecha_nacimiento,
        email=datos.email,
        telefono=datos.telefono,
        fecha_inicio=datos.fecha_inicio,
        activo=True,
        notas=datos.notas,
    )
    db.add(cliente)
    db.flush()  # asigna el id sin cerrar la transacción

    # Primer registro del historial: fecha_desde = fecha_inicio, vigente.
    db.add(
        ClienteRegimenHistorial(
            cliente_id=cliente.id,
            regimen=datos.regimen,
            fecha_desde=datos.fecha_inicio,
            fecha_hasta=None,
        )
    )
    db.commit()
    return cliente


def editar_cliente(
    db: Session,
    cliente_id: int,
    datos: FormularioCliente,
    fecha_cambio_regimen: date | None,
) -> Cliente:
    """Edita todos los campos salvo fecha_inicio.

    Si el régimen cambia, exige la fecha de cambio y aplica el flujo del
    Chat 3: cierra el registro vigente el día anterior y abre uno nuevo.
    """
    cliente = db.get(Cliente, cliente_id)
    errores = _validar_datos(db, datos, excluir_id=cliente_id)

    cambia_regimen = (
        "regimen" not in errores and datos.regimen != cliente.regimen.value
    )
    vigente = _regimen_vigente(db, cliente_id)

    if cambia_regimen:
        if fecha_cambio_regimen is None:
            errores["fecha_cambio_regimen"] = "Ingresá la fecha de cambio de régimen."
        elif fecha_cambio_regimen > hoy():
            errores["fecha_cambio_regimen"] = (
                "La fecha de cambio no puede ser futura."
            )
        elif vigente is not None and fecha_cambio_regimen < vigente.fecha_desde:
            errores["fecha_cambio_regimen"] = (
                "La fecha de cambio no puede ser anterior al inicio del régimen vigente."
            )

    if errores:
        raise ErrorValidacion(errores)

    cliente.nombre = datos.nombre
    cliente.rut = datos.rut
    cliente.ci = datos.ci
    cliente.fecha_nacimiento = datos.fecha_nacimiento
    cliente.email = datos.email
    cliente.telefono = datos.telefono
    cliente.notas = datos.notas

    if cambia_regimen:
        # Se cierra el vigente el día anterior y se abre el nuevo.
        if vigente is not None:
            vigente.fecha_hasta = fecha_cambio_regimen - timedelta(days=1)
        db.add(
            ClienteRegimenHistorial(
                cliente_id=cliente.id,
                regimen=datos.regimen,
                fecha_desde=fecha_cambio_regimen,
                fecha_hasta=None,
            )
        )
        cliente.regimen = datos.regimen

    db.commit()
    return cliente


def cambiar_activo(db: Session, cliente_id: int) -> Cliente:
    """Desactivar/reactivar: un clic, sin confirmación, sin tocar datos."""
    cliente = db.get(Cliente, cliente_id)
    cliente.activo = not cliente.activo
    db.commit()
    return cliente
