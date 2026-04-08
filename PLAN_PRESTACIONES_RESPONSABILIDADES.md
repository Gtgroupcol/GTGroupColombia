# PLAN DE RESPONSABILIDADES - SISTEMA DE PRESTACIONES SOCIALES

**Fecha:** 2026-01-27
**Versión:** 1.0
**Módulo:** lavish_hr_employee

---

## 1. MAPA DE MÓDULOS Y PROPÓSITO

### 1.1 Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                   SISTEMA DE PRESTACIONES                    │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ CÁLCULO BASE │    │   DETALLE    │    │  ADAPTADORES │
│prestaciones.py│    │detail.py     │    │liquidacion.py│
│              │───▶│              │◀───│provisiones.py│
└──────────────┘    └──────────────┘    └──────────────┘
```




### 1.2 Responsabilidad por Archivo

| Archivo | Modelo | Propósito Principal | Tipo |
|---------|--------|---------------------|------|
| `prestaciones.py` | `hr.salary.rule.prestaciones` | **Núcleo de cálculo unificado** - Periodos, días, base, fórmula, validaciones | Motor de cálculo |
| `prestaciones_detail.py` | `hr.salary.rule.prestaciones.detail` | **Armado de detalle/explicación** - Widget UI con 12 secciones | Presentación |
| `prestaciones_liquidacion.py` | `hr.salary.rule.prestaciones.liquidacion` | **Adaptación y pagos** - Puente a nómina, liquidación | Adaptador |
| `prestaciones_provisiones.py` | `hr.salary.rule.prestaciones.provisiones` | **Provisiones y consolidación** - Contabilidad, ajustes | Adaptador |

---

## 2. RESPONSABILIDADES POR MÉTODO (DETALLADO)

### 2.1 prestaciones.py - CÁLCULO UNIFICADO

**Modelo:** `hr.salary.rule.prestaciones`
**Propósito:** Motor central de cálculo - NO modifica, NO presenta, SOLO calcula

#### 2.1.1 Método Principal de Orquestación

##### `calculate_prestacion(localdict, tipo_prestacion, context, provision_type)`
**Responsabilidad:** Orquesta el flujo completo de cálculo
- **Entrada:**
  - `localdict`: {slip, contract, employee, annual_parameters}
  - `tipo_prestacion`: 'prima' | 'cesantias' | 'intereses' | 'vacaciones'
  - `context`: 'provision' | 'liquidacion' | 'consolidacion' | 'provision_completa'
  - `provision_type`: 'simple' | 'promediado' | 'porcentaje_fijo'
- **Proceso:**
  1. Determina modo de cálculo (líneas 54-65)
  2. Calcula periodo → `_get_period()`
  3. Calcula días → `_calculate_days()`
  4. Calcula base → `period.payslip.query.service.calculate_base_prestacion()`
  5. Calcula valor → `_calculate_value()`
  6. Genera detalle → `prestaciones.detail.generate()`
- **Salida:** `(base_diaria, dias, porcentaje, nombre, log, detail_dict)`
- **Reglas:**
  - NO llama a adaptadores (liquidacion/provisiones)
  - NO modifica base de datos
  - NO genera UI directamente

#### 2.1.2 Métodos de Cálculo de Periodo

##### `_get_period(localdict, tipo_prestacion, context)`
**Responsabilidad:** Define rango de fechas según tipo y contexto
- **Entrada:** localdict, tipo, context
- **Lógica:**
  - Prima: Semestre (Ene-Jun o Jul-Dic) - líneas 184-189
  - Cesantías/Intereses: Año completo (Ene 1 - fecha corte) - línea 193
  - Vacaciones: Desde inicio contrato o año - línea 198
  - Liquidación: Usa `contract.date_end` - línea 179
  - Provisión: Usa `slip.date_to` - línea 182
- **Salida:** `(date_from, date_to)`
- **Reglas:**
  - Ajusta si contrato inició después (líneas 205-206)
  - Ajusta si contrato terminó antes (líneas 209-210)
  - NO modifica el contrato

#### 2.1.3 Métodos de Cálculo de Días

##### `_calculate_days(localdict, date_from, date_to, tipo_prestacion)`
**Responsabilidad:** Calcula días trabajados descontando ausencias
- **Entrada:** localdict, periodo, tipo
- **Proceso:**
  1. Calcula días periodo con days360() - línea 244
  2. Obtiene ausencias no remuneradas - líneas 249-255
  3. Obtiene ausencias con `discounting_bonus_days` - líneas 264-267
  4. Suma y descuenta ambos tipos - líneas 274-275
- **Salida:** `dict` con:
  ```python
  {
      'dias_periodo': int,
      'dias_ausencias': int,           # Total a descontar
      'dias_ausencias_no_pago': int,   # No remuneradas
      'dias_descuento_bonus': int,     # Con flag especial
      'dias_total': int,               # Días finales
      'date_from': date,
      'date_to': date,
      'detalle_ausencias': list
  }
  ```
- **Reglas:**
  - Solo prima, cesantías e intereses usan `discounting_bonus_days` - línea 264
  - Evita doble conteo - línea 273
  - Usa `hr.leave.line` para mejor rendimiento - línea 314

##### `_get_discounting_bonus_days(slip, contract, date_from, date_to)`
**Responsabilidad:** Consulta ausencias específicas con flag `discounting_bonus_days=True`
- **Entrada:** slip, contrato, periodo
- **Proceso:**
  1. Busca en `hr.leave.line` - líneas 314-333
  2. Excluye ausencias no remuneradas (evita duplicado) - línea 325
  3. Agrupa por `leave_id` para detalle - líneas 338-350
- **Salida:** `(dias_total, detalle_list)`
- **Reglas:**
  - NO cuenta ausencias no remuneradas (ya están en `dias_ausencias_no_pago`)
  - Límite de 1000 líneas por rendimiento - línea 332

#### 2.1.4 Métodos de Cálculo de Valor

##### `_calculate_value(tipo_prestacion, base_info, days_info, context, provision_type)`
**Responsabilidad:** Aplica fórmula matemática por tipo
- **Entrada:** tipo, base_info, days_info, context, provision_type
- **Fórmulas (con parámetros configurables):**
  ```python
  # Prima (líneas 436-443)
  if context == 'provision' and provision_type == 'porcentaje_fijo':
      valor = (base * 8.33%)
  else:
      valor = (base * dias) / base_dias_prima  # default: 180

  # Cesantías (líneas 448-455)
  if context == 'provision' and provision_type == 'porcentaje_fijo':
      valor = (base * 8.33%)
  else:
      valor = (base * dias) / base_dias_prestaciones  # default: 360

  # Intereses (líneas 470-512)
  cesantias = base_info.get('cesantias_calculadas', 0)  # ¡CRÍTICO!
  tasa_efectiva = 1

  if provision_type == 'simple':
      valor = cesantias * tasa_efectiva
  elif provision_type == 'promediado':
      valor = cesantias * (12% * dias_mes / 360)
  elif provision_type == 'porcentaje_fijo':
      valor = (base * 1%) * dias_mes / dias_mes
  elif context in ('liquidacion', 'provision_completa'):
      valor = cesantias_acum * 12% * (dias / 360)  # TASA FIJA 12%

  # Vacaciones (líneas 517-523)
  if context == 'provision' and provision_type == 'porcentaje_fijo':
      valor = (base * 4.17%) 
  else:
      valor = (base * dias) / base_dias_vacaciones  # default: 720
  ```
- **Salida:** `float` (valor calculado)
- **Reglas:**
  - **CRÍTICO**: Para intereses, usa `cesantias_calculadas` de `base_info` - línea 472
  - NO recalcula cesantías dentro de intereses
  - Tasa FIJA 12% en liquidación - líneas 500-501
  - Parámetros configurables desde `ir.config_parameter` - líneas 97-102

##### `_get_cesantias_from_slip(localdict)`
**Responsabilidad:** Obtiene valor de cesantías ya calculado en la misma nómina
- **Entrada:** localdict con rules
- **Proceso:**
  1. Recorre `rules` dict - línea 574
  2. Busca códigos que contengan 'CESANTIAS' - línea 577
  3. Suma todos los valores encontrados - línea 580
- **Salida:** `float` (suma de cesantías) o 0
- **Reglas:**
  - Busca en `localdict['rules']` (reglas ya evaluadas)
  - Suma TODAS las reglas con 'CESANTIAS' en el código
  - Usado en cálculo de intereses - línea 107

#### 2.1.5 Métodos de Configuración y Condiciones

##### `_get_conditions(localdict, tipo_prestacion)`
**Responsabilidad:** Centraliza TODAS las configuraciones y condiciones
- **Entrada:** localdict, tipo
- **Fuentes de configuración (5):**
  1. **hr.contract** - Contrato del empleado (líneas 627-639)
  2. **hr.contract.type** - Tipo de contrato (líneas 644-668)
  3. **hr.annual.parameters** - Parámetros anuales SMMLV, aux_transporte (líneas 672-706)
  4. **ir.config_parameter** - Configuración global del sistema (líneas 710-789)
  5. **res.company** - Configuración de la compañía (líneas 794-798)
- **Salida:** `dict` con 8 secciones:
  ```python
  {
      'contract': {...},           # Wage, dates, modality_salary
      'contract_type': {...},      # has_prima, has_cesantias, is_apprenticeship
      'annual': {...},             # SMMLV, aux_transporte, simple_provisions
      'global': {...},             # Parámetros configurables del sistema
      'company': {...},            # Company info
      'slip': {...},               # Slip info, struct_process
      'validation': {...},         # Aplica, motivos, incluye_auxilio
      'porcentaje_fijo': {...},    # Config de porcentaje fijo
      'tipo_prestacion': str
  }
  ```
- **Reglas:**
  - NO modifica ningún registro
  - Lee desde 5 fuentes diferentes
  - Determina aplicabilidad por tipo de contrato - líneas 821-828
  - Valida aprendices según Ley 2466/2025 - líneas 831-835

##### `_validate_conditions(conditions)`
**Responsabilidad:** Valida si el cálculo aplica
- **Entrada:** dict de conditions
- **Validaciones:**
  1. Tipo de contrato permite prestación - línea 903
  2. Estado de contrato válido (open, close, finished) - línea 913
  3. Aprendiz con prestaciones habilitadas - línea 834
- **Salida:** `{aplica: bool, motivo: str, warnings: list}`
- **Reglas:**
  - Retorna warnings informativos (no bloqueantes) - líneas 920-928
  - NO modifica condiciones

##### `calculate_with_conditions(localdict, tipo_prestacion, context, provision_type)`
**Responsabilidad:** Wrapper que valida antes de calcular
- **Entrada:** localdict, tipo, context, provision_type
- **Flujo:**
  1. Obtiene condiciones → `_get_conditions()`
  2. Valida → `_validate_conditions()`
  3. Determina tipo de provisión si es 'auto'
  4. Calcula → `calculate_prestacion()`
  5. Agrega condiciones al detalle
- **Salida:** tuple estándar con conditions en detail
- **Reglas:**
  - Usado cuando se necesita validación previa
  - NO usado por defecto (calculate_prestacion es directo)

#### 2.1.6 Métodos Auxiliares Públicos

##### `calculate_prima(localdict, context, provision_type)`
##### `calculate_cesantias(localdict, context, provision_type)`
##### `calculate_intereses(localdict, context, provision_type)`
##### `calculate_vacaciones(localdict, context, provision_type)`

**Responsabilidad:** Helpers públicos para cada tipo
- **Entrada:** localdict, context, provision_type
- **Proceso:** Llama a `calculate_prestacion()` con tipo específico
- **Salida:** tuple estándar
- **Reglas:**
  - NO agregan lógica extra
  - Son wrappers convenientes
  - Usan el método unificado

#### 2.1.7 Métodos Internos de Utilidad

##### `_get_nombre(tipo_prestacion, slip)`
**Responsabilidad:** Genera nombre descriptivo
- **Salida:** str formateado (ej: "PRIMA DE SERVICIOS 1 SEMESTRE 2026")

##### `_resultado_no_aplica(motivo)`
**Responsabilidad:** Retorna resultado vacío estandarizado
- **Salida:** `(0, 0, 0, motivo, "", {'aplica': False, 'motivo': motivo})`

##### `_get_provision_type_descripcion(context, provision_type)`
**Responsabilidad:** Describe tipo de provisión
- **Salida:** str descriptivo del modo de cálculo

---

### 2.2 prestaciones_detail.py - DETALLE PARA WIDGET

**Modelo:** `hr.salary.rule.prestaciones.detail`
**Propósito:** Presenta datos calculados en formato UI - NO calcula, SOLO formatea

#### 2.2.1 Método Principal

##### `generate(localdict, tipo_prestacion, base_info, days_info, valor)`
**Responsabilidad:** Genera estructura completa con 12 secciones
- **Entrada:**
  - `localdict`: {slip, contract, employee}
  - `tipo_prestacion`: str
  - `base_info`: dict con salary, variable, auxilio, base_mensual
  - `days_info`: dict con dias_periodo, dias_ausencias, dias_total
  - `valor`: float (ya calculado)
- **Salida:** `dict` con 12 secciones:
  ```python
  {
      'metricas': {...},                          # KPIs principales
      'valores_usados': {...},                    # Desglose sueldo/aux/var
      'promedio_salario': {...},                  # Si promedia y por qué
      'condiciones': {...},                       # Reglas aplicadas
      'dias': {...},                              # Días trabajados/ausencias
      'valor_dia': {...},                         # Valor por día
      'formula_explicacion': {...},               # Paso a paso
      'resumen_dias': {...},                      # Resumen días
      'cambios_salario': {...},                   # Historial salario
      'cambios_auxilio': {...},                   # Historial auxilio
      'desglose_variables_ordenado': {...},       # Tabla ordenada
      'debug_formula_completa': {...},            # Debug completo
      'desglose_transporte_sueldo': {...},        # Desglose aux
      'lineas_base_variable': [...],              # Para frontend
      'metadata': {...},                          # Metadata
      'aplica': bool,
      'motivo': str
  }
  ```
- **Reglas:**
  - NO recalcula nada, solo consume `base_info`, `days_info`, `valor`
  - NO llama a `calculate_prestacion()`
  - Solo formatea y estructura datos

#### 2.2.2 Métodos de Construcción de Secciones

##### `_build_metricas(valor, base_info, days_info)`
**Responsabilidad:** Sección 1 - Métricas KPI
- **Datos:** valor_total, base_mensual, base_diaria, días
- **Formato:** Incluye formatos con separadores de miles
- **Reglas:** Solo lectura de datos ya calculados

##### `_build_valores_usados(base_info)`
**Responsabilidad:** Sección 2 - Desglose de valores
- **Datos:** salario_base, variable, auxilio con subdetalles
- **Reglas:**
  - Excluye líneas de auxilio (AUX*) del variable - línea 289
  - Calcula nota explicativa del auxilio - `_get_nota_auxilio()`

##### `_build_promedio_salario(base_info)`
**Responsabilidad:** Sección 3 - Explica si promedia salario
- **Datos:** Historial de cambios, motivo de promedio
- **Reglas:** Consulta `base_info['salary_info']['tiene_cambios']`

##### `_build_condiciones(localdict, tipo_prestacion)`
**Responsabilidad:** Sección 4 - Condiciones aplicadas
- **Datos:** Tipo contrato, aprendiz, salario integral, topes
- **Reglas:** Lee configuración, NO valida (solo presenta)

##### `_build_dias(days_info)`
**Responsabilidad:** Sección 5 - Desglose de días
- **Datos:** días_periodo, ausencias, total
- **Reglas:** Consume `days_info` directamente

##### `_build_valor_dia(valor, days_info)`
**Responsabilidad:** Sección 6 - Valor por día
- **Datos:** valor / días_total
- **Reglas:** Calcula división simple (no es parte del cálculo base)

##### `_build_formula_explicacion(tipo_prestacion, base_info, days_info, valor)`
**Responsabilidad:** Sección 7 - Fórmula paso a paso
- **Datos:** Pasos detallados de la fórmula aplicada
- **Reglas:** Genera explicación textual de cálculo ya realizado

##### `_build_resumen_dias(days_info, tipo_prestacion)`
**Responsabilidad:** Sección 8 - Resumen visual de días
- **Datos:** Resumen compacto de días
- **Reglas:** Formato para widget UI

##### `_build_cambios_salario(base_info)`
**Responsabilidad:** Sección 9 - Tabla historial salario
- **Datos:** Cambios de salario con ponderaciones
- **Reglas:** Consume `base_info['salary_info']['historial']`

##### `_build_cambios_auxilio(base_info, localdict, days_info)`
**Responsabilidad:** Sección 10 - Tabla historial auxilio
- **Datos:** Cambios de auxilio con aplicabilidad
- **Reglas:** Verifica tope SMMLV para cada periodo

##### `_build_desglose_variables_ordenado(base_info, days_info)`
**Responsabilidad:** Sección 11 - Tabla ordenada sueldo/aux/var
- **Datos:** Porcentajes de composición
- **Reglas:** Calcula % sobre base_mensual

##### `_build_debug_formula_completa(localdict, tipo, base_info, days_info, valor)`
**Responsabilidad:** Sección 12 - Debug completo
- **Datos:** Valores exactos, flags, lógica días, pasos finales
- **Reglas:** Para debugging, incluye TODO

##### `_build_desglose_transporte_sueldo(base_info, localdict)`
**Responsabilidad:** Desglose específico de transporte
- **Datos:** Separación sueldo vs auxilio
- **Reglas:** Considera modalidad y topes

##### `_build_lineas_base_variable(base_info)`
**Responsabilidad:** Formatea líneas para frontend
- **Datos:** Lista de lineas_base_variable
- **Reglas:**
  - **CRÍTICO**: Excluye líneas de auxilio (category_code='AUX') - línea 289
  - Soporta hr_payslip_line y hr_accumulated_payroll
  - Formatea nombres JSONB (Odoo 17)

#### 2.2.3 Métodos Auxiliares

##### `_get_nota_auxilio(base_info)`
**Responsabilidad:** Genera nota explicativa del auxilio
- **Lógica:**
  1. Si `modality_aux = 'no'`: "Sin auxilio"
  2. Si hay motivo: Mostrar motivo
  3. Si está en variable: "Promediado de líneas"
  4. Si es fijo: "Auxilio fijo vigente"
- **Reglas:** Solo genera texto, NO calcula

#### 2.2.4 Métodos de Regeneración (si existen)

##### `regenerate(localdict, tipo, sections_to_update)`
**Responsabilidad:** Refresco parcial de secciones
- **Entrada:** secciones específicas a regenerar
- **Reglas:** Útil para actualizaciones incrementales en UI

##### `generate_summary(localdict, tipo, base_info, days_info, valor)`
**Responsabilidad:** Genera resumen compacto
- **Reglas:** Versión reducida para logs o reportes

---

### 2.3 prestaciones_liquidacion.py - PAGOS Y LIQUIDACIÓN

**Modelo:** `hr.salary.rule.prestaciones.liquidacion`
**Propósito:** Adaptador entre cálculo y nómina - NO calcula, ADAPTA resultado

#### 2.3.1 Métodos de Pago (Reglas Salariales)

Estos métodos son llamados directamente por reglas salariales con `amount_select='concept'`

##### `_prima(localdict)`
**Código Regla:** PRIMA
- **Responsabilidad:** Entrada para prima en nómina
- **Proceso:**
  1. Determina context ('liquidacion' si struct_process='contrato', sino 'pago')
  2. Llama a `prestaciones.calculate_prestacion()`
  3. Adapta resultado → `_adapt_result_for_slip()`
- **Salida:** `(amount, qty, rate, name, log, data)` formato hr_slip
- **Reglas:**
  - NO calcula, solo llama y adapta
  - Usa `slip.struct_id.process` para determinar contexto

##### `_cesantias(localdict)`
**Código Regla:** CESANTIAS
- **Responsabilidad:** Entrada para cesantías en nómina
- **Proceso:** Similar a `_prima()`
- **Reglas:** Usa configuración `cesantias_salary_take` (promedio 3 meses)

##### `_intcesantias(localdict)`
**Código Regla:** INTCESANTIAS
- **Responsabilidad:** Entrada para intereses en nómina
- **Proceso:** Similar a `_prima()`
- **Reglas:**
  - **CRÍTICO**: Tasa FIJA 12% en liquidación (Art. 99 Ley 50/1990) - línea 106
  - Depende de cesantías ya calculadas en la misma nómina

##### `_vaccontrato(localdict)`
**Código Regla:** VACCONTRATO
- **Responsabilidad:** Entrada para vacaciones en liquidación
- **Proceso:** Similar a `_prima()`
- **Reglas:** Considera días pendientes de disfrute

##### `_ces_year(localdict)`
**Código Regla:** CES_YEAR
- **Responsabilidad:** Cesantías del año anterior (si no se consignaron)
- **Condiciones de aplicabilidad:**
  1. Solo en liquidación de contrato - línea 165
  2. Solo en enero/febrero - línea 171
  3. Solo si `pagar_cesantias_ano_anterior = True` - línea 172
- **Proceso:** Llama a `_calcular_prestacion_ano_anterior()`
- **Reglas:** Solo aplica en casos específicos

##### `_intces_year(localdict)`
**Código Regla:** INTCES_YEAR
- **Responsabilidad:** Intereses del año anterior
- **Condiciones:**
  1. No aplica en salario integral - línea 199
  2. No aplica si contrato inició este año - línea 202
  3. Solo si `pay_cesantias_in_payroll = True` - línea 206
- **Proceso:** Llama a `_calcular_prestacion_ano_anterior()`
- **Reglas:** Normalmente se pagan antes del 31 de enero

#### 2.3.2 Métodos Auxiliares de Adaptación

##### `_adapt_result_for_slip(result, localdict, tipo_prestacion)`
**Responsabilidad:** Convierte resultado de cálculo a formato hr_slip
- **Entrada:** tuple de calculate_prestacion()
- **Proceso:**
  1. Extrae `(base_diaria, dias, porcentaje, nombre, log, detail)`
  2. Calcula `monto_total` desde detail o con fórmula
  3. Construye `data` dict con:
     - `monto_total` - **CRÍTICO**: hr_slip.py busca este campo - línea 126
     - `fecha_inicio`, `fecha_fin`
     - `data_kpi` con métricas
     - `detail` completo
- **Salida:** `(amount, qty, rate, name, log, data)` formato hr_slip
- **Reglas:**
  - `amount = base_diaria * 30` (base mensual)
  - `qty = dias`
  - `rate = porcentaje`
  - `data['monto_total']` es el valor usado por nómina

##### `_calcular_prestacion_ano_anterior(localdict, tipo_prestacion, year, nombre)`
**Responsabilidad:** Calcula prestación de un año específico
- **Entrada:** localdict, tipo, año, nombre
- **Proceso:**
  1. Define periodo: 1 enero - 31 diciembre del año
  2. Ajusta por `contract.date_start`
  3. Llama a `prestaciones.calculate_prestacion()`
  4. Calcula total según tipo
- **Salida:** tuple formato hr_slip
- **Reglas:**
  - Usado por `_ces_year()` y `_intces_year()`
  - Calcula sobre año completo anterior

#### 2.3.3 Métodos de Servicio (para llamadas externas)

##### `calculate_liquidacion(localdict, tipo_prestacion)`
**Responsabilidad:** Calcula prestación en contexto de liquidación
- **Entrada:** localdict, tipo
- **Proceso:**
  1. Valida contexto → `_validar_liquidacion()`
  2. Llama a `prestaciones.calculate_prestacion(context='liquidacion')`
- **Salida:** tuple estándar
- **Reglas:**
  - Validación previa obligatoria
  - Context forzado a 'liquidacion'

##### `liquidar_prima(localdict)`
##### `liquidar_cesantias(localdict)`
##### `liquidar_intereses_cesantias(localdict)`
##### `liquidar_vacaciones(localdict)`

**Responsabilidad:** Wrappers específicos por tipo
- **Entrada:** localdict
- **Proceso:** Llama a `calculate_liquidacion()` con tipo específico
- **Reglas:** Útiles para llamadas externas programáticas

##### `liquidar_todas(localdict)`
**Responsabilidad:** Liquidación completa de todas las prestaciones
- **Entrada:** localdict
- **Proceso:**
  1. Itera sobre ['prima', 'cesantias', 'intereses', 'vacaciones']
  2. Llama a `calculate_liquidacion()` para cada tipo
  3. Acumula valores si aplican
  4. Maneja errores por tipo
- **Salida:**
  ```python
  {
      'resultados': {tipo: {resultado, valor, aplica}},
      'total': float,
      'fecha_liquidacion': date,
      'contract_id': int,
      'employee_id': int,
      'employee_name': str
  }
  ```
- **Reglas:**
  - Manejo robusto de errores
  - Suma solo valores aplicables

#### 2.3.4 Métodos de Validación

##### `_validar_liquidacion(localdict)`
**Responsabilidad:** Valida contexto de liquidación
- **Validaciones:**
  1. `slip.struct_id.process == 'contrato'` - línea 499
  2. `contract.date_end` existe - línea 503
  3. `contract.state in ('open', 'close', 'finished')` - línea 512
- **Salida:** `{aplica: bool, motivo: str, warnings: list}`
- **Reglas:**
  - NO modifica registros
  - Retorna warnings no bloqueantes

##### `_resultado_no_aplica(motivo)`
**Responsabilidad:** Resultado vacío estandarizado
- **Salida:** `(0, 0, 0, motivo, "", {'aplica': False, 'motivo': motivo})`

---

### 2.4 prestaciones_provisiones.py - PROVISIONES Y CONSOLIDACIÓN

**Modelo:** `hr.salary.rule.prestaciones.provisiones`
**Propósito:** Provisiones mensuales y consolidación contable - NO calcula prestación base

#### 2.4.1 Métodos de Provisión (Reglas Salariales)

##### `_prv_prim(localdict)`
**Código Regla:** PRV_PRIM
- **Responsabilidad:** Provisión mensual de prima
- **Proceso:**
  1. Determina modo: simple (8.33%) o completa (liquidación al corte)
  2. Llama a `_calculate_provision_rule()`
- **Consolidación:** Junio y Diciembre
- **Reglas:** Usa `annual_parameters.simple_provisions` o `company.simple_provisions`

##### `_prv_ces(localdict)`
**Código Regla:** PRV_CES
- **Responsabilidad:** Provisión mensual de cesantías
- **Fórmula simple:** Base * 8.33%
- **Consolidación:** Diciembre

##### `_prv_ices(localdict)`
**Código Regla:** PRV_ICES
- **Responsabilidad:** Provisión mensual de intereses
- **Fórmula simple:** Cesantías * 1% (12%/12)
- **Consolidación:** Diciembre

##### `_prv_vac(localdict)`
**Código Regla:** PRV_VAC
- **Responsabilidad:** Provisión mensual de vacaciones
- **Fórmula simple:** Base * 4.17% (15/360)
- **Consolidación:** Continua

#### 2.4.2 Método Central de Provisión

##### `_calculate_provision_rule(localdict, tipo_prestacion)`
**Responsabilidad:** Motor central de provisión
- **Entrada:** localdict, tipo
- **Proceso:**
  1. Lee `simple_provisions` desde annual_parameters o company - líneas 145-149
  2. Si simple_provisions = True:
     - context = 'provision'
     - provision_type = 'porcentaje_fijo'
  3. Si simple_provisions = False:
     - context = 'provision_completa'  (calcula como liquidación)
     - provision_type = 'simple'
  4. Llama a `prestaciones.calculate_prestacion()`
  5. Adapta resultado → `_adapt_provision_result()`
- **Salida:** `(amount, qty, rate, name, log, data)` formato hr_slip
- **Reglas:**
  - **CRÍTICO**: El flag `simple_provisions` determina TODO el modo de cálculo
  - NO calcula, solo orquesta y adapta

##### `_adapt_provision_result(result, localdict, tipo, simple_provisions)`
**Responsabilidad:** Adapta resultado de provisión a formato hr_slip
- **Entrada:** result tuple, localdict, tipo, flag
- **Proceso:**
  1. Extrae monto_total de detail o calcula con fórmula
  2. Genera nombre descriptivo (ej: "PROVISION CESANTIAS 01/2026")
  3. Construye data dict con:
     - `monto_total`
     - `tipo_provision`: 'simple' | 'completa'
     - `data_kpi`, `detail`
- **Salida:** tuple formato hr_slip
- **Reglas:**
  - Si simple_provisions: usa porcentajes fijos (líneas 199-206)
  - Si NO simple: usa días trabajados con divisores (líneas 208-216)

#### 2.4.3 Métodos de Consolidación (Reglas Salariales)

##### `_cesantias_cons(localdict)` / `_cons_ces(localdict)`
**Código Regla:** CESANTIAS_CONS / CONS_CES
- **Responsabilidad:** Ajuste cesantías provisión vs real
- **Proceso:** Llama a `_calculate_consolidacion()`
- **Cuentas:** 261005 (provisión) vs 2510 (obligación)

##### `_intcesantias_cons(localdict)` / `_cons_int(localdict)`
**Código Regla:** INTCESANTIAS_CONS / CONS_INT
- **Responsabilidad:** Ajuste intereses provisión vs real
- **Cuentas:** 261010 vs 2515

##### `_vacaciones_cons(localdict)` / `_cons_vac(localdict)`
**Código Regla:** VACACIONES_CONS / CONS_VAC
- **Responsabilidad:** Ajuste vacaciones provisión vs real
- **Cuentas:** 261015 vs 2525

#### 2.4.4 Método Central de Consolidación

##### `_calculate_consolidacion(localdict, tipo_prestacion)`
**Responsabilidad:** Calcula ajuste de consolidación
- **Entrada:** localdict, tipo
- **Proceso detallado:**
  1. **Calcular obligación real (lo que se DEBE):**
     - Llama a `prestaciones.calculate_prestacion(context='consolidacion')`
     - Obtiene `obligacion_real` de `detail['metricas']['valor_total']` - línea 343

  2. **Obtener provisiones acumuladas (lo que se HA PROVISIONADO):**
     - Define periodo según tipo → `_get_period_dates()` - línea 347
     - Busca provisiones en nóminas → `_get_provision_acumulada()` - líneas 348-354
     - Suma todas las provisiones del periodo

  3. **Opcionalmente: Obtener saldos contables:**
     - Si `integrar_consolidacion_liquidacion = True` - línea 361
     - Lee saldos de cuentas → `_get_saldo_cuenta()` - líneas 368-379

  4. **Calcular ajuste:**
     - `ajuste = obligacion_real - provision_acumulada` - línea 385
     - Positivo: Falta provisionar (pagar diferencia)
     - Negativo: Se provisionó de más (normalmente no aplica)

  5. **Construir data dict con estructura completa:**
     - `monto_total = ajuste`
     - `metricas` - líneas 423-428
     - `saldo_contable` - líneas 431-440
     - `formula_explicacion` con pasos - líneas 443-473
     - `provisiones_detalle` - línea 476

- **Salida:** `(ajuste, 1, 100, nombre_cons, '', data)`
- **Reglas:**
  - **CRÍTICO**: Compara obligación REAL vs provisiones ACUMULADAS
  - NO modifica contabilidad, solo calcula ajuste
  - Estructura data compatible con widget JavaScript

#### 2.4.5 Métodos de Consulta Contable

##### `_get_saldo_cuenta(param_key, prefijo_default, date_to, employee)`
**Responsabilidad:** Obtiene saldo de cuenta contable
- **Proceso:**
  1. Busca cuenta configurada en `ir.config_parameter` - línea 500
  2. Si no existe, busca por prefijo PUC - línea 512
  3. Llama a `_get_saldo_cuenta_by_id()` o `_get_saldo_cuenta_by_prefijo()`
- **Reglas:**
  - NO modifica cuentas
  - Filtra por employee.partner_id si disponible

##### `_get_saldo_cuenta_by_id(cuenta, date_to, employee)`
**Responsabilidad:** Saldo de cuenta específica
- **Proceso:**
  1. Busca en `account.move.line` - líneas 532-547
  2. Filtra por cuenta, fecha, estado='posted', partner
  3. Suma débito y crédito
  4. Retorna: `credito - debito` (para pasivos) - línea 553
- **Reglas:**
  - Límite 10,000 líneas
  - Solo movimientos posted

##### `_get_saldo_cuenta_by_prefijo(prefijo, date_to, employee)`
**Responsabilidad:** Saldo de cuentas por prefijo
- **Proceso:** Similar a `by_id` pero busca múltiples cuentas con LIKE
- **Reglas:** Suma saldos de todas las cuentas que coincidan

#### 2.4.6 Métodos de Consulta de Provisiones

##### `_get_provision_acumulada(contract_id, tipo, date_from, date_to, exclude_slip_id)`
**Responsabilidad:** Suma provisiones del periodo desde nóminas
- **Entrada:** contrato, tipo, periodo, slip a excluir
- **Proceso:**
  1. Define códigos de regla a buscar - líneas 817-822
     - Prima: ['PROV_PRIMA', 'PROVISION_PRIMA', 'PRV_PRIM', 'PRV_PRIMA']
     - Cesantías: ['PROV_CESANTIAS', 'PROVISION_CESANTIAS', 'PRV_CES', ...]
     - Intereses: ['PROV_INT_CESANTIAS', 'PRV_ICES', ...]
     - Vacaciones: ['PROV_VACACIONES', 'PRV_VAC', ...]

  2. Busca en `hr.payslip.line` con dominio:
     - `slip_id.contract_id = contract_id`
     - `slip_id.date_from >= date_period_from`
     - `slip_id.date_to <= date_period_to`
     - `slip_id.state in ['done', 'paid']`
     - `code in codes`
     - `slip_id != exclude_slip_id` (excluye nómina actual)

  3. Usa `search_read()` para mejor rendimiento - línea 843
  4. Suma `line.total` de todas las líneas - línea 849

- **Salida:**
  ```python
  {
      'total': float,              # Suma de provisiones
      'count': int,                # Cantidad de líneas
      'lineas': list,              # Detalle de líneas
      'codes_buscados': list       # Códigos buscados
  }
  ```
- **Reglas:**
  - Usa `date_from/date_to` del slip (periodo de nómina)
  - Límite 1,000 líneas por rendimiento
  - Excluye nómina actual (para evitar contarse a sí misma)

##### `_get_period_dates(tipo_prestacion, date_to)`
**Responsabilidad:** Define fechas del periodo de consolidación
- **Lógica:**
  - Prima: Semestre (Ene-Jun o Jul-Dic) - líneas 789-793
  - Cesantías/Intereses/Vacaciones: Año completo - línea 796
- **Salida:** `(date_from, date_to)`
- **Reglas:** Misma lógica que `prestaciones._get_period()`

#### 2.4.7 Métodos de Servicio (para llamadas externas)

##### `calculate_provision(localdict, tipo, provision_type='auto')`
**Responsabilidad:** Servicio público de provisión
- **Proceso:**
  1. Determina provision_type si es 'auto' → `_get_provision_type()`
  2. Llama a `prestaciones.calculate_prestacion(context='provision')`
  3. Si es cierre de periodo, agrega info de consolidación
- **Reglas:**
  - Método público para llamadas externas
  - Agrega metadata de consolidación en meses de cierre

##### `provision_prima(localdict, provision_type='auto')`
##### `provision_cesantias(localdict, provision_type='auto')`
##### `provision_intereses(localdict, provision_type='auto')`
##### `provision_vacaciones(localdict, provision_type='auto')`

**Responsabilidad:** Wrappers específicos por tipo
- **Reglas:** Útiles para llamadas programáticas

##### `calcular_todas_provisiones(localdict, provision_type='auto')`
**Responsabilidad:** Calcula todas las provisiones del mes
- **Proceso:** Similar a `liquidar_todas()` pero para provisiones
- **Salida:** dict con resultados por tipo y total

##### `get_saldos_provisiones(employee_id, date_to=None)`
**Responsabilidad:** Consulta saldos de TODAS las provisiones
- **Entrada:** employee_id, fecha
- **Proceso:**
  1. Itera sobre tipos
  2. Obtiene saldo provisión y obligación para cada tipo
  3. Calcula diferencia
- **Salida:**
  ```python
  {
      'saldos': {tipo: {saldo_provision, saldo_obligacion, diferencia}},
      'employee_id': int,
      'date_to': str,
      'total_provision': float,
      'total_obligacion': float
  }
  ```
- **Reglas:** Útil para reportes y dashboards

#### 2.4.8 Métodos Auxiliares de Consolidación

##### `_is_period_close(slip, tipo_prestacion)`
**Responsabilidad:** Determina si es mes de consolidación
- **Lógica:**
  - Prima: Junio (6) y Diciembre (12) - línea 723
  - Cesantías/Intereses: Diciembre (12) - línea 725
  - Vacaciones: Diciembre (12) - línea 727
- **Salida:** `bool`

##### `_get_consolidation_info(localdict, tipo_prestacion)`
**Responsabilidad:** Obtiene info completa de consolidación
- **Datos:**
  - Provisión acumulada desde nóminas
  - Saldo contable (si configurado)
  - Periodo de cierre
- **Salida:** dict con info de consolidación

##### `_get_periodo_cierre_label(tipo_prestacion, slip)`
**Responsabilidad:** Genera etiqueta del periodo
- **Salida:** str descriptivo (ej: "Prima 1 Semestre 2026")

##### `_get_provision_type(localdict, tipo_prestacion)`
**Responsabilidad:** Determina tipo de provisión según configuración
- **Lógica:**
  1. Lee parámetro `usar_porcentaje_fijo_{tipo}` - línea 665
  2. Si True: retorna 'porcentaje_fijo'
  3. Si False: retorna 'simple'
- **Salida:** 'simple' | 'promediado' | 'porcentaje_fijo'

---

## 3. CONTRATOS DE ENTRADA/SALIDA ENTRE MÉTODOS

### 3.1 Contrato de Entrada Común (localdict)

**TODOS los métodos principales reciben:**
```python
localdict = {
    'slip': hr.payslip,                    # Nómina actual
    'contract': hr.contract,               # Contrato del empleado
    'employee': hr.employee,               # Empleado
    'annual_parameters': hr.annual.parameters,  # Parámetros anuales (SMMLV, etc.)
    'rules': dict,                         # Reglas ya evaluadas (para intereses)
    # ... otros campos estándar de Odoo payroll
}
```

### 3.2 Contratos por Servicio

#### prestaciones.calculate_prestacion()
```python
# ENTRADA
localdict: dict
tipo_prestacion: 'prima' | 'cesantias' | 'intereses' | 'vacaciones'
context: 'provision' | 'liquidacion' | 'consolidacion' | 'provision_completa'
provision_type: 'simple' | 'promediado' | 'porcentaje_fijo'

