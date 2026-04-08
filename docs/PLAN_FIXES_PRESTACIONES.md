# Plan de Corrección de Bugs - Prestaciones Sociales

## Resumen Ejecutivo

Se identificaron 9 bugs críticos en el sistema de prestaciones sociales colombianas. Este documento detalla cada bug, su causa raíz y la solución propuesta.

---

## Bug 3: Auxilio Transporte Histórico (Caso João)

### Problema
João recibió auxilio de transporte en el pasado cuando ganaba < 2 SMMLV. Ahora gana > 2 SMMLV y no debería recibir auxilio. Sin embargo, el sistema incluye TODO el auxilio histórico pagado en el cálculo de prestaciones, incluso los períodos cuando no calificaba.

### Causa Raíz
**Archivo**: `lavish_hr_employee/models/reglas/prestaciones.py`
**Clase**: `PrestacionesAuxilioQueryComputer`
**Método**: `compute_promedio()` (líneas 904-957)

El método consulta TODOS los pagos históricos de auxilio sin validar si el empleado calificaba (< 2 SMMLV) en cada período:

```python
def compute_promedio(self, contract_id, date_from, date_to, exclude_slip_id=None):
    builder = AuxilioTransporteQueryBuilder()
    builder.for_contract(contract_id)
    builder.in_period(date_from, date_to)
    builder.mode_pagado()  # ❌ Incluye TODO sin validar tope por período
```

### Solución Propuesta

**Opción 1: Validación por período en SQL**
Agregar JOIN a nóminas para validar tope 2 SMMLV por cada período:

```python
def compute_promedio_con_tope_validation(self, contract_id, date_from, date_to,
                                         only_wage='wage', exclude_slip_id=None):
    """
    Calcula promedio de auxilio validando tope 2 SMMLV por período.

    Solo incluye auxilio de períodos donde el empleado calificaba.
    """
    # Query que:
    # 1. Agrupa pagos por período (mes)
    # 2. Calcula salario total del período según only_wage
    # 3. Compara con 2 SMMLV del período
    # 4. Solo incluye auxilio si salario < 2 SMMLV
```

**Opción 2: Filtrar por configuración de contrato**
Usar el campo `not_validate_top_auxtransportation` y `modality_aux` para determinar períodos válidos.

**Impacto**:
- Archivos: `prestaciones.py`, posiblemente crear nuevo query builder
- Riesgo: MEDIO (cambio en lógica de negocio crítica)

---

## Bug 4: Liquidaciones Sin Provisiones

### Problema
Las liquidaciones de contrato no están mostrando/trayendo las provisiones acumuladas. El cálculo se hace desde cero sin considerar lo ya provisionado.

### Causa Raíz
**Archivo**: `lavish_hr_employee/models/reglas/prestaciones_liquidacion.py`
**Métodos**: `_prima()`, `_cesantias()`, `_intcesantias()` (líneas 49-123)

Los métodos de liquidación calculan el total desde cero pero NO:
1. Consultan provisiones acumuladas de la base de datos
2. Calculan el ajuste (total - provisiones)
3. Retornan solo el valor pendiente

```python
def _cesantias(self, localdict):
    result = prestaciones_service.calculate_prestacion(
        localdict, 'cesantias', context='liquidacion', provision_type='simple'
    )
    # ❌ No carga provisiones acumuladas
    # ❌ No calcula ajuste
    return self._adapt_result_for_slip(result, localdict, 'cesantias')
```

### Solución Propuesta

**1. Crear servicio de consulta de provisiones**
```python
class PrestacionesProvisionLoader:
    """Carga provisiones acumuladas desde hr.payslip.line"""

    def load_provisions(self, contract_id, tipo_prestacion, date_from, date_to):
        """
        Query SQL:
        - Buscar líneas de nómina con categoría PROVISIONES
        - Filtrar por código de regla (PRIMA_PROV, CES_PROV, etc.)
        - Sumar totales por tipo
        """
```

