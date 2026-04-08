# CONTRATOS DE ENTRADA/SALIDA ENTRE MÉTODOS

**Archivo:** 07_CONTRATOS_ENTRADA_SALIDA.md
**Versión:** 2.0

---

## 🎯 PROPÓSITO

Este documento define los **contratos sagrados** entre métodos.

**CRÍTICO:** NO romper estos contratos. Cualquier cambio debe ser documentado y validado.

---

## 📥 CONTRATO DE ENTRADA COMÚN: localdict

### Estructura Estándar

**TODOS los métodos principales reciben:**

```python
localdict = {
    # ════════════════════════════════════════════════════════════
    # OBJETOS PRINCIPALES (OBLIGATORIOS)
    # ════════════════════════════════════════════════════════════
    'slip': hr.payslip,                    # Nómina actual
    'contract': hr.contract,               # Contrato del empleado
    'employee': hr.employee,               # Empleado
    'annual_parameters': hr.annual.parameters,  # Parámetros anuales

    # ════════════════════════════════════════════════════════════
    # REGLAS YA EVALUADAS (PARA INTERESES)
    # ════════════════════════════════════════════════════════════
    'rules': {
        'CESANTIAS': hr.payslip.line,      # Regla de cesantías
        'PRIMA': hr.payslip.line,          # Regla de prima
        # ... otras reglas evaluadas
    },

    # ════════════════════════════════════════════════════════════
    # CAMPOS ESTÁNDAR DE ODOO PAYROLL
    # ════════════════════════════════════════════════════════════
    'categories': dict,                     # Categorías de reglas
    'worked_days': dict,                    # Días trabajados
    'inputs': dict,                         # Inputs adicionales
    # ... otros campos estándar
}
```

### Campos Críticos

| Campo | Tipo | Obligatorio | Usado para |
|-------|------|-------------|------------|
| `slip` | hr.payslip | ✅ SÍ | Fechas, estructura, estado |
| `contract` | hr.contract | ✅ SÍ | Salario, tipo, fechas |
| `employee` | hr.employee | ✅ SÍ | Datos del empleado |
| `annual_parameters` | hr.annual.parameters | ⚠️ Recomendado | SMMLV, auxilio, configuración |
| `rules` | dict | ⚠️ Solo para intereses | Cesantías calculadas |

### Regla #1: localdict es INMUTABLE

```python
# ✅ CORRECTO - Solo lectura
def calculate_prestacion(localdict, tipo, context, provision_type):
    slip = localdict['slip']
    contract = localdict['contract']
    # ... usar datos

# ❌ INCORRECTO - Modificar localdict
def calculate_prestacion(localdict, tipo, context, provision_type):
    localdict['valor_calculado'] = 1000  # ¡NO!
    localdict['nueva_key'] = 'valor'     # ¡NO!
```

---

## 📤 CONTRATO DE SALIDA ESTÁNDAR

### calculate_prestacion() - Salida Principal

```python
# ════════════════════════════════════════════════════════════
# TUPLE DE SALIDA (6 elementos)
# ════════════════════════════════════════════════════════════
return (
    base_diaria,    # float - Base mensual / 30
    dias,           # int - Días trabajados finales
    porcentaje,     # float - Siempre 100
    nombre,         # str - Nombre descriptivo
    log,            # str - Log (normalmente vacío)
    detail          # dict - Detalle completo (12+ secciones)
)
```

### Campos del Tuple

| Índice | Campo | Tipo | Descripción | Ejemplo |
|--------|-------|------|-------------|---------|
| 0 | `base_diaria` | float | Base mensual / 30 | 50000.0 |
| 1 | `dias` | int | Días trabajados | 186 |
| 2 | `porcentaje` | float | Siempre 100 | 100.0 |
| 3 | `nombre` | str | Nombre descriptivo | "CESANTIAS ANO 2026" |
| 4 | `log` | str | Log (vacío) | "" |
| 5 | `detail` | dict | **CRÍTICO** - Ver estructura abajo | {...} |

### Estructura de detail (CRÍTICO)

