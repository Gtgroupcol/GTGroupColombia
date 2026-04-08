#!/bin/bash

# Script para instalar el módulo hr_payroll_analytic_distribution

echo "🚀 Instalando módulo hr_payroll_analytic_distribution..."

# Cambiar al directorio de Odoo
cd /home/daniel/Documents/nomina_gt/odoo

# Reinstalar el módulo (por si ya estaba instalado)
echo "📦 Reinstalando módulo..."
python3 odoo-bin -u hr_payroll_analytic_distribution -d nomina_gt --stop-after-init

echo "✅ Módulo reinstalado correctamente"
echo ""
echo "📋 PRÓXIMOS PASOS:"
echo "1. Verifica que el módulo aparece en Aplicaciones"
echo "2. Ve a Nómina → Recibos de Nómina"
echo "3. Crea o edita un recibo"
echo "4. Busca el campo 'Distribución Analítica'"
echo "5. Configura las cuentas analíticas y porcentajes"
echo ""
echo "🔧 SOLUCIÓN AL PROBLEMA:"
echo "- El sistema ya NO usará la cuenta analítica del empleado"
echo "- Usará la distribución del recibo de nómina si está configurada"
echo "- Si no hay distribución en el recibo, usará la del contrato"
echo "- Si no hay ninguna, no aplicará distribución analítica"
echo ""
echo "📖 Lee el archivo SOLUCION_DISTRIBUCION_ANALITICA.md para más detalles"
