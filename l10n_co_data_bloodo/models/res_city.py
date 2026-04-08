# coding: utf-8

from odoo import fields, models


class City(models.Model):
    _inherit = 'res.city'

    dian_code = fields.Char('DIAN code')
