# Estudio Contable — Stack Tecnológico
*Entregable Chat 4 — base para Chat 5: Plan de desarrollo por etapas*

---

## Resumen de decisiones

| # | Área | Decisión |
|---|---|---|
| 1 | Backend | Python + FastAPI + SQLAlchemy + Alembic |
| 2 | Base de datos | SQLite (ruta futura documentada a PostgreSQL/Supabase) |
| 3 | Frontend | Server-rendered: Jinja2 + HTMX + CSS framework simple. Arquitectura en capas |
| 4 | Hosting y respaldos | PaaS (Railway o Render, plan pago always-on con disco persistente) + respaldo diario externo |
| 5 | Scheduler | APScheduler dentro de la app + tabla `scheduler_ejecuciones` + recuperación al arranque |
| 6 | Cifrado del vault | Fernet (librería `cryptography`) + clave en variable de entorno |
| 7 | Email | Transaccional por API (Brevo candidato principal, Resend alternativa) |
| 8 | Autenticación | Usuario único + bcrypt + sesión por cookie + bloqueo anti fuerza bruta |
| 9 | Testing | pytest — capa de tests robusta, ejecutada por Claude Code en ciclo código → test → corrección |

Costo recurrente total estimado: **5-10 USD/mes** (hosting + centavos de almacenamiento de respaldos). Todo lo demás es gratuito.

---

## Decisión 1 — Backend: Python + FastAPI + SQLAlchemy + Alembic

**Qué:**
- Lenguaje: Python. Framework web: FastAPI.
- ORM: SQLAlchemy — el modelo de datos se define una sola vez como clases de Python (fuente única de verdad); el CRUD se trabaja con objetos, sin SQL a mano.
- Migraciones: Alembic — historial versionado de cambios al esquema. Todo cambio futuro a la estructura de la base (campos nuevos, valores de enum) se aplica como migración sin perder datos, y es reversible.

**Por qué:**
- Es el único stack donde el usuario puede leer y auditar el código generado con Claude Code (Python nivel básico-intermedio).
- FastAPI + Pydantic implementan las validaciones de F1–F10 de forma declarativa.
- Alembic materializa el criterio del Chat 3 ("cambios de enums por intervención directa en la base") como migraciones seguras de pocas líneas en lugar de SQL manual.
- Escalable sin reescritura: soporta API JSON, portal de clientes (F16) y web pública (F15) futuros sin cambiar de framework.

---

## Decisión 2 — Base de datos: SQLite

**Qué:** SQLite — la base es un único archivo (`estudio.db`) en el disco persistente del hosting. Sin servidor de base de datos.

**Por qué:**
- Cero mantenimiento: no hay servidor que configurar, actualizar ni que pueda caerse. Cumple al máximo la restricción "mantenible por una sola persona".
- Respaldo trivial: copiar un archivo (ver decisión 4).
- El volumen real del negocio (~12 clientes, ~200 filas/mes) está órdenes de magnitud por debajo de los límites de SQLite.
- SQLAlchemy hace la validación de enums en la capa de aplicación (SQLite no la hace nativa); coherente con que todas las validaciones de F1–F10 viven en la aplicación.

**Ruta de migración documentada (no es un plan, es una opción):**
- Disparador real para PostgreSQL: multiusuario concurrente (portal de clientes F16 o web pública F15).
- Candidato: **Supabase en plan pago** (el usuario ya lo conoce por su base de finanzas personales). El plan gratuito queda descartado para este sistema: se pausa tras 7 días de inactividad y no ofrece garantías aceptables para credenciales de clientes.
- Gracias a SQLAlchemy + Alembic, la migración es: cambiar la cadena de conexión + ejecutar las migraciones contra la base nueva. El código de la app no se toca.

---

## Decisión 3 — Frontend: server-rendered con Jinja2 + HTMX

