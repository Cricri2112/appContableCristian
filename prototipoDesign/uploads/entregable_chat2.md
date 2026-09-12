# Estudio Contable — Funcionalidades y Modelo de Datos
*Entregable Chat 2 — base para Chat 3: Requerimientos granulares*

---

## 1. Funcionalidades priorizadas

### MVP

| ID | Funcionalidad | Qué resuelve |
|---|---|---|
| F1 | Ficha de clientes unificada (mensuales + eventuales) | Base de todo el sistema |
| F2 | Vault de credenciales cifrado | Riesgo de seguridad crítico |
| F3 | Catálogo de servicios | Define qué se vende |
| F4 | Registro de servicios contratados por cliente | Qué tiene cada cliente |
| F5 | Control de cobros unificado con descuentos como concepto propio | Visión real de ingresos |
| F6 | Historial de honorarios por cliente | Trazabilidad de cambios de precio |
| F7 | Checklist de tareas por régimen (mensual y anual) | Elimina dependencia de memoria |
| F8 | Calendario de vencimientos por régimen | Elimina consulta manual DGI/BPS |
| F9 | Proyección de ingresos + registro de gastos/ingresos propios | Visión financiera del estudio |
| F10 | Recordatorios persistentes hasta completar tarea (solo para el contador) | Seguimiento hasta cierre |

### Post-MVP

| ID | Funcionalidad | Por qué espera |
|---|---|---|
| F11 | Recordatorios hacia clientes (avisos de vencimientos, solicitud de info) | Requiere integración WhatsApp/email |
| F12 | Generación automática de boletos BPS cuota fija | Requiere integración externa |
| F13 | Registro de comunicaciones por cliente | No es bloqueante |
| F14 | Base de conocimiento contable consultable | Necesita volumen de uso |

### Futuro

| ID | Funcionalidad |
|---|---|
| F15 | Web pública para captación de clientes |
| F16 | Portal del cliente con acceso limitado |

---

## 2. Decisiones de diseño clave

### Modelo de servicios
- No existe distinción "mensual vs eventual" como tipo de cliente: todos los clientes tienen una ficha en `clientes`.
- Lo que varía es qué servicios contratan: hay servicios con frecuencia mensual, anual o única.
- El **régimen del cliente** (no el nombre del servicio) determina las tareas a ejecutar.
- Relación: `servicio + régimen → tarea_template → tareas generadas`.

### Honorarios
- El honorario no se guarda como un valor único en el cliente.
- Se registra en `honorarios_historial` como log append-only: cada cambio de precio agrega una fila.
- El honorario vigente es el registro con `fecha_hasta = null`.

### Descuentos
- Son una entidad propia, no un cobro con importe negativo.
- El saldo de un cliente = honorario esperado − descuentos − cobros recibidos.

### Período
- Los períodos mensuales se almacenan como la fecha del primer día del mes.
- Ejemplo: mayo 2025 → `2025-05-01`.

### Credenciales
- Todos los campos sensibles (usuario, contraseña, notas) se almacenan cifrados en reposo.
- El cifrado es responsabilidad de la capa de aplicación antes de escribir en la base de datos.

### Tablas sin relaciones FK
- `vencimientos_calendario` y `gastos_ingresos_propios` no tienen claves foráneas.
- Son tablas de referencia/registro independientes.

### Recordatorios persistentes
- `repetir_hasta_completar = true` + `intervalo_repeticion_horas` implementan el patrón de recordatorio insistente.
- Se silencia solo cuando la tarea asociada se marca como completada.

---

## 3. Modelo de datos — 12 entidades

### `clientes`
Todos los clientes, mensuales y eventuales, en una sola tabla.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| nombre | TEXT | NOT NULL | |
| regimen | ENUM | NOT NULL | `unipersonal_prof`, `unipersonal_no_prof`, `monotributo`, `regimen_general`, `persona_fisica` |
| rut | TEXT | nullable | Eventuales persona física pueden no tener |
| ci | TEXT | nullable | |
| fecha_nacimiento | DATE | nullable | Requerido para BPS |
| email | TEXT | nullable | |
| telefono | TEXT | nullable | |
| fecha_inicio | DATE | NOT NULL | Fecha de inicio de la relación comercial |
| activo | BOOLEAN | NOT NULL, default true | |
| notas | TEXT | nullable | |

---

### `servicios`
Catálogo de lo que se vende. Pocos registros, estables en el tiempo.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| nombre | TEXT | NOT NULL | ej: "Liquidación mensual", "DDJJ IVA anual", "Certificado de ingresos" |
| frecuencia | ENUM | NOT NULL | `mensual`, `anual`, `unico` |
| activo | BOOLEAN | NOT NULL, default true | |

