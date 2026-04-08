# -*- coding: utf-8 -*-
{
    'name': 'Colombian Tax Base Threshold',
    'version': '17.0.2.6.1',
    'category': 'Accounting/Localizations',
    'summary': 'Colombian withholding taxes with UVT-based thresholds and progressive rates',
    'description': """
Colombian Tax Base Threshold
============================

Complete Colombian withholding tax management system including:

FEATURES:
---------
* Tax Parameters (UVT/SMMLV) by year
* Withholding Concepts:
  - Retención en la Fuente (Compras, Servicios, Honorarios, Salarios)
  - ReteIVA (Bienes, Servicios)
  - INC (Restaurantes, Telefonía)
  - ReteICA

    """,
    'author': 'Donsson',
    'website': 'https://www.donsson.com',
    'depends': ['account', 'base', 'sale', 'purchase', 'base_address_extended'],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Views
        'views/tax_general_parameter_views.xml',
        'views/withholding_concept_views.xml',
        'views/withholding_rate_views.xml',
        'views/tax_base_threshold_views.xml',
        'views/ica_tariff_views.xml',
        'views/account_tax_views.xml',
        'views/account_journal_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/menu_views.xml',
        # Data
        'data/withholding_data.xml',
        'data/ica_tariff_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
