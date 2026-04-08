# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class account_journal(models.Model):
    _inherit = 'account.journal'

    type = fields.Selection(tracking=True)
    company_id = fields.Many2one(tracking=True)
    code = fields.Char(tracking=True)
    sequence_number_next = fields.Integer(tracking=True)
    default_account_id = fields.Many2one(tracking=True)
    default_account_id = fields.Many2one(tracking=True)