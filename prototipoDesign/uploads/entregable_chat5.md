# Estudio Contable — Plan de Desarrollo por Etapas
*Entregable Chat 5 — cierre del anteproyecto. Con este documento comienza la ejecución.*

---

## 0. Regla transversal: la etapa de diseño puede modificar requerimientos

La Etapa 1 (diseño de UI) se ubica **antes** del desarrollo funcional por decisión explícita: el diseño se usa como segunda pasada de validación funcional — ver las funcionalidades con su visual correcta permite detectar mejoras de comportamiento y funcionalidades faltantes que el análisis puramente funcional no muestra.

Para que esto no rompa el principio de "nada sin definir":

1. Todo hallazgo de la etapa de diseño (mejora de comportamiento, funcionalidad faltante, vista nueva) se documenta como **adenda formal al entregable del Chat 3** antes de escribir código.
2. Cada hallazgo se clasifica: **entra al MVP** (modifica requerimientos) o **post-MVP** (se anota, no bloquea).
3. La Etapa 1 no cierra hasta que las adendas estén resueltas. Claude Code recibe requerimientos + diseño ya consistentes entre sí, sin decisiones abiertas.

---

## 1. Orden de etapas y justificación

| Etapa | Contenido | Por qué en este lugar |
|---|---|---|
| 0 | Fundación técnica | Todo lo demás se apoya acá. Auditoría y capas deben existir desde el primer archivo |
| 1 | Diseño de UI (Claude Design) | Validación funcional visual antes de construir; cada etapa siguiente se construye ya con el diseño final |
| 2 | Núcleo: clientes y servicios (F1+F3+F4) | La base de datos viva del negocio; ninguna otra F opera sin esto |
| 3 | Dinero (F5+F6) | Reemplaza la parte más crítica del Excel. Con E2+E3 hay sistema usable para lo esencial |
| 4 | Vault de credenciales (F2) | Elimina el riesgo de seguridad crítico; independiente, no bloquea ni es bloqueada |
| 5 | Tareas y vencimientos (F7+F8) + scheduler | F7 es el primer consumidor real del scheduler. Cortes internos 5a y 5b |
| 6 | Recordatorios y dashboard (F10+F9) | F10 lee tareas, vencimientos y cobros; F9 consume casi todas las tablas. Cortes internos 6a y 6b |
| 7 | Carga de datos + deploy + producción | Único criterio de terminado operativo: abandonar el Excel con confianza |

Cada etapa se ejecuta con Claude Code (salvo la 1, con Claude Design), se verifica contra su criterio de "terminado" y recién entonces se avanza. Las pruebas manuales complementan, no reemplazan, la suite pytest.

---

## 2. Etapa 0 — Fundación técnica

### Objetivo
Esqueleto completo del proyecto funcionando, sin ninguna funcionalidad de negocio.

### Alcance

**Estructura del proyecto (arquitectura en capas):**

```
app/
├── main.py              # arranque de FastAPI
├── routes/              # capa de rutas (endpoints)
├── services/            # capa de servicios (lógica de negocio)
├── models/              # capa de datos (clases SQLAlchemy)
├── schemas/             # validaciones Pydantic
├── templates/           # Jinja2 (por ahora, solo login y página base)
├── static/              # CSS del framework elegido en Etapa 1
alembic/                 # migraciones
tests/                   # pytest
```

**Modelo de datos completo — 16 tablas en la migración inicial:**
- Las 12 del Chat 2 + `clientes_regimen_historial` (Chat 3) + `auditoria` + `scheduler_ejecuciones` (Chat 4) + `usuario_login` (definida acá).
- Cambios consolidados aplicados: `clave_dgi` en enum de credenciales, `mes_generacion` en templates, `silenciado_hasta` y estado `cerrado` en recordatorios, `created_at`/`updated_at` automáticos en todas las tablas.
- Todo como clases SQLAlchemy + migración inicial de Alembic que crea el esquema completo.
- El esquema completo se define desde el día uno: el modelo ya está cerrado desde el Chat 3, evita migraciones intermedias y la auditoría cubre todo desde el inicio.

**Nueva tabla `usuario_login` (resuelve el pendiente del Chat 4):**

