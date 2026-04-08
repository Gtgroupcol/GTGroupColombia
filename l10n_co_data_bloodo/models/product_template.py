# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dian_brand = fields.Char(
        'Brand',
        help='Brand reported in the electronic documents to the DIAN.'
    )
    dian_model = fields.Char(
        'Model',
        help='Model reported in the electronic documents to the DIAN.'
    )
    dian_customs_code = fields.Char(
        'Customs Code',
        help='Mainly needed for export invoices.'
    )
    unspsc_code_id = fields.Many2one(
        'product.unspsc.code',
        'UNSPSC Product Category',
        domain=[('applies_to', '=', 'product')],
        help='The UNSPSC code related to this product. '
        'Used for edi in Colombia, Peru and Mexico'
    )
