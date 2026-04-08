# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    payment_policy = fields.Float(
        string='Payment policy',
    )


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    account_type = fields.Selection(
        selection=[
            ('saving', 'Saving'),
            ('current', 'Current'),
        ],
        string='Account type',
        default='saving'
    )