Ejemplos de registros iniciales:
- "Liquidación mensual" — mensual
- "DDJJ IVA anual" — anual
- "DDJJ IRPF anual" — anual
- "DDJJ FONASA" — anual
- "Declaración IRPF persona física" — anual
- "Certificado de ingresos" — unico
- "Gestión ante DGI" — unico
- "Gestión ante BPS" — unico

---

### `servicios_contratados`
Tabla central que vincula cliente con servicio. Un cliente puede tener múltiples servicios contratados.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| cliente_id | INT | FK → clientes, NOT NULL | |
| servicio_id | INT | FK → servicios, NOT NULL | |
| fecha_inicio | DATE | NOT NULL | |
| fecha_fin | DATE | nullable | null = vigente |
| activo | BOOLEAN | NOT NULL, default true | |

---

### `honorarios_historial`
Log append-only de cambios de honorario por servicio contratado.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| servicio_contratado_id | INT | FK → servicios_contratados, NOT NULL | |
| honorario | DECIMAL(10,2) | NOT NULL | |
| fecha_desde | DATE | NOT NULL | |
| fecha_hasta | DATE | nullable | null = honorario vigente |

Regla: solo puede haber un registro con `fecha_hasta = null` por `servicio_contratado_id`.

---

### `cobros`
Dinero efectivamente recibido. Cubre honorarios mensuales, DDJJ, trabajos eventuales.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| cliente_id | INT | FK → clientes, NOT NULL | Redundante pero conveniente para filtrado |
| servicio_contratado_id | INT | FK → servicios_contratados, nullable | null = cobro no vinculado a servicio específico |
| periodo_desde | DATE | nullable | Primer día del período cubierto |
| periodo_hasta | DATE | nullable | |
| fecha_cobro | DATE | NOT NULL | |
| importe | DECIMAL(10,2) | NOT NULL | |
| forma_pago | ENUM | NOT NULL | `efectivo`, `transferencia`, `otro` |
| tipo_comprobante | ENUM | NOT NULL | `e_ticket`, `no_gravado`, `sin_comprobante` |
| notas | TEXT | nullable | |

---

### `descuentos`
Descuentos como concepto propio. Se restan al calcular el saldo del cliente.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| cliente_id | INT | FK → clientes, NOT NULL | |
| servicio_contratado_id | INT | FK → servicios_contratados, nullable | |
| fecha | DATE | NOT NULL | |
| importe | DECIMAL(10,2) | NOT NULL | Siempre positivo |
| motivo | TEXT | NOT NULL | |

---

### `credenciales`
Campos sensibles cifrados en reposo por la capa de aplicación.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| cliente_id | INT | FK → clientes, NOT NULL | |
| tipo | ENUM | NOT NULL | `dgi`, `bps`, `facturador`, `pin`, `otro` |
| usuario | TEXT cifrado | nullable | |
| password | TEXT cifrado | nullable | |
| notas | TEXT cifrado | nullable | ej: "contraseña es fecha de nacimiento" |
| ultima_actualizacion | DATE | NOT NULL | |

---

### `tarea_templates`
Plantillas de tareas por combinación servicio + régimen. Se definen una vez, se reusan.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| servicio_id | INT | FK → servicios, NOT NULL | |
| regimen | ENUM | NOT NULL | Mismo enum que clientes, más valor `todos` |
| nombre | TEXT | NOT NULL | ej: "Descargar facturas del facturador electrónico" |
| descripcion | TEXT | nullable | |
| orden | INT | NOT NULL | Para ordenar el checklist |
| activo | BOOLEAN | NOT NULL, default true | |

---

### `tareas`
Instancias concretas generadas por cliente y período. Puede ser auto-generada desde template o ad-hoc.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| servicio_contratado_id | INT | FK → servicios_contratados, NOT NULL | |
| template_id | INT | FK → tarea_templates, nullable | null = tarea ad-hoc |
| nombre | TEXT | NOT NULL | Copiado del template o ingresado manualmente |
| periodo | DATE | NOT NULL | Primer día del mes/año que aplica |
| estado | ENUM | NOT NULL | `pendiente`, `en_proceso`, `completada`, `cancelada` |
| fecha_creacion | DATETIME | NOT NULL | |
| fecha_completada | DATETIME | nullable | |
| requiere_info_cliente | BOOLEAN | NOT NULL, default false | ¿Hay que esperar que el cliente envíe algo? |
| notas | TEXT | nullable | |

---

### `recordatorios`
Sistema de notificaciones persistentes para el contador.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| tarea_id | INT | FK → tareas, nullable | |
| tipo | ENUM | NOT NULL | `tarea_pendiente`, `vencimiento_proximo`, `cobro_pendiente` |
| mensaje | TEXT | NOT NULL | |
| fecha_programada | DATETIME | NOT NULL | |
| fecha_enviada | DATETIME | nullable | null = aún no enviado |
| estado | ENUM | NOT NULL | `pendiente`, `enviado`, `silenciado` |
| repetir_hasta_completar | BOOLEAN | NOT NULL, default false | |
| intervalo_repeticion_horas | INT | nullable | ej: 24 para repetir cada 24h |