| Campo | Tipo | Notas |
|---|---|---|
| id | INT PK | |
| usuario | TEXT NOT NULL | |
| password_hash | TEXT NOT NULL | bcrypt |
| intentos_fallidos | INT NOT NULL default 0 | |
| bloqueado_hasta | DATETIME nullable | |
| created_at / updated_at | DATETIME | estándar |

**Auditoría automática:** event listeners de SQLAlchemy configurados una vez, aplicando a todas las tablas (creación, edición, eliminación → `auditoria` con `datos_antes`/`datos_despues`). Campos cifrados de `credenciales` como `[cifrado]`.

**Autenticación:** login con sesión por cookie firmada (`Secure` + `HttpOnly`), expiración 7 días, bloqueo 5 intentos → 15 minutos con registro en `auditoria`. Toda ruta salvo el login exige sesión. Alta del usuario inicial por script de línea de comandos (una sola vez), sin pantalla de registro.

**Base de configuración:** secretos por variables de entorno desde el primer día (secreto de firma de cookies; Fernet y email se suman en sus etapas). Zona horaria America/Montevideo. `.env` local + `.env.example` en el repo sin valores reales.

**pytest configurado:** estructura de tests + fixture de base SQLite temporal. Tests de la propia etapa: login (correcto, incorrecto, bloqueo), auditoría, migración inicial.

### Lo que NO incluye
Ningún CRUD de negocio, scheduler (E5), cifrado Fernet (E4), diseño visual (HTML mínimo; el CSS llega de la E1).

### Criterio de "terminado"
1. `alembic upgrade head` sobre base vacía crea las 16 tablas.
2. Login funcional: autenticarse y ver la página base.
3. 5 errores de contraseña → bloqueo 15 minutos → intento registrado en `auditoria`.
4. Acceso sin sesión a cualquier ruta → redirección al login.
5. Insertar/editar/borrar un registro de prueba desde consola → aparece en `auditoria` con antes/después correctos.
6. Suite pytest completa en verde.

---

## 3. Etapa 1 — Diseño de UI con Claude Design

### Objetivo
Diseño visual completo del MVP + segunda pasada de validación funcional (regla transversal, sección 0).

### Insumo: inventario de las 26 vistas (del Chat 3)

**Navegación principal:**
1. Dashboard (F9): ingresos del mes, P&L, accesos rápidos
2. Listado de clientes (F1): dos secciones, filtro de inactivos
3. Vista global de cobros (F5): clientes por saldo descendente
4. Tareas del período (F7): agrupadas por cliente, semáforo, fecha límite
5. Calendario mensual de vencimientos (F8)
6. Panel de recordatorios — campanita (F10)

**Ficha del cliente y sus secciones:**
7. Datos generales + historial de regímenes (F1)
8. Servicios contratados (F4)
9. Vault de credenciales: listado + detalle (F2)
10. Estado de cuenta: saldo, cobros, descuentos (F5)
11. Historial de honorarios consolidado (F6)
12. Próximos vencimientos del cliente (F8)

**Formularios y flujos:**
13. Crear/editar cliente + flujo de cambio de régimen (F1)
14. Crear/editar credencial (F2)
15. Contratar/finalizar servicio (F4)
16. Registrar cobro / registrar descuento (F5)
17. Cambio individual de honorario (F6)
18. Aumento global de honorarios — 3 pasos (F6)
19. Crear tarea ad-hoc (F7)

**Configuración:**
20. Servicios (F3)
21. Templates de tareas (F7)
22. Vencimientos (F8)
23. Notificaciones — email destino (F10)

**Otras vistas:**
24. Histórico mensual + proyección futura (F9)
25. ABM de gastos/ingresos propios (F9)
26. Login (de la Etapa 0, se le aplica el diseño)

### Cómo se trabaja
1. **Primera decisión:** CSS framework (Pico.css vs Bootstrap) — condiciona el HTML de referencia.
2. **Sistema de diseño base primero** (colores, tipografía, layout de navegación, componentes repetidos: tablas, formularios, semáforos, indicadores verde/rojo), después las vistas **por grupos** en el orden del inventario, con revisión y confirmación por grupo.
3. **Registro de hallazgos** en el momento, clasificados MVP / post-MVP, consolidados al final como adenda al Chat 3.
4. **Salida:** HTML/CSS de referencia por vista, que Claude Code traduce a templates Jinja2 en las etapas siguientes.

### Responsive
Las vistas de uso móvil frecuente — **tareas del período, registro de cobros, dashboard, vault** — se diseñan y aprueban explícitamente en versión móvil. El resto: solo desktop con el responsive básico del framework.

