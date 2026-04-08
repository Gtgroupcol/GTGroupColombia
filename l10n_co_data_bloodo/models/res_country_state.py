# coding: utf-8

from odoo import fields, models


class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    dian_code = fields.Char('DIAN code')
