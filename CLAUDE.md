# CLAUDE.md — App de gestión del estudio contable

## Qué es este proyecto

App de gestión para un estudio contable independiente en Uruguay (~12 clientes mensuales en distintos regímenes + eventuales). El anteproyecto está **completo y cerrado**: funcionalidades, requerimientos granulares, modelo de datos, stack y plan por etapas. **Nada se inventa**: si encontrás una decisión no tomada en los documentos, frená y preguntame antes de avanzar.

## Quién soy (el usuario)

Contador Público, no desarrollador profesional. Python y FastAPI nivel básico-intermedio. Voy a **leer y auditar todo el código**: necesito código claro, comentado donde la lógica no sea obvia, sin construcciones avanzadas innecesarias. Explicaciones en español, directas, sin relleno.

## Documentación — orden de precedencia

Toda la especificación vive en `mdscontexto/`:

| Documento | Contenido |
|---|---|
| `chat1-entregable.md` | Relevamiento del negocio |
| `entregable_chat2.md` | Funcionalidades y modelo de datos (12 tablas base) |
| `entregable_chat3.md` | Requerimientos granulares F1–F10 (comportamiento exacto, validaciones, mensajes literales) |
| `entregable_chat4.md` | Stack tecnológico y requisitos transversales |
| `entregable_chat5.md` | Plan de desarrollo por etapas (E0–E7) y criterios de "terminado" |
| `adenda_revision_final.md` | Enmiendas A1–A4, B1–B2, C1–C2 a los chats 2–5 |
| `Adenda Chat 3 - Hallazgos Etapa 1.md` | Hallazgos H-01 a H-10 del diseño de UI + convenciones visuales |

**Regla de precedencia:** ante cualquier diferencia, las **adendas prevalecen sobre los entregables**, y la adenda de la Etapa 1 (la más reciente) prevalece sobre la revisión final. Antes de implementar cualquier funcionalidad, leé su sección del Chat 3 **y** verificá si alguna adenda la enmienda.

## Diseño de UI (Etapa 1, ya cerrada)

En `prototipoDesign/`:

- `Adenda Chat 3 - Hallazgos Etapa 1.md` — copia de la adenda (la normativa está en `mdscontexto/`)
- `referencia/README.md` — **leer obligatoriamente antes de escribir cualquier template**: orden de carga de CSS, cascarón, colores semánticos, formatos de importes/fechas, íconos Phosphor, interacciones
- `referencia/pico-map.css` — mapeo Pico.css ↔ Nocturne
- `referencia-html/` — HTML estático de referencia por vista (41 archivos + `nocturne.css`), generado desde el prototipo. Es la fuente visual que se traduce a templates Jinja2 en las Etapas 2–6. **Si esta carpeta no existe todavía, avisame: se genera desde `referencia/exportar.html` en el prototipo.**

Convenciones visuales con efecto en comportamiento (detalle completo en la adenda de la Etapa 1, §2):
- Cambio de estado de tarea: un clic avanza pendiente → en proceso → completada; solo **cancelar** pide confirmación.
- Confirmación destructiva únicamente para eliminaciones físicas y cancelar tarea. Desactivar (cliente/servicio/template/vencimiento): un clic, sin diálogo.
- Saldo > 0 rojo, ≤ 0 verde, en todas las vistas.
- Mensajes de validación: los **literales exactos** del Chat 3, debajo del campo.

## Stack (Chat 4 — no discutible sin consultarme)

- **Backend:** Python + FastAPI + SQLAlchemy + Alembic
- **Base de datos:** SQLite (archivo único; ruta futura a PostgreSQL documentada, no implementada)
- **Frontend:** server-rendered — Jinja2 + HTMX + Pico.css + `nocturne.css` + `pico-map.css`
- **Scheduler:** APScheduler en el mismo proceso (Etapa 5+)
- **Cifrado vault:** Fernet, clave en variable de entorno (Etapa 4)
- **Email:** transaccional por API (Etapa 6)
- **Auth:** usuario único, bcrypt, sesión por cookie firmada, bloqueo anti fuerza bruta
- **Testing:** pytest

