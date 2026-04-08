#!/usr/bin/env python3
"""
Script para debuggear las reglas salariales y su configuración
"""

print("=== VERIFICACIÓN DE REGLAS SALARIALES ===")

# 1. Verificar si existen reglas de devengos
accrued_rules = env['hr.accrued.rule'].search([])
print(f"Reglas de devengos encontradas: {len(accrued_rules)}")
for rule in accrued_rules:
    print(f"  - {rule.code}: {rule.name}")

print("\n")

# 2. Verificar si existen reglas de deducciones  
deduct_rules = env['hr.deduct.rule'].search([])
print(f"Reglas de deducciones encontradas: {len(deduct_rules)}")
for rule in deduct_rules:
    print(f"  - {rule.code}: {rule.name}")

print("\n")

# 3. Verificar reglas salariales configuradas
salary_rules = env['hr.salary.rule'].search([])
print(f"Reglas salariales totales: {len(salary_rules)}")

# Reglas con devengado configurado
rules_with_accrued = salary_rules.filtered(lambda r: r.devengado_rule_id)
print(f"Reglas con devengado configurado: {len(rules_with_accrued)}")
for rule in rules_with_accrued:
    print(f"  - {rule.code}: {rule.name} -> {rule.devengado_rule_id.code}")

print("\n")

# Reglas con deducción configurada
rules_with_deduct = salary_rules.filtered(lambda r: r.deduccion_rule_id)
print(f"Reglas con deducción configurada: {len(rules_with_deduct)}")
for rule in rules_with_deduct:
    print(f"  - {rule.code}: {rule.name} -> {rule.deduccion_rule_id.code}")

print("\n")

# 4. Verificar payslips existentes
payslips = env['hr.payslip'].search([('state', 'in', ['done', 'paid'])], limit=5)
print(f"Últimas 5 nóminas procesadas:")
for payslip in payslips:
    print(f"  - {payslip.employee_id.name}: {payslip.date_from} - {payslip.date_to}")
    lines_with_rules = payslip.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id or l.salary_rule_id.deduccion_rule_id)
    print(f"    Líneas con reglas electrónicas: {len(lines_with_rules)}")

print("\n=== FIN VERIFICACIÓN ===")