**2. Modificar métodos de liquidación**
```python
def _cesantias(self, localdict):
    # 1. Calcular total adeudado
    result = prestaciones_service.calculate_prestacion(...)
    total_adeudado = result[5].get('metricas', {}).get('valor_total', 0)

    # 2. Cargar provisiones acumuladas
    loader = self.env['hr.salary.rule.prestaciones.provision.loader']
    provisiones = loader.load_provisions(contract.id, 'cesantias', date_from, date_to)
    total_provisionado = provisiones.get('total', 0)

    # 3. Calcular ajuste
    ajuste = total_adeudado - total_provisionado

    # 4. Retornar con información de provisiones
    return (base, dias, pct, nombre, log, {
        'total_adeudado': total_adeudado,
        'total_provisionado': total_provisionado,
        'ajuste': ajuste,
        'provisiones_detalle': provisiones
    })
```

**Impacto**:
- Archivos nuevos: `prestaciones_provision_loader.py`
- Archivos modificados: `prestaciones_liquidacion.py`, `prestaciones.py`
- Riesgo: ALTO (cambio fundamental en liquidaciones)

---

## Bug 5: Provisiones Altas (Especialmente Intereses de Cesantías)

### Problema
Las provisiones simples calculan valores muy altos, especialmente para intereses de cesantías.

### Causa Raíz
**Archivo**: `lavish_hr_employee/models/reglas/prestaciones.py`
**Método**: `_calculate_value()` (líneas 1625-1638)

El cálculo de intereses para provisión simple está **duplicando los días**, resultando en valores astronómicos:

```python
elif tipo_prestacion == 'intereses':
    cesantias = base_info.get('cesantias_calculadas', 0)
    if not cesantias:
        cesantias = (base * dias) / base_dias_prestaciones  # dias aquí

    tasa_efectiva = tasa_intereses * dias / base_dias_prestaciones  # dias otra vez!

    if context == 'provision' and provision_type == 'simple':
        return cesantias * tasa_efectiva  # ❌ DOBLE CONTEO DE DÍAS
```

**Ejemplo del error:**
- Período: Enero-Junio = 180 días
- Base mensual: $3,000,000
- Cálculo actual:
  ```
  cesantias = (3,000,000 * 180) / 360 = 1,500,000
  tasa_efectiva = 0.12 * 180 / 360 = 0.06 (6%)
  intereses = 1,500,000 * 0.06 = 90,000
  ```

  Esto expande a: `base * días² * tasa / 360²` = **INCORRECTO**

**Valor correcto debería ser:**
```
cesantias_acumuladas = 1,500,000
intereses = cesantias_acumuladas * 0.12  # 12% anual
O para período: intereses = 1,500,000 * 0.12 * (180/360) = 90,000
```

Pero el cálculo está cuadrando los días.

### Solución Propuesta

**Para provisión simple de intereses:**

```python
elif tipo_prestacion == 'intereses':
    if context == 'provision' and provision_type == 'simple':
        # Opción A: Usar cesantías del período SIN multiplicar por tasa_efectiva
        # (ya que cesantías ya tiene los días incorporados)
        cesantias_periodo = (base * dias) / base_dias_prestaciones
        # Intereses = cesantías * 12% (NO multiplicar por días otra vez)
        return cesantias_periodo * tasa_intereses

    elif context == 'provision' and provision_type == 'promediado':
        # Provisión mensual: usar días del mes SOLAMENTE
        cesantias_mes = (base * dias_mes) / base_dias_prestaciones
        tasa_mes = tasa_intereses * dias_mes / base_dias_prestaciones
        return cesantias_mes * tasa_intereses  # O usar cesantías acumuladas
```

**Más específico - para provisión simple MENSUAL:**
```python
if context == 'provision' and provision_type == 'simple':
    # Para provisión mensual de intereses:
    # Intereses = Cesantías_Acumuladas * 12% * (30/360)
    # NO usar cesantías del período porque ya tiene días

    # Obtener cesantías acumuladas desde consulta SQL
    cesantias_acum = base_info.get('cesantias_acumuladas', 0)
    if not cesantias_acum:
        # Fallback: calcular cesantías del año hasta la fecha
        cesantias_acum = (base * dias) / base_dias_prestaciones

    # Intereses solo del mes actual
    tasa_mensual = tasa_intereses * dias_mes / base_dias_prestaciones
    return cesantias_acum * tasa_mensual
```

**Impacto**:
- Archivos: `prestaciones.py` método `_calculate_value()`
- Riesgo: ALTO (afecta nóminas existentes, requiere re-cálculo)
- **CRÍTICO**: Requiere análisis de todas las fórmulas (prima, cesantías, vacaciones)

