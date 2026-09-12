# Estudio Contable — Adenda de Revisión Final
*Revisión cruzada de los 5 entregables del anteproyecto. Este documento enmienda los entregables de los Chats 2, 3, 4 y 5. Se agrega a `/docs` junto a los cinco entregables y tiene precedencia sobre ellos en los puntos que modifica.*

**Fecha de cierre:** setiembre 2026
**Estado:** todas las enmiendas confirmadas. El anteproyecto queda cerrado con este documento.

---

## 1. Cambios al modelo de datos (afectan la migración inicial — Etapa 0)

El total de tablas de la migración inicial **se mantiene en 16**. Los cambios son a campos y enums.

### A1 — Tabla `recordatorios`: campos de referencia por tipo

**Problema:** F10 (Chat 3) define anti-duplicados y cierre automático que dependen de conocer el vencimiento, cliente o período asociado a cada recordatorio, pero el modelo solo tenía `tarea_id`. La lógica quedaba imposible de implementar sin parsear el texto del mensaje.

**Cambio:** se agregan cuatro campos nullable a `recordatorios`:

| Campo | Tipo | Restricciones | Notas |
|---|---|---|---|
| vencimiento_id | INT | FK → vencimientos_calendario, nullable | Usado por `vencimiento_proximo` |
| cliente_id | INT | FK → clientes, nullable | Usado por `cobro_pendiente` |
| periodo | DATE | nullable | Usado por `cobro_pendiente` (primer día del mes impago) |
| umbral_dias | INT | nullable | Usado por `vencimiento_proximo` (5, 2 o 1) |

**Uso por tipo:**
- `tarea_pendiente`: solo `tarea_id`. Anti-duplicado por `tarea_id` + tipo mientras haya uno activo (sin cambios).
- `vencimiento_proximo`: `vencimiento_id` + `umbral_dias`. Anti-duplicado por `vencimiento_id` + `umbral_dias` + fecha del vencimiento. Cierre automático: pasa la fecha del vencimiento referenciado.
- `cobro_pendiente`: `cliente_id` + `periodo`. Anti-duplicado por `cliente_id` + `periodo`. Cierre automático: el período referenciado queda cubierto.

### A2 — Enum `accion` de `auditoria`: valor `login_fallido`

**Problema:** el Chat 4 exige registrar intentos fallidos de login en `auditoria`, pero el enum solo tenía `creacion`, `edicion`, `eliminacion`.

**Cambio:** enum `accion` = `creacion`, `edicion`, `eliminacion`, `login_fallido`.

Registro de un intento fallido: `tabla = 'usuario_login'`, `registro_id` = id del usuario, `datos_antes` y `datos_despues` = null.

### A3 — `created_at` / `updated_at` en `tareas`: uniformidad total

**Problema:** el Chat 4 (nota al cambio 6) eximía a `tareas` de `created_at`; el Chat 5 (Etapa 0) decía "todas las tablas". Contradicción directa.

**Resolución:** gana la uniformidad. **Todas las tablas, incluida `tareas`, llevan `created_at` y `updated_at` automáticos.** Los event listeners se configuran una vez, sin excepciones. `fecha_creacion` y `fecha_completada` se mantienen en `tareas` como campos de negocio de F7. La redundancia entre `fecha_creacion` y `created_at` es aceptada a cambio de simplicidad.

La nota al cambio 6 del Chat 4 queda sin efecto.

### A4 — Enum `regimen`: nuevo valor `pequena_empresa`

**Problema:** la cartera incluye (o incluirá) clientes en régimen de pequeña empresa (Literal E / IVA mínimo), no contemplado en el enum.

**Cambio:** enum `regimen` = `unipersonal_prof`, `unipersonal_no_prof`, `monotributo`, `pequena_empresa`, `regimen_general`, `persona_fisica`.

Aplica en todas las tablas que usan el enum: `clientes`, `clientes_regimen_historial`, `tarea_templates` (+ `todos`), `vencimientos_calendario` (+ `todos`).

---

## 2. Enmiendas a requerimientos funcionales (Chat 3)

### B1 — F5: definición completa del cálculo de saldo

**Problema:** F5 limitaba el saldo a contratos activos, pero la Etapa 3 (Chat 5) exige como caso de test "contrato finalizado con períodos impagos" — contradicción directa. Además, la fórmula de "períodos impagos" solo estaba definida para servicios mensuales.

**Enmienda — el cálculo de saldo se redefine con tres reglas que aplican en conjunto:**