# SALIDA
tuple: (
    base_diaria: float,      # Base mensual / 30
    dias: int,               # Días trabajados finales
    porcentaje: float,       # Siempre 100
    nombre: str,             # Nombre descriptivo
    log: str,                # Log (vacío normalmente)
    detail: dict             # Detalle completo (ver estructura abajo)
)
```

#### Estructura de `detail` dict
```python
detail = {
    # Secciones de prestaciones_detail.generate()
    'metricas': {
        'valor_total': float,
        'base_mensual': float,
        'base_diaria': float,
        'dias_trabajados': int,
        'dias_periodo': int,
    },
    'valores_usados': {...},
    'promedio_salario': {...},
    'condiciones': {...},
    'dias': {...},
    'valor_dia': {...},
    'formula_explicacion': {...},
    'resumen_dias': {...},
    'cambios_salario': {...},
    'cambios_auxilio': {...},
    'desglose_variables_ordenado': {...},
    'debug_formula_completa': {...},
    'desglose_transporte_sueldo': {...},
    'lineas_base_variable': [...],
    'metadata': {...},
    'aplica': bool,
    'motivo': str,

    # CRÍTICO: Campo usado por hr_slip.py
    'monto_total': float,  # Valor total calculado
}
```

#### prestaciones_detail.generate()
```python
# ENTRADA
localdict: dict
tipo_prestacion: str
base_info: {
    'base_mensual': float,
    'base_diaria': float,
    'salary': float,
    'variable': float,
    'auxilio': float,
    'auxilio_promedio': float,
    'salary_info': {...},
    'auxilio_check': {...},
    'variable_lines': [...],
    # ... otros campos
}
days_info: {
    'dias_periodo': int,
    'dias_ausencias': int,
    'dias_total': int,
    'detalle_ausencias': list,
}
valor: float  # Valor ya calculado