---

## Bug 6: Auxilio en Vacaciones Incorrectamente Incluido

### Problema
El sistema está incluyendo auxilio de transporte en la liquidación de vacaciones, pero la regla salarial no tiene el checkbox `base_vacaciones` seleccionado.

### Causa Raíz
**Archivo**: `lavish_hr_employee/models/reglas/prestaciones.py`
**Clase**: `PrestacionesAuxilioValidator`
**Método**: `validate()` (líneas 545-551)

El validador permite auxilio en vacaciones si el parámetro global está activado, IGNORANDO la configuración de la regla:

```python
if tipo_prestacion == 'vacaciones':
    vac_incluye = self._str_to_bool(
        self._get_param('lavish_hr_payroll.vacaciones_incluye_auxilio', 'False')
    )
    if not vac_incluye:
        return _no_aplica('Vacaciones no incluye auxilio (Art. 186 CST)')
    # ❌ Si vac_incluye=True, permite auxilio SIN revisar regla
```

El sistema NO valida si las reglas salariales tienen `base_vacaciones = TRUE` antes de incluir auxilio.

### Solución Propuesta

**Opción 1: Respetar configuración de regla por encima de global**
```python
if tipo_prestacion == 'vacaciones':
    # Verificar configuración global
    vac_incluye_global = self._str_to_bool(
        self._get_param('lavish_hr_payroll.vacaciones_incluye_auxilio', 'False')
    )

    # Si global dice NO, rechazar inmediatamente
    if not vac_incluye_global:
        return _no_aplica('Config global: vacaciones sin auxilio (Art. 186 CST)')

    # Si global dice SI, verificar que existan reglas con base_vacaciones=True
    # que sean de auxilio (categoria AUX o es_auxilio_transporte=True)
    tiene_reglas_auxilio = self._verificar_reglas_auxilio_vacaciones()
    if not tiene_reglas_auxilio:
        return _no_aplica('No hay reglas de auxilio marcadas para vacaciones')
```

**Opción 2: Agregar parámetro adicional**
```python
# Nuevo parámetro:
# lavish_hr_payroll.vacaciones_auxilio_respect_rules = True/False
# Si True: solo incluir auxilio si regla tiene base_vacaciones
# Si False: incluir si global permite (comportamiento actual)
```

**Impacto**:
- Archivos: `prestaciones.py`
- Riesgo: BAJO (solo afecta validación de vacaciones)

---

## Bug 7: Días de Vacaciones Desde Año Actual en vez de Última Fecha

### Problema
En liquidación de contrato, el cálculo de días de vacaciones toma desde el año actual en vez de la última fecha de corte de vacaciones (`contract.date_vacaciones`).

### Causa Raíz
**Archivo**: `lavish_hr_employee/models/reglas/prestaciones.py`
**Clase**: `PrestacionesDateHelper`
**Método**: `compute_vacation_dates()` (líneas 91-131)

La lógica tiene dos problemas:

1. **Fallback incorrecto cuando no hay date_start:**
```python
date_from = contract.date_start or date(date_to.year, 1, 1)  # ❌ Año actual
```

2. **Condición restrictiva para date_vacaciones:**
```python
if contract.date_vacaciones:
    vacation_cutoff = contract.date_vacaciones
    if vacation_cutoff > date_from:  # ❌ Solo actualiza si es MAYOR
        date_from = vacation_cutoff
```

Si `contract.date_vacaciones` es anterior a `contract.date_start`, no se usa.

### Solución Propuesta

