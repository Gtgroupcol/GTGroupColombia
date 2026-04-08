# -*- coding: utf-8 -*-

from odoo import models, fields


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    json_data = fields.Text("Json Data")
