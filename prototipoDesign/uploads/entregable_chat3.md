# Estudio Contable — Requerimientos Funcionales Granulares
*Entregable Chat 3 — base para Chat 4: Stack tecnológico*

---

## 0. Cambios consolidados al modelo de datos (respecto al Chat 2)

| # | Cambio | Origen |
|---|---|---|
| 1 | Nueva tabla `clientes_regimen_historial` | F1 |
| 2 | Enum `tipo` de `credenciales`: `pin` se reemplaza por `clave_dgi` | F2 |
| 3 | Nuevo campo `mes_generacion` (INT 1-12, nullable) en `tarea_templates` | F7 |
| 4 | Nuevo campo `silenciado_hasta` (DATE, nullable) en `recordatorios` | F10 |
| 5 | Enum `estado` de `recordatorios`: se agrega valor `cerrado` | F10 |

### Nueva tabla: `clientes_regimen_historial`

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| cliente_id | INT | FK → clientes, NOT NULL | |
| regimen | ENUM | NOT NULL | Mismo enum que `clientes` |
| fecha_desde | DATE | NOT NULL | |
| fecha_hasta | DATE | nullable | null = régimen vigente |

Regla: solo puede haber un registro con `fecha_hasta = null` por `cliente_id`.

### Criterio general para enums

Agregar nuevos valores a cualquier enum (tipos de credencial, categorías, etc.) se resuelve por intervención directa en la base de datos. No hay pantallas de administración de enums en el MVP.

---

## F1 — Ficha de clientes unificada

### Comportamiento general

F1 cubre tres operaciones: listar clientes, ver ficha individual, crear/editar cliente.

Al crear un cliente se inserta automáticamente el primer registro en `clientes_regimen_historial` con `fecha_desde = fecha_inicio` y `fecha_hasta = null`. El campo `regimen` en `clientes` se mantiene y siempre refleja el régimen vigente (redundante pero conveniente para filtrado rápido).

### Vista: listado de clientes

**Contenido:**
- Dos secciones separadas: **Clientes mensuales** y **Clientes eventuales**.
- Un cliente es mensual si tiene al menos un `servicio_contratado` activo cuyo servicio tiene `frecuencia = mensual`. De lo contrario es eventual. El indicador es **derivado, no almacenado**.
- Por defecto se listan solo clientes con `activo = true`. Toggle/filtro para mostrar inactivos.

**Orden:**
- Mensuales: primero por `regimen` (orden alfabético del valor del enum), luego por `id` ascendente.
- Eventuales: por `id` ascendente.

**Columnas:** nombre, régimen (valor legible), RUT (o "—"), indicador mensual/eventual, estado.

**Acciones:** acceder a la ficha, crear nuevo cliente.

### Vista: ficha individual de cliente

**Secciones:**
- **Datos generales:** nombre, régimen vigente, RUT, CI, fecha de nacimiento, email, teléfono, fecha de inicio, estado, notas.
- **Historial de regímenes:** tabla de `clientes_regimen_historial` ordenada por `fecha_desde` descendente. Columnas: régimen, fecha desde, fecha hasta (si null: "vigente"). Solo lectura.
- **Servicios contratados:** lista resumida de servicios activos (ver F4).
- **Credenciales:** acceso al vault del cliente (ver F2).
- **Próximos vencimientos:** ver F8, Vista 3.
- **Estado de cuenta e historial de honorarios:** ver F5 y F6.

### Crear cliente

**Campos:**
- Nombre — texto libre, obligatorio
- Régimen — selector del enum, obligatorio
- RUT — texto, opcional
- CI — texto, opcional, sin validación de formato
- Fecha de nacimiento — fecha, opcional
- Email — texto, opcional, sin validación de formato
- Teléfono — texto, opcional, sin validación de formato
- Fecha de inicio — fecha, obligatorio, default: hoy
- Notas — texto libre, opcional

**Al guardar:**
1. Se inserta el registro en `clientes`.
2. Se inserta el primer registro en `clientes_regimen_historial` (`fecha_desde = fecha_inicio`, `fecha_hasta = null`).
3. Redirección a la ficha del cliente creado.

**Validaciones:**
- Nombre: no vacío.
- Régimen: valor del enum.
- Fecha de inicio: no futura.
- RUT: si se ingresa, exactamente 12 dígitos numéricos. Mensaje: *"El RUT debe tener 12 dígitos numéricos."*
- **Unicidad de RUT:** no puede existir otro cliente con el mismo RUT. Mensaje: *"Ya existe un cliente con ese RUT."*
- **Unicidad de CI:** no puede existir otro cliente con la misma CI. Mensaje: *"Ya existe un cliente con esa CI."*
- Ambas unicidades se validan contra **todos** los clientes, incluidos los inactivos.
- No se valida unicidad de nombre.

### Editar cliente

- Campos editables: todos excepto `fecha_inicio`.
- Mismas validaciones que en la creación (unicidad excluyendo el propio registro).

**Cambio de régimen — flujo especial:**
- Al modificar `regimen`, el sistema muestra el campo adicional *"Fecha de cambio de régimen"* (obligatorio, default: hoy).
- Al guardar: se cierra el registro vigente en `clientes_regimen_historial` (`fecha_hasta = fecha_de_cambio − 1 día`) y se abre uno nuevo (`fecha_desde = fecha_de_cambio`, `fecha_hasta = null`). Se actualiza `regimen` en `clientes`.
- Restricción: la fecha de cambio no puede ser anterior a la `fecha_desde` del registro vigente ni futura.

