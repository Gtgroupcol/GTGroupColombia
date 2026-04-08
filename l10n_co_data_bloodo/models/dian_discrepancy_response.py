# -*- coding: utf-8 -*-

from odoo import fields, models


class DianDiscrepancyResponse(models.Model):
    _name = 'dian.discrepancy.response'
    _description = 'DIAN correction concepts for Credit and Debit notes'

    name = fields.Char('Name')
    dian_code = fields.Char('DIAN code')
    type = fields.Selection([('credit', 'Credit Note'),
                             ('debit', 'Debit Note')],
                            'Type')
    is_sd = fields.Boolean("Is support document?", default=False)
    is_ei = fields.Boolean("Is electronic invoice?", default=False)