**Qué:**
- El backend genera el HTML con **Jinja2** (motor de plantillas integrado a FastAPI).
- **HTMX** para interacciones sin recarga de página completa: completar tareas y actualizar el semáforo, revelar/ocultar contraseñas, filtros, recálculo del honorario en el aumento global.
- CSS framework simple (Pico.css o Bootstrap) como base; el diseño final sale de la etapa de UI (ver hoja de ruta, Chat 5).
- Responsive: la app debe funcionar bien en celular (consultar tareas, registrar cobros). Depende del CSS, no del enfoque.

**Por qué:**
- Un solo lenguaje y un solo proyecto: sin ecosistema JavaScript (npm, builds) que mantener sin conocerlo.
- La app es formularios, tablas y listados — el caso ideal de server-rendered. Nada del MVP requiere SPA.
- Las validaciones viven una sola vez, en Python (una SPA las duplicaría en el frontend).

**Requisito arquitectónico — separación en capas (obligatorio desde el primer archivo):**

```
Capa de rutas (endpoints)  →  Capa de servicios (lógica de negocio)  →  Capa de datos (SQLAlchemy)
```

- Los endpoints solo reciben requests, llaman a servicios y devuelven HTML.
- Toda la lógica de negocio (validaciones, cálculo de saldos, generación de tareas, cifrado) vive en la capa de servicios.
- Funciones con responsabilidad única: cada función hace una sola cosa.
- **Beneficio directo:** si a futuro se quiere frontend React u otra interfaz, se agregan endpoints que devuelven JSON reutilizando los mismos servicios. El backend no se reescribe. No hay lock-in.

---

## Decisión 4 — Hosting: PaaS con instancia always-on + respaldo externo

**Qué:** la app corre en un PaaS — **Railway o Render** — en instancia paga always-on con disco persistente. Deploy desde GitHub (push = deploy). HTTPS automático de la plataforma.

**Por qué se descartaron las alternativas:**
- **PC propia:** incompatible con el scheduler (F7/F10 requieren procesos que corren aunque la PC esté apagada).
- **VPS:** administrar un servidor (parches, firewall, certificados) viola la restricción de mantenimiento unipersonal, y con credenciales de organismos estatales adentro un servidor mal mantenido es un riesgo real.
- **Planes gratuitos de PaaS:** incompatibles por diseño. En Render, los servicios gratuitos tienen filesystem efímero (la base SQLite se perdería en cada reinicio; los discos persistentes son solo para instancias pagas) y se apagan tras 15 minutos de inactividad (rompería el scheduler).

**Precios verificados (agosto 2026, a re-verificar al deploy):**
- **Render:** workspace Hobby $0 + instancia Starter always-on ~7 USD/mes + disco persistente ~0,25 USD/GB/mes. No se necesita el plan Pro de 25 USD (es cuota de workspace para equipos).
- **Railway:** plan Hobby, 5 USD/mes de uso mínimo con 5 USD de créditos incluidos; el consumo estimado de esta app (RAM ~0,2-0,5 GB, CPU marginal, volumen de centavos) probablemente quede dentro del mínimo.
- La elección final entre ambos se hace al momento del deploy con precios y condiciones vigentes. Ambos cumplen los requisitos: always-on + disco persistente.

**Respaldos — reglas:**
1. Proceso diario (dentro del scheduler, decisión 5) copia el archivo SQLite a almacenamiento externo: **Cloudflare R2 o Backblaze B2** (costo: centavos/mes).
2. Retención: diarios de los últimos 30 días + uno mensual histórico.
3. **El respaldo nunca vive solo en la misma plataforma que la app.** Si el proveedor pierde el disco, existe la copia de ayer en otro proveedor.
4. Los respaldos contienen las credenciales cifradas; sin la clave Fernet (decisión 6) son ilegibles. La clave se respalda por un camino separado, nunca junto a la base.

---

## Decisión 5 — Scheduler: APScheduler dentro de la app

