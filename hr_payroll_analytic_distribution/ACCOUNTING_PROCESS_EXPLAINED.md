# 📊 PROCESO DE GENERACIÓN DE ASIENTOS CONTABLES EN NÓMINA

## 🔄 FLUJO GENERAL DEL PROCESO

```
📋 Recibo de Nómina → 🧮 Cálculo de Reglas → 📊 Asientos Contables
```

## 📖 EXPLICACIÓN DETALLADA PASO A PASO

### 1️⃣ **INICIO DEL PROCESO**
```python
def _action_create_account_move(self):
```

**Qué hace**:
- Se ejecuta cuando confirmas/contabilizas la nómina
- Agrupa recibos por diario y fecha
- Filtra solo recibos en estado 'done' sin asiento contable

### 2️⃣ **AGRUPACIÓN DE RECIBOS**
```python
slip_mapped_data = {
    slip.struct_id.journal_id.id: {
        fields.Date().end_of(slip.date_to, 'month'): self.env['hr.payslip']
    } for slip in payslips_to_post
}
```

**Qué hace**:
- Agrupa recibos por **Diario** y **Mes**
- Un asiento por cada grupo (o individual según configuración)

### 3️⃣ **CONFIGURACIÓN DE ASIENTO**
```python
move_dict = {
    'narration': '',
    'ref': date.strftime('%B %Y'),  # Ej: "Enero 2025"
    'journal_id': journal_id,
    'date': date,
}
```

**Qué hace**:
- Crea encabezado del asiento contable
- Define diario, fecha y referencia

### 4️⃣ **PROCESAMIENTO DE LÍNEAS DE NÓMINA**
```python
for line in slip.line_ids.filtered(lambda line: line.category_id and line.salary_rule_id.not_computed_in_net == False):
```

**Qué hace**:
- Itera cada línea de nómina (Salario, Deducciones, Provisiones, etc.)
- Filtra solo líneas con categoría y que se computen en el neto

### 5️⃣ **CÁLCULO DE MONTOS**
```python
amount = -line.total if slip.credit_note else line.total

# Caso especial para NETO
if line.code == 'NET':
    for tmp_line in slip.line_ids.filtered(...):
        if tmp_line.salary_rule_id.not_computed_in_net:
            if amount > 0:
                amount -= abs(tmp_line.total)
            elif amount < 0:
                amount += abs(tmp_line.total)
```

**Qué hace**:
- Obtiene el valor de la línea
- Para el NETO: Ajusta restando conceptos que no se computan
- Maneja notas crédito (invierte signos)

### 6️⃣ **DETERMINACIÓN DE CUENTAS CONTABLES**
```python
debit_account_id = line.salary_rule_id.account_debit.id
credit_account_id = line.salary_rule_id.account_credit.id

# Lógica personalizada por regla de contabilización
for account_rule in line.salary_rule_id.salary_rule_accounting:
    # Validaciones por ubicación, compañía, departamento
    if bool_department and bool_company and bool_work_location:
        debit_account_id = account_rule.debit_account.id
        credit_account_id = account_rule.credit_account.id
```

**Qué hace**:
- Toma cuentas por defecto de la regla salarial
- Aplica reglas especiales según:
  - **Ubicación de trabajo** del empleado
  - **Compañía** del empleado  
  - **Departamento** del empleado
- Permite cuentas diferentes según contexto

### 7️⃣ **DETERMINACIÓN DE TERCEROS**
```python
# Tercero por defecto
debit_third_id = line.partner_id
credit_third_id = line.partner_id

# Lógica específica por tipo
if account_rule.third_debit == 'entidad':
    # Para seguridad social, busca la entidad específica
    for entity in slip.employee_id.social_security_entities:
        if entity.contrib_id.type_entities == 'eps' and line.code == 'SSOCIAL001':
            debit_third_id = entity.partner_id.partner_id
elif account_rule.third_debit == 'compañia':
    debit_third_id = slip.employee_id.company_id.partner_id
elif account_rule.third_debit == 'empleado':
    debit_third_id = slip.employee_id.work_contact_id
```

**Qué hace**:
- Determina quién es el tercero en cada línea contable
- **Entidad**: EPS, Pensión, ARL, etc.
- **Compañía**: La empresa empleadora
- **Empleado**: El trabajador

### 8️⃣ **DETERMINACIÓN DE CUENTA ANALÍTICA**
```python
analytic_account_id = line.employee_id.analytic_account_id.id

# Solo para cuentas de gasto (4,5,6,7)
if account_rule.debit_account.code[0:1] in ['4','5','6','7']:
    analytic_account_id = line.employee_id.analytic_account_id.id
```

