# -*- coding: utf-8 -*-
{
    'name': "Dynamic Excel Generation",

    'summary': """Easy create excel report from python code, Dynamic Excel Report, ,Global XLS Report, Export Excel, Export XLS Data, 
    Excel Custom Template, XLS Custom Template, Excel Export, Excel Output, XLS Export, Export XLS, XLSX Export, Export Special Fields Odoo
    """,

    'description': """
        easy create excel report from python code
    """,

    "author": "Openinside",
    "license": "OPL-1",
    'website': "https://www.open-inside.com",
    "price" : 81,
    "currency": 'USD',
    'category': 'Extra Tools',
    'version': "16.0",

    # any module necessary for this one to work correctly
    'depends': ['base','web', 'base_import'],
    #'depends': ['base','web', 'oi_action_file', 'base_import'],

    # always loaded
    'data': [        
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'report/templates.xml',
        'report/report.xml',
        'view/oi_excel_export.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        #'demo/demo.xml',
    ],
    
    'external_dependencies' : {
        'python' : ['xlsxwriter','json', 'openpyxl'],
    },
    'odoo-apps' : True,
    #'auto_install': True,
    'images':[
        'static/description/cover.png'
    ]    
}
