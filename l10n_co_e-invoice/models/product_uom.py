# coding: utf-8
from odoo import fields, models


class ProductUom(models.Model):
    _inherit = 'uom.uom'

    dian_country_code = fields.Char(
        'Country code',
        default=lambda self: self.env.company.country_id.code
    )
    dian_uom_id = fields.Many2one(
        'dian.uom.code', 'DIAN UoM'
    )
    unspsc_code_id = fields.Many2one(
        'product.unspsc.code',
        'UNSPSC Product Category',
        domain=[('applies_to', '=', 'uom')],
        help='The UNSPSC code related to this UoM. '
    )
