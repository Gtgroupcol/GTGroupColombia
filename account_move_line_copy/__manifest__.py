{
    'name': 'Duplicate Invoice Lines',
    'version': '1.0',
    'summary': 'Allow to duplicate an invoice line',
    'sequence': 10,
    'author': 'The Fish Consulting',
    'website': 'https://thefishconsulting.be',
    'images': ['static/description/duplicate_line.png'],
    'description': """
Duplicate Invoice Lines
=======================
Add a button at the end of each invoice line that allows users to quickly duplicate the line.    
""",
    'category': 'Accounting/Accounting',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'demo': [
    ],
    'price': 0.0,
    'currency': 'EUR',
    'support': 'contact@thefishconsulting.be',
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
