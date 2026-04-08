# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    qwen_api_key = fields.Char(config_parameter='sttl_vendor_bill_ocr.qwen_api_key', string="Qwen API key")
    allow_po_creation_from_bill = fields.Boolean(config_parameter='sttl_vendor_bill_ocr.allow_po_creation_from_bill', string="Allow PO Creation")