```python
detail = {
    # ════════════════════════════════════════════════════════════
    # CAMPO OBLIGATORIO PARA hr_slip.py
    # ════════════════════════════════════════════════════════════
    'monto_total': float,  # ← hr_slip.py BUSCA ESTE CAMPO

    # ════════════════════════════════════════════════════════════
    # SECCIÓN 1: MÉTRICAS PRINCIPALES (OBLIGATORIA)
    # ════════════════════════════════════════════════════════════
    'metricas': {
        'valor_total': float,          # Valor total calculado
        'valor_total_fmt': str,        # Formato: "$1,500,000"
        'base_mensual': float,         # Base de cálculo
        'base_mensual_fmt': str,       # Formato
        'base_diaria': float,          # Base / 30
        'base_diaria_fmt': str,        # Formato
        'dias_trabajados': int,        # Días finales
        'dias_periodo': int,           # Días del periodo
    },

    # ════════════════════════════════════════════════════════════
    # SECCIÓN 2: VALORES USADOS EN EL CÁLCULO
    # ════════════════════════════════════════════════════════════
    'valores_usados': {
        'salario_base': {
            'valor': float,
            'valor_fmt': str,
            'tiene_cambios': bool,
            'es_promedio': bool,
            'historial': list,
        },
        'variable': {
            'valor': float,
            'valor_fmt': str,
            'total_acumulado': float,
            'lineas_count': int,
            'dias_base': int,
            'formula': str,
        },
        'auxilio': {
            'valor': float,
            'valor_fmt': str,
            'metodo': str,
            'aplica': bool,
            'nota': str,
        },
    },

    # ════════════════════════════════════════════════════════════
    # SECCIONES 3-7: DETALLE COMPLETO
    # ════════════════════════════════════════════════════════════
    'promedio_salario': dict,          # Sección 3
    'condiciones': dict,               # Sección 4
    'dias': dict,                      # Sección 5
    'valor_dia': dict,                 # Sección 6
    'formula_explicacion': dict,       # Sección 7

    # ════════════════════════════════════════════════════════════
    # SECCIONES 8-12: VISUALIZACIÓN MEJORADA
    # ════════════════════════════════════════════════════════════
    'resumen_dias': dict,              # Sección 8
    'cambios_salario': dict,           # Sección 9
    'cambios_auxilio': dict,           # Sección 10
    'desglose_variables_ordenado': dict,  # Sección 11
    'debug_formula_completa': dict,    # Sección 12
    'desglose_transporte_sueldo': dict,

    # ════════════════════════════════════════════════════════════
    # METADATA
    # ════════════════════════════════════════════════════════════
    'metadata': {
        'tipo_prestacion': str,        # 'prima', 'cesantias', etc.
        'slip_id': int,
        'slip_name': str,
        'contract_id': int,
        'employee_id': int,
        'employee_name': str,
        'fecha_calculo': str,          # ISO format
        'context': str,                # 'provision', 'liquidacion', etc.
    },

    # ════════════════════════════════════════════════════════════
    # FLAGS DE APLICABILIDAD
    # ════════════════════════════════════════════════════════════
    'aplica': bool,                    # True si el cálculo aplica
    'motivo': str,                     # Motivo si no aplica

    # ════════════════════════════════════════════════════════════
    # LÍNEAS PARA FRONTEND
    # ════════════════════════════════════════════════════════════
    'lineas_base_variable': [
        {
            'slip_id': int,
            'slip_number': str,
            'rule_id': int,
            'rule_code': str,
            'rule_name': str,
            'category_code': str,      # NO debe ser 'AUX'
            'amount': float,
            'date': str,
            'source_type': str,        # 'payslip' | 'accumulated'
        },
        # ... más líneas
    ],
}
```

### Regla #2: detail['monto_total'] es OBLIGATORIO

```python
# ✅ CORRECTO
detail = {
    'monto_total': 1500000.0,  # ← OBLIGATORIO
    'metricas': {...},
    # ... otras secciones
}

# ❌ INCORRECTO - Falta monto_total
detail = {
    'metricas': {'valor_total': 1500000.0},  # No es suficiente
    # ... sin monto_total directo
}
```

**Por qué es crítico:**
```python
# hr_slip.py busca este campo directamente
valor = data.get('monto_total', 0)  # Si no existe, retorna 0
```

---

## 🔄 CONTRATO DE ADAPTACIÓN: hr_slip

### _adapt_result_for_slip() - Para Liquidación

**Entrada:**
```python
result = (base_diaria, dias, porcentaje, nombre, log, detail)
localdict = {...}
tipo_prestacion = 'cesantias'
```

