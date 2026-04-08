# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fiscalyear_lock_except = fields.Boolean(
        related='company_id.fiscalyear_lock_except',
        readonly=False
    )
    restriction_line_price = fields.Boolean(
        related='company_id.restriction_line_price',
        readonly=False
    )
    manage_partner_in_invoice_lines_out = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_out',
        readonly=False
    )
    manage_partner_in_invoice_lines_in = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_in',
        readonly=False
    )