## Requisitos transversales — obligatorios desde el primer archivo

1. **Arquitectura en capas:** `routes/` (endpoints) → `services/` (toda la lógica de negocio) → `models/` (SQLAlchemy). Los endpoints solo reciben requests, llaman servicios y devuelven HTML. Funciones de responsabilidad única.
2. **Secretos solo en variables de entorno** (secreto de cookies, Fernet, API keys). Nunca en código, GitHub ni base de datos. `.env` local + `.env.example` sin valores reales.
3. **Todas las validaciones en la capa de aplicación** (servicios + Pydantic), no delegadas a la base.
4. **Zona horaria:** America/Montevideo en toda la lógica de fechas y el scheduler.
5. **Migraciones siempre con Alembic.** Ningún cambio de esquema por fuera.
6. **Auditoría automática** vía event listeners de SQLAlchemy en todas las tablas; campos cifrados de `credenciales` se auditan como `[cifrado]`.
7. **Ciclo de trabajo:** código → pytest → corrección, hasta suite completa en verde. Cobertura alta en `services/` (reglas de negocio), proporcional en endpoints. Tests contra SQLite temporal, nunca datos reales.

## Plan de etapas y estado actual

| Etapa | Contenido | Estado |
|---|---|---|
| 0 | Fundación técnica: estructura, 16 tablas, auditoría, login, pytest | **← ACTUAL** |
| 1 | Diseño de UI | ✔ Cerrada (ver adenda de hallazgos) |
| 2 | F1 + F3 + F4 (clientes, servicios, contratos) | Pendiente |
| 3 | F5 + F6 (cobros, descuentos, honorarios) | Pendiente |
| 4 | F2 (vault de credenciales, Fernet) | Pendiente |
| 5 | F7 + F8 + scheduler (cortes 5a/5b) | Pendiente |
| 6 | F10 + F9 + email (cortes 6a/6b) | Pendiente |
| 7 | Carga de datos + deploy + producción | Pendiente |

**Regla de alcance:** trabajá **solo en la etapa actual**. No adelantes funcionalidades de etapas futuras aunque parezca conveniente. Los puntos de integración diferidos (ej. generación de tareas al contratar, E2 → E5) se dejan como función vacía con nota, según lo define el Chat 5.

**Al terminar cada etapa:** dejame la lista de verificación manual del criterio de "terminado" (Chat 5) con instrucciones exactas de cómo probar cada punto.

## Etapa 0 — alcance inmediato

Según Chat 5 §2, con las enmiendas de la adenda de revisión final:

- Estructura del proyecto en capas (`app/main.py`, `routes/`, `services/`, `models/`, `schemas/`, `templates/`, `static/`, `alembic/`, `tests/`).
- **Migración inicial con las 16 tablas**: 12 del Chat 2 + `clientes_regimen_historial` + `auditoria` + `scheduler_ejecuciones` + `usuario_login`. Aplicar los cambios consolidados de Chats 3 y 4 **y las enmiendas A1–A4** (campos de referencia en `recordatorios`, `login_fallido` en enum de auditoría, `created_at`/`updated_at` en TODAS las tablas incluida `tareas`, régimen `pequena_empresa`).
- Auditoría automática por event listeners.
- Login de usuario único: bcrypt, cookie firmada `Secure`+`HttpOnly`, expiración 7 días, bloqueo 5 intentos → 15 min con registro en `auditoria`. Alta del usuario inicial por script CLI.
- pytest configurado con fixture de base temporal. Tests: login (correcto, incorrecto, bloqueo), auditoría, migración inicial.
- **NO incluye:** CRUD de negocio, scheduler, cifrado Fernet, diseño visual (HTML mínimo; el CSS se integra en E2).

## Convenciones de código

- Idioma: código y comentarios pueden usar los nombres de dominio en español tal como están en el modelo de datos (`clientes`, `honorarios_historial`, etc.). No traducir nombres de tablas ni campos.
- Commits descriptivos en español.
- Los mensajes al usuario final (validaciones, confirmaciones) son los **literales exactos** del Chat 3 y sus adendas.