# SALIDA
detail: dict  # Ver estructura arriba
```

#### prestaciones_liquidacion._adapt_result_for_slip()
```python
# ENTRADA
result: tuple  # Resultado de calculate_prestacion()
localdict: dict
tipo_prestacion: str

# SALIDA
tuple: (
    amount: float,       # base_diaria * 30 (base mensual)
    qty: float,          # dias
    rate: float,         # porcentaje
    name: str,           # nombre
    log: str,            # log
    data: {              # CRÍTICO: formato para hr_slip.py
        'monto_total': float,      # ← hr_slip.py busca este campo
        'fecha_inicio': str,
        'fecha_fin': str,
        'data_kpi': {...},
        'aplica': bool,
        'detail': dict,
    }
)
```

#### prestaciones_provisiones._calculate_consolidacion()
```python
# ENTRADA
localdict: dict
tipo_prestacion: 'cesantias' | 'intereses' | 'vacaciones'

# SALIDA
tuple: (
    ajuste: float,       # obligacion_real - provision_acumulada
    qty: 1,
    rate: 100,
    nombre: str,
    log: '',
    data: {
        'monto_total': float,              # ajuste
        'ajuste': float,
        'obligacion_real': float,
        'provision_acumulada': float,      # Desde nóminas
        'saldo_provision': float,          # Desde contabilidad (opcional)
        'saldo_obligacion': float,         # Desde contabilidad (opcional)
        'metricas': {...},
        'saldo_contable': {...},
        'formula_explicacion': {...},
        'provisiones_detalle': [...],
    }
)
```

---

## 4. REGLAS DE INTERACCIÓN (CLARAS Y CONCISAS)

### 4.1 Separación de Responsabilidades (Principio ÚNICO)

```
┌─────────────────────────────────────────────────────────┐
│  REGLA #1: Solo prestaciones.py CALCULA                 │
│  Los demás archivos ADAPTAN o PRESENTAN                 │
└─────────────────────────────────────────────────────────┘
```

**PROHIBIDO:**
- ❌ `prestaciones_detail.py` NO puede llamar a `calculate_prestacion()` internamente
- ❌ `prestaciones_liquidacion.py` NO puede recalcular valores
- ❌ `prestaciones_provisiones.py` NO puede modificar fórmulas de prestación base

**PERMITIDO:**
- ✅ `prestaciones.py` calcula y retorna tuple + detail
- ✅ `prestaciones_detail.py` consume `base_info`, `days_info`, `valor` y genera dict
- ✅ Adaptadores llaman a `calculate_prestacion()` y reformatean salida

### 4.2 Flujos de Llamadas Permitidos

#### Flujo Normal de Provisión Mensual
```
Regla PRV_CES
    ↓
