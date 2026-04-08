# -*- coding: utf-8 -*-
#################################################################################
# Author      : Terabits Technolab (<www.terabits.xyz>)
# Copyright(c): 2021
# All Rights Reserved.
#
# This module is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################
{
    "name": "Advanced Web Domain Widget",
    "version": "17.0.1.1.0",
    "summary": "Set all relational fields domain by selecting its records unsing `in, not in` operator.",
    "sequence": 10,
    "author": "Terabits Technolab",
    "license": "OPL-1",
    "website": "https://www.terabits.xyz",
    "description": """
      
        """,
    "price": "29.00",
    "currency": "USD",
    "depends": ["base", "web"],
    "data": [
        # 'views/assets.xml',
    ],
    "assets": {
        "web.assets_frontend": [
            "advanced_web_domain_widget/static/src/core/**/*",
            "advanced_web_domain_widget/static/src/dateSelectionBits/dateSelectionBits.js",
            "advanced_web_domain_widget/static/src/dateSelectionBits/dateSelectionBits.xml",
        ],
        "web._assets_core": [
            "advanced_web_domain_widget/static/src/core/**/*",
            "advanced_web_domain_widget/static/src/dateSelectionBits/dateSelectionBits.js",
            "advanced_web_domain_widget/static/src/dateSelectionBits/dateSelectionBits.xml",
        ],
        "web.assets_backend": [
            "advanced_web_domain_widget/static/src/core/**/*",
            "advanced_web_domain_widget/static/src/fields/domain/domain_field.js",
            "advanced_web_domain_widget/static/src/fields/domain/domain_field.xml",
            "advanced_web_domain_widget/static/src/dateSelectionBits/dateSelectionBits.js",
            "advanced_web_domain_widget/static/src/dateSelectionBits/dateSelectionBits.xml",
        ],
    },
    "images": ["static/description/banner.png"],
    "application": True,
    "installable": True,
    "auto_install": False,
}
