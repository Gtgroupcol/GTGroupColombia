# ARQUITECTURA GENERAL - SISTEMA DE PRESTACIONES

**Archivo:** 01_ARQUITECTURA_GENERAL.md
**Versión:** 2.0

---

## 📐 ARQUITECTURA DEL SISTEMA

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│             SISTEMA DE PRESTACIONES SOCIALES                 │
│                   (Odoo 17 - Colombia)                       │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ MOTOR DE     │    │  PRESENTACIÓN│    │  ADAPTADORES │
│  CÁLCULO     │───▶│     (UI)     │◀───│   (PUENTE)   │
│              │    │              │    │              │
│prestaciones  │    │prestaciones  │    │prestaciones  │
│    .py       │    │  _detail.py  │    │_liquidacion  │
│              │    │              │    │_provisiones  │
└──────────────┘    └──────────────┘    └──────────────┘
      │                    ▲                     │
      │                    │                     │
      └────────────────────┴─────────────────────┘
              Flujo de datos unidireccional
```

---

## 🗂️ RESPONSABILIDADES POR ARCHIVO

### Tabla Resumen

| Archivo | Modelo | Propósito | Tipo | Lo que HACE | Lo que NO HACE |
|---------|--------|-----------|------|-------------|----------------|
| `prestaciones.py` | `hr.salary.rule.prestaciones` | **Núcleo de cálculo** | Motor | Calcula fórmulas, valida condiciones, orquesta flujo | NO formatea UI, NO adapta a hr_slip |
| `prestaciones_detail.py` | `hr.salary.rule.prestaciones.detail` | **Generador de detalle** | Presentación | Formatea datos en 12 secciones para widget | NO calcula valores, NO llama a calculate_prestacion |
| `prestaciones_liquidacion.py` | `hr.salary.rule.prestaciones.liquidacion` | **Puente a nómina** | Adaptador | Adapta resultado a formato hr_slip, maneja pagos | NO recalcula, solo reformatea |
| `prestaciones_provisiones.py` | `hr.salary.rule.prestaciones.provisiones` | **Provisiones y contabilidad** | Adaptador | Provisiones mensuales, consolidación, consultas contables | NO modifica contabilidad, solo consulta y reporta |

---

## 🎯 PRINCIPIO ÚNICO DE RESPONSABILIDAD

### Regla #1: Solo prestaciones.py CALCULA

```python
# ✅ CORRECTO
# prestaciones.py
def calculate_prestacion(localdict, tipo, context, provision_type):
    # ... calcula usando fórmulas matemáticas
    valor = (base * dias) / divisor
    return (base_diaria, dias, 100, nombre, "", detail)

# prestaciones_liquidacion.py
def _cesantias(localdict):
    result = prestaciones.calculate_prestacion(...)  # Llama y adapta
    return _adapt_result_for_slip(result, ...)

# ❌ INCORRECTO
# prestaciones_liquidacion.py
def _cesantias(localdict):
    valor = (base * dias) / 360  # ¡NO! No recalcular aquí
```

### Regla #2: prestaciones_detail.py SOLO presenta

```python
# ✅ CORRECTO
# prestaciones_detail.py
def generate(localdict, tipo, base_info, days_info, valor):
    # 'valor' ya está calculado, solo formatea
    return {
        'metricas': {
            'valor_total': valor,  # Usa el valor recibido
            'valor_total_fmt': f"${valor:,.0f}"
        }
    }

# ❌ INCORRECTO
def generate(localdict, tipo, base_info, days_info, valor):
    # NO llamar a calculate_prestacion aquí
    result = prestaciones.calculate_prestacion(...)
```

### Regla #3: Adaptadores NO recalculan

```python
# ✅ CORRECTO
def _adapt_result_for_slip(result, localdict, tipo):
    base_diaria, dias, porcentaje, nombre, log, detail = result
    monto_total = detail.get('metricas', {}).get('valor_total', 0)
    # Solo reformatea
    return (base_diaria * 30, dias, porcentaje, nombre, log, data)

# ❌ INCORRECTO
def _adapt_result_for_slip(result, localdict, tipo):
    # Recalcular aquí rompe el principio
    base = localdict['contract'].wage
    dias = 180
    valor = (base * dias) / 180  # ¡NO!
