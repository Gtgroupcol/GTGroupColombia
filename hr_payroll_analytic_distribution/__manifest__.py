# -*- coding: utf-8 -*-
{
    'name': "HR Payroll Analytic Distribution",
    'summary': """
        Distribución analítica multicuenta para nómina""",
    'description': """
        Módulo personalizado que permite distribuir los costos de nómina 
        entre múltiples cuentas analíticas con porcentajes específicos.
        
        Características principales:
        - Widget multicuenta en formulario de nómina
        - Validación automática de porcentajes (debe sumar 100%)
        - Integración completa con asientos contables
        - Compatibilidad con sistema existente
    """,
    'author': "Desarrollo Personalizado",
    'website': "",
    'category': 'Human Resources/Payroll',
    'version': '17.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'hr_payroll',
        'account',
        'analytic',
        'lavish_hr_payroll',  # Dependencia del módulo base de nómina
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_payslip_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_payroll_analytic_distribution/static/src/scss/payroll_analytic.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