**(a) Contratos considerados:** el saldo incluye contratos **activos y finalizados**. Para los finalizados, los períodos se computan hasta `fecha_fin`. Finalizar un contrato no borra la deuda pendiente.

**(b) Contratos anuales:** generan **un cargo esperado por año**, imputado al mes de `mes_generacion` de sus templates (el menor si hay varios), usando el honorario vigente en ese mes. Un contrato anual sin templates no genera cargo esperado (solo se refleja al cobrarse). Criterio alineado con el "esperado del mes" de F9.

**(c) Contratos únicos:** el honorario se adeuda **como cargo único desde la `fecha_inicio` del contrato**, usando el honorario vigente a esa fecha.

La fórmula general queda:

```
Saldo = Σ cargos esperados (mensuales por período + anuales por año + únicos)
      − Σ descuentos aplicados
      − Σ cobros recibidos
```

El resto de F5 (indicadores, listados, validaciones de cobros y descuentos) no cambia.

### B2 — F4: visibilidad de contratos finalizados

**Problema:** F4 define que `fecha_fin` de los servicios únicos representa la duración real del trabajo, "insumo para cotizar trabajos futuros", pero ninguna vista mostraba contratos finalizados. El dato existía pero era inaccesible.

**Enmienda:** la sección "Servicios contratados" de la ficha del cliente incorpora un **toggle "mostrar finalizados"** (mismo patrón que el filtro de inactivos de F1). Con el toggle activo, los contratos finalizados se listan con sus columnas habituales más `fecha_fin`. Solo lectura.

**Clasificación:** hallazgo anticipado de la Etapa 1, **entra al MVP**. Afecta la vista 8 del inventario (Chat 5, Etapa 1). El párrafo "Lo que F4 NO hace" del Chat 3 queda enmendado en su segundo punto.

### C1 — F5: convención de período en cobros de servicios únicos

**Aclaración:** para cobros de servicios únicos, `periodo_desde` y `periodo_hasta` llevan ambos la **fecha real del trabajo** (excepción a la convención "primer/último día del mes"). La única validación aplicable es `periodo_hasta ≥ periodo_desde`; no existe validación adicional específica para únicos. Se elimina la ambigüedad de "el sistema lo valida si se ingresan ambos campos".

---

## 3. Enmienda al plan de desarrollo (Chat 5)

### C2 — Etapa 6: alcance del scheduler

**Aclaración:** la Etapa 6 no solo completa el proceso **diario**; también **extiende el proceso mensual** construido en la Etapa 5, agregándole la evaluación de `cobro_pendiente` (día 1, según F10). El alcance de la Etapa 6 debe leerse como: "se completa el proceso diario y se extiende el proceso mensual con la evaluación de cobros pendientes".

---

## 4. Verificado sin problemas

La revisión cruzada confirmó la consistencia de:

- Las 16 tablas de la migración inicial (12 del Chat 2 + `clientes_regimen_historial` + `auditoria` + `scheduler_ejecuciones` + `usuario_login`).
- La cadena de cambios consolidados Chat 3 → Chat 4 → Chat 5.
- Los puntos de integración diferidos: generación de tareas al contratar (E2 → E5) y reevaluación de recordatorios al registrar cobros (E3 → E6).
- El traslado de la decisión Brevo vs Resend del deploy a la Etapa 6.
- El corte limpio de saldos históricos (opción A) y su coherencia con la Etapa 7.
- Las 26 vistas del inventario contra los requerimientos de F1–F10 (con la única adición de B2).
- Pendientes y decisiones diferidas: sin contradicciones entre documentos.

---

## 5. Estado del anteproyecto

Con esta adenda, la revisión final queda **completa** y el anteproyecto **cerrado**:

- Chat 1 — Relevamiento del negocio ✔
- Chat 2 — Funcionalidades y modelo de datos ✔ (enmendado: A1, A2, A4)
- Chat 3 — Requerimientos granulares ✔ (enmendado: B1, B2, C1)
- Chat 4 — Stack tecnológico ✔ (enmendado: A3)
- Chat 5 — Plan de desarrollo ✔ (enmendado: C2)
- **Adenda de revisión final ✔ (este documento)**

**Instrucción para Claude Code:** este documento se agrega a `/docs` junto a los cinco entregables. Ante cualquier diferencia entre un entregable y esta adenda, **prevalece la adenda**.

Próximo paso: iniciar la **Etapa 0** con Claude Code según las instrucciones del entregable del Chat 5, incluyendo esta adenda en `/docs`.
