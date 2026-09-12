# Prompt para Claude Design — Etapa 1: Diseño de UI
*Pegar como primer mensaje en un proyecto nuevo de Claude Design (claude.ai/design). Adjuntar o pegar también el entregable del Chat 3 (requerimientos F1–F10), el del Chat 5 (Etapa 1, inventario de vistas) y la adenda de revisión final.*

---

## Contexto

Soy Contador Público en Uruguay. Estoy diseñando la interfaz completa de una app de gestión para mi estudio contable independiente (~12 clientes mensuales + eventuales). El anteproyecto está cerrado: funcionalidades, requerimientos granulares (F1–F10), modelo de datos y plan de desarrollo ya están definidos en los documentos adjuntos. Esta es la **Etapa 1: diseño de UI**, previa al desarrollo.

La app será server-rendered (FastAPI + Jinja2 + HTMX + **Pico.css** como base CSS). El resultado de este proyecto de diseño es **HTML/CSS de referencia por vista**, que Claude Code traducirá a templates Jinja2. El HTML debe ser realista y traducible: tablas, formularios y componentes estándar — nada que requiera JavaScript complejo o frameworks de frontend.

## Dirección visual

**Modo oscuro, minimalista.** Referencias: Linear (tipografía y espaciado), Supabase dashboard (tablas y datos en dark), Mercury (indicadores financieros).

- Fondo oscuro casi negro (no negro puro), superficies elevadas apenas más claras, bordes sutiles.
- Un solo color de acento, usado con moderación (links, botones primarios, elementos activos).
- Colores semánticos reservados para significado real:
  - **Verde:** cliente al día, saldo positivo del estudio, semáforo verde.
  - **Rojo:** cliente que debe, saldo negativo, semáforo rojo.
  - **Amarillo:** semáforo amarillo (tareas pendientes, vencimiento a más de 5 días).
- Tipografía sans-serif limpia, jerarquía por peso y tamaño, no por color.
- Números tabulares (alineados) en toda columna de importes.
- Densidad media: es una herramienta de trabajo diario, no un sitio de marketing. Tablas compactas pero legibles.
- Sin ilustraciones, sin gradientes decorativos, sin sombras pesadas. Todo lo que está en pantalla cumple una función.

## Metodología de trabajo — respetar estrictamente

1. **Primero el sistema de diseño, nada más.** Antes de diseñar cualquier vista: paleta completa (fondos, superficies, textos, acento, semánticos), tipografía y escala, layout de navegación general (barra lateral o superior — proponé y justificá), y los componentes repetidos: tabla de datos, formulario, botones (primario/secundario/peligro), badges de estado, semáforo verde/amarillo/rojo, indicador al día/debe, toggle de filtro, modal de confirmación, campanita de notificaciones con contador. Presentalo y **esperá mi aprobación antes de seguir**.
2. Después, las vistas **por grupos** en el orden de abajo. Un grupo por vez, con mi confirmación antes del siguiente.
3. **Registro de hallazgos:** si al diseñar detectás una mejora de comportamiento, una funcionalidad faltante o una inconsistencia con los requerimientos (Chat 3 + adenda), registrala explícitamente en el momento, clasificada como *entra al MVP* o *post-MVP*. No la resuelvas por tu cuenta en el diseño: la lista de hallazgos se consolida al final como adenda formal. Nada se inventa ni se decide en silencio.
4. Los textos de la interfaz van en **español rioplatense** (voseo: "Confirmás", "Ingresá"), usando los mensajes exactos definidos en el Chat 3 donde existan.
5. Los datos de ejemplo deben ser realistas del dominio: clientes con nombres uruguayos, regímenes reales (unipersonal profesional, monotributo, pequeña empresa, régimen general), importes en pesos uruguayos ($ con separador de miles), fechas dd/mm/aaaa, organismos DGI y BPS.

## Inventario de vistas — 26, por grupos

**Grupo 1 — Navegación principal (6):**
1. Dashboard (F9): ingresos del mes (esperado/cobrado/diferencia con barra de progreso), P&L del mes con indicador verde/rojo, accesos rápidos (próximos vencimientos, tareas pendientes, mayores deudores)
2. Listado de clientes (F1): dos secciones (mensuales/eventuales), filtro de inactivos
3. Vista global de cobros (F5): clientes ordenados por saldo descendente, acceso directo a registrar cobro
4. Tareas del período (F7): agrupadas por cliente, indicador X de Y completadas, fecha límite en el encabezado del grupo, semáforo de urgencia
5. Calendario mensual de vencimientos (F8): grilla navegable, color por organismo, detalle al clic
6. Panel de recordatorios — campanita (F10): contador, agrupado por tipo, acciones ir/silenciar (3/5/7 días)

**Grupo 2 — Ficha del cliente (6):**
7. Datos generales + historial de regímenes (F1)
8. Servicios contratados (F4) — con toggle "mostrar finalizados" (adenda B2)
9. Vault de credenciales: listado con contraseña oculta y ojo por fila + detalle (F2)
10. Estado de cuenta: saldo con indicador, listados de cobros y descuentos (F5)
11. Historial de honorarios consolidado (F6)
12. Próximos vencimientos del cliente — 30 días (F8)

**Grupo 3 — Formularios y flujos (7):**
13. Crear/editar cliente + flujo de cambio de régimen (F1)
14. Crear/editar credencial (F2)
15. Contratar/finalizar servicio (F4)
16. Registrar cobro / registrar descuento (F5)
17. Cambio individual de honorario (F6)
18. Aumento global de honorarios — asistente de 3 pasos (F6)
19. Crear tarea ad-hoc (F7)

**Grupo 4 — Configuración (4):**
20. Servicios (F3)
21. Templates de tareas (F7)
22. Vencimientos (F8)
23. Notificaciones — email de destino (F10)

**Grupo 5 — Otras (3):**
24. Histórico mensual 12 meses + proyección futura 6 meses (F9)
25. ABM de gastos/ingresos propios con filtros y totales (F9)
26. Login (diseño aplicado a la pantalla existente de la Etapa 0)

## Responsive

Cuatro vistas se usan frecuentemente desde el celular y requieren **versión móvil diseñada y aprobada explícitamente**: tareas del período (4), registro de cobros (16 + vista global 3), dashboard (1) y vault (9). El resto: desktop con el responsive básico de Pico.css.

## Criterio de cierre de la Etapa 1

1. Las 26 vistas con diseño aprobado (las 4 móviles en ambas versiones).
2. HTML/CSS de referencia exportable, organizado por vista.
3. Lista de hallazgos consolidada y clasificada MVP / post-MVP (o registro explícito de "sin hallazgos").
4. Ninguna decisión visual o funcional abierta que bloquee a Claude Code.

Empezá por el punto 1 de la metodología: el sistema de diseño.
