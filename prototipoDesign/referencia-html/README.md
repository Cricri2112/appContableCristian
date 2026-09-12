# HTML de referencia — Estudio Contable (Etapa 1)

Un archivo estático por vista, generado desde el prototipo navegable. Es la referencia visual que Claude Code traduce a templates Jinja2 en las Etapas 2–6.

## Qué hay

- `NN-nombre.html` — una vista (o un estado de una vista: diálogo abierto, paso de wizard). Números según el inventario de 26 vistas del Chat 5; `a/b/c` para estados de la misma vista; prefijo `m` para las versiones móvil (dashboard, tareas, cobros, vault, registrar cobro).
- `nocturne.css` — sistema de diseño (tokens + clases `.btn .tag .card .table .field .input .seg .dialog`).
- `pico-map.css` — mapeo Pico.css ↔ Nocturne + colores semánticos de la app.
- `index.html` — índice.

## Cómo traducirlo

1. **Base**: Pico.css (`pico.min.css`) → `nocturne.css` → `pico-map.css`, en ese orden, en el layout base de Jinja2. Pico da reset, grilla y formularios nativos; Nocturne las clases de componentes; `pico-map.css` alinea las variables `--pico-*` con los tokens.
2. **Estilos inline**: el HTML de referencia lleva estilos inline (así se generó). Al traducir a Jinja2 se pueden mover a clases utilitarias propias o dejarse inline: el resultado visual debe ser el mismo. No introducir otra paleta.
3. **Cascarón**: `aside` (212px, sticky) + barra superior (fecha, campanita con contador, salir) + `main`. En móvil (`body.movil`): barra inferior de 5 entradas; Vencimientos y Configuración bajo "Más".
4. **Colores semánticos** (ver `pico-map.css`): saldo > 0 → `--color-danger-text`; saldo ≤ 0 → `--color-ok-text`. Semáforo de grupo de tareas: verde (todo completado/cancelado), amarillo (pendientes y > 5 días), rojo (pendientes y ≤ 5 días o vencido). Organismos: DGI acento, BPS neutro claro, Otro neutro medio.
5. **Formatos**: importes `$ 6.190` (punto de miles, sin decimales salvo que existan, `−` para negativos), fechas `dd/mm/aaaa`, períodos `jun 2026`, vacíos `—`.
6. **Mensajes de validación**: son los literales del Chat 3; van debajo del campo con borde rojo + ícono `ph-warning-circle`.
7. **Íconos**: Phosphor (regular). Los `<i class="ph ph-...">` se mantienen tal cual.
8. **Interacciones ya representadas**: estado de tarea = un clic avanza pendiente → en proceso → completada (sin diálogo); cancelar tarea y eliminaciones físicas = diálogo de confirmación; toggles "mostrar inactivos/finalizados"; revelar contraseña con ojo por fila; silenciar recordatorio con 3/5/7 días inline.

## Mapa vista → etapa

| Archivos | Función | Etapa |
|---|---|---|
| 26 | Login | E0 (se le aplica el diseño en E2) |
| 02, 07, 13, 20, 20b, 08, 15a, 15b | F1, F3, F4 | E2 |
| 03, 10, 16a, 16b, 11, 17, 18a–d, m03, m16 | F5, F6 | E3 |
| 09, 14, m09 | F2 | E4 |
| 04, 19, 21, 21b, 05, 12, 22, 22b, 06, 23, m04 | F7, F8, F10 | E5 |
| 01, 24a, 24b, 25, 25b, m01 | F9 | E6 |

## Regenerar

Abrir `referencia/exportar.html` en el proyecto → "Generar zip". Toma el prototipo actual como fuente, así que cualquier cambio aprobado en el prototipo se propaga con un clic.
