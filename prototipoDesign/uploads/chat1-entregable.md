# Estudio Contable — Operativa actual
*Documento base para el anteproyecto de la app de gestión*

---

## 1. Perfil del negocio

- Contador Público independiente, trabajando en solitario
- ~12 clientes mensuales activos + clientes eventuales en temporada
- Opera en paralelo con empleo en relación de dependencia (Ricoh Uruguay)
- Restricción de crecimiento actual: tiempo limitado por cursada en ORT
- Objetivo de crecimiento: post-graduación, incorporar más clientes con el tiempo liberado por la app
- Presión financiera concreta: cambio de franja CJPPU en febrero, requiere aumentar ingresos o reducir tiempo por cliente

---

## 2. Cartera de clientes mensuales

| Régimen | Clientes | Cantidad |
|---|---|---|
| Unipersonal profesional | Agustina, María José, Mauro, Camila, Mariela | 5 |
| Unipersonal no profesional | Roque, Miguel | 2 |
| Régimen general | Frutería, Pablo, Luis | 3 |
| Monotributo | Cuchi, Luciana | 2 |
| **Total** | | **12** |

---

## 3. Flujo de trabajo mensual

### 3.1 Variantes por tipo de cliente

| Variante | Descripción | Clientes típicos |
|---|---|---|
| Cuota fija | Se emite y envía boleto directamente, sin consultar al cliente | Monotributos, algunos unipersonales |
| Variable con info del cliente | Se le solicitan las facturas emitidas, se calculan IVA e IRPF, se emiten boletos | Unipersonales, régimen general |
| Acceso directo al sistema | Se descarga la info del facturador electrónico del cliente sin intermediación | Régimen general con sistema propio |

En todos los casos: se corrobora en DGI las facturas a favor para descontar IVA compras.

### 3.2 Tareas anuales
- Declaraciones juradas: IVA, IRPF, FONASA
- Se cobran aparte de los honorarios mensuales

### 3.3 Clientes eventuales
- Sin ficha ni registro formal — solo carpeta en el explorador
- Trabajos típicos: declaraciones de IRPF, certificados de ingresos, gestiones ante DGI/BPS
- Honorario definido por tipo de trámite o complejidad, sin tarifa formalizada

---

## 4. Herramientas actuales

### Excel — 5 pestañas

| Pestaña | Contenido |
|---|---|
| Clientes | ID, nombre, fecha inicio, honorario mensual, día de vencimiento, observaciones |
| Histórico de honorarios | ID, fechas, honorario por período — permite saber el honorario actual |
| Cobros | Fecha, ID cliente, período cubierto, importe, forma de pago, observaciones |
| Estado de cuenta | Cliente, meses facturados, total esperado, cobrado, diferencia, estado |
| Credenciales | RUT, usuario BPS, contraseña, CI, fecha de nacimiento, mail, clave PIN ⚠️ sin cifrado |
| Ingresos y gastos | Registro libre para calcular saldo mensual neto |

**Limitaciones del Excel actual:**
- El estado de cuenta solo controla honorarios mensuales; no contempla DDJJ ni trabajos eventuales
- Los descuentos se registran como pagos con método modificado (workaround)
- No hay vista unificada de ingresos reales (mensuales + eventuales)

### Carpetas en explorador

```
Unipersonal/
├── #Mi Empresa/
├── Base Empresa/
│   ├── 1 Datos Empresa/
│   ├── 2 Varios/
│   └── 3 Facturas Reportes Declaraciones/
│       └── [Año]/
├── Empresas/
│   └── [Base Empresa renombrada por cliente]
├── Eventuales/
│   └── [Carpeta por cliente con todo lo trabajado]
└── Trabajos/ (obsoleta)
```

### Comunicación
- Canal principal: WhatsApp (texto y audio)
- El historial de WPP es el único registro de comunicaciones con clientes

### Facturación propia
- Proveedor de facturación electrónica activo
- Uso parcial: algunos clientes con e-ticket, otros cobrados sin comprobante
- Clasificación: "facturado" / "no gravado" / "sin comprobante" — decisión del contador

### Vencimientos
- Gestionados de memoria o consultando la web de DGI/BPS en el mes
- Existen calendarios oficiales anuales publicados por DGI y BPS, diferenciados por régimen

---

## 5. Puntos de dolor — priorizados