**Qué:** APScheduler (librería Python) corriendo dentro del mismo proceso FastAPI. Los procesos programados son funciones normales de la capa de servicios, con acceso directo a la base y a la lógica de negocio.

**Procesos programados:**

| Proceso | Frecuencia | Contenido |
|---|---|---|
| Mensual | Día 1, antes del diario | Generación automática de tareas (F7) + evaluación de `cobro_pendiente` (F10) |
| Diario | Todos los días, 06:00 hora Uruguay | Evaluación de recordatorios: generación, repetición 24 hs, reapertura de silenciados, cierre automático (F10) + envío del email resumen (decisión 7) + respaldo de la base (decisión 4) |

El horario de 06:00 asegura que el email resumen llegue antes de arrancar el día. El día 1 el proceso mensual corre primero para que el diario evalúe recordatorios sobre las tareas recién generadas.

**Por qué:**
- Cero piezas nuevas: viaja con el código a cualquier plataforma (el cron de plataforma es configuración específica del proveedor y un servicio extra a pagar; Celery + Redis es sobre-ingeniería para 2 procesos diarios de segundos de duración).
- Funciona porque la instancia es always-on (decisión 4): el scheduler interno siempre está vivo.

**Recuperación ante caídas — tabla `scheduler_ejecuciones`:**
- Cada proceso registra su última ejecución exitosa (proceso, fecha, resultado).
- Al arrancar la app, el scheduler verifica: ¿el diario corrió hoy? ¿el mensual corrió este mes? Si no, ejecuta inmediatamente.
- Es seguro porque el Chat 3 definió toda la generación como re-ejecutable (anti-duplicados en tareas y recordatorios): no hay riesgo de duplicar ni de saltearse un día.
- Las fallas de subprocesos (ej: email caído) se registran acá sin bloquear el resto del ciclo.

---

## Decisión 6 — Cifrado del vault: Fernet + clave en variable de entorno

**Qué:** los campos `usuario`, `password` y `notas` de `credenciales` (F2) se cifran/descifran en la capa de servicios con **Fernet** (librería `cryptography` de Python). La base solo almacena texto cifrado.

**Por qué Fernet:**
- Cifrado simétrico (una clave cifra y descifra) — lo correcto cuando la misma app hace ambas cosas.
- Es una "receta cerrada": AES-128 + verificación de integridad, con todas las decisiones criptográficas ya tomadas por expertos. Elimina la posibilidad de errores de implementación propios del cifrado armado a mano.
- Estándar de facto en Python; uso de dos líneas, auditable.

**Gestión de la clave:**
1. La clave Fernet se genera **una sola vez** y vive en una **variable de entorno secreta** de la plataforma de hosting. **Nunca en el código, nunca en GitHub, nunca en la base de datos.**
2. Copia de respaldo de la clave en el gestor de contraseñas personal del usuario — camino separado del respaldo de la base.

> **⚠️ Si se pierde la clave, las credenciales cifradas son irrecuperables. Por diseño.** No existe "recuperar contraseña". Restaurar un respaldo de la base también requiere la clave. Base y clave se respaldan siempre por caminos separados.

**Lo que NO se hace:**
- No se cifra la base entera (SQLCipher): el objetivo de F2 es proteger credenciales, no toda la base; el resto no justifica la complejidad operativa.
- No hay rotación programada de claves. Procedimiento de emergencia documentado ante sospecha de filtración: generar clave nueva + script de recifrado (a generar con Claude Code en el momento).

---

## Decisión 7 — Email: transaccional por API

**Qué:** el email resumen diario (F10) se envía mediante un **servicio de email transaccional por API** (llamada HTTPS, no SMTP). El HTML del email se arma con un template Jinja2 (mismo motor del frontend).