**Salida:**
```python
return (
    amount,     # float - base_diaria * 30 (base mensual)
    qty,        # float - dias
    rate,       # float - porcentaje
    name,       # str - nombre
    log,        # str - log
    data        # dict - FORMATO ESPECÍFICO PARA hr_slip
)
```

### Estructura de data (para hr_slip)

```python
data = {
    # ════════════════════════════════════════════════════════════
    # CAMPO CRÍTICO - hr_slip.py LO BUSCA
    # ════════════════════════════════════════════════════════════
    'monto_total': float,  # ← OBLIGATORIO

    # ════════════════════════════════════════════════════════════
    # FECHAS DEL PERIODO
    # ════════════════════════════════════════════════════════════
    'fecha_inicio': str,   # ISO format: '2026-01-01'
    'fecha_fin': str,      # ISO format: '2026-06-30'

    # ════════════════════════════════════════════════════════════
    # DATA KPI (MÉTRICAS RESUMIDAS)
    # ════════════════════════════════════════════════════════════
    'data_kpi': {
        'base_diaria': float,
        'base_mensual': float,
        'days_worked': int,
        'tipo_prestacion': str,
    },

    # ════════════════════════════════════════════════════════════
    # FLAGS
    # ════════════════════════════════════════════════════════════
    'aplica': bool,

    # ════════════════════════════════════════════════════════════
    # DETALLE COMPLETO (opcional pero recomendado)
    # ════════════════════════════════════════════════════════════
    'detail': dict,  # Todo el detail de calculate_prestacion()

    # ════════════════════════════════════════════════════════════
    # ACUMULADOS (si existen)
    # ════════════════════════════════════════════════════════════
    'acum_line_ids': list,      # IDs de líneas acumuladas
    'source_rule_ids': list,    # IDs de reglas origen
}
```

### Ejemplo Completo

```python
# Entrada (de calculate_prestacion)
result = (
    50000.0,                    # base_diaria
    186,                        # dias
    100.0,                      # porcentaje
    "CESANTIAS ANO 2026",      # nombre
    "",                         # log
    {
        'monto_total': 775000.0,
        'metricas': {...},
        # ... 12 secciones
    }
)

# Salida (para hr_slip)
adapted = (
    1500000.0,                  # amount (base_diaria * 30)
    186.0,                      # qty (dias)
    100.0,                      # rate (porcentaje)
    "CESANTIAS ANO 2026",      # name
    "",                         # log
    {
        'monto_total': 775000.0,       # ← CRÍTICO
        'fecha_inicio': '2026-01-01',
        'fecha_fin': '2026-06-30',
        'data_kpi': {
            'base_diaria': 50000.0,
            'base_mensual': 1500000.0,
            'days_worked': 186,
            'tipo_prestacion': 'cesantias',
        },
        'aplica': True,
        'detail': {...},  # Detail completo
    }
)
```

---

## 🔄 CONTRATO DE CONSOLIDACIÓN

### _calculate_consolidacion() - Salida

```python
return (
    ajuste,         # float - Obligación real - Provisión acumulada
    qty,            # int - Siempre 1
    rate,           # int - Siempre 100
    nombre,         # str - "CONSOLIDACION CESANTIAS..."
    log,            # str - Vacío
    data            # dict - Estructura especial para consolidación
)
```

### Estructura de data (consolidación)