**Qué hace**:
- Asigna cuenta analítica del empleado
- Solo para cuentas de **gastos** (4,5,6,7)
- **Balance** (1,2,3) no llevan analítica

### 9️⃣ **CREACIÓN DE LÍNEA DÉBITO**
```python
if debit_account_id:
    debit = amount if amount > 0.0 else 0.0
    credit = -amount if amount < 0.0 else 0.0
    
    # Buscar si ya existe línea similar
    existing_debit_lines = (
        line_id for line_id in line_ids if
        line_id['partner_id'] == debit_third_id.id
        and line_id['account_id'] == debit_account_id
        and ((line_id['debit'] > 0 and credit <= 0) or (line_id['credit'] > 0 and debit <= 0))
    )
    debit_line = next(existing_debit_lines, False)
    
    if not debit_line:
        # Crear nueva línea
        debit_line = {
            'name': line.name,
            'hr_salary_rule_id': line.salary_rule_id.id,
            'partner_id': debit_third_id.id,
            'account_id': debit_account_id,
            'date': date,
            'debit': debit,
            'credit': credit,
            'analytic_distribution': analytic_account_id and {analytic_account_id: 100}
        }
        line_ids.append(debit_line)
    else:
        # Consolidar con línea existente
        debit_line['debit'] += debit
        debit_line['credit'] += credit
```

**Qué hace**:
- Calcula débito/crédito según signo del monto
- **Consolida** líneas similares (misma cuenta, tercero, naturaleza)
- Agrega **cuenta analítica** si corresponde

### 🔟 **CREACIÓN DE LÍNEA CRÉDITO**
```python
if credit_account_id:
    # Ajuste para deducciones negativas
    if amount < 0.0 and line.salary_rule_id.dev_or_ded == 'deduccion':
        amount = amount * -1
    
    debit = -amount if amount < 0.0 else 0.0
    credit = amount if amount > 0.0 else 0.0
    
    # Proceso similar al débito...
    # Casos especiales para retención fuente
    if line.salary_rule_id.code == 'RETFTE001':
        credit_line['tax_line_id'] = line.salary_rule_id.account_tax_id.id
        credit_line['tax_base_amount'] = base_tax
```

**Qué hace**:
- Mismo proceso que débito pero para crédito
- **Caso especial**: Retención fuente incluye datos fiscales
- Maneja deducciones con montos negativos

### 1️⃣1️⃣ **BALANCEO Y AJUSTES**
```python
for line_id in line_ids:
    debit_sum += line_id['debit']
    credit_sum += line_id['credit']

# Si no está balanceado, crear ajuste al peso
if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
    adjust_credit = {
        'name': 'Ajuste al peso',
        'account_id': slip.journal_id.default_account_id.id,
        'credit': debit_sum - credit_sum,
        'debit': 0.0,
    }
    line_ids.append(adjust_credit)
```

**Qué hace**:
- Suma todos los débitos y créditos
- Si no están balanceados, crea **"Ajuste al peso"**
- Usa cuenta por defecto del diario

### 1️⃣2️⃣ **CREACIÓN DEL ASIENTO**
```python
move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
move = self.env['account.move'].create(move_dict)
slip.write({'move_id': move.id, 'date': date})
```

**Qué hace**:
- Crea el asiento contable con todas las líneas
- Vincula el asiento al recibo de nómina

## 📋 **EJEMPLO PRÁCTICO**

### Recibo de Nómina de Juan Pérez
```
Salario Básico:     $1,000,000
Auxilio Transporte:   $162,000
Salud (4%):           -$40,000
Pensión (4%):         -$40,000
NETO:              $1,082,000
```

### Asiento Contable Resultante
```
DÉBITOS:
5105 - Salario Básico           $1,000,000  (Gasto)
5120 - Auxilio Transporte        $162,000   (Gasto)
2367 - Salud por Pagar           $40,000    (Pasivo)
2370 - Pensión por Pagar         $40,000    (Pasivo)

CRÉDITOS:
2105 - Nomina por Pagar                     $1,082,000
2367 - Salud por Pagar                      $40,000
2370 - Pensión por Pagar                    $40,000
2380 - EPS Empleador                        $85,000
2381 - Pensión Empleador                    $120,000
```

## 🎯 **PUNTOS CLAVE**

1. **Consolidación**: Líneas similares se agrupan automáticamente
2. **Flexibilidad**: Cuentas y terceros varían según configuración
3. **Analítica**: Solo en cuentas de gasto (4,5,6,7)
4. **Balanceo**: Sistema garantiza que débitos = créditos
5. **Trazabilidad**: Cada línea tiene referencia a la regla salarial original