| # | Problema | Impacto |
|---|---|---|
| 1 | Tareas no documentadas — todo en la cabeza | Alto: riesgo de olvido, no escalable |
| 2 | Credenciales de clientes en Excel sin cifrar | Alto: riesgo de seguridad crítico |
| 3 | Control de cobros no unifica mensuales + eventuales | Alto: no hay visión real de ingresos |
| 4 | Vencimientos de memoria o consulta manual | Medio: falla bajo carga, no automatizable |
| 5 | Sin recordatorios automáticos | Medio: depende de atención manual |
| 6 | Clientes eventuales sin ficha ni historial | Medio: duplica trabajo en temporada |
| 7 | Descuentos como workaround en cobros | Medio: distorsiona reportes |
| 8 | Conocimiento contable solo en la cabeza | Bajo ahora, alto al escalar |
| 9 | Sin estandarización de honorarios por tipo | Bajo: se maneja por experiencia |

---

## 6. Oportunidades detectadas

| Oportunidad | Valor | Prioridad |
|---|---|---|
| Flujo de trabajo estandarizado por régimen → checklist automático mensual | Elimina el punto de dolor #1 | MVP |
| Vault de credenciales cifrado | Elimina riesgo de seguridad #2 | MVP |
| Control de ingresos unificado (mensuales + eventuales + DDJJ) | Elimina punto de dolor #3 | MVP |
| Calendario de vencimientos automático por régimen | Elimina punto de dolor #4 | MVP |
| Ficha mínima de clientes eventuales | Elimina punto de dolor #6 | MVP |
| Proyección de ingresos mensual esperado vs cobrado | Clave para presión CJPPU | MVP |
| Descuentos como concepto propio, no workaround | Limpia reportes | MVP |
| Registro de comunicaciones por cliente | Trazabilidad sin depender de WPP | Post-MVP |
| Base de conocimiento contable consultable | Escalabilidad y respaldo ante consultas | Post-MVP |
| Web pública para captación de clientes | Crecimiento futuro | Futuro |

---

## 7. Restricciones y condicionantes del sistema

- Mantenido por una sola persona sin equipo técnico
- Debe cumplir con regulación uruguaya (DGI, BPS, CJPPU)
- Credenciales de clientes requieren cifrado — son claves de organismos estatales
- Facturación mixta: el sistema debe reflejar la realidad sin forzar ninguna clasificación
- Crecimiento planificado post-ORT: la arquitectura debe soportarlo sin reescritura

---

*Entregable Chat 1 completo.*

---
---

# Instrucciones para iniciar el Chat 2

Pegá esto al comienzo del Chat 2 como contexto inicial:

---

## Contexto del proyecto

Soy Contador Público en Uruguay. Trabajo de forma independiente llevando la contabilidad de ~12 clientes mensuales (unipersonales profesionales y no profesionales, monotributos, régimen general) y clientes eventuales. También trabajo en relación de dependencia en Ricoh Uruguay.

Estoy diseñando el anteproyecto completo de una app de gestión para mi estudio contable **antes de escribir código**. El Chat 1 fue el relevamiento del negocio. Este es el Chat 2.

## Perfil técnico

- Python y FastAPI: nivel básico-intermedio
- Manejo conceptos de base de datos, entidades y relaciones (estudio en ORT Uruguay)
- No soy desarrollador profesional
- Necesito explicaciones claras, sin asumir conocimiento avanzado

## Cómo trabajamos

- Un paso a la vez. Sin avanzar al siguiente hasta terminar el anterior.
- Si algo es vago o puede generar problemas, decímelo antes de avanzar.
- Si ves algo que estoy pasando por alto, decímelo aunque no te lo pregunte.
- Respuestas directas, sin relleno.

## Entregable del Chat 1 (base para este chat)

[PEGAR ACÁ EL CONTENIDO COMPLETO DEL DOCUMENTO DE ARRIBA]

---

## Chat 2 — Funcionalidades y modelo de datos

**Objetivo:** definir qué hace la app y cómo se estructuran los datos.

**Entregable:** listado de funcionalidades priorizadas (MVP vs post-MVP) y modelo de datos completo con entidades, atributos y relaciones.

**Pasos:**
1. Definir y priorizar funcionalidades
2. Diseñar el modelo de datos
3. Generar el entregable del Chat 2