prestaciones_provisiones._prv_ces(localdict)
    ↓
_calculate_provision_rule(localdict, 'cesantias')
    ↓
prestaciones.calculate_prestacion(localdict, 'cesantias', context='provision', ...)
    ↓ (interno)
    ├─ _get_period()
    ├─ _calculate_days()
    ├─ period.payslip.query.service.calculate_base_prestacion()
    ├─ _calculate_value()
    └─ prestaciones_detail.generate()  ← GENERA DETAIL
    ↓
Retorna tuple + detail
    ↓
_adapt_provision_result()  ← ADAPTA A FORMATO HR_SLIP
    ↓
Retorna (amount, qty, rate, name, log, data)
```

#### Flujo de Liquidación
```
Regla CESANTIAS
    ↓
prestaciones_liquidacion._cesantias(localdict)
    ↓
prestaciones.calculate_prestacion(localdict, 'cesantias', context='liquidacion', ...)
    ↓ (mismo flujo interno)
    └─ Retorna tuple + detail
    ↓
_adapt_result_for_slip()  ← ADAPTA A FORMATO HR_SLIP
    ↓
Retorna (amount, qty, rate, name, log, data)
```

#### Flujo de Consolidación
```
Regla CONS_CES
    ↓
prestaciones_provisiones._cons_ces(localdict)
    ↓
