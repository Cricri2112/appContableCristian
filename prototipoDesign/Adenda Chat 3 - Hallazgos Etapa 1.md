# Estudio Contable — Adenda al Chat 3: hallazgos de la Etapa 1 (Diseño de UI)
*Cierre de la Etapa 1 — se lee junto con el Chat 3 (requerimientos) y el Chat 5 (plan)*

---

## 0. Resumen

Diseñadas y aprobadas las 26 vistas del inventario (+ estados de diálogo y 5 versiones móvil) sobre el sistema de diseño Nocturne con Pico.css como base. Durante el trabajo surgieron **10 hallazgos**: 7 clasificados **MVP** (ninguno cambia el modelo de datos; todos son derivados, ubicación o copy), 1 **técnico** y 2 **post-MVP**. No quedan decisiones visuales ni funcionales abiertas que bloqueen la Etapa 2.

Decisiones de la Etapa 1 que el Chat 5 dejaba abiertas y quedaron resueltas:

| Pendiente en Chat 5 | Resolución |
|---|---|
| CSS framework | **Pico.css** + `nocturne.css` + `pico-map.css` (ver `referencia/README.md`) |
| Ubicación del aumento global (F6) | Vista completa de 3 pasos, accesible desde **Cobros** como acción secundaria (H-08) |
| Cómo se muestra el detalle de vencimiento en el calendario (F8) | Panel lateral fijo en la misma vista, con lista "próximos 15 días" debajo (H-05) |
| Vistas móvil | Dashboard, tareas, cobros (lista + registrar), vault. Barra inferior de 5 entradas |

---

## 1. Registro de hallazgos

| # | Hallazgo | Función | Clasificación | Impacto en Chat 3 |
|---|---|---|---|---|
| H-01 | Pico.css se usa solo como reset, grilla y formularios nativos; los tokens de Nocturne sobreescriben las variables `--pico-*`. | — | Técnico | Ninguno. Documentado en `referencia/pico-map.css`. |
| H-02 | La barra lateral muestra junto a "Tareas" el total **X/Y completadas del período** (suma de los progresos por cliente que F7 ya calcula). | F7 | MVP | Agregar a F7 → "Vista: tareas del período": *"El total de completadas/total del período (excluyendo canceladas) se expone también en la navegación principal."* |
| H-03 | Los recordatorios `cobro_pendiente` ofrecen **"Registrar cobro"** como acción directa (abre el formulario F5 precargado con el cliente). | F10 | MVP | Precisar en F10 → acciones: *"Ir al elemento relacionado: vencimiento → calendario; tarea → tareas del período; cobro → formulario de cobro con cliente preseleccionado."* |
| H-04 | La vista global de cobros muestra en cabecera **Total adeudado** (suma de saldos > 0) y **A favor** (suma de saldos < 0) de clientes activos. | F5 | MVP | Agregar a F5 → "Vista global de cobros" los dos totales como derivados. |
| H-05 | En el calendario, el detalle del vencimiento (regímenes, clientes alcanzados) es un **panel lateral** en la misma vista, con la lista de próximos 15 días debajo. Clic en un evento del mes o en la lista lo selecciona. | F8 | MVP | Cierra el "se define en UI" de F8. Sin cambio funcional. |
| H-06 | El estado de cuenta muestra un **mapa de períodos del año** (cubierto / impago) para el servicio mensual, más el desglose del saldo (esperado impago − descuentos − cobros). | F5 | MVP | Agregar a F5 → "Vista: estado de cuenta": *"Se muestra el detalle del cálculo del saldo vigente y qué períodos del año están cubiertos."* Es la misma fórmula, presentada. |
| H-07 | **"Cambiar honorario"** y **"Finalizar"** como acciones directas en la fila del contrato, además del detalle. | F4/F6 | MVP | Solo ubicación. Sin cambio. |
| H-08 | El **aumento global** vive en Cobros como acción secundaria ("Aumento global de honorarios"), no en Configuración ni en la ficha. | F6 | MVP | Cierra el "ubicación a definir" de F6. |
| H-09 | El diálogo de **finalizar servicio** enumera las consecuencias (cierra honorario, tareas pendientes quedan, deuda no se borra). | F4 | MVP (copy) | Sin cambio funcional; copy a mantener en el template. |
| H-10 | **Notificaciones** muestra el último estado de los procesos diario y mensual (`scheduler_ejecuciones`), solo lectura, dos filas. | F10 / infra | MVP | Agregar a F10 → "Configuración: notificaciones": *"Se muestra fecha, hora y resultado de la última ejecución de cada proceso programado."* El Chat 4 dejaba esa tabla "sin UI"; el costo es una consulta. |

### Post-MVP (registrados, no diseñados)

| # | Idea | Motivo de exclusión |
|---|---|---|
| P-01 | Filtro por cliente en la vista de tareas con búsqueda incremental (hoy: `select` simple). | Con ~20 clientes el `select` alcanza. |
| P-02 | Gráfico de barras en histórico mensual (hoy: tabla con barra de % cobrado por fila). | La tabla resuelve la comparación; un gráfico suma dependencia JS. |

---

## 2. Convenciones visuales que Claude Code debe respetar

Detalladas en `referencia/README.md`. Las que afectan comportamiento:

- **Cambio de estado de tarea**: un clic sobre el tag avanza pendiente → en proceso → completada; completada/cancelada vuelven a pendiente con un clic. Solo **cancelar** pide confirmación (F7 ya lo indica; acá se fija que el resto no la pide).
- **Confirmación destructiva** únicamente para eliminaciones físicas (credencial, cobro, descuento, gasto/ingreso) y cancelar tarea. Desactivar cliente/servicio/template/vencimiento: un clic, sin diálogo, reversible.
- **Silenciar recordatorio**: opciones 3 / 5 / 7 días inline en el ítem; 7 deshabilitado cuando excede la fecha del vencimiento (regla de F10).
- **Semáforo** solo en el encabezado del grupo por cliente; nunca por tarea individual. Sin vencimientos aplicables: sin punto ni fecha límite.
- **Saldo**: verde/rojo por signo, mismo tratamiento en ficha, vista global, dashboard y móvil.
- **Móvil**: hit targets ≥ 44px; tablas pasan a lista de tarjetas; registrar cobro es pantalla completa.

---

## 3. Entregables de la Etapa 1

| Entregable | Ubicación |
|---|---|
| Sistema de diseño base (tokens, tipografía, cascarón, componentes) | `01 Sistema base.dc.html` |
| Prototipo navegable con las 26 vistas + móvil | `Prototipo Estudio Contable.dc.html` (tweak `pantalla`: escritorio / móvil) |
| HTML de referencia por vista (41 archivos) + CSS | `referencia/exportar.html` → genera `referencia-html.zip` |
| Mapeo Pico ↔ Nocturne | `referencia/pico-map.css` |
| Esta adenda | `Adenda Chat 3 — Hallazgos Etapa 1.md` |

**Criterio de "terminado" del Chat 5 (§3):** 1 ✓ 26 vistas aprobadas · 2 ✓ HTML organizado por vista · 3 ✓ hallazgos clasificados y adenda · 4 ✓ sin decisiones abiertas.
