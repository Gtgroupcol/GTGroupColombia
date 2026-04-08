#!/bin/bash
# Script para instalar y probar el módulo

echo "🔄 Instalando módulo hr_payroll_analytic_distribution..."

# Verificar que Odoo esté funcionando
if ! pgrep -f "odoo-bin" > /dev/null; then
    echo "❌ Error: Odoo no está ejecutándose"
    exit 1
fi

echo "✅ Odoo está ejecutándose"

# Verificar sintaxis de archivos Python
echo "🔍 Verificando sintaxis de archivos Python..."
for file in models/*.py; do
    if ! python3 -m py_compile "$file"; then
        echo "❌ Error de sintaxis en $file"
        exit 1
    fi
done
echo "✅ Sintaxis de archivos Python correcta"

# Verificar sintaxis de archivos XML
echo "🔍 Verificando sintaxis de archivos XML..."
for file in views/*.xml data/*.xml; do
    if [[ -f "$file" ]]; then
        if ! xmllint --noout "$file" 2>/dev/null; then
            echo "❌ Error de sintaxis XML en $file"
            exit 1
        fi
    fi
done
echo "✅ Sintaxis de archivos XML correcta"

echo "🎉 Módulo listo para instalación"
echo ""
echo "📋 Pasos para instalar:"
echo "1. Ir a Apps en Odoo"
echo "2. Actualizar lista de aplicaciones"
echo "3. Buscar 'HR Payroll Analytic Distribution'"
echo "4. Hacer clic en Instalar"
echo ""
echo "🧪 Para probar:"
echo "1. Ir a Nómina > Recibos de Nómina"
echo "2. Crear/editar un recibo"
echo "3. Configurar 'Distribución Analítica'"
echo "4. Verificar que se guarde correctamente"