```python
data = {
    # ════════════════════════════════════════════════════════════
    # VALORES PRINCIPALES
    # ════════════════════════════════════════════════════════════
    'monto_total': float,              # = ajuste
    'ajuste': float,                   # Diferencia a provisionar
    'obligacion_real': float,          # Lo que se DEBE
    'provision_acumulada': float,      # Lo que se HA provisionado

    # ════════════════════════════════════════════════════════════
    # SALDOS CONTABLES (opcional)
    # ════════════════════════════════════════════════════════════
    'saldo_provision': float,          # Cuenta 261005 (ej: cesantías)
    'saldo_obligacion': float,         # Cuenta 2510 (ej: cesantías)
    'cuenta_provision': str,           # Código cuenta
    'cuenta_obligacion': str,          # Código cuenta

    # ════════════════════════════════════════════════════════════
    # METADATA
    # ════════════════════════════════════════════════════════════
    'fecha_corte': str,                # ISO format
    'tipo_prestacion': str,
    'aplica': bool,
    'detail': dict,                    # Detail de calculate_prestacion()

    # ════════════════════════════════════════════════════════════
    # MÉTRICAS (compatible con widget)
    # ════════════════════════════════════════════════════════════
    'metricas': {
        'base_mensual': float,
        'base_diaria': float,
        'dias_trabajados': int,
        'valor_total': float,          # = obligacion_real
    },

    # ════════════════════════════════════════════════════════════
    # SALDO CONTABLE (estructura para widget)
    # ════════════════════════════════════════════════════════════
    'saldo_contable': {
        'cuenta_provision': str,
        'cuenta_obligacion': str,
        'provision_acumulada': float,
        'obligacion_real': float,
        'ajuste': float,
        'saldo_provision_contable': float,
        'saldo_obligacion_contable': float,
        'diferencia_pct': float,       # (ajuste / obligacion) * 100
    },

    # ════════════════════════════════════════════════════════════
    # FÓRMULA EXPLICACIÓN (paso a paso)
    # ════════════════════════════════════════════════════════════
    'formula_explicacion': {
        'formula_aplicada': str,
        'desarrollo': str,
        'pasos': [
            {
                'paso': int,
                'titulo': str,
                'descripcion': str,
                'formula': str,
                'valor': float,
                'formato': str,         # 'currency', 'number', etc.
                'highlight': bool,
            },
            # ... más pasos
        ],
    },

    # ════════════════════════════════════════════════════════════
    # DETALLE DE PROVISIONES ACUMULADAS
    # ════════════════════════════════════════════════════════════
    'provisiones_detalle': [
        {
            'slip_id': int,
            'slip_number': str,
            'date_from': str,
            'date_to': str,
            'rule_code': str,
            'rule_name': str,
            'total': float,
        },
        # ... más líneas
    ],
}
```

---

## ⚠️ CAMPOS CRÍTICOS (RESUMEN)

### Para hr_slip.py

```python
# OBLIGATORIO en data
data['monto_total'] = valor  # hr_slip.py lo busca directamente
```

### Para Intereses de Cesantías

```python
# OBLIGATORIO en base_info
base_info['cesantias_calculadas'] = valor  # De rules['CESANTIAS']
```

### Para Exclusión de Auxilio

```python
# OBLIGATORIO verificar en lineas_base_variable
if line['category_code'].upper() == 'AUX':
    continue  # No incluir en variable
```

### Para Widget JavaScript

```python
# OBLIGATORIO en detail
detail = {
    'monto_total': float,      # ← Valor principal
    'metricas': {...},         # ← Métricas KPI
    'metadata': {...},         # ← Info contextual
    # ... 12+ secciones
}
```

---

## 🔒 VALIDACIÓN DE CONTRATOS

### Checklist al Modificar Código

#### Al modificar prestaciones.py
- [ ] Retorna tuple de 6 elementos
- [ ] detail incluye 'monto_total'
- [ ] detail incluye 'metricas'
- [ ] detail incluye 12+ secciones
- [ ] NO modifica localdict
- [ ] NO modifica base de datos

#### Al modificar prestaciones_detail.py
- [ ] generate() retorna dict con 12+ secciones
- [ ] Incluye 'monto_total' en raíz
- [ ] NO llama a calculate_prestacion()
- [ ] NO modifica valores recibidos
- [ ] Excluye líneas AUX de variable

#### Al modificar prestaciones_liquidacion.py
- [ ] _adapt_result_for_slip() retorna tuple de 6 elementos
- [ ] data incluye 'monto_total'
- [ ] data incluye 'fecha_inicio', 'fecha_fin'
- [ ] data incluye 'data_kpi'
- [ ] NO recalcula valores

#### Al modificar prestaciones_provisiones.py
- [ ] _calculate_consolidacion() retorna tuple de 6 elementos
- [ ] data incluye 'ajuste', 'obligacion_real', 'provision_acumulada'
- [ ] data incluye 'formula_explicacion'
- [ ] data incluye 'provisiones_detalle'
- [ ] NO modifica contabilidad

---

## 📊 EJEMPLO COMPLETO DE FLUJO