### Criterio de "terminado"
1. Las 26 vistas con diseño aprobado.
2. HTML/CSS de referencia generado y organizado por vista.
3. Hallazgos clasificados y adendas al Chat 3 redactadas (o registro explícito de "sin hallazgos").
4. Ninguna decisión visual o funcional abierta que bloquee a Claude Code.

---

## 4. Etapa 2 — Núcleo de clientes y servicios (F1 + F3 + F4)

### Objetivo
Primer bloque funcional real, ya con el diseño final de la Etapa 1.

### Alcance
**F1 — completa según Chat 3:** listado con dos secciones (mensual/eventual derivado de contratos) y filtro de inactivos; ficha con datos generales + historial de regímenes (las demás secciones llegan en sus etapas: credenciales E4, estado de cuenta E3, vencimientos E5); crear/editar con todas las validaciones (RUT 12 dígitos, unicidad RUT/CI contra todos incluidos inactivos); flujo de cambio de régimen con `clientes_regimen_historial`; desactivar.

**F3 — completa:** Configuración → Servicios con listado, crear, editar, desactivar/reactivar; unicidad de nombre; restricción de cambio de frecuencia con contratos activos.

**F4 — completa salvo generación de tareas:** listado en ficha, contratar (con primer registro en `honorarios_historial`), editar fecha de inicio, finalizar; validaciones (no duplicar mensual/anual activo, honorario > 0). **Excepción explícita:** el paso "generación de tareas según F7" al contratar queda pendiente hasta la Etapa 5; la función existe vacía, con nota, como punto de integración marcado.

**Nota:** la ficha muestra el honorario vigente por contrato, pero el cambio de honorario (F6) llega en la Etapa 3. En esta etapa el honorario solo se define al contratar.

### Criterio de "terminado"
1. Ciclo completo de cliente: crear, ver en el listado en la sección correcta, editar, cambiar régimen (con historial visible), desactivar, encontrar con el filtro.
2. Todas las validaciones de F1 responden con sus mensajes exactos del Chat 3.
3. Catálogo de servicios cargable, restricción de frecuencia verificada.
4. Contratar un servicio (honorario inicial en el historial), duplicado de mensual rechazado, finalizar contrato (cierra honorario y contrato).
5. Todo con el diseño de la Etapa 1.
6. Suite pytest en verde, cobertura alta en servicios: derivación mensual/eventual, unicidades, mecánica de regímenes, cierre de contratos.

---

## 5. Etapa 3 — Dinero (F5 + F6)

### Objetivo
Reemplazar la parte más crítica del Excel. Al cerrar: sistema usable para lo esencial (clientes + servicios + cobros).

### Alcance
**F5 — completa:** estado de cuenta con cálculo de saldo (honorarios esperados por período impago − descuentos − cobros, usando el honorario vigente **de cada período** según historial) e indicador verde/rojo; listados de cobros y descuentos; vista global por saldo descendente con acceso directo al registro; registrar cobro con todas las validaciones (períodos van juntos, importe > 0, fecha no futura, rango multi-mes en un solo cobro); registrar descuento desde la ficha; editar/eliminar ambos (eliminación física con confirmación, rastro en `auditoria`); recálculo de saldo en cada operación.

**F6 — completa:** mecánica append-only común (cerrar vigente + insertar nuevo); cambio individual con validaciones y advertencia de cambio retroactivo con recálculo; aumento global en 3 pasos (parámetros → selección con redondeo hacia arriba a múltiplo de 10, editable por fila, ninguno preseleccionado → confirmación); historial por contrato y consolidado por cliente.

**Foco de testing (decisión 9, Chat 4):** el cálculo de saldo es la lógica más delicada de la app. Cobertura obligatoria de casos borde: contrato iniciado a mitad de mes, cambio retroactivo de honorario, cobro multi-período, descuento parcial, contrato finalizado con períodos impagos.

### Criterio de "terminado"
1. Saldo verificado a mano contra el Excel con un caso real (datos copiados a mano, sin migrar).
2. Cobro multi-mes → saldo correcto.
3. Descuento aplicado → saldo lo refleja.
4. Cambio de honorario retroactivo → advertencia → recálculo con el honorario correcto por período.
5. Aumento global de prueba: redondeo esperado (ej: $5.700 × 8,5% → $6.190), fila editada a mano, historiales correctos.
6. Vista global ordena por deuda y lleva al formulario de cobro.
7. Editar/eliminar cobro → saldo recalculado, rastro en `auditoria`.
8. Suite pytest en verde con los casos borde cubiertos en servicios.