**Desactivar cliente:**
- Toggle `activo` en la ficha. No elimina datos; el cliente sale del listado principal pero sigue accesible con el filtro de inactivos.
- No hay restricción por servicios activos o cobros pendientes: el sistema lo permite sin acciones automáticas.

### Lo que F1 NO hace

- No elimina clientes (solo desactiva).
- No valida duplicados de nombre.
- No gestiona servicios contratados ni credenciales (F4 y F2).
- No calcula saldos ni cobros (F5).

---

## F2 — Vault de credenciales cifrado

### Enum actualizado

`tipo`: `dgi`, `bps`, `facturador`, `clave_dgi`, `otro`. (`clave_dgi` es la clave para sistemas como el de solicitud de certificados de crédito.)

### Comportamiento general

- El vault es accesible desde la ficha de cada cliente. No hay vista global de credenciales de todos los clientes.
- Acceso protegido únicamente por el login de la app (usuario único). Sin contraseña maestra adicional.

### Vista: listado de credenciales de un cliente

- Todas las credenciales del cliente, ordenadas por `tipo` ascendente, luego `ultima_actualizacion` descendente.
- Columnas: tipo (legible), usuario (en claro), contraseña (oculta por defecto: `••••••••`), última actualización, acciones (ver detalle, editar, eliminar).
- **Revelar contraseña:** ícono de ojo por fila, alterna revelar/ocultar. No existe "revelar todas".

### Vista: detalle de credencial

Todos los campos: tipo, usuario, contraseña (oculta por defecto con opción de revelar), notas, última actualización.

### Crear credencial

**Campos:**
- Tipo — selector del enum, obligatorio
- Usuario — texto, opcional
- Contraseña — texto, opcional, input tipo password con opción de revelar
- Notas — texto libre, opcional (ej: "la contraseña es la fecha de nacimiento")
- `ultima_actualizacion` — automática (hoy), no editable

**Validaciones:**
- Tipo: obligatorio.
- Al menos usuario o contraseña. Mensaje: *"Ingresá al menos usuario o contraseña."*
- No se valida unicidad de tipo por cliente (puede haber dos accesos DGI).

**Al guardar:** los campos `usuario`, `password` y `notas` se cifran en la capa de aplicación antes de escribir en la base.

### Editar credencial

- Todos los campos editables. `ultima_actualizacion` se actualiza automáticamente a hoy. El cifrado se reaplica.

### Eliminar credencial

- Eliminación física (sin soft delete), con confirmación: *"¿Confirmás que querés eliminar esta credencial? Esta acción no se puede deshacer."*

### Cifrado — responsabilidades

- `usuario`, `password` y `notas` nunca se escriben en texto plano.
- Cifrado/descifrado en la capa de aplicación (backend), no en frontend ni base de datos.
- Algoritmo y gestión de claves se definen en el Chat 4 (stack).

### Lo que F2 NO hace

- No registra historial de cambios de contraseñas.
- No tiene expiración ni alertas de contraseñas viejas.
- No permite exportar credenciales.
- No tiene contraseña maestra separada del login.

---

## F3 — Catálogo de servicios

### Comportamiento general

Tabla de referencia cargada en la configuración inicial, de bajo movimiento. Accesible desde **Configuración → Servicios** (sin lugar prominente en la navegación).

### Vista: listado de servicios

- Todos los servicios, activos e inactivos, ordenados por `frecuencia` ascendente y luego `nombre` ascendente.
- Columnas: nombre, frecuencia, estado.
- Acciones: crear, editar, desactivar/reactivar.

### Crear servicio

**Campos:** nombre (texto, obligatorio), frecuencia (`mensual`/`anual`/`unico`, obligatorio).

**Validaciones:**
- Nombre: no vacío.
- **Unicidad de nombre independientemente del estado (activo o inactivo).** Mensaje: *"Ya existe un servicio con ese nombre."*

**Al guardar:** se inserta con `activo = true`.

### Editar servicio

- Editables: `nombre` y `frecuencia`. Unicidad de nombre igual que en creación, excluyendo el propio registro.
- **Restricción:** si el servicio tiene al menos un `servicio_contratado` activo, no se puede cambiar la frecuencia. Mensaje: *"No se puede cambiar la frecuencia de un servicio con contratos activos."* El nombre sí puede cambiarse.

### Desactivar servicio

- `activo = false`. Desaparece de los selectores de F4. Los contratos existentes no se modifican.
- Sin confirmación. Reactivable desde el listado.

### Eliminación

- No existe eliminación física desde la app; de ser necesario, se hace en la base de datos.

### Registros iniciales

| Nombre | Frecuencia |
|---|---|
| Liquidación mensual | mensual |
| DDJJ IVA anual | anual |
| DDJJ IRPF anual | anual |
| DDJJ FONASA | anual |
| Declaración IRPF persona física | anual |
| Certificado de ingresos | unico |
| Gestión ante DGI | unico |
| Gestión ante BPS | unico |

### Lo que F3 NO hace

- No gestiona precios (viven en `honorarios_historial`).
- No gestiona tareas ni templates (F7).
- No tiene historial de cambios de nombre o frecuencia.

---

## F4 — Servicios contratados por cliente