```python
@staticmethod
def compute_vacation_dates(date_to, contract, company=None):
    """
    Prioridad para fecha inicio:
    1. contract.date_vacaciones (último corte) - SIEMPRE PRIMERO
    2. contract.date_start (inicio de contrato)
    3. Enero del año del contrato (fallback mínimo)
    """
    # Fallback base: inicio de contrato o año de inicio
    if contract.date_start:
        date_from = contract.date_start
    else:
        # Si no hay date_start, usar año de inicio estimado
        # NUNCA usar año actual (date_to.year)
        date_from = date(date_to.year - 1, 1, 1)  # Año anterior como mínimo

    vacation_cutoff = None

    # PRIORIDAD: Si existe date_vacaciones, SIEMPRE usarla
    if contract.date_vacaciones:
        vacation_cutoff = contract.date_vacaciones
        # Usar date_vacaciones INDEPENDIENTE de si es mayor o menor
        # (es el último corte legítimo de vacaciones)
        date_from = vacation_cutoff

    # Ajustar si contrato termina antes
    effective_date_to = date_to
    if contract.date_end and contract.date_end < date_to:
        effective_date_to = contract.date_end

    return {
        'date_from': date_from,
        'date_to': effective_date_to,
        'tipo_periodo': 'vacaciones',
        'vacation_cutoff': vacation_cutoff,
        'date_start_contract': contract.date_start,
    }
```

**Validación adicional:**
```python
# Si date_vacaciones > date_to, error (no puede tener corte futuro)
if contract.date_vacaciones and contract.date_vacaciones > date_to:
    raise ValueError(
        f"Fecha corte vacaciones ({contract.date_vacaciones}) "
        f"no puede ser posterior a fecha de cálculo ({date_to})"
    )
```

**Impacto**:
- Archivos: `prestaciones.py`
- Riesgo: MEDIO (puede afectar cálculos existentes de vacaciones)

---

## Bug 8: Prima en Liquidación Genera 0 o No Trae Ajuste

### Problema
Cuando se paga prima por separado en una liquidación, no trae el valor de ajuste (prima total - prima ya pagada) o genera valor 0.

### Causa Raíz
Relacionado con **Bug 4**. La liquidación no carga provisiones ni pagos anteriores de prima, por lo que:

1. Si ya se pagó prima en el semestre → no resta el valor pagado
2. Si se genera con valor 0 → no hay validación de pagos previos

**Archivo**: `prestaciones_liquidacion.py` líneas 49-74

```python
def _prima(self, localdict):
    result = prestaciones_service.calculate_prestacion(
        localdict, 'prima', context='liquidacion', provision_type='simple'
    )
    # ❌ No consulta prima ya pagada en el semestre
    # ❌ No calcula ajuste
    return self._adapt_result_for_slip(result, localdict, 'prima')
```

### Solución Propuesta

**Integrado con la solución del Bug 4:**

```python
def _prima(self, localdict):
    contract = localdict['contract']
    slip = localdict['slip']

    # 1. Calcular prima total adeudada del semestre
    result = prestaciones_service.calculate_prestacion(
        localdict, 'prima', context='liquidacion', provision_type='simple'
    )

    if not result or len(result) < 6:
        return (0, 0, 0, 'Error', '', {'aplica': False})

    base_diaria, dias, porcentaje, nombre, log, detail = result
    total_adeudado = detail.get('metricas', {}).get('valor_total', 0)

    # 2. Cargar prima ya pagada/provisionada en el semestre
    loader = self.env['hr.salary.rule.prestaciones.provision.loader']

    # Determinar período del semestre
    if slip.date_to.month <= 6:
        date_from_sem = date(slip.date_to.year, 1, 1)
        date_to_sem = date(slip.date_to.year, 6, 30)
    else:
        date_from_sem = date(slip.date_to.year, 7, 1)
        date_to_sem = date(slip.date_to.year, 12, 31)

    # Consultar prima ya pagada
    prima_pagada = loader.load_payments(
        contract.id, 'prima', date_from_sem, date_to_sem,
        exclude_slip_id=slip.id
    )
    total_pagado = prima_pagada.get('total', 0)

    # Consultar provisiones
    prima_prov = loader.load_provisions(
        contract.id, 'prima', date_from_sem, date_to_sem
    )
    total_provisionado = prima_prov.get('total', 0)

    # 3. Calcular ajuste
    ajuste = total_adeudado - total_pagado - total_provisionado

    # 4. Validar si ya se pagó completo
    if ajuste <= 0:
        return (0, 0, 0, f'Prima ya pagada (ajuste: {ajuste:,.2f})', log, {
            'aplica': False,
            'motivo': 'Prima ya liquidada en el semestre',
            'total_adeudado': total_adeudado,
            'total_pagado': total_pagado,
            'total_provisionado': total_provisionado,
            'ajuste': ajuste
        })

    # 5. Retornar solo el ajuste pendiente
    detail['total_adeudado'] = total_adeudado
    detail['total_pagado'] = total_pagado
    detail['total_provisionado'] = total_provisionado
    detail['ajuste'] = ajuste
    detail['metricas']['valor_total'] = ajuste

    return self._adapt_result_for_slip(result, localdict, 'prima')
```

