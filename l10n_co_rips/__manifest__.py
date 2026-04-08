# -*- coding: utf-8 -*-
{
    'name': 'Colombia RIPS',
    'summary': 'RIPS',
    'description': """ Extras para medfix RIPS""",
    'version': '1.0',
    'category': 'Medical',
    'author': 'Lavish',
    'license': 'OPL-1',
    'depends': ['base_address_extended', 'acs_hms','lavish_erp',"l10n_co_e-invoice","customer_contract"],
    "data": [
        "data/data.xml",
        "data/l10n_latam.identification.type.csv",
        "data/co_medical_services.xml",
        "data/rip_sequence_data.xml",
        "security/ir.model.access.csv",
        "views/account_move_view.xml",

        "views/glosa_medicas_view.xml",
        "views/hospital_rips_view.xml",
        "views/menuitem_view.xml",
        "views/res_partner_view.xml",      
        "views/configuracion_co_salud.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_co_rips/static/src/scss/notarial_kanban.scss',
        ],
    },
}