### Semántica de `fecha_fin`

- Servicios `mensual`/`anual`: se registra cuando el cliente deja de contratar el servicio.
- Servicios `unico`: se registra cuando el trabajo se completa; representa la **duración real del trabajo** (insumo para cotizar trabajos futuros).

### Comportamiento general

Cada contratación es un registro independiente en `servicios_contratados`, incluso si el cliente contrata el mismo servicio `unico` varias veces (cada engagement conserva su propio honorario, fechas y tareas).

### Vista: servicios contratados en la ficha del cliente

- Solo servicios con `activo = true`.
- Orden: frecuencia del servicio (mensual → anual → unico), luego `fecha_inicio` descendente.
- Columnas: nombre del servicio, frecuencia, honorario vigente (registro de `honorarios_historial` con `fecha_hasta = null`), fecha de inicio, acciones (ver detalle, editar, finalizar).

### Contratar servicio (crear)

**Campos:**
- Servicio — selector con servicios activos del catálogo, obligatorio
- Fecha de inicio — fecha, obligatorio, default: hoy
- Honorario — decimal, obligatorio

**Validaciones:**
- Fecha de inicio: no futura.
- Honorario: mayor a cero.
- Servicios `mensual`/`anual`: no puede existir otro contrato activo del mismo servicio para el mismo cliente. Mensaje: *"El cliente ya tiene ese servicio contratado activo."*
- Servicios `unico`: sin restricción de duplicados.

**Al guardar:**
1. Se inserta en `servicios_contratados` con `activo = true`, `fecha_fin = null`.
2. Se inserta el primer registro en `honorarios_historial` (`fecha_desde = fecha_inicio`, `fecha_hasta = null`).
3. Generación de tareas según F7 (mensual: tareas del período en curso; único: desde templates si existen; anual: no genera al contratar).

### Editar servicio contratado

- Editable únicamente `fecha_inicio`, y solo si no existen tareas ni cobros asociados. Mensaje si existen: *"No se puede modificar la fecha de inicio porque existen tareas o cobros asociados."*
- El honorario no se edita acá (F6). El servicio no es editable: ante un error, se finaliza el contrato y se crea uno nuevo.

### Finalizar servicio contratado

**Flujo:** acción "Finalizar" → el sistema solicita *"Fecha de finalización"* (obligatorio, default: hoy). Restricción: no anterior a `fecha_inicio` del contrato.

**Al confirmar:**
1. `fecha_fin` = fecha ingresada.
2. `activo = false`.
3. Se cierra el honorario vigente: `fecha_hasta = fecha_fin`.
4. Las tareas pendientes asociadas no se cancelan automáticamente; quedan en su estado.

### Eliminación

- No existe eliminación física desde la app.

### Lo que F4 NO hace

- No gestiona cambios de honorario (F6).
- No muestra historial de contratos finalizados en la ficha (solo activos).

---

## F5 — Control de cobros con descuentos

### Comportamiento general

Tres aspectos: registrar cobros, registrar descuentos, ver estado de cuenta. Los cobros se registran desde la ficha del cliente o desde una vista global.

### Vista: estado de cuenta del cliente

**Saldo vigente:**

```
Saldo = Σ honorarios esperados (todos los períodos impagos)
      − Σ descuentos aplicados
      − Σ cobros recibidos
```

- El honorario esperado por período usa el registro vigente de `honorarios_historial` **en ese período**.
- Se consideran todos los períodos desde `fecha_inicio` de cada contrato activo.
- Saldo positivo: el cliente debe. Cero o negativo: al día o saldo a favor.
- Indicador visual: verde (al día), rojo (debe).

**Listado de cobros:** ordenados por `fecha_cobro` descendente. Columnas: fecha, servicio asociado (si existe), período cubierto, importe, forma de pago, tipo de comprobante, notas.

**Listado de descuentos:** ordenados por `fecha` descendente. Columnas: fecha, servicio asociado (si existe), importe, motivo.

### Vista global: registro de cobros

Vista dedicada en la navegación principal, pensada para el día de revisión de cobros.

- Todos los clientes activos con su saldo vigente, ordenados por saldo descendente (mayor deuda primero).
- Columnas: nombre, régimen, saldo vigente.
- Desde cada fila: acceso directo al formulario de registro de cobro de ese cliente.

### Registrar cobro

**Campos:**
- Cliente — selector, obligatorio (pre-seleccionado desde la ficha)
- Servicio contratado — selector con contratos activos del cliente, opcional (vacío = cobro sin servicio específico)
- Período desde — fecha (primer día del mes), opcional
- Período hasta — fecha (último día del mes), opcional
- Fecha de cobro — fecha, obligatorio, default: hoy
- Importe — decimal, obligatorio
- Forma de pago — `efectivo`/`transferencia`/`otro`, obligatorio
- Tipo de comprobante — `e_ticket`/`no_gravado`/`sin_comprobante`, obligatorio
- Notas — texto libre, opcional

**Validaciones:**
- Importe: mayor a cero.
- `periodo_desde` y `periodo_hasta` van juntos: si se ingresa uno, se requiere el otro.
- `periodo_hasta` ≥ `periodo_desde`.
- Fecha de cobro: no futura.