_calculate_consolidacion(localdict, 'cesantias')
    ↓
    ├─ prestaciones.calculate_prestacion(..., context='consolidacion')  ← OBLIGACIÓN REAL
    ├─ _get_provision_acumulada()  ← PROVISIONES DESDE NÓMINAS
    ├─ _get_saldo_cuenta() (opcional)  ← SALDOS CONTABLES
    └─ Calcula: ajuste = obligacion_real - provision_acumulada
    ↓
Retorna (ajuste, 1, 100, nombre, '', data_consolidacion)
```

### 4.3 Reglas de Dependencia de Datos

#### Para INTERESES de Cesantías (CRÍTICO)

```python
# ✅ CORRECTO: Intereses usa cesantías YA CALCULADAS
localdict['rules']['CESANTIAS'].total  # Valor de la misma nómina
    ↓
prestaciones._get_cesantias_from_slip(localdict)
    ↓
base_info['cesantias_calculadas'] = valor
    ↓
_calculate_value('intereses', base_info, ...)
    usa cesantias = base_info.get('cesantias_calculadas', 0)

# ❌ INCORRECTO: Recalcular cesantías dentro de intereses
def _calculate_value(...):
    if tipo == 'intereses':
        cesantias = (base * dias) / 360  # ¡NO! Usar base_info
```

**Regla #2:**
```
INTERESES siempre depende de CESANTIAS ya calculadas.
NUNCA recalcular cesantías dentro del método de intereses.
```

### 4.4 Reglas de Contexto

| Context | Cuándo usar | Características |
|---------|-------------|-----------------|
| `'provision'` | Nóminas mensuales normales | Usa `slip.date_to`, puede usar porcentaje_fijo |
| `'provision_completa'` | Provisiones cuando `simple_provisions=False` | Calcula como liquidación pero usando `slip.date_to` |
| `'liquidacion'` | Liquidación de contrato | Usa `contract.date_end`, acumulados completos |
| `'consolidacion'` | Ajuste de consolidación | Calcula obligación real para comparar con provisiones |

**Regla #3:**
```
El flag 'simple_provisions' (desde annual_parameters o company)
determina si usar 'provision' o 'provision_completa'.

- simple_provisions = True  → context='provision', provision_type='porcentaje_fijo'
- simple_provisions = False → context='provision_completa', provision_type='simple'
```

### 4.5 Reglas de Formato de Salida

#### Para Reglas Salariales (hr_payslip_line)
```python
# FORMATO REQUERIDO
(amount, qty, rate, name, log, data)

# donde:
amount = base_diaria * 30  # Base mensual
qty = dias                 # Días trabajados
rate = 100                 # Porcentaje (siempre 100)
name = "NOMBRE DESCRIPTIVO"
log = ""                   # Normalmente vacío
data = {
    'monto_total': float,  # ← CRÍTICO: hr_slip.py busca este campo
    'fecha_inicio': str,
    'fecha_fin': str,
    'data_kpi': {...},
    'detail': {...},       # Detalle completo de prestaciones_detail
}
```

**Regla #4:**
```
hr_slip.py busca data['monto_total'] para el valor de la regla.
Este campo es OBLIGATORIO en el dict 'data'.
```

### 4.6 Reglas de NO Modificación

**PROHIBIDO modificar:**
- ❌ `localdict` (es entrada, no salida)
- ❌ Registros de base de datos (slip, contract, employee)
- ❌ Parámetros de configuración
- ❌ Cuentas contables (solo lectura de saldos)

**PERMITIDO consultar:**
- ✅ hr.payslip.line (para provisiones acumuladas)
- ✅ hr.leave.line (para ausencias)
- ✅ account.move.line (para saldos contables)
- ✅ hr.accumulated_payroll (para variables)
- ✅ ir.config_parameter (para configuración)

### 4.7 Reglas de Manejo de Errores

```python
# ✅ CORRECTO: Try-catch en consultas externas
try:
    dias_ausencias = slip.get_leave_days_no_pay(...)
except Exception as e:
    _logger.warning(f"Error obteniendo ausencias: {e}")
    dias_ausencias = 0

# ✅ CORRECTO: Validación de aplicabilidad
if not validation['aplica']:
    return (0, 0, 0, motivo, "", {'aplica': False, 'motivo': motivo})

# ✅ CORRECTO: Manejo robusto en batch
for tipo in ['prima', 'cesantias', ...]:
    try:
        result = calculate_liquidacion(localdict, tipo)
        # ... procesar result
    except Exception as e:
        _logger.error(f"Error en {tipo}: {e}")
        resultados[tipo] = {'error': str(e), 'aplica': False}
```

**Regla #5:**
```
SIEMPRE usar try-catch al consultar datos externos
(ausencias, acumulados, movimientos contables).
NUNCA dejar que una excepción rompa el cálculo completo.
```

---

## 5. AGRUPACIÓN LÓGICA POR RESPONSABILIDAD

### 5.1 Capa de Cálculo (prestaciones.py)

**Responsabilidad:** Ejecutar fórmulas matemáticas y lógica de negocio

**Métodos clave:**
- `calculate_prestacion()` - Orquestador principal
- `_get_period()` - Lógica de periodos
- `_calculate_days()` - Lógica de días y ausencias
- `_calculate_value()` - Fórmulas matemáticas
- `_get_conditions()` - Centralización de configuración
- `_validate_conditions()` - Validaciones de aplicabilidad

**Características:**
- NO formatea para UI
- NO adapta para hr_slip
- NO consulta contabilidad
- Solo matemática y lógica de negocio

### 5.2 Capa de Presentación (prestaciones_detail.py)

**Responsabilidad:** Formatear datos para visualización

**Métodos clave:**
- `generate()` - Generador principal
- `_build_metricas()` - Sección KPIs
- `_build_valores_usados()` - Desglose de valores
- `_build_dias()` - Desglose de días
- `_build_formula_explicacion()` - Explicación paso a paso
- `_build_*()` - Constructores de secciones

**Características:**
- NO calcula valores
- NO llama a calculate_prestacion()
- Solo consume y formatea
- Genera estructura para widget JavaScript

### 5.3 Capa de Adaptación - Nómina (prestaciones_liquidacion.py)

**Responsabilidad:** Puente entre cálculo y sistema de nómina

**Métodos clave:**
- `_prima()`, `_cesantias()`, `_intcesantias()`, `_vaccontrato()` - Entradas de reglas
- `_adapt_result_for_slip()` - Adaptador de formato
- `calculate_liquidacion()` - Servicio de liquidación
- `liquidar_todas()` - Batch liquidación

**Características:**
- NO recalcula, solo adapta
- Determina context según struct_process
- Formatea salida para hr_slip.py
- Maneja casos especiales (año anterior)

### 5.4 Capa de Adaptación - Contabilidad (prestaciones_provisiones.py)

**Responsabilidad:** Provisiones mensuales y consolidación contable

**Métodos clave:**
- `_prv_*()` - Entradas de reglas de provisión
- `_calculate_provision_rule()` - Motor de provisión
- `_cons_*()` - Entradas de reglas de consolidación
- `_calculate_consolidacion()` - Motor de consolidación
- `_get_provision_acumulada()` - Consulta desde nóminas
- `_get_saldo_cuenta()` - Consulta desde contabilidad

**Características:**
- NO modifica contabilidad
- Lee provisiones desde hr.payslip.line
- Lee saldos desde account.move.line
- Calcula ajustes (no los aplica)

---

## 6. PARÁMETROS CONFIGURABLES Y SU UBICACIÓN

### 6.1 Parámetros en ir.config_parameter

| Parámetro | Default | Descripción | Usado en |
|-----------|---------|-------------|----------|
| `lavish_hr_payroll.base_dias_prestaciones` | 360 | Divisor para cesantías e intereses | _calculate_value() |
| `lavish_hr_payroll.base_dias_prima` | 180 | Divisor para prima semestral | _calculate_value() |
| `lavish_hr_payroll.base_dias_vacaciones` | 720 | Divisor para vacaciones | _calculate_value() |
| `lavish_hr_payroll.dias_vacaciones` | 15 | Días de vacaciones por año | Informativo |
| `lavish_hr_payroll.dias_mes` | 30 | Días comerciales por mes | _calculate_value() |
| `lavish_hr_payroll.tasa_intereses_cesantias` | 0.12 | Tasa anual de intereses (12%) | _calculate_value() |
| `lavish_hr_payroll.tope_auxilio_smmlv` | 2 | Tope para derecho a auxilio | _get_conditions() |
| `lavish_hr_payroll.prima_incluye_auxilio` | True | Incluir auxilio en prima | _get_conditions() |
| `lavish_hr_payroll.cesantias_incluye_auxilio` | True | Incluir auxilio en cesantías | _get_conditions() |
| `lavish_hr_payroll.intereses_incluye_auxilio` | True | Incluir auxilio en intereses | _get_conditions() |
| `lavish_hr_payroll.vacaciones_incluye_auxilio` | False | Incluir auxilio en vacaciones | _get_conditions() |
| `lavish_hr_payroll.auxilio_prestaciones_metodo` | 'dias_trabajados' | Método de cálculo de auxilio | period.payslip.query.service |
| `lavish_hr_payroll.provision_cesantias_porcentaje` | 8.33 | Porcentaje fijo cesantías | _calculate_value() |
| `lavish_hr_payroll.provision_intereses_porcentaje` | 1.0 | Porcentaje fijo intereses | _calculate_value() |
| `lavish_hr_payroll.provision_prima_porcentaje` | 8.33 | Porcentaje fijo prima | _calculate_value() |
| `lavish_hr_payroll.provision_vacaciones_porcentaje` | 4.17 | Porcentaje fijo vacaciones | _calculate_value() |
| `lavish_hr_payroll.usar_porcentaje_fijo_cesantias` | False | Usar % fijo en provisión | _calculate_value() |
| `lavish_hr_payroll.usar_porcentaje_fijo_intereses` | False | Usar % fijo en provisión | _calculate_value() |
| `lavish_hr_payroll.usar_porcentaje_fijo_prima` | False | Usar % fijo en provisión | _calculate_value() |
| `lavish_hr_payroll.usar_porcentaje_fijo_vacaciones` | False | Usar % fijo en provisión | _calculate_value() |
| `lavish_hr_payroll.integrar_consolidacion_liquidacion` | False | Integrar con contabilidad | _calculate_consolidacion() |

### 6.2 Parámetros en hr.annual.parameters

| Campo | Default | Descripción | Usado en |
|-------|---------|-------------|----------|
| `smmlv_monthly` | - | Salario mínimo mensual | _get_conditions(), tope auxilio |
| `transportation_assistance_monthly` | - | Auxilio de transporte | _get_conditions(), base cálculo |
| `uvt` | - | Unidad de Valor Tributario | Informativo |
| `simple_provisions` | False | Modo de cálculo de provisiones | calculate_prestacion(), provision_rule |
| `value_porc_provision_bonus` | 8.33 | Porcentaje provisión prima | _get_conditions() |
| `value_porc_provision_cesantias` | 8.33 | Porcentaje provisión cesantías | _get_conditions() |
| `value_porc_provision_intcesantias` | 1.0 | Porcentaje provisión intereses | _get_conditions() |
| `value_porc_provision_vacation` | 4.17 | Porcentaje provisión vacaciones | _get_conditions() |

### 6.3 Parámetros en res.company

| Campo | Default | Descripción | Usado en |
|-------|---------|-------------|----------|
| `simple_provisions` | False | Fallback para modo provisiones | calculate_prestacion() |

### 6.4 Parámetros en hr.contract

| Campo | Descripción | Usado en |
|-------|-------------|----------|
| `wage` | Salario base | Base de cálculo |
| `modality_salary` | 'basico' \| 'integral' \| ... | Determina tipo de cálculo |
| `modality_aux` | 'basico' \| 'variable' \| 'no' | Manejo de auxilio |
| `only_wage` | 'wage' \| ... | Solo salario base |
| `factor_integral` | Factor para salario integral | Cálculo integral |

### 6.5 Parámetros en hr.contract.type

| Campo | Descripción | Usado en |
|-------|-------------|----------|
| `has_prima` | Aplica prima | Validación |
| `has_cesantias` | Aplica cesantías | Validación |
| `has_intereses_cesantias` | Aplica intereses | Validación |
| `has_vacaciones` | Aplica vacaciones | Validación |
| `has_auxilio_transporte` | Aplica auxilio | Validación |
| `is_apprenticeship` | Es aprendiz | Validación Ley 2466 |
| `has_social_benefits_aprendiz` | Aprendiz con prestaciones | Validación Ley 2466 |

### 6.6 Parámetros en hr.leave.type

| Campo | Descripción | Usado en |
|-------|-------------|----------|
| `unpaid_absences` | Ausencia no remunerada | _calculate_days() |
| `discounting_bonus_days` | Descuenta de prestaciones | _get_discounting_bonus_days() |

---

## 7. FÓRMULAS INTERNAS POR MÉTODO

### 7.1 _calculate_value() - Prima

```python
# PROVISION SIMPLE (porcentaje_fijo)
if context == 'provision' and provision_type == 'porcentaje_fijo':
    porcentaje = 8.33  # 1/12 del salario
    valor = (base_mensual * (porcentaje / 100) * dias_mes) / dias_mes
    # Simplificado: base_mensual * 8.33%