```

---

## 🔄 FLUJOS DE DATOS PERMITIDOS

### Flujo 1: Provisión Mensual

```
┌─────────────────────────────────────────────────────────┐
│ REGLA SALARIAL: PRV_CES (Provisión Cesantías)          │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ prestaciones_provisiones._prv_ces(localdict)            │
│   - Lee flag simple_provisions                          │
│   - Determina context y provision_type                  │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ prestaciones.calculate_prestacion(                      │
│     localdict,                                          │
│     tipo='cesantias',                                   │
│     context='provision',                                │
│     provision_type='porcentaje_fijo'                    │
│ )                                                       │
│                                                         │
│ Proceso interno:                                        │
│   1. _get_period() → periodo de cálculo                │
│   2. _calculate_days() → días trabajados               │
│   3. calculate_base_prestacion() → base mensual        │
│   4. _calculate_value() → aplica fórmula               │
│   5. prestaciones_detail.generate() → detalle UI       │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Retorna: (base_diaria, dias, 100, nombre, "", detail)  │
│                                                         │
│ detail = {                                              │
│     'metricas': {...},                                  │
│     'monto_total': 124950.0,  ← CRÍTICO                │
│     ...12 secciones...                                  │
│ }                                                       │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ prestaciones_provisiones._adapt_provision_result()      │
│   - Extrae monto_total del detail                      │
│   - Genera nombre descriptivo                          │
│   - Construye data dict para hr_slip                   │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Retorna: (124950, 1, 100, "PROVISION CESANTIAS", "", data) │
│                                                         │
│ Formato hr_slip:                                        │
│   amount = 124950                                       │
│   qty = 1                                               │
│   rate = 100                                            │
│   data['monto_total'] = 124950  ← hr_slip.py lo busca  │
└─────────────────────────────────────────────────────────┘
```

### Flujo 2: Liquidación de Contrato

```
┌─────────────────────────────────────────────────────────┐
│ REGLA SALARIAL: CESANTIAS (Liquidación)                │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ prestaciones_liquidacion._cesantias(localdict)          │
│   - Detecta struct_process = 'contrato'                │
│   - context = 'liquidacion'                             │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ prestaciones.calculate_prestacion(                      │
│     localdict,                                          │
│     tipo='cesantias',                                   │
│     context='liquidacion',  ← Usa contract.date_end    │
│     provision_type='simple'                             │
│ )                                                       │
│                                                         │
│ Proceso interno: (igual que provisión)                 │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ prestaciones_liquidacion._adapt_result_for_slip()       │
│   - Adapta a formato hr_slip                           │
│   - Agrega acum_line_ids si existen                    │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Retorna formato hr_slip para nómina                     │
└─────────────────────────────────────────────────────────┘
```

### Flujo 3: Consolidación Contable

```
┌─────────────────────────────────────────────────────────┐
│ REGLA SALARIAL: CONS_CES (Consolidación)               │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ prestaciones_provisiones._cons_ces(localdict)           │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ prestaciones_provisiones._calculate_consolidacion()     │
│                                                         │
│ PASO 1: Calcular obligación real                       │
│   └─> prestaciones.calculate_prestacion(               │
│           context='consolidacion'                       │
│       )                                                 │
│       Retorna: obligacion_real = $1,500,000            │
│                                                         │
│ PASO 2: Buscar provisiones acumuladas                  │
│   └─> _get_provision_acumulada(                        │
│           contract_id, tipo, periodo                   │
│       )                                                 │
│       Consulta hr.payslip.line                         │
│       Suma provisiones del periodo                     │
│       Retorna: provision_acumulada = $1,374,450        │
│                                                         │
│ PASO 3: Calcular ajuste                                │
│   ajuste = obligacion_real - provision_acumulada       │
│   ajuste = $1,500,000 - $1,374,450 = $125,550         │
│                                                         │
│ PASO 4: (Opcional) Consultar contabilidad              │
│   └─> _get_saldo_cuenta(...)                          │
│       Consulta account.move.line                       │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Retorna: (125550, 1, 100, "CONSOLIDACION...", data)    │
│                                                         │
│ data = {                                                │
│     'monto_total': 125550,                             │
│     'ajuste': 125550,                                  │
│     'obligacion_real': 1500000,                        │
│     'provision_acumulada': 1374450,                    │
│     'formula_explicacion': {...pasos...}               │
│ }                                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 🚫 FLUJOS PROHIBIDOS

### ❌ Detail llamando a calculate_prestacion

```python
# ❌ PROHIBIDO
class HrSalaryRulePrestacionesDetail:
    def generate(self, localdict, tipo, base_info, days_info, valor):
        # ¡NO! Detail no debe calcular
        result = self.env['hr.salary.rule.prestaciones'].calculate_prestacion(...)
```

### ❌ Adaptador recalculando valores

```python
# ❌ PROHIBIDO
class HrSalaryRulePrestacionesLiquidacion:
    def _cesantias(self, localdict):
        # ¡NO! No recalcular aquí
        base = localdict['contract'].wage
        dias = 360
        valor = (base * dias) / 360
        return (valor, ...)
```

### ❌ Modificar localdict

```python
# ❌ PROHIBIDO
def calculate_prestacion(localdict, tipo, context, provision_type):
    # localdict es ENTRADA, no salida
    localdict['valor_calculado'] = 1000  # ¡NO!
```

### ❌ Modificar base de datos directamente

```python
# ❌ PROHIBIDO
def _calculate_consolidacion(localdict, tipo):
    # NO modificar contabilidad, solo reportar
    move_line.write({'credit': ajuste})  # ¡NO!
```

---

## 📊 MATRIZ DE RESPONSABILIDADES