---

### `vencimientos_calendario`
Tabla de referencia sin relaciones FK. Se carga manualmente desde el calendario oficial DGI/BPS.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| regimen | ENUM | NOT NULL | Mismo enum que clientes, más valor `todos` |
| descripcion | TEXT | NOT NULL | ej: "BPS cuota mensual" |
| organismo | ENUM | NOT NULL | `dgi`, `bps`, `otro` |
| mes | INT | nullable | null = aplica todos los meses |
| dia_vencimiento | INT | NOT NULL | Día del mes (1-31) |
| anio | INT | nullable | null = recurrente anualmente |
| activo | BOOLEAN | NOT NULL, default true | |

---

### `gastos_ingresos_propios`
Registro de P&L del estudio. Sin relaciones FK. Incluye gastos operativos e ingresos propios.

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| fecha | DATE | NOT NULL | |
| tipo | ENUM | NOT NULL | `ingreso`, `gasto` |
| concepto | TEXT | NOT NULL | |
| importe | DECIMAL(10,2) | NOT NULL | |
| categoria | ENUM | NOT NULL | `cjppu`, `aportes_bps`, `gasto_operativo`, `otro` |
| notas | TEXT | nullable | |

---

## 4. Relaciones entre entidades

```
clientes          1──N  servicios_contratados
servicios         1──N  servicios_contratados
servicios_contratados  1──N  honorarios_historial
servicios_contratados  1──N  cobros
servicios_contratados  1──N  descuentos
servicios_contratados  1──N  tareas
clientes          1──N  credenciales
servicios         1──N  tarea_templates
tarea_templates   1──N  tareas
tareas            1──N  recordatorios

── Sin relaciones FK ──
vencimientos_calendario   (tabla de referencia)
gastos_ingresos_propios   (tabla de referencia)
```

---

*Entregable Chat 2 completo.*

---
---

# Instrucciones para iniciar el Chat 3

Pegá esto al comienzo del Chat 3 como contexto inicial:

---

## Contexto del proyecto

Soy Contador Público en Uruguay. Trabajo de forma independiente llevando la contabilidad de ~12 clientes mensuales (unipersonales profesionales y no profesionales, monotributos, régimen general) y clientes eventuales. También trabajo en relación de dependencia en Ricoh Uruguay y estudio en ORT Uruguay.

Estoy diseñando el anteproyecto completo de una app de gestión para mi estudio contable **antes de escribir código**. Los chats anteriores definieron el relevamiento del negocio (Chat 1) y las funcionalidades + modelo de datos (Chat 2). Este es el Chat 3.

## Perfil técnico

- Python y FastAPI: nivel básico-intermedio
- Manejo conceptos de base de datos, entidades y relaciones
- No soy desarrollador profesional
- Necesito explicaciones claras, sin asumir conocimiento avanzado

## Cómo trabajamos

- Un paso a la vez. Sin avanzar al siguiente hasta terminar el anterior.
- Si algo es vago o puede generar problemas, decímelo antes de avanzar.
- Si ves algo que estoy pasando por alto, decímelo aunque no te lo pregunte.
- Respuestas directas, sin relleno.
- El objetivo es que los requerimientos sean tan granulares que un desarrollador no tenga que inventar nada ni tomar decisiones de negocio.

## Entregable del Chat 2 (base para este chat)

[PEGAR ACÁ EL CONTENIDO COMPLETO DEL DOCUMENTO DE ARRIBA]

---

## Chat 3 — Requerimientos granulares

**Objetivo:** definir el comportamiento exacto de cada funcionalidad MVP antes de escribir código.

**Por qué importa:** cada requerimiento sin definir es una decisión que va a tomar el desarrollador (o la IA que genere el código). Esas decisiones suelen no reflejar la operativa real del negocio.

**Entregable:** documento de requerimientos funcionales granulares por funcionalidad, cubriendo:
- Comportamiento esperado (qué hace exactamente)
- Reglas de negocio (condiciones, validaciones, casos borde)
- Qué muestra el sistema al usuario (vistas, campos, mensajes)
- Qué genera o modifica en la base de datos

**Funcionalidades a especificar (MVP):**
- F1: Ficha de clientes unificada
- F2: Vault de credenciales cifrado
- F3: Catálogo de servicios
- F4: Servicios contratados por cliente
- F5: Control de cobros con descuentos
- F6: Historial de honorarios
- F7: Checklist de tareas por régimen
- F8: Calendario de vencimientos
- F9: Proyección de ingresos + gastos propios
- F10: Recordatorios persistentes

**Metodología sugerida:** una funcionalidad a la vez, con confirmación antes de pasar a la siguiente.