---

## 6. Etapa 4 — Vault de credenciales (F2)

### Objetivo
Eliminar el riesgo de seguridad crítico. Etapa corta y autocontenida.

### Alcance
**Cifrado Fernet (decisión 6, Chat 4):** funciones de cifrado/descifrado en la capa de servicios; `FERNET_KEY` se suma al `.env`; la clave se genera una sola vez con instrucción documentada de guardarla en el gestor de contraseñas personal **antes** de cargar credenciales reales; si la clave no está configurada, la app falla al arrancar con mensaje claro.

**F2 — completa:** sección "Credenciales" en la ficha; listado (tipo, usuario en claro, contraseña oculta con ojo por fila, última actualización); detalle, crear, editar (recifra y actualiza fecha), eliminar (física, con confirmación, rastro `[cifrado]` en `auditoria`); validaciones (tipo obligatorio, al menos usuario o contraseña); revelar/ocultar vía HTMX — el descifrado ocurre en el servidor solo al pedir revelar, la contraseña en claro nunca viaja al navegador antes.

**Verificación de la regla de auditoría:** acá se prueba en serio que `auditoria` registra `[cifrado]` y nunca el valor (ni cifrado ni en claro). El listener genérico de la Etapa 0 recibe acá su excepción específica — test obligatorio.

**Definición operativa:** al cerrar esta etapa se cargan solo credenciales **de prueba**. Las credenciales reales migran en la Etapa 7, cuando existan respaldos diarios funcionando. Motivo: mientras la app corre solo en la PC local, migrar credenciales reales sin respaldo automático es un riesgo innecesario.

### Criterio de "terminado"
1. Crear credencial → en la base (consulta directa) los tres campos sensibles son texto cifrado ilegible.
2. En la app se ven en claro solo al revelar; el ojo alterna por fila.
3. Editar → recifra y la fecha de actualización cambia sola.
4. Eliminar → confirmación previa; en `auditoria` los campos sensibles dicen `[cifrado]`.
5. Arrancar sin `FERNET_KEY` → falla con mensaje claro.
6. Simular pérdida de clave (cambiarla por otra) → credenciales existentes indescifrables; restaurar la clave correcta después. Confirma que "sin clave no hay datos" es real.
7. Suite pytest en verde: cifrado/descifrado, validaciones, excepción de auditoría.

---

## 7. Etapa 5 — Tareas y vencimientos (F7 + F8) + scheduler

### Objetivo
Eliminar la dependencia de la memoria: checklist por régimen con generación automática, calendario de vencimientos, fecha límite y semáforo. Es la etapa más grande: se ejecuta con **dos cortes internos de verificación** (5a y 5b); el corte 5a se verifica antes de que Claude Code arranque 5b.

### Alcance

**Scheduler (decisión 5, Chat 4):** APScheduler dentro de la app + proceso mensual (día 1); registro en `scheduler_ejecuciones` + recuperación al arranque (¿corrió el mensual este mes? si no, ejecuta ya). El proceso diario se completa en la Etapa 6.

**Herramienta de desarrollo:** mecanismo para disparar el proceso mensual a demanda (comando o script). Es seguro por diseño (anti-duplicados, re-ejecutable). No es pantalla de la app.

**Corte 5a — F7 completa:**
- Configuración → Templates de tareas: CRUD con validaciones (unicidad servicio+régimen+nombre, `mes_generacion` obligatorio si el servicio es anual).
- Generación automática día 1: mensuales + anuales según `mes_generacion`, anti-duplicado, re-ejecutable.
- **Se completa la integración pendiente de la Etapa 2:** generación al contratar (mensual a mitad de mes genera el período en curso, único desde templates si existen, anual no genera).
- Tareas ad-hoc.
- Vista "Tareas del período": filtros, agrupada por cliente, indicador X de Y, transiciones de estado (cancelar con confirmación), edición limitada.
- Casos borde: cambio de régimen, contrato finalizado, template desactivado.