# PROVISION COMPLETA / LIQUIDACION (días trabajados)
else:
    valor = (base_mensual * dias_trabajados) / base_dias_prima
    # Default: base_dias_prima = 180 (semestre comercial)
```

**Ejemplo:**
```
Base mensual: $1,500,000
Días trabajados: 90 (3 meses)

Provisión porcentaje fijo:
  $1,500,000 * 8.33% = $124,950

Provisión completa/liquidación:
  ($1,500,000 * 90) / 180 = $750,000
```

### 7.2 _calculate_value() - Cesantías

```python
# PROVISION SIMPLE (porcentaje_fijo)
if context == 'provision' and provision_type == 'porcentaje_fijo':
    porcentaje = 8.33  # 1/12 del salario
    valor = (base_mensual * (porcentaje / 100) * dias_mes) / dias_mes
    # Simplificado: base_mensual * 8.33%

# PROVISION COMPLETA / LIQUIDACION (días trabajados)
else:
    valor = (base_mensual * dias_trabajados) / base_dias_prestaciones
    # Default: base_dias_prestaciones = 360 (año comercial)
```

**Ejemplo:**
```
Base mensual: $1,500,000
Días trabajados: 186 (6 meses + 6 días)

Provisión porcentaje fijo:
  $1,500,000 * 8.33% = $124,950

Provisión completa/liquidación:
  ($1,500,000 * 186) / 360 = $775,000
```

### 7.3 _calculate_value() - Intereses de Cesantías

```python
# Obtener cesantías YA CALCULADAS (crítico)
cesantias = base_info.get('cesantias_calculadas', 0)

# PROVISION SIMPLE
if context == 'provision' and provision_type == 'simple':
    tasa_efectiva = tasa_intereses * dias_trabajados / 360
    valor = cesantias * tasa_efectiva
    # Tasa efectiva = 12% * (dias / 360)

# PROVISION PROMEDIADA
elif context == 'provision' and provision_type == 'promediado':
    tasa_efectiva_mes = tasa_intereses * dias_mes / 360
    valor = cesantias * tasa_efectiva_mes
    # Tasa efectiva mes = 12% * (30 / 360) = 1%

# PROVISION PORCENTAJE FIJO
elif context == 'provision' and provision_type == 'porcentaje_fijo':
    porcentaje = 1.0  # 12%/12 meses
    valor = (base_mensual * (porcentaje / 100) * dias_mes) / dias_mes
    # Simplificado: base_mensual * 1%

# LIQUIDACION / PROVISION COMPLETA
elif context in ('liquidacion', 'provision_completa'):
    cesantias_acum = base_info.get('cesantias_acumuladas', cesantias)
    TASA_FIJA = 0.12  # 12% LEGAL (Art. 99 Ley 50/1990)
    tasa_efectiva_liq = TASA_FIJA * dias_trabajados / 360
    valor = cesantias_acum * tasa_efectiva_liq

# CONSOLIDACION
elif context == 'consolidacion':
    intereses_prov = base_info.get('intereses_provisionados', 0)
    intereses_real = cesantias * tasa_efectiva
    valor = intereses_real - intereses_prov  # Ajuste
```

**Ejemplo:**
```
Cesantías calculadas: $956,068
Días: 186

Provision simple:
  Tasa efectiva = 12% * (186/360) = 6.2%
  Intereses = $956,068 * 6.2% = $59,276

Provision promediada (mensual):
  Tasa mes = 12% * (30/360) = 1%
  Intereses = $956,068 * 1% = $9,561

Provision porcentaje fijo:
  Base mensual = $1,500,000
  Intereses = $1,500,000 * 1% = $15,000

Liquidación:
  Tasa FIJA = 12% * (186/360) = 6.2%
  Intereses = $956,068 * 6.2% = $59,276
```

### 7.4 _calculate_value() - Vacaciones

```python
# PROVISION SIMPLE (porcentaje_fijo)
if context == 'provision' and provision_type == 'porcentaje_fijo':
    porcentaje = 4.17  # 15/360
    valor = (base_mensual * (porcentaje / 100) * dias_mes) / dias_mes
    # Simplificado: base_mensual * 4.17%

# PROVISION COMPLETA / LIQUIDACION (días trabajados)
else:
    valor = (base_mensual * dias_trabajados) / base_dias_vacaciones
    # Default: base_dias_vacaciones = 720 (año x 2)
```

**Ejemplo:**
```
Base mensual: $1,500,000
Días trabajados: 360 (1 año completo)

Provisión porcentaje fijo:
  $1,500,000 * 4.17% = $62,550

Provisión completa/liquidación:
  ($1,500,000 * 360) / 720 = $750,000
  Equivalente a 15 días de vacaciones
```

### 7.5 _calculate_days() - Descuento de Ausencias

```python
# 1. Días del periodo (año comercial 360)
dias_periodo = days360(date_from, date_to)

# 2. Ausencias no remuneradas (aplica a TODAS las prestaciones)
dias_ausencias_no_pago = slip.get_leave_days_no_pay(date_from, date_to, contract.id)

# 3. Ausencias con discounting_bonus_days (solo prima, cesantías, intereses)
if tipo_prestacion in ('prima', 'cesantias', 'intereses'):
    dias_descuento_bonus = count(hr.leave.line where:
        - contract_id = contract.id
        - date >= date_from and date <= date_to
        - leave_id.state = 'validate'
        - leave_id.holiday_status_id.discounting_bonus_days = True
        - leave_id.holiday_status_id.unpaid_absences = False  # Evita doble conteo
    )
else:
    dias_descuento_bonus = 0

# 4. Total de días a descontar
dias_ausencias_total = dias_ausencias_no_pago + dias_descuento_bonus

# 5. Días finales
dias_total = max(0, dias_periodo - dias_ausencias_total)
```

**Ejemplo:**
```
Periodo: 1 Ene - 30 Jun (180 días)
Ausencias no remuneradas: 10 días
Ausencias con discounting_bonus_days: 5 días

Cálculo:
  dias_periodo = 180
  dias_ausencias_no_pago = 10
  dias_descuento_bonus = 5
  dias_ausencias_total = 10 + 5 = 15
  dias_total = 180 - 15 = 165
```

### 7.6 _calculate_consolidacion() - Ajuste

```python
# 1. Calcular obligación real (lo que se DEBE)
result = prestaciones.calculate_prestacion(
    localdict, tipo_prestacion, context='consolidacion', provision_type='simple'
)
obligacion_real = result[5]['metricas']['valor_total']

# 2. Obtener provisiones acumuladas (lo que se HA PROVISIONADO)
date_from, date_to = _get_period_dates(tipo_prestacion, slip.date_to)

provision_acumulada_data = _get_provision_acumulada(
    contract_id=contract.id,
    tipo_prestacion=tipo_prestacion,
    date_period_from=date_from,
    date_period_to=date_to,
    exclude_slip_id=slip.id
)
provision_acumulada = provision_acumulada_data['total']

# 3. Calcular ajuste
ajuste = obligacion_real - provision_acumulada

# Si ajuste > 0: Falta provisionar (pagar diferencia)
# Si ajuste < 0: Se provisionó de más (normalmente no pasa)
```

**Ejemplo:**
```
Tipo: Cesantías
Periodo: 1 Ene - 31 Dic 2026

Paso 1: Calcular obligación real
  Base: $1,500,000
  Días: 360
  Obligación = ($1,500,000 * 360) / 360 = $1,500,000

