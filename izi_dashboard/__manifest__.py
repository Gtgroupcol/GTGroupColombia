# -*- coding: utf-8 -*-
# Copyright 2022 IZI PT Solusi Usaha Mudah
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
# noinspection PyUnresolvedReferences,SpellCheckingInspection
{
    "name": """IZI Dashboard with AI""",
    "summary": """
        Beautiful Analytic Dashboard by IZI.
        You can create a Sales Dashboard, Inventory Dashboard, Finance Dashboard, or Others dynamically with this module.
        You can explore data with AI too!
    """,
    "category": "Reporting",
    "version": "17.0",
    "development_status": "Production",  # Options: Alpha|Beta|Production/Stable|Mature
    "auto_install": False,
    "installable": True,
    "application": True,
    "author": "IZI PT Solusi Usaha Mudah",
    "support": "admin@iziapp.id",
    "website": "https://www.iziapp.id",
    "license": "OPL-1",
    "images": [
        'static/description/banner.gif'
    ],

    "price": 285,
    "currency": "USD",

    "depends": [
        # odoo addons
        'base',
        'web',
        # third party addons

        # developed addons
        'izi_data',
    ],
    "data": [
        # group
        'security/res_groups.xml',

        # data
        'data/izi_visual_type.xml',
        'data/izi_visual_config.xml',
        'data/izi_visual_config_value.xml',
        'data/izi_dashboard_theme.xml',
        'data/izi_data_template.xml',

        # global action
        # 'views/action/action.xml',

        # view
        'views/common/izi_dashboard.xml',
        'views/common/izi_analysis.xml',
        'views/common/izi_lab_api_key_wizard.xml',
        'views/common/res_company.xml',

        # wizard
        'views/wizard/izi_dashboard_config_wizard.xml',

        # report paperformat
        # 'data/report_paperformat.xml',

        # report template
        # 'views/report/report_template_model_name.xml',

        # report action
        # 'views/action/action_report.xml',

        # assets
        # 'views/assets.xml',

        # onboarding action
        # 'views/action/action_onboarding.xml',

        # action menu
        'views/action/action_menu.xml',

        # action onboarding
        # 'views/action/action_onboarding.xml',

        # menu
        'views/menu.xml',

        # security
        'security/ir.model.access.csv',
        # 'security/ir.rule.csv',

        # template
        'views/template/izi_dashboard.xml',
    ],
    "demo": [
        # 'demo/demo.xml',
    ],
    "qweb": [

    ],

    "post_load": None,
    # "pre_init_hook": "pre_init_hook",
    # "post_init_hook": "post_init_hook",
    "uninstall_hook": None,

    "external_dependencies": {"python": [], "bin": []},
    "live_test_url": "https://demo.iziapp.id/web/login",
    # "demo_title": "{MODULE_NAME}",
    # "demo_addons": [
    # ],
    # "demo_addons_hidden": [
    # ],
    "demo_url": "https://demo.iziapp.id/web/login",
    # "demo_summary": "{SHORT_DESCRIPTION_OF_THE_MODULE}",
    # "demo_images": [
    #    "images/MAIN_IMAGE",
    # ]


}