| Tarea | prestaciones.py | detail.py | liquidacion.py | provisiones.py |
|-------|----------------|-----------|----------------|----------------|
| Calcular fórmulas matemáticas | ✅ SÍ | ❌ NO | ❌ NO | ❌ NO |
| Determinar periodo | ✅ SÍ | ❌ NO | ❌ NO | ❌ NO |
| Calcular días y ausencias | ✅ SÍ | ❌ NO | ❌ NO | ❌ NO |
| Validar condiciones | ✅ SÍ | ❌ NO | ⚠️ Valida contexto | ❌ NO |
| Generar detalle UI (12 secciones) | ❌ NO | ✅ SÍ | ❌ NO | ❌ NO |
| Formatear para widget | ❌ NO | ✅ SÍ | ❌ NO | ❌ NO |
| Adaptar a formato hr_slip | ❌ NO | ❌ NO | ✅ SÍ | ✅ SÍ |
| Consultar hr.payslip.line | ❌ NO | ❌ NO | ❌ NO | ✅ SÍ (provisiones) |
| Consultar account.move.line | ❌ NO | ❌ NO | ❌ NO | ✅ SÍ (saldos) |
| Modificar base de datos | ❌ NO | ❌ NO | ❌ NO | ❌ NO |
| Llamar a calculate_prestacion() | - | ❌ NO | ✅ SÍ | ✅ SÍ |

---

## ⚙️ PARÁMETROS DE CONFIGURACIÓN

### Fuentes de Configuración (5)

```
┌─────────────────────────────────────────────────────────┐
│                  CONFIGURACIÓN                           │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────────┬──────────────┐
        ▼               ▼                   ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│hr.contract   │ │hr.contract   │ │hr.annual     │ │ir.config     │
│              │ │.type         │ │.parameters   │ │.parameter    │
│- wage        │ │- has_prima   │ │- smmlv       │ │- base_dias   │
│- modality    │ │- has_ces     │ │- aux_trans   │ │- tasas       │
│- date_start  │ │- is_aprendiz │ │- simple_prov │ │- porcentajes │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
        │               │                   │              │
        └───────────────┴───────────────────┴──────────────┘
                        │
                        ▼
                _get_conditions()
        Centraliza TODA la configuración
```

### Parámetros Críticos

| Parámetro | Fuente | Default | Impacto |
|-----------|--------|---------|---------|
| `simple_provisions` | hr.annual.parameters | False | Modo de provisión (simple vs completa) |
| `base_dias_prestaciones` | ir.config_parameter | 360 | Divisor para cesantías e intereses |
| `base_dias_prima` | ir.config_parameter | 180 | Divisor para prima |
| `tasa_intereses_cesantias` | ir.config_parameter | 0.12 | Tasa anual de intereses (12%) |
| `auxilio_prestaciones_metodo` | ir.config_parameter | 'dias_trabajados' | Método de cálculo de auxilio |

Ver archivo completo de parámetros en [01_ARQUITECTURA_GENERAL.md - Sección Parámetros]

---

## 🎯 REGLAS DE ORO

### 1. Separación de Responsabilidades
```
CALCULAR ≠ PRESENTAR ≠ ADAPTAR
```

### 2. Fuente Única de Verdad
```
Un solo lugar para calcular → prestaciones.calculate_prestacion()
```

### 3. Contratos Sagrados
```
NO romper contratos de entrada/salida
Especialmente: detail['monto_total'] es OBLIGATORIO
```

### 4. Inmutabilidad
```
NO modificar localdict
NO modificar registros de base de datos
Solo lectura y cálculo
```

### 5. Dependencias Críticas
```
Intereses SIEMPRE usa cesantias_calculadas
NUNCA recalcular cesantías dentro de intereses
```

---

## 📁 UBICACIÓN DE ARCHIVOS

```
lavish_hr_employee/
└── models/
    └── reglas/
        ├── prestaciones.py ...................... Motor de cálculo
        ├── prestaciones_detail.py ............... Generador de detalle
        ├── prestaciones_liquidacion.py .......... Adaptador de liquidación
        └── prestaciones_provisiones.py .......... Adaptador de provisiones

docs/
└── prestaciones/
    ├── 00_INDICE_PRINCIPAL.md
    ├── 01_ARQUITECTURA_GENERAL.md .............. Este archivo
    ├── 02_PRESTACIONES_CALCULO.md
    ├── 03_PRESTACIONES_DETALLE.md
    ├── 04_PRESTACIONES_LIQUIDACION.md
    ├── 05_PRESTACIONES_PROVISIONES.md
    ├── 06_PRESTACIONES_VACACIONES.md
    ├── 07_CONTRATOS_ENTRADA_SALIDA.md
    ├── 08_FORMULAS_DETALLADAS.md
    ├── 09_CASOS_ESPECIALES.md
    └── 10_PRUEBAS_Y_RECOMENDACIONES.md
```

---

## ✅ SIGUIENTE PASO

Después de entender la arquitectura, consultar:
- [07_CONTRATOS_ENTRADA_SALIDA.md](07_CONTRATOS_ENTRADA_SALIDA.md) - Contratos de datos
- [02_PRESTACIONES_CALCULO.md](02_PRESTACIONES_CALCULO.md) - Motor de cálculo

---

**Última Actualización:** 2026-01-27