**Reglas de período:**
- Pago que cubre varios meses: **un solo cobro** con `periodo_desde`/`periodo_hasta` cubriendo el rango (ej: abril y mayo → `2025-04-01` a `2025-05-31`).
- Servicios `unico`: `periodo_desde = periodo_hasta` = fecha del trabajo. El sistema lo valida si se ingresan ambos campos, sin forzarlo automáticamente.

**Al guardar:** se inserta en `cobros` y el saldo se recalcula automáticamente.

### Registrar descuento

Solo desde la ficha del cliente. Los descuentos son puntuales y se aplican como ajuste.

**Campos:** servicio contratado (opcional), fecha (obligatorio, default hoy), importe (obligatorio), motivo (obligatorio).

**Validaciones:** importe mayor a cero, motivo no vacío, fecha no futura.

**Al guardar:** se inserta en `descuentos` y el saldo se recalcula.

### Editar y eliminar cobros y descuentos

- Todos los campos editables.
- Eliminación física con confirmación: *"¿Confirmás que querés eliminar este registro? Esta acción no se puede deshacer."*
- Al editar o eliminar, el saldo se recalcula.

### Lo que F5 NO hace

- No genera comprobantes ni documentos fiscales.
- No distingue si un cobro corresponde a un período facturado o no.
- No envía notificaciones al cliente (post-MVP, F11).
- No gestiona cambios de honorarios (F6).

---

## F6 — Historial de honorarios

### Mecánica común de cambio de honorario (append-only)

Todo cambio, individual o global:

1. Se cierra el registro vigente: `fecha_hasta = fecha_de_vigencia − 1 día`.
2. Se inserta un nuevo registro: `honorario` = nuevo importe, `fecha_desde = fecha_de_vigencia`, `fecha_hasta = null`.

Se mantiene la regla: un solo registro con `fecha_hasta = null` por `servicio_contratado_id`. Los registros históricos nunca se modifican ni eliminan desde la app.

### Cambio individual de honorario

Desde la ficha del cliente, en el detalle del servicio contratado.

**Campos:** nuevo honorario (decimal, obligatorio), fecha de vigencia (primer día de mes, obligatorio, default: primer día del mes siguiente).

**Validaciones:**
- Nuevo honorario: mayor a cero y distinto del vigente. Mensaje si es igual: *"El nuevo honorario es igual al vigente."*
- Fecha de vigencia: primer día de un mes; no anterior a la `fecha_desde` del registro vigente (evita superposición con registros cerrados).

**Cambio retroactivo:**
- Permitido respetando la validación anterior. Si la fecha es anterior al mes en curso, advertencia: *"Estás aplicando un cambio retroactivo desde [mes/año]. El saldo del cliente se recalculará."*

**Al guardar:** mecánica común + recálculo automático del saldo (cada período impago usa el honorario vigente en ese período).

### Aumento global de honorarios

Vista dedicada (ubicación exacta en navegación se define en la etapa de UI). Uso típico: ajuste de enero por IPC + margen.

**Paso 1 — Parámetros:** porcentaje de aumento (decimal, obligatorio, mayor a cero), fecha de vigencia (primer día de mes, obligatorio, default: primer día del mes siguiente).

**Paso 2 — Selección:**
- Se listan todos los `servicios_contratados` activos de frecuencia `mensual` o `anual`. Los `unico` quedan excluidos (ya cotizados).
- Columnas: cliente, servicio, frecuencia, honorario vigente, honorario nuevo (calculado), checkbox.
- Orden: frecuencia (mensual → anual), luego cliente.
- Controles "seleccionar todos" / "deseleccionar todos" + selección individual. **Por defecto, ninguno seleccionado** (permite excluir clientes con acuerdos o de ingreso reciente).

**Cálculo:**

```
honorario_nuevo = redondear_hacia_arriba(honorario_vigente × (1 + porcentaje/100), múltiplo de 10)
```

Ejemplo: $5.700 × 1,085 = $6.184,50 → **$6.190**.

- El honorario nuevo es **editable por fila**; el importe manual reemplaza al calculado sin redondeo adicional.

**Paso 3 — Confirmar:**
- Resumen: cantidad seleccionada, fecha de vigencia, listado honorario vigente → nuevo.
- Al confirmar: mecánica común por cada seleccionado + recálculo de saldos.

**Validaciones:**
- Al menos un servicio seleccionado.
- La fecha de vigencia aplica a todos; si algún contrato no cumple la validación (fecha anterior a su `fecha_desde` vigente), se indica por fila y no se puede confirmar hasta deseleccionarlo o cambiar la fecha.
- Honorarios editados a mano: mayores a cero.

### Visualización del historial

- **Por servicio contratado:** en el detalle del contrato (F4), tabla completa ordenada por `fecha_desde` descendente. Columnas: honorario, fecha desde, fecha hasta (null: "vigente"). Solo lectura.
- **Consolidado por cliente:** en la ficha, sección "Historial de honorarios": registros de todos sus contratos (activos y finalizados), ordenados por `fecha_desde` descendente. Columnas: servicio, honorario, fecha desde, fecha hasta. Solo lectura.

### Lo que F6 NO hace

- No edita ni elimina registros históricos desde la app (corrección: nuevo cambio retroactivo o base de datos).
- No aplica aumentos automáticos programados: el aumento global es siempre manual.
- No obtiene el IPC de fuentes externas.

---

## F7 — Checklist de tareas por régimen

### Regla central de matching

