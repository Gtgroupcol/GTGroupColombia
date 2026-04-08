{
    'name': 'Débitos y Créditos Pendientes en Líneas de Factura',
    'version': '1.0',
    'summary': 'Muestra todos los apuntes contables relacionados con el partner en las líneas de factura',
    'category': 'Accounting',
    'author': 'JPabloGA',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/account_security.xml',
        'views/account_move_line_partner_lines_tree.xml',
        'views/account_move_line_inherit.xml',
        'views/account_move_line_list_view.xml',
        'views/account_move_line_reconcile_view.xml',  # Nuevo archivo
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
