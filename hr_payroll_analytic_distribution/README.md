# HR Payroll Analytic Distribution

## Descripción

Módulo personalizado que extiende la funcionalidad de nómina de Odoo para soportar distribución analítica multicuenta. Permite distribuir los costos de nómina entre múltiples cuentas analíticas con porcentajes específicos.

## Características

- ✅ **Widget multicuenta**: Interfaz nativa de Odoo para distribución analítica
- ✅ **Validación automática**: La suma de porcentajes debe ser exactamente 100%
- ✅ **Integración completa**: Afecta todos los asientos contables generados
- ✅ **Compatibilidad**: Mantiene funcionalidad existente del sistema base
- ✅ **Módulo independiente**: No modifica código del módulo base

## Instalación

1. Copiar el módulo a la carpeta `addons` de Odoo
2. Actualizar la lista de módulos
3. Instalar el módulo "HR Payroll Analytic Distribution"

## Dependencias

- `hr_payroll` - Módulo de nómina base de Odoo
- `analytic` - Módulo de contabilidad analítica
- `lavish_hr_payroll` - Módulo de nómina personalizado existente

## Uso

### Configurar Distribución Analítica

1. **Abrir un recibo de nómina**
2. **Localizar el campo "Distribución Analítica"** (antes del campo Diario)
3. **Hacer clic en el widget** para abrir el selector de cuentas
4. **Seleccionar cuentas analíticas** y asignar porcentajes
5. **Verificar que la suma sea 100%**
6. **Guardar** el recibo de nómina

### Ejemplo de Configuración

```json
{
    "account_id_1": 60.0,    // Departamento A: 60%
    "account_id_2": 25.0,    // Departamento B: 25%
    "account_id_3": 15.0     // Departamento C: 15%
}
```

## Comportamiento

### Prioridad de Distribución

El sistema determina la distribución analítica en el siguiente orden:

1. **Distribución específica** definida en el recibo de nómina
2. **Cuenta analítica del contrato** (al 100% si no hay distribución específica)
3. **Campo legacy** de cuenta analítica (compatibilidad)

### Validaciones

- La suma de todos los porcentajes debe ser exactamente **100.0%**
- Tolerancia de **0.01%** para evitar errores de redondeo
- Validación automática al guardar el registro

### Integración Contable

- Todos los asientos contables generados por nómina incluyen la distribución analítica
- Cada línea de asiento se distribuye según los porcentajes configurados
- Compatible con el flujo contable existente

## Estructura del Módulo

```
hr_payroll_analytic_distribution/
├── __manifest__.py              # Configuración del módulo
├── __init__.py                  # Importaciones principales
├── models/
│   ├── __init__.py
│   ├── hr_payslip.py           # Extensión del modelo de nómina
│   └── account_integration.py   # Integración con contabilidad
├── views/
│   └── hr_payslip_views.xml    # Vistas del formulario
├── security/
│   └── ir.model.access.csv     # Permisos de acceso
└── README.md                   # Esta documentación
```

## Archivos Principales

### `models/hr_payslip.py`
- Agrega campo `analytic_distribution` a `hr.payslip`
- Implementa validaciones de porcentajes
- Método `get_effective_analytic_distribution()`

### `views/hr_payslip_views.xml`
- Widget multicuenta en formulario de nómina
- Posicionado antes del campo "Diario"

### `models/account_integration.py`
- Métodos auxiliares para integración contable
- Preparación de líneas de asiento con distribución

## Versiones Compatibles

- **Odoo 17.0+**
- Compatible con módulos de nómina localizados
- Requiere módulo `analytic` activado

## Soporte

Para soporte técnico o consultas sobre el módulo, contactar al equipo de desarrollo.

## Licencia

LGPL-3