**Candidatos (a definir al momento del deploy con condiciones vigentes):**
- **Brevo — candidato principal:** permite verificar una dirección individual como remitente, sin dominio propio. El email sale desde la propia casilla del usuario, enviado por los servidores de Brevo.
- **Resend — alternativa:** sin dominio verificado solo permite envío a la propia casilla de registro con remitente genérico (modo de prueba). Pasa a ser opción equivalente si al deploy se cuenta con dominio propio.

**Por qué API y no SMTP:**
- Los PaaS suelen bloquear o restringir puertos SMTP salientes (prevención de spam). Una llamada HTTPS esquiva el problema por completo.
- Gmail SMTP descartado: el usuario opera en ecosistema Microsoft/Outlook, y acoplaría el sistema a políticas de Google fuera de su control.
- Volumen (~30 emails/mes) entra por dos órdenes de magnitud en cualquier plan gratuito.

**Reglas:**
1. API key del proveedor en variable de entorno (mismo criterio que la clave Fernet).
2. No se requiere dominio propio para el MVP. Si a futuro existe dominio (F15), se configura entonces.
3. **Falla de envío no bloquea el ciclo diario:** se registra el error en `scheduler_ejecuciones` y el ciclo continúa. El panel en la app es la fuente; el email es un espejo.
4. Dirección de destino configurable (F10, Configuración → Notificaciones): cambiar de casilla no toca código.

---

## Decisión 8 — Autenticación: usuario único con sesión por cookie

**Qué:** login propio en la app: un solo usuario, usuario + contraseña.

- **Contraseña de login hasheada con bcrypt.** Distinción clave: las credenciales de los *clientes* se cifran con Fernet porque hay que poder leerlas; la contraseña de login se *hashea* (irreversible) porque solo hay que verificarla.
- **Sesión por cookie firmada**, marcada `Secure` + `HttpOnly` (no accesible por JavaScript). Es el mecanismo natural para server-rendered (JWT es para APIs consumidas por SPAs; no aplica).
- **Expiración:** 7 días sin uso → nuevo login.
- **Anti fuerza bruta:** 5 intentos fallidos → bloqueo de 15 minutos. Implementado en la propia app. Los intentos fallidos se registran en `auditoria`.
- HTTPS garantizado por la plataforma (decisión 4): la cookie siempre viaja cifrada.

**Lo que NO se hace:**
- No OAuth (Google/Microsoft): dependencia externa innecesaria para un usuario.
- No 2FA en el MVP: el modelo de amenaza (acceso no autorizado desde internet) queda cubierto por bcrypt + bloqueo + HTTPS. **Anotado como mejora post-MVP evaluable**, especialmente si algún día hay más usuarios.
- No recuperación de contraseña por email: con un usuario único, el reseteo es por intervención directa en la base (mismo criterio del Chat 3 para enums). Un flujo de recuperación es superficie de ataque sin beneficio.

---

## Decisión 9 — Testing: pytest con ciclo autónomo de Claude Code

**Qué:** capa completa de tests unitarios y de integración con **pytest** (estándar de Python). No es una capa "mínima viable": es un requisito de calidad del proyecto.

**Cómo se integra al desarrollo:**
- Claude Code trabaja en ciclo cerrado: escribe código → ejecuta pytest → lee los fallos → corrige → repite, hasta que la suite pasa completa. Los tests son la verificación automática de que lo construido cumple los requerimientos de F1–F10.
- El usuario audita el código y los tests, y realiza las pruebas manuales por etapa (criterio de "terminado" del Chat 5).

**Foco de la cobertura (dónde ser robusto):**
- **Capa de servicios — cobertura alta, prioridad máxima:** todas las reglas de negocio de F1–F10. Ejemplos: cálculo de saldos usando el honorario vigente por período, mecánica append-only de honorarios y regímenes, anti-duplicados de generación de tareas y recordatorios, redondeo del aumento global, restricciones de silenciado, cierre automático de recordatorios, cifrado/descifrado del vault.
- **Endpoints — cobertura más liviana:** casos principales y validaciones de entrada, usando el cliente de pruebas de FastAPI (simula requests sin levantar servidor).
- Los tests corren contra una base SQLite temporal, nunca contra datos reales.

