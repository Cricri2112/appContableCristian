"""Modelos SQLAlchemy — las 16 tablas de la migración inicial (Chat 5 + adenda).

Importar este paquete deja registrados todos los modelos y activa la
auditoría automática, de modo que también funcione al usar la base "desde
consola" (criterio de terminado 5 de la Etapa 0).
"""

from app.models.base import Base
from app.models.clientes import Cliente, ClienteRegimenHistorial
from app.models.servicios import HonorarioHistorial, Servicio, ServicioContratado
from app.models.cobros import Cobro, Descuento
from app.models.credenciales import Credencial
from app.models.tareas import Tarea, TareaTemplate
from app.models.recordatorios import Recordatorio
from app.models.vencimientos import VencimientoCalendario
from app.models.gastos import GastoIngresoPropio
from app.models.sistema import Auditoria, SchedulerEjecucion, UsuarioLogin

# Se importa al final para evitar un ciclo: el servicio necesita que todos
# los modelos ya estén definidos para registrar sus listeners.
from app.services.auditoria import configurar_auditoria

configurar_auditoria()

__all__ = [
    "Base",
    "Cliente",
    "ClienteRegimenHistorial",
    "Servicio",
    "ServicioContratado",
    "HonorarioHistorial",
    "Cobro",
    "Descuento",
    "Credencial",
    "TareaTemplate",
    "Tarea",
    "Recordatorio",
    "VencimientoCalendario",
    "GastoIngresoPropio",
    "Auditoria",
    "SchedulerEjecucion",
    "UsuarioLogin",
]