Al generar tareas para un contrato se usan los templates cuyo `servicio_id` coincide con el servicio del contrato **y** cuyo `regimen` coincide con el régimen vigente del cliente **o** es `todos`. Solo templates con `activo = true`.

### Campo nuevo: `mes_generacion` en `tarea_templates`

- Obligatorio si el servicio del template es `anual` (mes fijo de generación, ej: DDJJ FONASA = 2, DDJJ IVA/IRPF = 6).
- Null si el servicio es `mensual` o `unico`.

### Administración de templates

Accesible desde **Configuración → Templates de tareas** (administrables desde la app: es la parte del catálogo con más movimiento).

**Listado:** todos los templates, ordenados por servicio → régimen → `orden`. Columnas: servicio, régimen, nombre, orden, mes de generación (si aplica), estado.

**Crear template — campos:**
- Servicio — selector con servicios activos, obligatorio
- Régimen — enum + `todos`, obligatorio
- Nombre — texto, obligatorio
- Descripción — texto, opcional
- Orden — entero, obligatorio
- Mes de generación — selector 1-12, obligatorio si el servicio es `anual`, oculto si es `mensual` o `unico`

**Validaciones:**
- No pueden existir dos templates activos con el mismo servicio + régimen + nombre.
- Orden: mayor a cero; puede repetirse entre combinaciones distintas de servicio + régimen, no dentro de la misma.

**Editar:** todos los campos, mismas validaciones. Los cambios aplican solo a generaciones futuras (el nombre se copia al generar).

**Desactivar:** `activo = false`, sin confirmación, reactivable. Deja de usarse a futuro; tareas ya generadas no se tocan. Sin eliminación física.

### Generación automática — día 1 de cada mes

El día 1 el sistema genera las tareas del período (período = primer día del mes en curso):

- **Mensuales:** por cada contrato activo de servicio `mensual`, tareas desde los templates que matcheen.
- **Anuales:** por cada contrato activo de servicio `anual`, tareas desde los templates que matcheen **y** cuyo `mes_generacion` = mes en curso. El `periodo` es el primer día del mes en curso.

**Anti-duplicado:** antes de generar, se verifica que no exista tarea con el mismo `servicio_contratado_id` + `template_id` + `periodo`. La generación es re-ejecutable sin riesgo.

**Cada tarea generada:** `nombre` copiado del template, `estado = pendiente`, `periodo` = primer día del mes, `fecha_creacion` = ahora, `requiere_info_cliente = false` (ajustable a mano).

### Generación al contratar (F4 → F7)

- **Mensual a mitad de mes:** al crear el contrato se generan inmediatamente las tareas del período en curso; desde el mes siguiente entra al ciclo automático. Las tareas generadas son cancelables individualmente (caso del cliente que arranca a fin de mes).
- **Anual:** no genera al contratar; genera en su `mes_generacion` dentro del ciclo automático.
- **Único:** si existen templates que matcheen, se generan inmediatamente con `periodo` = primer día del mes en curso; si no, el contrato queda sin tareas y se cargan ad-hoc.

### Tareas ad-hoc

Creables en cualquier momento. Campos: servicio contratado (obligatorio), nombre (obligatorio), período (mes/año, obligatorio, default: mes en curso), requiere info del cliente (checkbox, default: no), notas (opcional). Se crean con `template_id = null`, `estado = pendiente`.

### Gestión de tareas — checklist de trabajo

**Vista principal: tareas del período** (navegación principal)

- Filtros: período (default: mes en curso), cliente, estado.
- Agrupadas por cliente; dentro de cada cliente, por `orden` del template (ad-hoc al final, por fecha de creación).
- Columnas: cliente, servicio, tarea, estado, requiere info cliente, notas.
- Indicador por cliente: X de Y tareas completadas del período.
- Incorpora fecha límite y semáforo de urgencia (ver F8, Conexión con el checklist).

**Estados y transiciones:**
- `pendiente` → `en_proceso` → `completada`.
- Desde `pendiente` o `en_proceso` se puede pasar a `cancelada`.
- `completada` y `cancelada` son finales, con posibilidad de reabrir (volver a `pendiente`).
- Al completar: `fecha_completada` = ahora. Al reabrir: vuelve a null.
- Cambio de estado en un clic, sin confirmación. **Cancelar sí pide confirmación:** *"¿Confirmás que querés cancelar esta tarea?"*

**Edición:** editables nombre (solo ad-hoc), `requiere_info_cliente`, notas. No editables: servicio contratado, período, template de origen.

**Eliminación:** no hay eliminación física; las tareas no deseadas se cancelan.

### Casos borde

- **Cambio de régimen del cliente:** tareas ya generadas no se modifican; la siguiente generación usa el nuevo régimen vigente.
- **Contrato finalizado:** no participa de la generación automática; sus tareas pendientes quedan como estaban.
- **Template desactivado:** simplemente no genera más.

### Lo que F7 NO hace

- No dispara recordatorios (F10 lee el estado de las tareas).
- No notifica al cliente (post-MVP, F11).
- No define el contenido de los checklists: los templates concretos se cargan en la fase de carga de datos, cuando se estandaricen los pasos por régimen.

---

## F8 — Calendario de vencimientos

### Regla de aplicabilidad

Un vencimiento aplica a un cliente en un período dado si:
- `regimen` del vencimiento = régimen vigente del cliente, **o** `regimen = todos`, y
- `mes` = mes del período, **o** `mes = null`, y
- `anio` = año del período, **o** `anio = null`, y
- `activo = true`.