**Corte 5b — F8 completa:**
- Configuración → Vencimientos: CRUD con la regla del día inexistente (31 en abril → último día real).
- Calendario mensual navegable, detalle por vencimiento con clientes alcanzados.
- Vista próximos 15 días + sección próximos 30 días en la ficha.
- Conexión con F7: fecha límite por cliente/período + semáforo verde/amarillo/rojo en la vista de tareas.

### Criterio de "terminado"

**Corte 5a:**
1. Templates cargados para un servicio mensual y un anual (con `mes_generacion`), validaciones funcionando.
2. Proceso mensual a demanda → genera las tareas correctas; segunda ejecución → no duplica.
3. Contratar mensual a mitad de mes → tareas del período en curso generadas al instante.
4. Ciclo de estados completo de una tarea, incluida cancelación con confirmación y reapertura.
5. Matar la app, borrar el registro del mensual en `scheduler_ejecuciones`, arrancar → lo ejecuta solo.

**Corte 5b:**
6. Vencimientos cargados (incluido uno con día 31 para verificar meses cortos).
7. Calendario mensual correcto, con clientes alcanzados por régimen.
8. Vistas de 15 días y de la ficha (30 días) responden a la regla de aplicabilidad.
9. Fecha límite correcta por cliente y semáforo cambiando según tareas completadas o proximidad de fecha (simulable moviendo fechas de vencimientos de prueba).
10. Suite pytest en verde: matching de templates, anti-duplicados, generación al contratar, regla de aplicabilidad, cálculo del semáforo.

---

## 8. Etapa 6 — Recordatorios y dashboard (F10 + F9)

### Objetivo
El sistema persigue al contador (recordatorios persistentes) y muestra la foto financiera (dashboard, histórico, proyección). Última etapa de desarrollo funcional. Dos cortes internos (6a y 6b); 6a se verifica antes de arrancar 6b.

### Alcance

**Se completa el scheduler — proceso diario (06:00 Uruguay):** evaluación de recordatorios (generación, repetición 24 hs, reapertura de silenciados, cierre automático) + envío del email resumen + respaldo diario de la base (la lógica se construye acá; en desarrollo respalda a carpeta local, el destino externo real se configura en la Etapa 7) + recuperación al arranque también para el diario. Falla de email no bloquea el ciclo (queda en `scheduler_ejecuciones`).

**Corte 6a — F10 completa:**
- Los tres tipos con sus reglas exactas del Chat 3: `tarea_pendiente` (10 días corridos, repite cada 24 hs), `vencimiento_proximo` (5/2/1 días, sin repetición), `cobro_pendiente` (un mes completo después del período, evaluado el día 1 dentro del proceso mensual, repite cada 24 hs). Anti-duplicados por tipo.
- Panel campanita: contador, orden definido, acciones (ir al elemento, silenciar).
- Silenciar 3/5/7 días con restricciones por fecha límite (opciones deshabilitadas si superan el vencimiento).
- Cierre automático por causa desaparecida — incluida la reevaluación al registrar cobros en F5 (punto de integración con la Etapa 3).
- Email resumen diario: un solo email, solo si hay activos no silenciados, template Jinja2, agrupado por tipo, destino configurable en Configuración → Notificaciones.
- **Acá se resuelve el pendiente Brevo vs Resend** (condiciones vigentes al momento) y se integra por API con la key en variable de entorno. El email se prueba de verdad en esta etapa, llegando a la casilla real — no queda para el deploy.

**Corte 6b — F9 completa:**
- Dashboard como pantalla inicial: ingresos del mes (esperado/cobrado/diferencia con barra), P&L del mes, accesos rápidos (vencimientos F8, tareas F7, deudores F5).
- Cálculo del esperado con sus reglas exactas: mensuales por honorario vigente, anuales por `mes_generacion` (el menor si hay varios), únicos excluidos.
- Histórico mensual 12 meses navegable + proyección futura 6 meses con su leyenda.
- ABM de gastos/ingresos propios con filtros y totales.

**Nota de prueba:** los recordatorios se prueban con datos de fechas movidas (consola o script de desarrollo) y disparando el diario a demanda. Los tests automáticos cubren las reglas sin trucos.

### Criterio de "terminado"