Paso 2: Obtener provisiones acumuladas
  Enero: $124,950
  Febrero: $124,950
  ...
  Noviembre: $124,950
  Total 11 meses = $1,374,450

Paso 3: Calcular ajuste
  Ajuste = $1,500,000 - $1,374,450 = $125,550

  → Falta provisionar $125,550 en Diciembre
```

---

## 8. CASOS ESPECIALES Y CONSIDERACIONES

### 8.1 Salario Integral

**Configuración:**
- `contract.modality_salary = 'integral'`
- `contract.factor_integral` (ej: 1.3 = 30% de factor prestacional)

**Comportamiento:**
- Algunas prestaciones NO aplican (ej: intereses año anterior)
- Validación en `_validate_conditions()`
- Warning informativo: "Salario integral - prestaciones incluidas"

### 8.2 Aprendices (Ley 2466/2025)

**Configuración:**
- `contract_type.is_apprenticeship = True`
- `contract_type.has_social_benefits_aprendiz = True/False`

**Lógica de aplicabilidad:**
```python
is_apprenticeship = contract_type.is_apprenticeship
has_social_benefits_aprendiz = contract_type.has_social_benefits_aprendiz

# Aplica si NO es aprendiz, o si es aprendiz CON prestaciones
aplica_aprendiz = (not is_apprenticeship) or has_social_benefits_aprendiz
```

### 8.3 Auxilio de Transporte

**Configuración:**
- `annual_parameters.transportation_assistance_monthly`
- `lavish_hr_payroll.tope_auxilio_smmlv` (default: 2)
- `contract.modality_aux` ('basico', 'variable', 'no')

**Tope de aplicabilidad:**
```python
salario_base = contract.wage
smmlv = annual_parameters.smmlv_monthly
tope_smmlv = 2

aplica_auxilio = salario_base <= (smmlv * tope_smmlv)
```

**Ejemplo:**
```
SMMLV 2026: $1,300,000
Tope: 2 SMMLV = $2,600,000

Salario: $2,400,000 → Aplica auxilio ✅
Salario: $2,700,000 → NO aplica auxilio ❌
```

**Métodos de cálculo:**
- `'basico_fijo'`: Auxilio vigente del contrato
- `'dias_trabajados'`: Promedio proporcional a días trabajados
- `'variable'`: Desde líneas de nómina (modality_aux='variable')

### 8.4 Promedio de Salario

**Configuración:**
- `lavish_hr_payroll.prima_salary_take` (promedio 6 meses en prima)
- `lavish_hr_payroll.cesantias_salary_take` (promedio 3 meses en cesantías)

**Cuándo promedia:**
- Si hay cambios de salario en el periodo
- Usa `period.payslip.query.service.calculate_base_prestacion()`
- Pondera por días de cada salario

**Detalle en widget:**
- `detail['promedio_salario']['es_promedio'] = True`
- `detail['cambios_salario']` con historial y ponderaciones

### 8.5 Variables y Bonos

**Fuentes:**
- `hr.payslip.line` (líneas de la nómina actual)
- `hr.accumulated_payroll` (acumulados de periodos anteriores)

**Inclusión en base:**
```python
variable_total = sum(lineas con category_code != 'AUX')
variable_promedio = (variable_total / days_worked) * 30

base_mensual = salary + variable_promedio + auxilio_promedio
```

**Exclusión de auxilio:**
- Líneas con `category_code = 'AUX'` se excluyen de variable
- Se suman a auxilio_promedio separadamente
- Ver `_build_lineas_base_variable()` línea 289

### 8.6 Año Anterior (CES_YEAR, INTCES_YEAR)

**Aplicabilidad:**
- Solo en liquidación de contrato
- Solo en enero/febrero
- Solo si `pagar_cesantias_ano_anterior = True`

**Cálculo:**
```python
# Periodo: 1 Ene año_anterior - 31 Dic año_anterior
year = slip.date_to.year - 1
date_from = date(year, 1, 1)
date_to = date(year, 12, 31)

# Ajustar por fecha de inicio de contrato
if contract.date_start > date_from:
    date_from = contract.date_start

# Calcular con periodo del año anterior
result = calculate_prestacion(temp_localdict, tipo, context='liquidacion')
```

### 8.7 Provisiones con simple_provisions

**Flag crítico:** `simple_provisions` (desde `hr.annual.parameters` o `res.company`)

| simple_provisions | Context | Provision Type | Método |
|-------------------|---------|----------------|--------|
| True | 'provision' | 'porcentaje_fijo' | Porcentaje mensual fijo |
| False | 'provision_completa' | 'simple' | Liquidación al corte usando date_to |

**Impacto:**
```python
# simple_provisions = True (provisión simple)
Prima:      base * 8.33%
Cesantías:  base * 8.33%
Intereses:  base * 1%
Vacaciones: base * 4.17%

# simple_provisions = False (provisión completa)
Prima:      (base * dias) / 180
Cesantías:  (base * dias) / 360
Intereses:  (cesantias * 12% * dias) / 360
Vacaciones: (base * dias) / 720
```

**Ventajas simple=True:**
- Cálculo rápido y constante
- No depende de días trabajados del mes
- Siempre el mismo % mensual

**Ventajas simple=False:**
- Más preciso (considera días reales)
- Acumula correctamente ausencias
- Ajusta automáticamente por proporcionalidad

### 8.8 Consolidación Contable

**Configuración:**
- `lavish_hr_payroll.integrar_consolidacion_liquidacion` (True/False)
- Parámetros de cuentas:
  - `lavish_hr_payroll.cuenta_provision_cesantias_id`
  - `lavish_hr_payroll.cuenta_consolidacion_cesantias_id`
  - (similar para intereses, vacaciones, prima)

**Cuentas por defecto (PUC Colombia):**
```python
CUENTAS_PRESTACIONES = {
    'cesantias': {
        'provision': '261005',    # Pasivos estimados
        'obligacion': '2510',     # Obligaciones laborales
    },
    'intereses': {
        'provision': '261010',
        'obligacion': '2515',
    },
    'vacaciones': {
        'provision': '261015',
        'obligacion': '2525',
    },
    'prima': {
        'provision': '261020',
        'obligacion': '2520',
    },
}
```

**Flujo de consolidación:**
1. Calcula obligación real (prestaciones)
2. Busca provisiones en hr.payslip.line
3. Opcionalmente lee saldos de account.move.line
4. Calcula ajuste = obligacion - provisiones
5. **NO modifica contabilidad** (solo reporta ajuste)

---

## 9. RECOMENDACIONES FINALES

### 9.1 Pruebas Unitarias Recomendadas

#### Archivo: tests/test_prestaciones_calculo.py

```python
class TestPrestacionesCalculo(TransactionCase):
    """Pruebas del motor de cálculo (prestaciones.py)"""

    def test_calculate_value_prima_simple(self):
        """Prima con fórmula simple (base * dias / 180)"""

    def test_calculate_value_prima_porcentaje_fijo(self):
        """Prima con porcentaje fijo (8.33%)"""

    def test_calculate_value_cesantias_simple(self):
        """Cesantías con fórmula simple (base * dias / 360)"""

    def test_calculate_value_intereses_con_cesantias(self):
        """Intereses usando cesantías calculadas"""

    def test_calculate_value_intereses_sin_cesantias(self):
        """Intereses fallback si no hay cesantías"""

    def test_calculate_days_con_ausencias_no_pago(self):
        """Descuento de ausencias no remuneradas"""

    def test_calculate_days_con_discounting_bonus_days(self):
        """Descuento de ausencias con flag especial"""

    def test_calculate_days_evita_doble_conteo(self):
        """No contar dos veces ausencias no remuneradas"""

    def test_get_period_prima_semestre_1(self):
        """Periodo de prima: Ene-Jun"""

    def test_get_period_prima_semestre_2(self):
        """Periodo de prima: Jul-Dic"""

    def test_get_period_cesantias_ano(self):
        """Periodo de cesantías: Ene-Dic"""

    def test_get_conditions_aprendiz_sin_prestaciones(self):
        """Aprendiz sin prestaciones (Ley 2466)"""

    def test_get_conditions_aprendiz_con_prestaciones(self):
        """Aprendiz con prestaciones (Ley 2466)"""

    def test_validate_conditions_salario_integral(self):
        """Validación salario integral"""

    def test_get_cesantias_from_slip(self):
        """Obtener cesantías de rules dict"""
```

#### Archivo: tests/test_prestaciones_detail.py

```python
class TestPrestacionesDetail(TransactionCase):
    """Pruebas del generador de detalle (prestaciones_detail.py)"""

    def test_generate_estructura_completa(self):
        """Genera todas las 12 secciones"""

    def test_build_metricas(self):
        """Sección 1: Métricas KPI"""

    def test_build_valores_usados_con_auxilio(self):
        """Sección 2: Desglose con auxilio"""

    def test_build_valores_usados_sin_auxilio(self):
        """Sección 2: Desglose sin auxilio"""

    def test_build_lineas_base_variable_excluye_auxilio(self):
        """Excluir líneas AUX de variable"""

    def test_build_formula_explicacion_prima(self):
        """Explicación paso a paso de prima"""

    def test_build_formula_explicacion_intereses(self):
        """Explicación paso a paso de intereses"""
```

#### Archivo: tests/test_prestaciones_liquidacion.py

```python
class TestPrestacionesLiquidacion(TransactionCase):
    """Pruebas del adaptador de liquidación"""

    def test_adapt_result_for_slip_formato(self):
        """Adapta a formato hr_slip correcto"""

    def test_adapt_result_monto_total_presente(self):
        """data['monto_total'] existe (crítico)"""

    def test_calcular_prestacion_ano_anterior_cesantias(self):
        """Cesantías del año anterior"""

    def test_calcular_prestacion_ano_anterior_intereses(self):
        """Intereses del año anterior"""

    def test_validar_liquidacion_struct_process_contrato(self):
        """Valida que sea liquidación de contrato"""

    def test_liquidar_todas_suma_correctamente(self):
        """Suma de todas las prestaciones"""
```

#### Archivo: tests/test_prestaciones_provisiones.py

```python
class TestPrestacionesProvisiones(TransactionCase):
    """Pruebas del adaptador de provisiones"""

    def test_calculate_provision_rule_simple_provisions_true(self):
        """Provisión simple con porcentaje fijo"""

    def test_calculate_provision_rule_simple_provisions_false(self):
        """Provisión completa (liquidación al corte)"""

    def test_calculate_consolidacion_ajuste_positivo(self):
        """Ajuste positivo (falta provisionar)"""

    def test_calculate_consolidacion_ajuste_cero(self):
        """Ajuste cero (provisión exacta)"""

    def test_get_provision_acumulada_excluye_slip_actual(self):
        """Excluir nómina actual de acumulados"""

    def test_get_provision_acumulada_codigos_correctos(self):
        """Usa códigos correctos por tipo"""

    def test_get_saldo_cuenta_by_id(self):
        """Consulta saldo de cuenta específica"""

    def test_get_saldo_cuenta_by_prefijo(self):
        """Consulta saldo por prefijo PUC"""