### Administración de vencimientos

Accesible desde **Configuración → Vencimientos**. Operativa: carga manual una vez al año cuando DGI/BPS publican los calendarios; los vencimientos estables pueden cargarse como recurrentes (`anio = null`).

**Listado:** todos los registros; filtros por año, organismo y régimen; orden por mes y día ascendentes. Columnas: descripción, organismo, régimen, mes (o "todos"), día, año (o "recurrente"), estado.

**Crear — campos:** descripción (obligatorio), organismo (`dgi`/`bps`/`otro`, obligatorio), régimen (enum + `todos`, obligatorio), mes (1-12, opcional), día de vencimiento (1-31, obligatorio), año (opcional).

**Validaciones:**
- Descripción no vacía; día entre 1 y 31. Si el día no existe en un mes (ej: 31 en abril), a efectos de visualización se toma el último día real del mes.
- No se valida duplicado exacto (carga anual de bajo volumen, responsabilidad del contador).

**Editar:** todos los campos. **Desactivar:** `activo = false`, reactivable, sin confirmación, sin eliminación física desde la app.

### Vista 1: calendario mensual

- Grilla del mes seleccionado (default: mes en curso), navegable.
- Cada vencimiento aplicable aparece en su día con descripción y organismo, color por organismo.
- Clic en un vencimiento: detalle con descripción, organismo, regímenes alcanzados y listado de clientes activos a los que aplica (derivado por régimen).

### Vista 2: próximos vencimientos

- Vencimientos de los próximos 15 días, orden por fecha ascendente.
- Columnas: fecha exacta, descripción, organismo, regímenes alcanzados, cantidad de clientes afectados.
- Vacío: *"No hay vencimientos en los próximos 15 días."*
- Puede convivir con el calendario o en el dashboard (se define en la etapa de UI).

### Vista 3: en la ficha del cliente

- Sección "Próximos vencimientos": aplicables al cliente por su régimen vigente, próximos 30 días, orden por fecha. Columnas: fecha, descripción, organismo. Solo lectura.

### Conexión con el checklist de tareas (F7)

Conexión **derivada en tiempo de consulta, sin FK** en la base:

- **Fecha límite del período por cliente:** el vencimiento aplicable más próximo dentro del período visualizado, destacado en el encabezado del grupo: *"Fecha límite: 22/06 — DGI"*.
- Desplegable con todos los vencimientos del cliente en el período.
- **Semáforo de urgencia:**
  - Verde: todas las tareas del período completadas (o canceladas).
  - Amarillo: tareas pendientes y faltan más de 5 días para la fecha límite.
  - Rojo: tareas pendientes y faltan 5 días o menos (o fecha pasada).
- Cliente sin vencimientos aplicables: sin fecha límite ni semáforo.

### Evolución prevista (no se implementa en MVP)

Tabla hija `vencimientos_por_terminacion` con día de vencimiento por terminación de RUT, extendiendo cada registro sin modificar la estructura actual.

### Lo que F8 NO hace

- No importa calendarios automáticamente desde DGI/BPS.
- No contempla terminación de RUT (evolución prevista).
- No genera recordatorios (F10 lee vencimientos próximos).
- No vincula tareas individuales a vencimientos específicos: la conexión es a nivel cliente/período.

---

## F9 — Proyección de ingresos + gastos/ingresos propios

### Semántica de `gastos_ingresos_propios`

- `tipo = gasto`: gastos del estudio (CJPPU, aportes BPS, operativos, otros).
- `tipo = ingreso`: **solo ingresos que no provienen de clientes** (intereses, trabajos fuera del sistema). Los cobros de F5 se toman automáticamente como ingresos; no se duplican acá.

### Cálculo del "esperado" de un mes

```
Esperado del mes = Σ honorarios mensuales vigentes
                 + Σ honorarios anuales cuyo mes_generacion = mes
                 − Σ descuentos del mes
```

- **Mensuales:** honorario vigente en ese mes según `honorarios_historial`. Un contrato entra si estuvo activo en algún momento del mes (`fecha_inicio`/`fecha_fin`).
- **Anuales:** entran en el mes donde se generan sus tareas (`mes_generacion` de sus templates). Con templates de distintos `mes_generacion`, se usa el menor. Sin templates: no entran al esperado, solo al cobrado.
- **Únicos:** no entran al esperado (pueden llevar más de un mes); solo se reflejan al cobrarse.

### Cálculo del "cobrado" de un mes

Suma de `importe` de los cobros con `fecha_cobro` dentro del mes. Se usa la fecha de cobro, no el período cubierto: refleja el dinero que efectivamente entró.

### Diferencia

`Diferencia = Esperado − Cobrado`. Positiva: falta cobrar. Negativa: se cobró más de lo esperado (pagos atrasados, trabajos únicos).

### Dashboard principal (pantalla inicial de la app)

- **Bloque 1 — Ingresos del mes:** esperado / cobrado / diferencia, con barra de progreso.
- **Bloque 2 — P&L del mes:**

```
Ingresos totales = cobros del mes (F5) + ingresos propios del mes
Gastos totales   = gastos propios del mes
Saldo neto       = Ingresos totales − Gastos totales
```