**Corte 6a:**
1. Con fechas movidas: se genera un recordatorio de cada tipo con su mensaje exacto del Chat 3.
2. Diario disparado dos veces → no duplica; `fecha_enviada` se actualiza en la repetición.
3. Silenciar → sale de panel y email; vencido el silencio → reaparece. Opciones deshabilitadas correctamente cerca de la fecha límite.
4. Completar tarea / registrar cobro / pasar la fecha → el recordatorio se cierra solo.
5. Email resumen llega a la casilla con contenido agrupado correcto; sin activos, no se envía.
6. Falla simulada de email (key inválida) → el ciclo continúa y el error queda registrado.

**Corte 6b:**
7. Dashboard con esperado/cobrado/diferencia verificables a mano.
8. P&L cruza cobros + ingresos propios − gastos, indicador correcto.
9. Histórico de 12 meses usa el honorario vigente de cada mes (verificable con un cambio de honorario de por medio).
10. Proyección de 6 meses refleja la cartera actual, anuales en su mes.
11. ABM de gastos/ingresos con validaciones y totales del filtro.
12. Suite pytest en verde: reglas de los tres tipos, anti-duplicados, silenciado y restricciones, cierre automático, esperado/cobrado/diferencia, proyección.

---

## 9. Etapa 7 — Carga de datos + deploy + producción

### Objetivo
Pasar de "app terminada en la PC" a "sistema en producción que reemplaza al Excel". Criterio de terminado operativo: dejar de usar el Excel con confianza.

### Alcance — en orden estricto

**7.1 — Resolución de pendientes de infraestructura:**
- Railway vs Render, con precios vigentes.
- Cloudflare R2 vs Backblaze B2 para respaldos.
- (Brevo vs Resend ya resuelto en la Etapa 6.)

**7.2 — Deploy inicial (con base vacía):**
- Repo en GitHub, deploy desde push, HTTPS verificado.
- Variables de entorno en la plataforma: clave Fernet, key de email, secreto de cookies, credenciales del storage de respaldos.
- Clave Fernet respaldada en el gestor de contraseñas **antes** de cargar ninguna credencial real.
- Scheduler corriendo en producción (verificable en `scheduler_ejecuciones` al día siguiente).
- **Respaldo diario funcionando contra el storage externo real + restauración de prueba:** bajar el respaldo, levantarlo localmente, verificar que abre y descifra. Un respaldo nunca probado no es un respaldo.

**7.3 — Carga de datos inicial (directo en producción):**
- Catálogo de servicios (los 8 registros del Chat 3).
- **Templates de tareas por régimen — se resuelve el diferido del Chat 3:** antes de cargar, el contador define los pasos concretos del checklist por régimen (trabajo de estandarización propio; puede ser una sesión de trabajo aparte). La app solo los recibe.
- Calendario de vencimientos del año (calendarios oficiales DGI/BPS).
- Migración desde el Excel: clientes (regímenes y fechas de inicio reales), contratos con honorarios vigentes, y saldos históricos según la definición siguiente.

**Definición cerrada — saldos históricos: opción A (corte limpio):**
- Los contratos entran con `fecha_inicio` = fecha de migración.
- El saldo previo de cada cliente se ajusta con un registro inicial (cobro o descuento de ajuste con nota "saldo inicial migración").
- El Excel queda como archivo histórico de todo lo anterior. No se migran cobros históricos.
- Motivo: el objetivo es operar hacia adelante, no reconstruir el pasado; la carga completa es larga y cada error distorsiona saldos.

**7.4 — Paralelo y corte:**
- **Un mes calendario completo** operando app y Excel en paralelo: todo se registra en los dos lados.
- Al cierre del mes: saldos coincidentes, generación automática del día 1 corrió bien, email diario llega.
- Recién ahí: migrar las credenciales reales al vault, borrar la pestaña de credenciales del Excel, y el Excel pasa a archivo histórico.

### Criterio de "terminado"
1. App en producción con HTTPS, accesible desde el celular.
2. `scheduler_ejecuciones` muestra el diario corriendo solo, días consecutivos.
3. Respaldo externo verificado con restauración de prueba exitosa.
4. Datos iniciales cargados: catálogo, templates por régimen, vencimientos del año, clientes y contratos reales.
5. Mes de paralelo cerrado con saldos coincidentes app vs Excel.
6. Credenciales reales migradas al vault y eliminadas del Excel.
7. **El Excel ya no se usa para operar.**

---

## 10. Decisiones tomadas en este chat (consolidado)