**Principio:** robusto no es testear todo por igual — es cobertura exhaustiva donde un error cuesta plata o confianza (saldos, honorarios, generación automática, cifrado), y proporcional en el resto.

**Al Chat 5:** la estrategia detallada (qué tests exige cada etapa como parte de su criterio de "terminado") se define en el plan de desarrollo.

---

## Cambios consolidados al modelo de datos (respecto al Chat 3)

Decididos en este chat, se suman a los del Chat 3:

| # | Cambio | Origen |
|---|---|---|
| 6 | Campos `created_at` y `updated_at` (DATETIME, automáticos) en **todas** las tablas | Auditoría |
| 7 | Nueva tabla `auditoria` | Auditoría |
| 8 | Nueva tabla `scheduler_ejecuciones` | Decisión 5 |
| 9 | Almacenamiento del usuario de login (hash bcrypt) — estructura a definir en el plan de desarrollo (tabla mínima o configuración) | Decisión 8 |

Nota sobre el cambio 6: `tareas` conserva `fecha_creacion` y `fecha_completada` tal como están definidas en F7; solo se agrega `updated_at`.

### Nueva tabla: `auditoria`

Registro automático de toda creación, edición y eliminación en el sistema. Append-only: nunca se edita ni borra desde la app. Sin vista en la UI para el MVP (consulta directa a la base).

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| fecha | DATETIME | NOT NULL | |
| tabla | TEXT | NOT NULL | ej: `cobros` |
| registro_id | INT | NOT NULL | id del registro afectado |
| accion | ENUM | NOT NULL | `creacion`, `edicion`, `eliminacion` |
| datos_antes | TEXT (JSON) | nullable | null en creación |
| datos_despues | TEXT (JSON) | nullable | null en eliminación |

Reglas:
- Se escribe automáticamente vía event listeners de SQLAlchemy (se configura una vez, aplica a todas las tablas).
- **Los campos cifrados de `credenciales` se auditan como `[cifrado]`, nunca con el valor** (ni cifrado ni en claro): la tabla de auditoría no debe convertirse en copia paralela de credenciales.
- También registra los intentos fallidos de login (decisión 8).
- Con esta tabla, la eliminación física de cobros, descuentos y credenciales (F2/F5/F9) deja rastro: el registro borrado queda en `datos_antes`.

### Nueva tabla: `scheduler_ejecuciones`

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | INT | PK, autoincrement | |
| proceso | ENUM | NOT NULL | `diario`, `mensual` |
| fecha_ejecucion | DATETIME | NOT NULL | |
| resultado | TEXT | NOT NULL | `ok` o detalle del error |

La escribe y lee solo el scheduler. Sin UI.

---

## Requisitos transversales de implementación

Reglas que Claude Code debe respetar desde el primer archivo:

1. **Arquitectura en capas:** rutas → servicios → datos. Lógica de negocio solo en servicios. Funciones de responsabilidad única.
2. **Secretos solo en variables de entorno:** clave Fernet, API key de email, secreto de firma de cookies, credenciales de acceso al storage de respaldos. Nunca en código, GitHub ni base de datos.
3. **Todas las validaciones de F1–F10 en la capa de aplicación** (servicios + Pydantic), no delegadas a la base.
4. **Zona horaria:** America/Montevideo para toda la lógica de fechas y el scheduler.
5. **Migraciones siempre con Alembic:** ningún cambio de esquema por fuera.

---

## Pendientes anotados (no bloquean el desarrollo)

