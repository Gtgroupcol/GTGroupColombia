# -*- coding: utf-8 -*-
{
    'name': 'Invoicing Baseline',
    'summary': '''
        Invoices & Payments
    ''',
    'description': '''
        - Administrar terceros en lineas de factura de venta (Política).
        - Administrar terceros en lineas de factura de proveedor (Política).
        - Bloquear fechas cuando hay asientos en borrador (Política).
    ''',
    'author': 'lavish',
    'category': 'Accounting/Accounting',
    'license': 'LGPL-3',
    'version': '17.0.0.1.8',
    'depends': [
        'account',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        #'security/account_baseline_groups.xml',
        'views/account_move_views.xml',
        'views/product_category_views.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/account_journal_views.xml',
        'reports/account_details_report.xml',
        'reports/report_account_details.xml',
        'wizard/account_details_views.xml',
    ],
}