```python
# ════════════════════════════════════════════════════════════
# PASO 1: Llamada desde regla salarial
# ════════════════════════════════════════════════════════════
localdict = {
    'slip': hr_payslip_obj,
    'contract': hr_contract_obj,
    'employee': hr_employee_obj,
    'annual_parameters': hr_annual_parameters_obj,
    'rules': {...},
}

# ════════════════════════════════════════════════════════════
# PASO 2: prestaciones.calculate_prestacion()
# ════════════════════════════════════════════════════════════
result = prestaciones.calculate_prestacion(
    localdict,
    tipo_prestacion='cesantias',
    context='liquidacion',
    provision_type='simple'
)

# result = (50000.0, 186, 100.0, "CESANTIAS...", "", {...})

# ════════════════════════════════════════════════════════════
# PASO 3: prestaciones_detail.generate() (llamado internamente)
# ════════════════════════════════════════════════════════════
detail = {
    'monto_total': 775000.0,
    'metricas': {
        'valor_total': 775000.0,
        'base_mensual': 1500000.0,
        'base_diaria': 50000.0,
        'dias_trabajados': 186,
    },
    # ... 11 secciones más
    'aplica': True,
    'motivo': '',
}

# ════════════════════════════════════════════════════════════
# PASO 4: _adapt_result_for_slip()
# ════════════════════════════════════════════════════════════
adapted = _adapt_result_for_slip(result, localdict, 'cesantias')

# adapted = (
#     1500000.0,  # amount
#     186.0,      # qty
#     100.0,      # rate
#     "CESANTIAS ANO 2026",
#     "",
#     {
#         'monto_total': 775000.0,  # ← CRÍTICO
#         'fecha_inicio': '2026-01-01',
#         'fecha_fin': '2026-06-30',
#         'data_kpi': {...},
#         'detail': {...},
#     }
# )

# ════════════════════════════════════════════════════════════
# PASO 5: hr_slip.py usa el resultado
# ════════════════════════════════════════════════════════════
# En hr_slip.py:
amount, qty, rate, name, log, data = adapted
monto_total = data.get('monto_total', 0)  # 775000.0

# Crea hr.payslip.line con:
#   code = 'CESANTIAS'
#   total = monto_total = 775000.0
```

---

## 🚨 ERRORES COMUNES Y CÓMO EVITARLOS

### Error 1: Falta monto_total

```python
# ❌ INCORRECTO
detail = {
    'metricas': {'valor_total': 1500000.0},
    # ... sin monto_total
}

# ✅ CORRECTO
detail = {
    'monto_total': 1500000.0,  # ← Agregar
    'metricas': {'valor_total': 1500000.0},
}
```

### Error 2: Recalcular en adaptador

```python
# ❌ INCORRECTO
def _adapt_result_for_slip(result, localdict, tipo):
    base = localdict['contract'].wage
    valor = (base * 360) / 360  # ¡NO recalcular!

# ✅ CORRECTO
def _adapt_result_for_slip(result, localdict, tipo):
    base_diaria, dias, porcentaje, nombre, log, detail = result
    monto_total = detail.get('monto_total', 0)  # Usar valor existente
```

### Error 3: Modificar localdict

```python
# ❌ INCORRECTO
def calculate_prestacion(localdict, tipo, context, provision_type):
    localdict['resultado'] = 1000  # ¡NO!

# ✅ CORRECTO
def calculate_prestacion(localdict, tipo, context, provision_type):
    resultado = 1000
    return (base, dias, 100, nombre, "", detail)
```

---

## ✅ VALIDACIÓN FINAL

### Test de Contrato

```python
def test_contract_calculate_prestacion():
    """Valida contrato de calculate_prestacion"""
    result = calculate_prestacion(localdict, 'cesantias', 'liquidacion', 'simple')

    # Validar tuple de 6 elementos
    assert len(result) == 6

    # Validar tipos
    base_diaria, dias, porcentaje, nombre, log, detail = result
    assert isinstance(base_diaria, float)
    assert isinstance(dias, (int, float))
    assert isinstance(porcentaje, float)
    assert isinstance(nombre, str)
    assert isinstance(log, str)
    assert isinstance(detail, dict)

    # Validar detail
    assert 'monto_total' in detail  # ← CRÍTICO
    assert 'metricas' in detail
    assert 'aplica' in detail

    # Validar metricas
    assert 'valor_total' in detail['metricas']
    assert 'base_mensual' in detail['metricas']
```

---

**Última Actualización:** 2026-01-27
**Versión:** 2.0