**Impacto**:
- Dependencia: Requiere implementar Bug 4 primero
- Archivos: `prestaciones_liquidacion.py`
- Riesgo: ALTO (cambio en lógica de liquidación de prima)

---

## Bug 9: Auxilio con Menos de 30 Días de Contrato

### Problema
Si el contrato tiene menos de 30 días, no debería promediar el auxilio de transporte, o debería usar el campo de selección del contrato (`modality_aux` o `tope_aux_method`).

### Causa Raíz
**Archivo**: `lavish_hr_employee/models/reglas/prestaciones.py`
**Clase**: `PrestacionesAuxilioValidator`
**Método**: `validate()` (líneas 585-591)

La modalidad de auxilio se determina solo por `modality_aux`, sin verificar duración del contrato:

```python
modality_aux = contract.modality_aux or 'basico'
usar_liquidado = modality_aux in ('variable', 'variable_sin_tope')

if usar_liquidado:
    # ❌ No valida si contrato tiene < 30 días
    # ❌ Promedia auxilio sin importar duración
    warnings.append('Modalidad auxilio=variable: usa promedio periodo')
```

### Solución Propuesta

**Agregar validación de duración del contrato:**

```python
# En PrestacionesAuxilioValidator.validate()

# 5. Modalidad auxilio y flags derivados
modality_aux = contract.modality_aux or 'basico'
if modality_aux == 'no':
    return _no_aplica('Modalidad auxilio configurada como "Sin auxilio"')

# 5.1 NUEVO: Verificar duración del contrato
dias_contrato = 0
if contract.date_start:
    date_calculo = localdict.get('slip').date_to if localdict.get('slip') else date.today()
    dias_contrato = (date_calculo - contract.date_start).days

# Si contrato < 30 días y modo variable, forzar a basico
usar_liquidado_original = modality_aux in ('variable', 'variable_sin_tope')
usar_liquidado = usar_liquidado_original

if usar_liquidado_original and dias_contrato < 30:
    # Revisar campo de configuración especial
    # Opción A: Siempre usar basico si < 30 días
    usar_liquidado = False
    warnings.append(
        f'Contrato con {dias_contrato} días (< 30): '
        'usando auxilio básico en vez de variable'
    )

    # Opción B: Respetar tope_aux_method del contrato
    # if contract.tope_aux_method == 'proporcional':
    #     usar_liquidado = False  # Usar fijo proporcional
    # else:  # mes_completo
    #     usar_liquidado = True   # Permitir variable

saltar_tope = modality_aux == 'variable_sin_tope' and usar_liquidado

if usar_liquidado:
    warnings.append(
        f'Modalidad auxilio={modality_aux}: usa auxilio ya liquidado (promedio periodo)'
    )
elif usar_liquidado_original and not usar_liquidado:
    warnings.append(
        f'Modalidad auxilio={modality_aux} ajustada a básico por duración'
    )
```

**Alternativa: Usar campo de contrato existente**

El campo `tope_aux_method` podría usarse:
- `mes_completo`: Permitir promedio incluso con < 30 días
- `proporcional`: Usar auxilio fijo proporcional, no promedio

```python
if usar_liquidado_original and dias_contrato < 30:
    tope_method = contract.tope_aux_method or 'mes_completo'

    if tope_method == 'proporcional':
        usar_liquidado = False
        warnings.append(
            f'Contrato < 30 días con método proporcional: auxilio fijo'
        )
    else:  # mes_completo
        # Permitir variable según configuración
        warnings.append(
            f'Contrato < 30 días con método mes completo: permitiendo promedio'
        )
```

**Impacto**:
- Archivos: `prestaciones.py`
- Riesgo: MEDIO (afecta cálculo de auxilio en prestaciones)

---

## Priorización de Fixes