| # | Decisión |
|---|---|
| 1 | La etapa de UI se ubica **antes** del desarrollo funcional (Etapa 1), como segunda pasada de validación funcional |
| 2 | Regla de adendas: hallazgos de diseño → adenda formal al Chat 3, clasificados MVP/post-MVP, antes de escribir código |
| 3 | Tabla `usuario_login` definida → **16 tablas** en la migración inicial (resuelve pendiente del Chat 4) |
| 4 | Responsive explícito solo para vistas de uso móvil frecuente: tareas del período, registro de cobros, dashboard, vault |
| 5 | Etapas 5 y 6 con cortes internos de verificación (5a/5b, 6a/6b) |
| 6 | Brevo vs Resend se resuelve en la Etapa 6 (el email se prueba de verdad ahí, no en el deploy) |
| 7 | Credenciales reales migran recién en la Etapa 7, con respaldos funcionando; hasta ahí, solo de prueba |
| 8 | Saldos históricos: **opción A — corte limpio** con ajuste de saldo inicial; el Excel queda como archivo histórico |
| 9 | Procesos del scheduler disparables a demanda como herramienta de desarrollo (seguro por anti-duplicados) |

## Pendientes actualizados

| Pendiente | Cuándo se resuelve |
|---|---|
| CSS framework (Pico.css vs Bootstrap) | Etapa 1, primera decisión |
| Brevo vs Resend | Etapa 6 |
| Railway vs Render | Etapa 7.1, con precios vigentes |
| Cloudflare R2 vs Backblaze B2 | Etapa 7.1 |
| Contenido concreto de templates de tareas por régimen | Etapa 7.3 (estandarización previa del contador) |
| 2FA | Post-MVP evaluable |

---

## 11. Estado del anteproyecto

Con este documento el anteproyecto queda **completo**:

- Chat 1 — Relevamiento del negocio ✔
- Chat 2 — Funcionalidades y modelo de datos ✔
- Chat 3 — Requerimientos funcionales granulares ✔
- Chat 4 — Stack tecnológico ✔
- Chat 5 — Plan de desarrollo por etapas ✔ (este documento)

**Antes de ejecutar: revisión final del plan completo** (los 5 entregables juntos, buscando inconsistencias entre documentos). Luego comienza la ejecución: Etapa 0 con Claude Code, Etapa 1 con Claude Design, y de ahí en adelante según este plan.

---
---

# Instrucciones para iniciar la ejecución — Etapa 0 con Claude Code

Pegá esto al comienzo de la sesión de Claude Code, junto con los entregables de los Chats 2, 3, 4 y 5 en el repositorio (carpeta `/docs` sugerida):

---

## Contexto del proyecto

Soy Contador Público en Uruguay. Esta app gestiona mi estudio contable independiente (~12 clientes mensuales + eventuales). El anteproyecto completo está en `/docs`: modelo de datos (Chat 2 + cambios de Chats 3 y 4), requerimientos granulares F1–F10 (Chat 3), stack tecnológico (Chat 4) y plan de desarrollo por etapas (Chat 5).

## Mi perfil

Python y FastAPI nivel básico-intermedio. No soy desarrollador profesional. Voy a leer y auditar todo el código que generes: necesito código claro, comentado donde la lógica no sea obvia, sin construcciones avanzadas innecesarias.

## Reglas de trabajo

- Ejecutá **solo la Etapa 0** según el entregable del Chat 5. No avances a ninguna funcionalidad de negocio.
- Nada que no esté definido en los documentos se inventa: si encontrás una decisión no tomada, frenás y me preguntás.
- Requisitos transversales del Chat 4, obligatorios desde el primer archivo: arquitectura en capas (rutas → servicios → datos), funciones de responsabilidad única, secretos solo en variables de entorno, validaciones en la capa de aplicación, zona horaria America/Montevideo, migraciones siempre con Alembic.
- Trabajá en ciclo código → pytest → corrección hasta suite completa en verde.
- Al terminar, dejame la lista de verificación manual del criterio de "terminado" de la Etapa 0 con instrucciones exactas de cómo probar cada punto.

## Alcance de la Etapa 0

[Ver sección "Etapa 0 — Fundación técnica" del entregable del Chat 5: estructura del proyecto, 16 tablas con migración inicial, auditoría automática por event listeners, login de usuario único con bloqueo, base de configuración y pytest.]

---

*Entregable Chat 5 completo. Fin del anteproyecto.*
