# -*- coding: utf-8 -*-

{
    'name': 'Vendor Bill Digitalisation',
    'version': '17.0.1.0',
    'category': 'Tools',
    'description': 'Extracts the information from the vendor bills in image or pdf format and creates bill as well as purchase order.',
    'license': 'LGPL-3',
    'author': 'Silver Touch Technologies Limited',
    'website': 'https://www.silvertouch.com/',
    'summary': 'Extracts the information from the vendor bills in image or pdf format and creates bill as well as purchase order.',
    'depends': ['account', 'purchase'],
    'data': [
        'views/res_config_view.xml',
    ],
    'external_dependencies': {
        'python': ['pdf2image', 'pillow', 'pytesseract', 'python-docx', 'pypdf']
    },
    'installable': True,
    'application': False,
    'images': ['static/description/banner.png'],
}