### Prioridad CRÍTICA (Implementar primero)
1. **Bug 5 - Provisiones Altas**: Fórmula incorrecta genera valores exorbitantes
2. **Bug 4 - Liquidaciones Sin Provisiones**: Fundamental para liquidaciones correctas
3. **Bug 8 - Prima en Liquidación**: Depende de Bug 4, crítico para liquidaciones

### Prioridad ALTA
4. **Bug 3 - Auxilio Histórico**: Afecta cálculo de prestaciones de múltiples empleados
5. **Bug 7 - Días de Vacaciones**: Error en período de cálculo de vacaciones

### Prioridad MEDIA
6. **Bug 6 - Auxilio en Vacaciones**: Configuración vs global
7. **Bug 9 - Auxilio < 30 días**: Edge case pero importante

---

## Plan de Implementación Sugerido

### Fase 1: Corrección de Fórmulas (Semana 1)
- [ ] Bug 5: Corregir fórmula de intereses de cesantías
- [ ] Bug 5: Revisar fórmulas de prima, cesantías, vacaciones
- [ ] Pruebas exhaustivas con datos históricos

### Fase 2: Sistema de Provisiones (Semana 2)
- [ ] Bug 4: Crear `PrestacionesProvisionLoader`
- [ ] Bug 4: Modificar métodos de liquidación
- [ ] Bug 8: Integrar ajuste de prima
- [ ] Pruebas de liquidación completa

### Fase 3: Auxilio de Transporte (Semana 3)
- [ ] Bug 3: Implementar validación de tope por período
- [ ] Bug 9: Agregar validación de 30 días
- [ ] Bug 6: Respetar configuración de reglas
- [ ] Pruebas de auxilio en diferentes escenarios

### Fase 4: Vacaciones (Semana 4)
- [ ] Bug 7: Corregir lógica de fechas de vacaciones
- [ ] Pruebas de cálculo de vacaciones

### Fase 5: Testing y QA (Semana 5)
- [ ] Pruebas integradas de todos los bugs
- [ ] Validación con casos reales (João, etc.)
- [ ] Documentación de cambios
- [ ] Migración de datos si es necesario

---

## Riesgos y Consideraciones

### Riesgos Técnicos
1. **Re-cálculo de nóminas existentes**: Cambios en fórmulas pueden requerir re-cálculo
2. **Compatibilidad hacia atrás**: Provisiones ya calculadas con fórmula incorrecta
3. **Performance**: Validación de tope por período puede ser costosa en SQL

### Mitigaciones
1. Crear script de migración/re-cálculo con opción de rollback
2. Agregar flag de versión en cálculos para identificar fórmula usada
3. Optimizar queries SQL con índices apropiados
4. Implementar en ambiente de prueba primero
5. Documentar todos los cambios de fórmulas

### Testing Requerido
- [ ] Casos de prueba para cada bug
- [ ] Validación con datos de producción (sandbox)
- [ ] Performance testing con volúmenes reales
- [ ] Validación legal de fórmulas con contador/abogado laboral

---

## Archivos Impactados

### Modificaciones Mayores
- `lavish_hr_employee/models/reglas/prestaciones.py`
- `lavish_hr_employee/models/reglas/prestaciones_liquidacion.py`

### Archivos Nuevos
- `lavish_hr_employee/models/reglas/prestaciones_provision_loader.py`
- `lavish_hr_employee/models/services/service_sql/tope_auxilio_queries.py` (opcional)

### Modificaciones Menores
- `lavish_hr_employee/models/services/service_sql/auxilio_transporte_queries.py`

---

## Conclusión

Los 9 bugs identificados requieren correcciones en 3 áreas principales:

1. **Fórmulas matemáticas** (Bug 5): Error crítico de duplicación de días
2. **Carga de datos históricos** (Bugs 3, 4, 8): Falta consultar provisiones y validar períodos
3. **Lógica de negocio** (Bugs 6, 7, 9): Validaciones y configuraciones incorrectas

La implementación debe ser secuencial, empezando por las fórmulas (Bug 5) ya que afecta todos los cálculos, seguido del sistema de provisiones (Bug 4) que es fundamental para liquidaciones correctas.

**Tiempo estimado total**: 5 semanas
**Riesgo general**: ALTO (cambios en lógica crítica de nómina)
**Requiere**: Aprobación de usuario, validación legal, testing exhaustivo
