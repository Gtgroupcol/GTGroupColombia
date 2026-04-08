# FÓRMULAS DETALLADAS CON EJEMPLOS

**Archivo:** 08_FORMULAS_DETALLADAS.md
**Versión:** 2.0

---

## 📐 TABLA DE CONTENIDOS

1. [Parámetros Configurables](#parámetros-configurables)
2. [Prima de Servicios](#prima-de-servicios)
3. [Cesantías](#cesantías)
4. [Intereses de Cesantías](#intereses-de-cesantías)
5. [Vacaciones](#vacaciones)
6. [Cálculo de Días](#cálculo-de-días)
7. [Consolidación](#consolidación)

---

## ⚙️ PARÁMETROS CONFIGURABLES

### Divisores Base

```python
# ir.config_parameter

# Divisor para cesantías e intereses
base_dias_prestaciones = 360  # Año comercial

# Divisor para prima
base_dias_prima = 180  # Semestre comercial

# Divisor para vacaciones
base_dias_vacaciones = 720  # Año × 2

# Días comerciales por mes
dias_mes = 30
```

### Porcentajes de Provisión

```python
# Porcentajes para provisión simple (porcentaje_fijo)

provision_prima_porcentaje = 8.33       # 1/12 = 8.33%
provision_cesantias_porcentaje = 8.33   # 1/12 = 8.33%
provision_intereses_porcentaje = 1.0    # 12%/12 = 1%
provision_vacaciones_porcentaje = 4.17  # (15/360) * 100 = 4.17%
```

### Tasa de Intereses

```python
tasa_intereses_cesantias = 0.12  # 12% anual (Art. 99 Ley 50/1990)
```

---

## 💰 PRIMA DE SERVICIOS

### Fórmula General

```python
prima = (base_mensual * dias_trabajados) / base_dias_prima
```

### Por Contexto y Provision Type

#### 1. Provisión Simple (Porcentaje Fijo)

```python
# Cuando: context='provision' AND provision_type='porcentaje_fijo'
# Usa: simple_provisions = True

porcentaje = 8.33  # 1/12 del salario
prima = (base_mensual * (porcentaje / 100) * dias_mes) / dias_mes

# Simplificado:
prima = base_mensual * 0.0833
```

**Ejemplo:**
```
Base mensual: $1,500,000
Porcentaje: 8.33%

Prima mensual = $1,500,000 * 8.33%
              = $1,500,000 * 0.0833
              = $124,950

Prima anual = $124,950 * 12 = $1,499,400
Prima semestre = $124,950 * 6 = $749,700
```

#### 2. Provisión Completa (Días Trabajados)

```python
# Cuando: context='provision_completa' OR context='liquidacion'
# Usa: simple_provisions = False

prima = (base_mensual * dias_trabajados) / base_dias_prima
# base_dias_prima = 180 (semestre comercial)
```

**Ejemplo Semestre 1 (Ene-Jun):**
```
Base mensual: $1,500,000
Días trabajados: 180 (semestre completo)

Prima = ($1,500,000 * 180) / 180
      = $1,500,000
```

**Ejemplo Proporcional:**
```
Base mensual: $1,500,000
Días trabajados: 90 (3 meses)

Prima = ($1,500,000 * 90) / 180
      = $750,000
```

#### 3. Liquidación

```python
# Cuando: context='liquidacion'
# Igual que provisión completa pero usa contract.date_end

prima = (base_mensual * dias_trabajados) / base_dias_prima
```

**Ejemplo:**
```
Fecha ingreso: 2026-01-15
Fecha retiro: 2026-04-30
Base mensual: $1,800,000

Días trabajados:
  days360('2026-01-15', '2026-04-30') = 105 días

Prima = ($1,800,000 * 105) / 180
      = $1,050,000
```

### Con Ausencias

```python
dias_periodo = days360(date_from, date_to)
dias_ausencias = dias_no_pago + dias_discounting_bonus
dias_trabajados = dias_periodo - dias_ausencias

prima = (base_mensual * dias_trabajados) / base_dias_prima
```

**Ejemplo:**
```
Periodo: Ene-Jun 2026 (180 días)
Ausencias no remuneradas: 15 días
Ausencias discounting_bonus: 10 días

Días trabajados = 180 - 15 - 10 = 155 días

Base mensual: $1,500,000

Prima = ($1,500,000 * 155) / 180
      = $1,291,667
```

---

## 💼 CESANTÍAS

### Fórmula General

```python
cesantias = (base_mensual * dias_trabajados) / base_dias_prestaciones
```

### Por Contexto y Provision Type

#### 1. Provisión Simple (Porcentaje Fijo)

```python
# Cuando: context='provision' AND provision_type='porcentaje_fijo'

porcentaje = 8.33  # 1/12
cesantias = base_mensual * 0.0833
```

**Ejemplo:**
```
Base mensual: $1,500,000

Cesantías mensual = $1,500,000 * 8.33%
                  = $124,950

Cesantías anual = $124,950 * 12 = $1,499,400 ≈ $1,500,000
```

#### 2. Provisión Completa (Días Trabajados)

```python
# Cuando: context='provision_completa' OR context='liquidacion'

cesantias = (base_mensual * dias_trabajados) / base_dias_prestaciones
# base_dias_prestaciones = 360
```

**Ejemplo Año Completo:**
```
Base mensual: $1,500,000
Días trabajados: 360

Cesantías = ($1,500,000 * 360) / 360
          = $1,500,000
```

**Ejemplo Proporcional:**
```
Base mensual: $1,500,000
Días trabajados: 186 (6 meses + 6 días)

Cesantías = ($1,500,000 * 186) / 360
          = $775,000
```

#### 3. Liquidación

```python
# Cuando: context='liquidacion'

cesantias = (base_mensual * dias_trabajados) / base_dias_prestaciones
```

**Ejemplo:**
```
Fecha ingreso: 2023-03-15
Fecha retiro: 2026-06-30
Base mensual final: $2,000,000

Días trabajados:
  days360('2023-03-15', '2026-06-30') = 1,155 días

Cesantías = ($2,000,000 * 1,155) / 360
          = $6,416,667

Equivalente a 3.2 años de servicio
```

### Con Promedio de Salario

```python
# Si hay cambios de salario, se promedia ponderado

salario_promedio = sum(salario_i * dias_i) / sum(dias_i)

cesantias = (salario_promedio * dias_trabajados) / base_dias_prestaciones
```

**Ejemplo:**
```
Periodo: 2026-01-01 a 2026-06-30

Cambios de salario:
  Ene-Mar (90 días): $1,300,000
  Abr-Jun (90 días): $1,700,000

Salario promedio:
  ($1,300,000 * 90) + ($1,700,000 * 90)
  ────────────────────────────────────── = $1,500,000
           90 + 90

Días trabajados: 180

Cesantías = ($1,500,000 * 180) / 360
          = $750,000
```

---

## 📈 INTERESES DE CESANTÍAS

### Fórmula Legal (Art. 99 Ley 50/1990)

```
Intereses = Cesantías × 12% × (días / 360)
```

### CRÍTICO: Usar Cesantías Ya Calculadas

```python
# ✅ CORRECTO
cesantias = base_info.get('cesantias_calculadas', 0)
tasa_efectiva = 0.12 * dias_trabajados / 360
intereses = cesantias * tasa_efectiva

# ❌ INCORRECTO
cesantias = (base * dias) / 360  # ¡NO recalcular!
```

### Por Contexto y Provision Type

#### 1. Provisión Simple

```python
# Cuando: context='provision' AND provision_type='simple'

cesantias = base_info['cesantias_calculadas']
tasa_efectiva = 0.12 * dias_trabajados / 360
intereses = cesantias * tasa_efectiva
```

**Ejemplo:**
```
Cesantías calculadas: $956,068
Días: 186

Tasa efectiva = 12% × (186/360) = 6.2%

Intereses = $956,068 × 6.2%
          = $59,276
```

#### 2. Provisión Promediada (Mensual)

```python
# Cuando: context='provision' AND provision_type='promediado'

cesantias = base_info['cesantias_calculadas']
tasa_efectiva_mes = 0.12 * dias_mes / 360
intereses = cesantias * tasa_efectiva_mes
```

**Ejemplo:**
```
Cesantías calculadas: $956,068
Días mes: 30

Tasa mensual = 12% × (30/360) = 1%

Intereses mensual = $956,068 × 1%
                  = $9,561
```

#### 3. Provisión Porcentaje Fijo

```python
# Cuando: context='provision' AND provision_type='porcentaje_fijo'

porcentaje = 1.0  # 12%/12 = 1%
intereses = (base_mensual * (porcentaje / 100) * dias_mes) / dias_mes

# Simplificado:
intereses = base_mensual * 0.01
```

**Ejemplo:**
```
Base mensual: $1,500,000
Porcentaje: 1%

Intereses mensual = $1,500,000 × 1%
                  = $15,000
```

#### 4. Liquidación (Tasa FIJA 12%)

```python
# Cuando: context='liquidacion' OR context='provision_completa'

cesantias_acum = base_info.get('cesantias_acumuladas', cesantias)
TASA_INTERESES_LIQUIDACION = 0.12  # ← FIJA por ley
tasa_efectiva = TASA_INTERESES_LIQUIDACION * dias_trabajados / 360
intereses = cesantias_acum * tasa_efectiva
```

**Ejemplo:**
```
Cesantías acumuladas: $6,416,667
Días trabajados: 1,155

Tasa efectiva = 12% × (1,155/360) = 38.5%

Intereses = $6,416,667 × 38.5%
          = $2,470,417
```

#### 5. Consolidación

```python
# Cuando: context='consolidacion'

intereses_prov = base_info.get('intereses_provisionados', 0)
intereses_real = cesantias * tasa_efectiva
ajuste = intereses_real - intereses_prov
```

**Ejemplo:**
```
Cesantías: $1,500,000
Días: 360
Tasa efectiva = 12% × (360/360) = 12%

Intereses real = $1,500,000 × 12% = $180,000

Intereses provisionados (Ene-Nov):
  $15,000 × 11 = $165,000

Ajuste = $180,000 - $165,000 = $15,000
```

### Casos Especiales de Intereses

#### Sin Cesantías Calculadas (Fallback)

```python
# Si no hay cesantias_calculadas, calcular como fallback
if not cesantias:
    cesantias = (base_mensual * dias_trabajados) / 360
```

#### Intereses sobre Cesantías de Años Anteriores

```python
# Intereses año anterior
cesantias_year_anterior = calcular_cesantias_year_anterior()
tasa_efectiva = 0.12 * dias_year_anterior / 360
intereses = cesantias_year_anterior * tasa_efectiva
```

---

## 🏖️ VACACIONES

### Ver Documentación Completa

**Archivo:** [06_PRESTACIONES_VACACIONES.md](06_PRESTACIONES_VACACIONES.md)

### Fórmula General

```python
vacaciones = (base_mensual * dias_trabajados) / base_dias_vacaciones
# base_dias_vacaciones = 720
```

### Resumen de Fórmulas

#### Provisión Simple

```python
porcentaje = 4.17  # (15/360) * 100
vacaciones = base_mensual * 0.0417
```

#### Provisión Completa

```python
vacaciones = (base_mensual * dias_trabajados) / 720
```

#### Liquidación

```python
dias_pendientes = dias_acumulados - dias_disfrutados
vacaciones = (base_mensual * dias_pendientes) / 720
```

**Ver ejemplos completos en:** [06_PRESTACIONES_VACACIONES.md](06_PRESTACIONES_VACACIONES.md)

---

## 📅 CÁLCULO DE DÍAS

### Días del Periodo (Año Comercial)

```python
dias_periodo = days360(date_from, date_to)
```

**Función days360:**
```python
def days360(date_from, date_to):
    """
    Calcula días entre fechas usando año comercial (360 días).

    Mes comercial = 30 días
    Año comercial = 360 días
    """
    years = date_to.year - date_from.year
    months = date_to.month - date_from.month
    days = date_to.day - date_from.day

    return years * 360 + months * 30 + days
```

**Ejemplo:**
```python
date_from = date(2026, 1, 1)
date_to = date(2026, 6, 30)

dias = days360(date_from, date_to)
     = 0 * 360 + 5 * 30 + 29
     = 0 + 150 + 29
     = 179

# Pero si el mes tiene 31 días, se ajusta a 30
# Resultado final: 180 días (6 meses × 30)
```

### Ausencias a Descontar

#### 1. Ausencias No Remuneradas

```python
dias_ausencias_no_pago = slip.get_leave_days_no_pay(date_from, date_to, contract.id)
```

**Qué incluye:**
- Licencias no remuneradas
- Suspensiones
- Ausencias injustificadas

#### 2. Ausencias con discounting_bonus_days

```python
# Solo para prima, cesantías e intereses
if tipo_prestacion in ('prima', 'cesantias', 'intereses'):
    dias_descuento_bonus = count(hr.leave.line where:
        - holiday_status_id.discounting_bonus_days = True
        - holiday_status_id.unpaid_absences = False  # Evita doble conteo
        - date >= date_from and date <= date_to
        - state = 'validate'
    )
```

**Qué incluye:**
- Licencias que descuentan de bonos pero SÍ se pagan
- Ejemplos: Licencia de maternidad parcial, permisos especiales

### Total de Días Trabajados

```python
dias_total = max(0, dias_periodo - dias_ausencias_no_pago - dias_descuento_bonus)
```

**Ejemplo Completo:**
```
Periodo: 2026-01-01 a 2026-06-30

Días periodo: 180

Ausencias:
  - No remuneradas: 10 días
  - Discounting bonus (licencia maternidad): 15 días

Días trabajados = 180 - 10 - 15 = 155 días

Prima = ($1,500,000 * 155) / 180 = $1,291,667
```

---

## 🔄 CONSOLIDACIÓN

### Fórmula General

```python
ajuste = obligacion_real - provision_acumulada
```

### Proceso Paso a Paso

#### PASO 1: Calcular Obligación Real

```python
result = prestaciones.calculate_prestacion(
    localdict,
    tipo_prestacion,
    context='consolidacion',
    provision_type='simple'
)
obligacion_real = result[5]['metricas']['valor_total']
```

**Ejemplo:**
```
Tipo: Cesantías
Periodo: 2026-01-01 a 2026-12-31
Base mensual: $1,500,000
Días trabajados: 360

Obligación real = ($1,500,000 * 360) / 360
                = $1,500,000
```

#### PASO 2: Obtener Provisiones Acumuladas

```python
provision_acumulada = sum(hr.payslip.line where:
    - code in ['PRV_CES', 'PROVISION_CESANTIAS', 'PROV_CESANTIAS']
    - slip.contract_id = contract.id
    - slip.date_from >= date_period_from
    - slip.date_to <= date_period_to
    - slip.state in ['done', 'paid']
    - slip.id != slip_actual.id  # Excluir nómina actual
)
```

**Ejemplo:**
```
Provisiones del año (Ene-Nov):
  Enero:     $124,950
  Febrero:   $124,950
  Marzo:     $124,950
  Abril:     $124,950
  Mayo:      $124,950
  Junio:     $124,950
  Julio:     $124,950
  Agosto:    $124,950
  Septiembre:$124,950
  Octubre:   $124,950
  Noviembre: $124,950
  ─────────────────────
  Total:     $1,374,450
```

#### PASO 3: Calcular Ajuste

```python
ajuste = obligacion_real - provision_acumulada

# Si ajuste > 0: Falta provisionar
# Si ajuste < 0: Se provisionó de más (normalmente no pasa)
```

**Ejemplo:**
```
Obligación real:       $1,500,000
Provisión acumulada:   $1,374,450
─────────────────────────────────
Ajuste:                $125,550

→ Falta provisionar $125,550 en Diciembre
```

#### PASO 4: (Opcional) Validar con Contabilidad

```python
saldo_provision = sum(account.move.line where:
    - account.code = '261005'  # Provisión cesantías
    - date <= date_to
    - state = 'posted'
).credit - debit

saldo_obligacion = sum(account.move.line where:
    - account.code = '2510'  # Obligación cesantías
    - date <= date_to
    - state = 'posted'
).credit - debit
```

### Ejemplo Completo de Consolidación

```
════════════════════════════════════════════════════════════
CONSOLIDACIÓN CESANTÍAS - DICIEMBRE 2026
════════════════════════════════════════════════════════════

Empleado: Juan Pérez
Periodo: 2026-01-01 a 2026-12-31
Base mensual promedio: $1,500,000

────────────────────────────────────────────────────────────
PASO 1: OBLIGACIÓN REAL
────────────────────────────────────────────────────────────
Días trabajados: 360 (año completo)
Base mensual: $1,500,000

Cálculo:
  Obligación = ($1,500,000 × 360) / 360
             = $1,500,000

────────────────────────────────────────────────────────────
PASO 2: PROVISIONES ACUMULADAS (Ene-Nov)
────────────────────────────────────────────────────────────
Provisión mensual: $124,950 (8.33% de $1,500,000)

  Ene - Nov: $124,950 × 11 = $1,374,450

────────────────────────────────────────────────────────────
PASO 3: AJUSTE DICIEMBRE
────────────────────────────────────────────────────────────
Ajuste = Obligación real - Provisiones acumuladas
       = $1,500,000 - $1,374,450
       = $125,550

────────────────────────────────────────────────────────────
PASO 4: PROVISIÓN DICIEMBRE
────────────────────────────────────────────────────────────
Opción 1: Provisión normal
  Diciembre: $124,950

Opción 2: Ajustar en consolidación
  Consolidación: $125,550

────────────────────────────────────────────────────────────
TOTAL AÑO
────────────────────────────────────────────────────────────
Con opción 1:
  $1,374,450 + $124,950 = $1,499,400
  Diferencia: $1,500,000 - $1,499,400 = $600 (pequeña)

Con opción 2:
  $1,374,450 + $125,550 = $1,500,000
  Diferencia: $0 (exacto)

════════════════════════════════════════════════════════════
```

---

## 📊 TABLA RESUMEN DE FÓRMULAS

| Prestación | Provisión Simple | Provisión Completa | Liquidación |
|------------|------------------|-------------------|-------------|
| **Prima** | base × 8.33% | (base × dias) / 180 | (base × dias) / 180 |
| **Cesantías** | base × 8.33% | (base × dias) / 360 | (base × dias) / 360 |
| **Intereses** | base × 1% | (ces × 12% × dias) / 360 | (ces × 12% × dias) / 360 |
| **Vacaciones** | base × 4.17% | (base × dias) / 720 | (base × dias_pend) / 720 |

### Divisores

| Prestación | Divisor | Periodo |
|------------|---------|---------|
| Prima | 180 | Semestre comercial |
| Cesantías | 360 | Año comercial |
| Intereses | 360 | Año comercial |
| Vacaciones | 720 | Año comercial × 2 |

---

**Última Actualización:** 2026-01-27
**Versión:** 2.0