| Pendiente | Cuándo se resuelve |
|---|---|
| Elección final Railway vs Render | Al momento del deploy, con precios vigentes |
| Elección final Brevo vs Resend | Al momento del deploy, con condiciones vigentes |
| Elección final Cloudflare R2 vs Backblaze B2 | Al momento del deploy |
| Elección CSS framework (Pico.css vs Bootstrap) | Etapa de diseño de UI |
| Estructura exacta del usuario de login | Plan de desarrollo (Chat 5) |
| 2FA | Post-MVP evaluable |

---

*Entregable Chat 4 completo.*

---
---

# Instrucciones para iniciar el Chat 5

Pegá esto al comienzo del Chat 5 como contexto inicial:

---

## Contexto del proyecto

Soy Contador Público en Uruguay. Trabajo de forma independiente llevando la contabilidad de ~12 clientes mensuales (unipersonales profesionales y no profesionales, monotributos, régimen general) y clientes eventuales. También trabajo en relación de dependencia en Ricoh Uruguay y estudio en ORT Uruguay.

Estoy diseñando el anteproyecto completo de una app de gestión para mi estudio contable **antes de escribir código**. Los chats anteriores definieron: relevamiento del negocio (Chat 1), funcionalidades + modelo de datos (Chat 2), requerimientos funcionales granulares de las 10 funcionalidades MVP (Chat 3), y stack tecnológico completo (Chat 4). Este es el Chat 5, el último del anteproyecto.

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
- El plan debe estar pensado para ejecutarse con Claude Code, por etapas verificables, con criterios claros de "terminado" en cada una.

## Entregables previos (base para este chat)

[PEGAR ACÁ EL ENTREGABLE DEL CHAT 2 — modelo de datos]
[PEGAR ACÁ EL ENTREGABLE DEL CHAT 3 — requerimientos granulares]
[PEGAR ACÁ EL ENTREGABLE DEL CHAT 4 — stack tecnológico]

---

## Chat 5 — Plan de desarrollo por etapas

**Objetivo:** definir el plan de construcción de la app, por etapas, listo para ejecutar con Claude Code.

**Entregable:** documento con la hoja de ruta completa de desarrollo, cubriendo:

- División del desarrollo en etapas ordenadas por dependencia (qué se construye primero y por qué)
- Alcance exacto de cada etapa: qué funcionalidades (F1–F10) o partes de ellas incluye
- Criterio de "terminado" verificable por etapa (qué tengo que poder hacer/probar para dar la etapa por cerrada)
- **Etapa de diseño de UI con Claude Design:** ubicada después de definir las vistas y antes de construir el frontend. Insumo: el inventario de vistas de F1–F10 del Chat 3 (listados, fichas, dashboard, calendario, checklist con semáforo). Resultado: diseños y HTML/CSS de referencia que Claude Code traduce a templates Jinja2.
- **Estrategia de pruebas robusta con pytest (decisión 9 del Chat 4):** qué tests exige cada etapa como parte de su criterio de "terminado". Claude Code trabaja en ciclo código → test → corrección hasta suite en verde. Cobertura alta en la capa de servicios (reglas de negocio de F1–F10); proporcional en endpoints. Las pruebas manuales del usuario complementan, no reemplazan, la suite automática.
- Momento de la carga de datos inicial (catálogo de servicios, templates de tareas, calendario de vencimientos, migración de datos del Excel actual)
- Momento del primer deploy y de la puesta en producción real (cuándo se abandona el Excel)

**Restricciones a respetar:**
- Mantenible por una sola persona sin equipo técnico
- Etapas chicas y verificables: cada una debe dejar algo funcionando
- El código será generado con asistencia de Claude Code
- Priorizar llegar rápido a un sistema usable con lo esencial (clientes + servicios + cobros) y sumar el resto por etapas

**Metodología sugerida:** definir primero el orden de etapas y su justificación, luego el detalle de cada una, con confirmación antes de pasar a la siguiente. Al final, generar el entregable del Chat 5. Con ese documento queda completo el anteproyecto y comienza la ejecución con Claude Code.
