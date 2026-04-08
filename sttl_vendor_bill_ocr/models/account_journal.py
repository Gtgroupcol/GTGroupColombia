# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _create_document_from_attachment(self, attachment_ids=None):
        qwen_api_key = self.env['ir.config_parameter'].sudo().get_param('sttl_vendor_bill_ocr.qwen_api_key')
        if not qwen_api_key:
            raise UserError(_("Please enter valid Qwen API key"))
        
        attachments = self.env['ir.attachment'].browse(attachment_ids)
        if not attachments:
            raise UserError(_("No attachment was provided"))
        invoices = self.env['account.move']
        for attachment in attachments:
            self.env['account.move'].action_ocr_resume(attachment)
            invoice = self.env['account.move'].action_save(attachment)
            if invoice:
                invoices += invoice
        return invoices
