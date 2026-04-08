# VACACIONES - DOCUMENTACIÓN COMPLETA

**Archivo:** 06_PRESTACIONES_VACACIONES.md
**Versión:** 2.0

---

## 🏖️ TABLA DE CONTENIDOS

1. [Marco Legal](#marco-legal)
2. [Diferencias con Otras Prestaciones](#diferencias-con-otras-prestaciones)
3. [Fórmulas de Cálculo](#fórmulas-de-cálculo)
4. [Tipos de Vacaciones](#tipos-de-vacaciones)
5. [Provisión de Vacaciones](#provisión-de-vacaciones)
6. [Liquidación de Vacaciones](#liquidación-de-vacaciones)
7. [Consolidación](#consolidación)
8. [Días Acumulados y Pendientes](#días-acumulados-y-pendientes)
9. [Casos Especiales](#casos-especiales)
10. [Ejemplos Completos](#ejemplos-completos)

---

## 📜 MARCO LEGAL

### Legislación Aplicable

**Código Sustantivo del Trabajo (Colombia)**
- **Artículo 186:** Derecho a 15 días hábiles de vacaciones por cada año de servicio
- **Artículo 187:** Las vacaciones NO son compensables en dinero (solo al finalizar contrato)
- **Artículo 189:** Proporcionalidad en caso de terminación

### Reglas Fundamentales

1. **Días de vacaciones:** 15 días hábiles por año
2. **Acumulación:** Por cada 360 días trabajados (año comercial)
3. **Compensación:** Solo al terminar contrato (no durante)
4. **Proporcionalidad:** Se calcula por días trabajados

---

## 🔄 DIFERENCIAS CON OTRAS PRESTACIONES

### Vacaciones vs Prima vs Cesantías

| Característica | Vacaciones | Prima | Cesantías |
|----------------|-----------|-------|-----------|
| **Periodicidad pago** | Continua (al disfrutar) | Semestral | Anual |
| **Divisor base** | 720 (360 × 2) | 180 | 360 |
| **Días otorgados** | 15 por año | N/A | N/A |
| **Incluye auxilio** | ❌ NO (default) | ✅ SÍ | ✅ SÍ |
| **Compensable en dinero** | Solo al terminar | ✅ SÍ | ✅ SÍ |
| **Puede disfrutarse** | ✅ SÍ | ❌ NO | ❌ NO |
| **Acumulable** | ✅ SÍ (hasta 2 años) | ❌ NO | ❌ NO |

### ¿Por qué divisor 720?

```
Lógica:
- Por cada 360 días trabajados → 15 días de vacaciones
- Por cada 360 días trabajados → salario mensual completo

Fórmula para salario por 15 días:
  salario_por_15_dias = (salario_mensual * 15) / 30
  salario_por_15_dias = salario_mensual * 0.5

Fórmula proporcional por días trabajados:
  vacaciones = (salario_mensual * dias_trabajados) / (360 * 2)
  vacaciones = (salario_mensual * dias_trabajados) / 720

Ejemplo:
  360 días trabajados:
    vacaciones = ($1,500,000 * 360) / 720 = $750,000
    Equivalente a 15 días de salario
```

---

## 📐 FÓRMULAS DE CÁLCULO

### Fórmula General

```python
vacaciones = (base_mensual * dias_trabajados) / base_dias_vacaciones
```

**Donde:**
- `base_mensual`: Salario base mensual
- `dias_trabajados`: Días efectivamente trabajados (descontando ausencias)
- `base_dias_vacaciones`: 720 (configurable en `ir.config_parameter`)

### Provisión Simple (Porcentaje Fijo)

```python
# Cuando simple_provisions = True
vacaciones_mes = base_mensual * porcentaje_vacaciones / 100

# Porcentaje default: 4.17%
# Cálculo: (15 días / 360 días) * 100 = 4.17%
```

**Ejemplo:**
```
Base mensual: $1,500,000
Porcentaje: 4.17%

Provisión mensual = $1,500,000 * 4.17% = $62,550
```

### Provisión Completa (Días Trabajados)

```python
# Cuando simple_provisions = False
vacaciones = (base_mensual * dias_acumulados) / 720
```

**Ejemplo:**
```
Base mensual: $1,500,000
Días acumulados: 360 (1 año completo)

Vacaciones = ($1,500,000 * 360) / 720 = $750,000
Equivalente a 15 días de salario
```

### Liquidación de Vacaciones

```python
# Al terminar contrato
vacaciones_pendientes = (base_mensual * dias_pendientes) / 720

# Donde dias_pendientes = dias_acumulados - dias_disfrutados
```

**Ejemplo:**
```
Base mensual: $1,500,000
Días acumulados: 360
Días disfrutados: 180

Días pendientes = 360 - 180 = 180
Vacaciones a pagar = ($1,500,000 * 180) / 720 = $375,000
Equivalente a 7.5 días de salario
```

---

## 🎯 TIPOS DE VACACIONES

### 1. Vacaciones por Disfrutar (En Tiempo)

**Descripción:** Empleado toma días de descanso remunerado

**Proceso:**
1. Empleado solicita vacaciones
2. Se aprueba solicitud
3. Se crea hr.leave con tipo "Vacaciones"
4. Se descuentan de días acumulados
5. Se paga salario normal durante ausencia

**Nómina:**
- Tipo de estructura: `process = 'vacaciones'`
- Regla: `VACACIONES_TIEMPO`
- Monto: Salario normal del periodo

### 2. Vacaciones Compensadas (En Dinero)

**Descripción:** Se pagan en dinero sin tomar descanso

**Cuándo aplica:**
- **Terminación de contrato** (obligatorio)
- **Solicitud del empleado** (si empresa lo permite)
- **Acumulación máxima** (2 años - debe disfrutarse)

**Proceso:**
1. Se calcula días acumulados pendientes
2. Se aplica fórmula: `(base * dias_pendientes) / 720`
3. Se paga en nómina o liquidación

**Nómina:**
- Tipo de estructura: `process = 'contrato'` (liquidación)
- Regla: `VACCONTRATO`
- Monto: Proporcional a días pendientes

### 3. Vacaciones Anticipadas

**Descripción:** Se otorgan días antes de completar el año

**Proceso:**
1. Empleado solicita anticipar vacaciones
2. Se aprueban días futuros
3. Se descuenta de acumulación futura
4. Si termina contrato antes, se descuenta de liquidación

---

## 📊 PROVISIÓN DE VACACIONES

### Código de Regla: PRV_VAC

**Archivo:** `prestaciones_provisiones.py`
**Método:** `_prv_vac(localdict)`

### Modo Simple (simple_provisions = True)

```python
def _calculate_value(tipo_prestacion, base_info, days_info, context, provision_type):
    if tipo_prestacion == 'vacaciones':
        if context == 'provision' and provision_type == 'porcentaje_fijo':
            porcentaje = base_info.get('porcentaje_fijo', 4.17)
            return (base * (porcentaje / 100) * dias_mes) / dias_mes
```

**Ejemplo:**
```
Base mensual: $1,500,000
Porcentaje: 4.17%

Provisión enero: $1,500,000 * 4.17% = $62,550
Provisión febrero: $1,500,000 * 4.17% = $62,550
...
Provisión diciembre: $1,500,000 * 4.17% = $62,550

Total año: $62,550 * 12 = $750,600 ≈ $750,000 (15 días)
```

### Modo Completo (simple_provisions = False)

```python
def _calculate_value(tipo_prestacion, base_info, days_info, context, provision_type):
    if tipo_prestacion == 'vacaciones':
        return (base * dias) / base_dias_vacaciones  # 720
```

**Ejemplo:**
```
Base mensual: $1,500,000
Días trabajados enero: 30

Provisión enero = ($1,500,000 * 30) / 720 = $62,500

Días acumulados febrero: 60
Provisión febrero = ($1,500,000 * 60) / 720 = $125,000

Provisión del mes = provisión_acumulada_mes - provisión_mes_anterior
                  = $125,000 - $62,500 = $62,500
```

### Configuración de Auxilio

**Por defecto: NO incluye auxilio de transporte**

```python
# ir.config_parameter
lavish_hr_payroll.vacaciones_incluye_auxilio = False
```

**Razón legal:** Las vacaciones se calculan sobre salario básico, no sobre auxilio

**Si se requiere incluir auxilio:**
```python
# Cambiar parámetro a True
lavish_hr_payroll.vacaciones_incluye_auxilio = True
```

---

## 💰 LIQUIDACIÓN DE VACACIONES

### Código de Regla: VACCONTRATO

**Archivo:** `prestaciones_liquidacion.py`
**Método:** `_vaccontrato(localdict)`

### Flujo de Liquidación

```python
def _vaccontrato(localdict):
    """
    VACACIONES EN LIQUIDACION - Codigo regla: VACCONTRATO

    Formula: (Base * Dias) / 720
    Considera: Dias acumulados pendientes de disfrute
    """
    slip = localdict['slip']

    # Determinar contexto segun estructura
    struct_process = slip.struct_id.process if slip.struct_id else 'nomina'
    context = 'liquidacion' if struct_process == 'contrato' else 'pago'

    # Usar servicio unificado
    prestaciones_service = self.env['hr.salary.rule.prestaciones']
    result = prestaciones_service.calculate_prestacion(
        localdict, 'vacaciones', context=context, provision_type='simple'
    )

    return self._adapt_result_for_slip(result, localdict, 'vacaciones')
```

### Cálculo de Días Pendientes

**Lógica:**
```python
dias_acumulados = days360(contract.date_start, contract.date_end or slip.date_to)
dias_disfrutados = sum(hr.leave where tipo='vacaciones' and state='validate')
dias_pendientes = dias_acumulados - dias_disfrutados
```

**Ejemplo:**
```
Contrato: 2023-01-01 a 2026-01-31 (3 años + 1 mes)

Días acumulados:
  days360('2023-01-01', '2026-01-31') = 1,110 días

Días disfrutados:
  Vacaciones 2023: 180 días
  Vacaciones 2024: 180 días
  Total: 360 días

Días pendientes:
  1,110 - 360 = 750 días

Liquidación vacaciones:
  Base mensual: $1,500,000
  Valor = ($1,500,000 * 750) / 720 = $1,562,500
```

### Ajuste por Ausencias

**Las ausencias NO remuneradas se descuentan:**

```python
dias_periodo = days360(contract.date_start, contract.date_end)
dias_ausencias_no_pago = slip.get_leave_days_no_pay(...)
dias_total = dias_periodo - dias_ausencias_no_pago

vacaciones = (base_mensual * dias_total) / 720
```

**Ejemplo:**
```
Días acumulados: 360
Ausencias no remuneradas: 30

Días efectivos: 360 - 30 = 330

Vacaciones = ($1,500,000 * 330) / 720 = $687,500
En lugar de: ($1,500,000 * 360) / 720 = $750,000

Descuento: $750,000 - $687,500 = $62,500
```

---

## 🔄 CONSOLIDACIÓN

### Código de Regla: VACACIONES_CONS / CONS_VAC

**Archivo:** `prestaciones_provisiones.py`
**Método:** `_vacaciones_cons(localdict)` / `_cons_vac(localdict)`

### Flujo de Consolidación

```python
def _calculate_consolidacion(localdict, tipo_prestacion='vacaciones'):
    """
    Calcula ajuste de consolidacion.

    Proceso:
    1. Calcula liquidacion al corte (obligacion real - lo que se debe)
    2. Busca provisiones acumuladas en nominas del periodo
    3. Ajuste = Obligacion real - Provisiones acumuladas
    """
    # 1. Calcular obligación real
    result = prestaciones.calculate_prestacion(
        localdict, 'vacaciones', context='consolidacion', provision_type='simple'
    )
    obligacion_real = result[5]['metricas']['valor_total']

    # 2. Obtener provisiones acumuladas del año
    date_from = date(slip.date_to.year, 1, 1)
    date_to = slip.date_to

    provision_acumulada_data = _get_provision_acumulada(
        contract_id=contract.id,
        tipo_prestacion='vacaciones',
        date_period_from=date_from,
        date_period_to=date_to,
        exclude_slip_id=slip.id
    )
    provision_acumulada = provision_acumulada_data['total']

    # 3. Calcular ajuste
    ajuste = obligacion_real - provision_acumulada

    return (ajuste, 1, 100, nombre, '', data)
```

### Periodo de Consolidación

**Vacaciones:** Año completo (Enero - Diciembre)

```python
# Diferente a prima (semestral)
if tipo_prestacion == 'vacaciones':
    # Consolidación anual
    date_from = date(date_to.year, 1, 1)
    return date_from, date_to
```

### Ejemplo de Consolidación

```
Año: 2026
Contrato: Activo todo el año
Base mensual promedio: $1,500,000

PASO 1: Calcular obligación real al 31 Dic 2026
  Días trabajados: 360
  Obligación = ($1,500,000 * 360) / 720 = $750,000

PASO 2: Provisiones acumuladas (Ene-Nov)
  Provisión mensual: $62,550
  Total 11 meses: $62,550 * 11 = $688,050

PASO 3: Ajuste en Diciembre
  Ajuste = $750,000 - $688,050 = $61,950

PASO 4: Provisión Diciembre
  Si simple_provisions=True:
    Provisión Dic = $62,550 (normal)

  Si ajustar en consolidación:
    Consolidación = $61,950 (ajuste calculado)
```

---

## 📅 DÍAS ACUMULADOS Y PENDIENTES

### Sistema de Acumulación

**Regla:** Por cada 360 días trabajados → 15 días de vacaciones

```python
dias_vacaciones_derecho = (dias_trabajados / 360) * 15

# Equivalente a:
dias_vacaciones_derecho = dias_trabajados * (15 / 360)
dias_vacaciones_derecho = dias_trabajados * 0.04166666...
```

### Tracking de Días

**Modelo sugerido:** `hr.vacation.balance`

```python
class HrVacationBalance(models.Model):
    _name = 'hr.vacation.balance'

    employee_id = fields.Many2one('hr.employee')
    contract_id = fields.Many2one('hr.contract')

    # Acumulación
    dias_acumulados = fields.Float()  # Total acumulado
    dias_disfrutados = fields.Float()  # Ya tomados
    dias_compensados = fields.Float()  # Pagados en dinero
    dias_pendientes = fields.Float(compute='_compute_pendientes')

    # Límites
    fecha_acumulacion_desde = fields.Date()
    fecha_vencimiento = fields.Date()  # 2 años máximo

    @api.depends('dias_acumulados', 'dias_disfrutados', 'dias_compensados')
    def _compute_pendientes(self):
        for record in self:
            record.dias_pendientes = (
                record.dias_acumulados
                - record.dias_disfrutados
                - record.dias_compensados
            )
```

### Límite de Acumulación

**Legal:** Las vacaciones pueden acumularse hasta **2 años** (720 días)

```python
# Validación de acumulación máxima
if dias_acumulados >= 720:
    # Obligar a disfrutar o compensar
    raise ValidationError(
        "Ha alcanzado el límite de acumulación (2 años). "
        "Debe disfrutar o compensar las vacaciones pendientes."
    )
```

---

## 🎭 CASOS ESPECIALES

### 1. Vacaciones en Periodo de Prueba

**Regla:** Se acumulan pero NO se pueden disfrutar hasta terminar periodo de prueba

```python
if contract.trial_date_end and date.today() < contract.trial_date_end:
    # Acumular pero no permitir disfrute
    dias_acumulados += dias_periodo / 360 * 15
    puede_disfrutar = False
```

### 2. Terminación en Periodo de Vacaciones

**Regla:** Si se termina contrato mientras está de vacaciones:

```python
# Se paga lo que falta de vacaciones disfrutadas
dias_vacaciones_curso = days_between(date.today(), leave.date_to)

# Se compensan días pendientes adicionales
dias_pendientes = dias_acumulados - dias_disfrutados - dias_vacaciones_curso

valor_total = (
    (base_mensual * dias_vacaciones_curso / 720) +  # Vacaciones en curso
    (base_mensual * dias_pendientes / 720)          # Pendientes
)
```

### 3. Vacaciones Colectivas

**Regla:** La empresa puede decretar vacaciones colectivas

```python
# Todos los empleados toman vacaciones al mismo tiempo
# Se descuenta de días acumulados de cada empleado
for employee in employees:
    if employee.dias_acumulados >= dias_vacaciones_colectivas:
        employee.dias_disfrutados += dias_vacaciones_colectivas
    else:
        # Si no tiene suficientes, se anticipa
        employee.dias_anticipados += (
            dias_vacaciones_colectivas - employee.dias_acumulados
        )
```

### 4. Vacaciones Fraccionadas

**Regla:** Se pueden dividir las vacaciones

```python
# Ejemplo: 15 días divididos en 3 periodos
vacaciones_1 = 7 dias  # Primera quincena julio
vacaciones_2 = 5 dias  # Diciembre
vacaciones_3 = 3 dias  # Semana santa

total = 7 + 5 + 3 = 15 dias
```

### 5. Vacaciones con Aumento de Salario

**Regla:** Se paga con el salario vigente al momento de disfrutar

```python
# Acumulación con salario anterior
# Periodo 2023-2024: Salario $1,300,000
dias_acumulados = 360  # 1 año completo
provision_acumulada = ($1,300,000 * 360) / 720 = $650,000

# Disfrute con salario actual
# Enero 2025: Nuevo salario $1,500,000
vacaciones_a_pagar = ($1,500,000 * 360) / 720 = $750,000

# Diferencia: $750,000 - $650,000 = $100,000 (favor empleado)
```

**Solución:** Ajustar en consolidación

```python
# En consolidación diciembre 2024
obligacion_real = ($1,500,000 * 360) / 720  # Con nuevo salario
provision_acumulada = $650,000  # Con salario anterior
ajuste = $750,000 - $650,000 = $100,000  # Provisionar diferencia
```

---

## 💡 EJEMPLOS COMPLETOS

### Ejemplo 1: Provisión Mensual (Simple)

```
Empleado: Juan Pérez
Contrato: Indefinido
Base mensual: $1,500,000
Modo: simple_provisions = True

--- ENERO 2026 ---
Provisión vacaciones = $1,500,000 * 4.17% = $62,550

Asiento (automático):
  Debe: Gasto vacaciones ........... $62,550
  Haber: Provisión vacaciones ...... $62,550

--- FEBRERO 2026 ---
Provisión vacaciones = $1,500,000 * 4.17% = $62,550

--- ... DICIEMBRE 2026 ---
Total provisionado año = $62,550 * 12 = $750,600
```

### Ejemplo 2: Liquidación con Días Pendientes

```
Empleado: María González
Fecha ingreso: 2023-01-01
Fecha retiro: 2026-06-30
Base mensual final: $2,000,000

--- CÁLCULO DÍAS ---
Días trabajados totales:
  days360('2023-01-01', '2026-06-30') = 1,260 días

Días de vacaciones derecho:
  (1,260 / 360) * 15 = 52.5 días

Días disfrutados:
  Vacaciones 2023: 15 días
  Vacaciones 2024: 15 días
  Total: 30 días

Días pendientes:
  52.5 - 30 = 22.5 días

--- LIQUIDACIÓN ---
Vacaciones a pagar = ($2,000,000 * 22.5) / 15
                   = $2,000,000 * 1.5
                   = $3,000,000

Equivalente a 1.5 meses de salario (22.5 días / 15 días por mes)
```

### Ejemplo 3: Consolidación Anual

```
Empleado: Carlos López
Año: 2026
Base mensual promedio: $1,800,000

--- PROVISIONES DEL AÑO (Ene-Nov) ---
Provisión mensual = $1,800,000 * 4.17% = $75,060

Ene-Nov: $75,060 * 11 = $825,660

--- CONSOLIDACIÓN DICIEMBRE ---
Días trabajados año: 360
Obligación real = ($1,800,000 * 360) / 720 = $900,000

Ajuste = $900,000 - $825,660 = $74,340

Provisión Diciembre:
  Opción 1: Normal $75,060
  Opción 2: Ajustada $74,340 (vía consolidación)

--- TOTAL AÑO ---
Si opción 1: $825,660 + $75,060 = $900,720 (pequeño exceso $720)
Si opción 2: $825,660 + $74,340 = $900,000 (exacto)
```

### Ejemplo 4: Vacaciones con Ausencias

```
Empleado: Ana Martínez
Periodo: Enero - Diciembre 2026
Base mensual: $1,500,000

--- AUSENCIAS ---
Incapacidad médica (no remunerada): 30 días

--- CÁLCULO ---
Días periodo: 360
Días ausencias: 30
Días efectivos: 360 - 30 = 330

Vacaciones provisionadas año:
  Simple: $1,500,000 * 4.17% * 12 = $750,600 (sin ajuste)

  Completo: ($1,500,000 * 330) / 720 = $687,500

Diferencia: $750,600 - $687,500 = $63,100 (exceso por ausencias)

Ajuste en consolidación:
  Obligación real: $687,500
  Provisión acumulada: $750,600
  Ajuste: $687,500 - $750,600 = -$63,100 (reverso de provisión)
```

---

## 📋 CHECKLIST DE IMPLEMENTACIÓN

### Provisión Mensual
- [ ] Verificar modo `simple_provisions` en annual_parameters
- [ ] Configurar porcentaje (default 4.17%)
- [ ] Configurar si incluye auxilio (default NO)
- [ ] Validar regla PRV_VAC en estructura de nómina
- [ ] Verificar cuenta contable de provisión

### Liquidación
- [ ] Validar cálculo de días pendientes
- [ ] Consultar hr.leave para días disfrutados
- [ ] Aplicar descuentos por ausencias no remuneradas
- [ ] Verificar regla VACCONTRATO en estructura de liquidación
- [ ] Incluir en total de liquidación

### Consolidación
- [ ] Configurar periodo anual (Ene-Dic)
- [ ] Validar consulta de provisiones acumuladas
- [ ] Calcular obligación real al cierre
- [ ] Generar ajuste si hay diferencia
- [ ] Documentar en widget de consolidación

### Tracking de Días
- [ ] Implementar modelo de balance de vacaciones
- [ ] Actualizar días acumulados mensualmente
- [ ] Descontar días disfrutados en hr.leave
- [ ] Validar límite de acumulación (2 años)
- [ ] Alertar cuando se acerque a vencimiento

---

## 🔗 REFERENCIAS

### Archivos Relacionados
- `02_PRESTACIONES_CALCULO.md` - Motor de cálculo
- `05_PRESTACIONES_PROVISIONES.md` - Provisiones
- `04_PRESTACIONES_LIQUIDACION.md` - Liquidación
- `08_FORMULAS_DETALLADAS.md` - Fórmulas completas

### Código Fuente
- `prestaciones.py` - calculate_prestacion()
- `prestaciones_liquidacion.py` - _vaccontrato()
- `prestaciones_provisiones.py` - _prv_vac(), _vacaciones_cons()

---

**Última Actualización:** 2026-01-27
**Versión:** 2.0
