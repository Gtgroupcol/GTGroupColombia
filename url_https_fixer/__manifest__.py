{
    'name': 'URL HTTPS Fixer',
    'version': '17.0.1.0.0',
    'category': 'Hidden',
    'summary': 'Cambia automáticamente HTTP a HTTPS en web.base.url (excepto localhost)',
    'description': """
URL HTTPS Fixer
===============

Módulo simple que:
- Consulta web.base.url cada minuto
- Cambia HTTP a HTTPS automáticamente
- Excepto cuando la URL contiene localhost
- Registra todos los cambios en logs
    """,
    'author': 'Auto Generated',
    'depends': ['base'],
    'data': [
        'data/cron_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