Saldo neto con indicador: verde (positivo), rojo (negativo). El análisis CJPPU lo hace el contador a partir del P&L; el sistema no calcula franjas.

- **Bloque 3 — Accesos rápidos:** próximos vencimientos (F8), tareas pendientes del período (F7), clientes con mayor saldo deudor (F5).

### Vista: histórico mensual

- Últimos 12 meses por default, navegable hacia atrás.
- Columnas por mes: esperado, cobrado, diferencia, ingresos propios, gastos, saldo neto.
- Cálculo con los mismos criterios, usando el honorario vigente de cada mes según historial. Solo lectura.

### Vista: proyección futura

- Próximos 6 meses. Supuesto: cartera actual sin cambios (contratos activos × honorarios vigentes; anuales en su `mes_generacion` si cae en la ventana).
- Columnas por mes: ingreso esperado proyectado. No proyecta gastos.
- Leyenda: *"Proyección basada en la cartera actual. No incluye trabajos únicos ni cambios futuros."*

### ABM de gastos/ingresos propios

**Listado:** filtros por mes (default: en curso), tipo y categoría; orden por fecha descendente. Columnas: fecha, tipo, concepto, categoría, importe, notas. Totales del filtro: ingresos, gastos, neto.

**Crear — campos:** fecha (obligatorio, default hoy), tipo (`ingreso`/`gasto`, obligatorio), concepto (obligatorio), importe (decimal, obligatorio, mayor a cero), categoría (`cjppu`/`aportes_bps`/`gasto_operativo`/`otro`, obligatorio), notas (opcional).

**Validaciones:** concepto no vacío, importe mayor a cero, fecha no futura.

**Editar/eliminar:** todos los campos editables; eliminación física con confirmación: *"¿Confirmás que querés eliminar este registro? Esta acción no se puede deshacer."*

### Lo que F9 NO hace

- No proyecta gastos futuros.
- No incluye trabajos únicos en el esperado ni en la proyección.
- No calcula impuestos propios ni la franja CJPPU.
- No genera reportes exportables (evaluable post-MVP).

---

## F10 — Recordatorios persistentes

### Cambios al modelo

- Nuevo campo `silenciado_hasta` (DATE, nullable) en `recordatorios`. Un recordatorio está silenciado mientras `silenciado_hasta` ≥ hoy.
- Enum `estado` actualizado: `pendiente`, `enviado`, `silenciado`, `cerrado`.

### Comportamiento general

Recordatorios solo para el contador (nada hacia clientes; post-MVP, F11). Tres partes: generación automática, entrega (panel en app + email resumen diario), gestión (silenciar, cierre automático). La generación corre en un proceso diario (mismo scheduler anotado en F7).

### Generación automática

**Tipo `tarea_pendiente`:**
- Se genera cuando una tarea lleva **10 días corridos** en estado `pendiente` o `en_proceso` desde su `fecha_creacion`. Regla uniforme, sin días hábiles (evita mantener tabla de feriados).
- Un recordatorio por tarea; anti-duplicado por `tarea_id` + tipo mientras haya uno activo.
- Mensaje: *"La tarea [nombre] de [cliente] lleva 10 días sin completarse."*
- `repetir_hasta_completar = true`, `intervalo_repeticion_horas = 24`.

**Tipo `vencimiento_proximo`:**
- Se genera **5, 2 y 1 día antes** de cada vencimiento aplicable a al menos un cliente activo (regla de F8).
- Tres recordatorios independientes (uno por umbral); anti-duplicado por vencimiento + umbral + fecha.
- No repiten: `repetir_hasta_completar = false`, intervalo null. `tarea_id = null`.
- Mensaje: *"[Descripción] ([organismo]) vence el [fecha] — faltan [N] días. Afecta a [X] clientes."*

**Tipo `cobro_pendiente`:**
- Se genera cuando un período queda impago **un mes completo después de finalizado**. Ejemplo: honorarios de julio impagos al 31/08 → se genera el 01/09.
- Evaluación el día 1 de cada mes: para cada cliente con contratos mensuales activos, se verifica si el período de hace dos meses tiene cobros que lo cubran (`periodo_desde`/`periodo_hasta`). Si no, se genera.
- Un recordatorio por cliente + período impago; anti-duplicado por esa combinación. `tarea_id = null`.
- Mensaje: *"[Cliente] tiene pendiente el pago de [mes/año]. Saldo actual: $[saldo]."*
- `repetir_hasta_completar = true`, `intervalo_repeticion_horas = 24`.

**Campos comunes al generar:** `estado = pendiente`, `fecha_programada` = ahora, `fecha_enviada = null`.

### Entrega 1: panel dentro de la app

- Campanita en la navegación, visible en toda la app, con contador de recordatorios activos.
- Activo = no silenciado (o silenciado vencido) y condición de cierre no cumplida.
- Orden del panel: `vencimiento_proximo` (por fecha ascendente), luego `tarea_pendiente` y `cobro_pendiente` (por antigüedad descendente).
- Cada ítem: mensaje, tipo (ícono/color), antigüedad, acciones (ir al elemento relacionado, silenciar).
- La repetición cada 24 hs significa: permanece visible en panel y contador mientras esté activo; `fecha_enviada` se actualiza en cada ciclo del scheduler.

### Entrega 2: email resumen diario