```

### 9.2 Documentación Recomendada

#### 9.2.1 Documentar el Contrato de detail

Crear archivo: `docs/CONTRATO_DETAIL_PRESTACIONES.md`

**Contenido:**
- Estructura completa del dict `detail`
- Descripción de cada sección
- Campos obligatorios vs opcionales
- Ejemplos JSON completos
- Cambios de versión

**Objetivo:** Evitar cambios ocultos que rompan el widget JavaScript

#### 9.2.2 Documentar Flujos de Cálculo

Crear archivo: `docs/FLUJOS_CALCULO_PRESTACIONES.md`

**Contenido:**
- Diagrama de flujo de provisión mensual
- Diagrama de flujo de liquidación
- Diagrama de flujo de consolidación
- Casos especiales y sus flujos

#### 9.2.3 Documentar Parámetros de Configuración

Crear archivo: `docs/PARAMETROS_CONFIGURACION_PRESTACIONES.md`

**Contenido:**
- Lista completa de parámetros
- Valores por defecto
- Impacto de cada parámetro
- Ejemplos de configuración

### 9.3 Refactorización Recomendada (Futuro)

#### 9.3.1 Extraer Servicio de Base de Cálculo

**Problema:** `period.payslip.query.service` se llama desde prestaciones.py

**Propuesta:** Crear servicio dedicado `prestaciones.base.service`

**Beneficio:**
- Centraliza cálculo de base
- Facilita testing
- Separa responsabilidad

#### 9.3.2 Constantes en Archivo Dedicado

**Problema:** Constantes duplicadas en varios archivos

**Propuesta:** Crear `models/reglas/prestaciones_constants.py`

```python
# prestaciones_constants.py

# Divisores legales
BASE_DIAS_PRESTACIONES = 360  # Año comercial
BASE_DIAS_PRIMA = 180          # Semestre comercial
BASE_DIAS_VACACIONES = 720     # 15 días / 360 = año x 2
DIAS_MES = 30                  # Mes comercial

# Porcentajes de provisión
PORCENTAJE_CESANTIAS = 8.33    # 1/12
PORCENTAJE_PRIMA = 8.33        # 1/12
PORCENTAJE_INTERESES = 1.0     # 12%/12
PORCENTAJE_VACACIONES = 4.17   # 15/360

# Tasas
TASA_INTERESES_CESANTIAS = 0.12  # 12% anual (Art. 99 Ley 50/1990)

# Topes
TOPE_AUXILIO_SMMLV = 2  # 2 SMMLV para derecho a auxilio

# Cuentas PUC
CUENTAS_PRESTACIONES = {...}
```

**Beneficio:**
- Un único lugar para cambiar constantes
- Facilita mantenimiento
- Evita inconsistencias

#### 9.3.3 Validador de Detalle (Schema)

**Problema:** No hay validación de estructura de `detail`

**Propuesta:** Usar schema validator (ej: `cerberus`, `marshmallow`)

```python
# prestaciones_detail_schema.py

DETAIL_SCHEMA = {
    'metricas': {
        'type': 'dict',
        'required': True,
        'schema': {
            'valor_total': {'type': 'float', 'required': True},
            'base_mensual': {'type': 'float', 'required': True},
            # ...
        }
    },
    'monto_total': {'type': 'float', 'required': True},  # ← CRÍTICO
    # ...
}
```

**Beneficio:**
- Detecta errores de estructura temprano
- Documenta contrato implícitamente
- Facilita migraciones

### 9.4 Monitoreo y Logging

#### 9.4.1 Logging Estructurado

**Propuesta:** Usar logging estructurado con niveles claros

```python
# Nivel INFO: Flujo normal
_logger.info(f"[PREST] {tipo} context={context} periodo={date_from} a {date_to}")

# Nivel WARNING: Datos faltantes o casos edge
_logger.warning(f"[PREST] No aplica: {motivo}")

# Nivel ERROR: Errores inesperados
_logger.error(f"[PREST] Error calculando {tipo}: {e}", exc_info=True)

# Nivel DEBUG: Detalles de cálculo
_logger.debug(f"[PREST] base={base}, dias={dias}, valor={valor}")
```

#### 9.4.2 Métricas de Rendimiento

**Propuesta:** Medir tiempos de ejecución

```python
import time

def calculate_prestacion(...):
    start = time.time()
    # ... cálculo
    elapsed = time.time() - start
    _logger.debug(f"[PERF] calculate_prestacion({tipo}) took {elapsed:.3f}s")
```

**Beneficio:**
- Detecta cuellos de botella
- Facilita optimización
- Monitorea degradación

### 9.5 Checklist de Desarrollo

#### Al Modificar prestaciones.py (Cálculo)
- [ ] Verificar que NO se rompa contrato de salida (tuple + detail)
- [ ] Actualizar fórmulas en PLAN_PRESTACIONES_RESPONSABILIDADES.md
- [ ] Agregar/actualizar pruebas unitarias
- [ ] Validar con casos edge (ausencias, aprendices, salario integral)
- [ ] Verificar que intereses usa `cesantias_calculadas`
- [ ] Logging apropiado en puntos clave

#### Al Modificar prestaciones_detail.py (Detalle)
- [ ] Verificar que NO se llama a `calculate_prestacion()`
- [ ] Actualizar schema de `detail` si cambia estructura
- [ ] Validar que widget JavaScript sigue funcionando
- [ ] Verificar que `monto_total` está presente
- [ ] Excluir líneas AUX del variable
- [ ] Pruebas de formateo correcto

#### Al Modificar prestaciones_liquidacion.py (Adaptador)
- [ ] Verificar que `data['monto_total']` está presente
- [ ] Validar formato de salida hr_slip
- [ ] Pruebas con diferentes struct_process
- [ ] Validar liquidación año anterior

#### Al Modificar prestaciones_provisiones.py (Provisiones)
- [ ] Verificar lógica de `simple_provisions`
- [ ] Validar consulta de provisiones acumuladas
- [ ] Validar consolidación con ajuste correcto
- [ ] Pruebas con integración contable activada/desactivada
- [ ] Verificar exclusión de slip actual en acumulados

---

## 10. RESUMEN EJECUTIVO

### 10.1 Principios Arquitectónicos

1. **Separación de Responsabilidades:**
   - prestaciones.py → CALCULA
   - prestaciones_detail.py → PRESENTA
   - prestaciones_liquidacion.py → ADAPTA para nómina
   - prestaciones_provisiones.py → ADAPTA para contabilidad

2. **Fuente Única de Verdad:**
   - TODO cálculo pasa por `prestaciones.calculate_prestacion()`
   - Adaptadores NO recalculan, solo reformatean

3. **Dependencia Unidireccional:**
   ```
   prestaciones.py → prestaciones_detail.py
        ↑
        └── prestaciones_liquidacion.py
        └── prestaciones_provisiones.py
   ```

4. **Inmutabilidad de Entrada:**
   - `localdict` es entrada, NO se modifica
   - NO se modifican registros de base de datos
   - Solo lectura de datos externos

### 10.2 Flujos Críticos

#### Provisión Mensual
```
Regla PRV_CES → _prv_ces() → _calculate_provision_rule()
→ calculate_prestacion(context='provision') → tuple + detail
→ _adapt_provision_result() → (amount, qty, rate, name, log, data)
```

#### Liquidación
```
Regla CESANTIAS → _cesantias()
→ calculate_prestacion(context='liquidacion') → tuple + detail
→ _adapt_result_for_slip() → (amount, qty, rate, name, log, data)
```

#### Consolidación
```
Regla CONS_CES → _cons_ces() → _calculate_consolidacion()
→ calculate_prestacion(context='consolidacion')  [obligación real]
→ _get_provision_acumulada()                     [desde nóminas]
→ Calcula: ajuste = obligacion - provisiones
→ (ajuste, 1, 100, nombre, '', data_consolidacion)
```

### 10.3 Campos Críticos

| Campo | Dónde | Por qué es CRÍTICO |
|-------|-------|-------------------|
| `detail['monto_total']` | prestaciones.py | hr_slip.py busca este campo para valor de regla |
| `base_info['cesantias_calculadas']` | _calculate_value() | Intereses DEBE usar cesantías ya calculadas, NO recalcular |
| `simple_provisions` | annual_parameters/company | Determina TODO el modo de provisión (simple vs completa) |
| `context` | calculate_prestacion() | Define lógica de periodo y fórmula |
| `provision_type` | calculate_prestacion() | Define si usa porcentaje_fijo o días trabajados |

### 10.4 Puntos de Atención

1. **Intereses de Cesantías:**
   - SIEMPRE usar `base_info['cesantias_calculadas']`
   - NUNCA recalcular cesantías internamente
   - Tasa FIJA 12% en liquidación (Art. 99 Ley 50/1990)

2. **Ausencias:**
   - Evitar doble conteo (no_pago + discounting_bonus_days)
   - Solo prima/cesantías/intereses usan `discounting_bonus_days`
   - Límite de 1000 líneas en consultas

3. **Auxilio de Transporte:**
   - Excluir de líneas de variable (category_code='AUX')
   - Verificar tope 2 SMMLV
   - Considerar `modality_aux` del contrato

4. **Consolidación:**
   - Excluir nómina actual de provisiones acumuladas
   - Buscar provisiones por fecha de periodo de nómina (date_from/date_to)
   - NO modificar contabilidad (solo reportar ajuste)

5. **Formato de Salida:**
   - `data['monto_total']` es OBLIGATORIO para hr_slip
   - Tuple siempre: `(base_diaria, dias, 100, nombre, "", detail)`
   - Detail debe tener 12+ secciones estándar

---

## 11. CONTACTO Y MANTENIMIENTO

**Autor del Plan:** Sistema de Análisis
**Fecha:** 2026-01-27
**Versión del Plan:** 1.0

**Para Actualizaciones:**
1. Leer este documento completo antes de modificar código
2. Actualizar sección relevante del plan al hacer cambios
3. Ejecutar pruebas unitarias completas
4. Validar que contratos de entrada/salida no se rompen
5. Actualizar ejemplos si cambian fórmulas

**Archivos Relacionados:**
- `/odoo/gtgroupcolombia-1/lavish_hr_employee/models/reglas/prestaciones.py`
- `/odoo/gtgroupcolombia-1/lavish_hr_employee/models/reglas/prestaciones_detail.py`
- `/odoo/gtgroupcolombia-1/lavish_hr_employee/models/reglas/prestaciones_liquidacion.py`
- `/odoo/gtgroupcolombia-1/lavish_hr_employee/models/reglas/prestaciones_provisiones.py`

**Servicios Relacionados:**
- `period.payslip.query.service` - Cálculo de base
- `hr.salary.rule` - Reglas salariales
- `hr.payslip` - Nómina

---

**FIN DEL PLAN DE RESPONSABILIDADES**