- **Un único email por día**, solo si hay al menos un recordatorio activo no silenciado.
- Contenido agrupado por tipo, mismo orden que el panel: vencimientos próximos → tareas atrasadas → cobros pendientes. Al pie, link a la app.
- Sin recordatorios activos: no se envía email.
- Dirección de destino configurable (Configuración → Notificaciones). Infraestructura de envío (SMTP, dominio) se define en el Chat 4.

### Silenciar

- Opciones: **3, 5 o 7 días**. Al silenciar: `silenciado_hasta = hoy + N días`, `estado = silenciado`.
- Efecto: fuera del panel, del contador y del email. Al vencer el plazo: vuelve a `pendiente` y reaparece.

**Restricción por fecha límite:**
- `vencimiento_proximo`: una opción se deshabilita si `hoy + N días` > fecha del vencimiento.
- `tarea_pendiente`: se valida contra la fecha límite del cliente en el período (F8). Si `hoy + N días` > fecha límite, la opción se deshabilita.
- Tarea sin fecha límite y `cobro_pendiente`: las tres opciones siempre disponibles.
- Si las tres quedan deshabilitadas: *"Este recordatorio no se puede silenciar porque el vencimiento está demasiado próximo."*

### Cierre automático

Los recordatorios no se cierran a mano; se cierran solos (`estado = cerrado`) cuando su causa desaparece:

- `tarea_pendiente`: la tarea pasa a `completada` o `cancelada`.
- `vencimiento_proximo`: pasa la fecha del vencimiento.
- `cobro_pendiente`: se registra un cobro que cubre el período (o descuento/edición que lo lleve a cubierto). Se reevalúa en cada ciclo diario y al registrar cobros en F5.

Los cerrados no se muestran; quedan en la base como historial (sin vista de consulta en el MVP). Si una tarea completada se reabre y sigue cumpliendo la regla de los 10 días, el ciclo diario genera un recordatorio nuevo.

### Lo que F10 NO hace

- No envía nada a clientes (post-MVP, F11).
- No permite recordatorios manuales ad-hoc.
- No envía push ni WhatsApp; solo panel + email.
- No permite configurar los umbrales (10 días, 5/2/1, un mes) desde la UI: reglas fijas del MVP; cambiarlas requiere intervención en código/base.

---

## Anotaciones para el Chat 4 (stack tecnológico)

1. **Scheduler:** la generación automática de tareas (día 1, F7) y la evaluación diaria de recordatorios (F10) requieren un mecanismo de ejecución programada. Definir cómo se implementa.
2. **Cifrado del vault (F2):** algoritmo y gestión de claves de cifrado en la capa de aplicación.
3. **Email (F10):** proveedor SMTP, dominio y configuración de envío del resumen diario.

## Diferido a la fase de carga de datos

- Contenido concreto de los templates de tareas por régimen (los pasos del checklist), a definir cuando se estandarice la operativa.
- Carga inicial del catálogo de servicios y del calendario de vencimientos del año.

---

*Entregable Chat 3 completo.*

---
---

# Instrucciones para iniciar el Chat 4

Pegá esto al comienzo del Chat 4 como contexto inicial:

---

## Contexto del proyecto

Soy Contador Público en Uruguay. Trabajo de forma independiente llevando la contabilidad de ~12 clientes mensuales (unipersonales profesionales y no profesionales, monotributos, régimen general) y clientes eventuales. También trabajo en relación de dependencia en Ricoh Uruguay y estudio en ORT Uruguay.

Estoy diseñando el anteproyecto completo de una app de gestión para mi estudio contable **antes de escribir código**. Los chats anteriores definieron: relevamiento del negocio (Chat 1), funcionalidades + modelo de datos (Chat 2), y requerimientos funcionales granulares de las 10 funcionalidades MVP (Chat 3). Este es el Chat 4.

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
- Cada decisión de stack debe estar justificada en función de mis restricciones: mantenimiento por una sola persona, simplicidad y robustez sobre features avanzadas, y desarrollo asistido con Claude Code.

## Entregables previos (base para este chat)

[PEGAR ACÁ EL ENTREGABLE DEL CHAT 2 — modelo de datos]
[PEGAR ACÁ EL ENTREGABLE DEL CHAT 3 — requerimientos granulares]

---

## Chat 4 — Stack tecnológico

**Objetivo:** decidir y justificar el stack tecnológico completo de la app.

**Entregable:** documento de decisiones técnicas con justificación, cubriendo:

- Backend (lenguaje, framework)
- Base de datos
- Frontend (enfoque y tecnología)
- **Scheduler** para tareas programadas (generación de tareas el día 1, evaluación diaria de recordatorios) — anotado en F7 y F10
- **Cifrado del vault de credenciales**: algoritmo y gestión de claves — anotado en F2
- **Infraestructura de email** para el resumen diario de recordatorios — anotado en F10
- Hosting / despliegue (dónde corre la app, respaldo de datos)
- Autenticación (login de usuario único)

**Restricciones a respetar en cada decisión:**
- Mantenible por una sola persona sin equipo técnico
- Perfil: Python/FastAPI básico-intermedio
- Simplicidad y robustez sobre sofisticación
- Escalable sin reescritura, sin sobre-ingeniería inicial
- El código será generado con asistencia de Claude Code

**Metodología sugerida:** una decisión a la vez, con confirmación antes de pasar a la siguiente. Al final, generar el entregable del Chat 4 y las instrucciones para el Chat 5 (plan de desarrollo por etapas).
