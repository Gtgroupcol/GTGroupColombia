# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


# ------------------
# Migrate documents
# ------------------

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for product in env['product.template'].search([('dr_document_ids', '!=', False)]):
        att_without_document = product.dr_document_ids - product.product_document_ids.mapped('ir_attachment_id')
        att_with_document = product.product_document_ids.filtered(lambda doc: doc.ir_attachment_id not in att_without_document.ids)

        if att_with_document:
            att_with_document.write({'shown_on_product_page': True})

        if att_without_document:
            attachment_data = [{'ir_attachment_id': attachment.id, 'shown_on_product_page': True} for attachment in att_without_document]
            documents = env['product.document'].sudo().with_context(disable_product_documents_creation=True).create(attachment_data)
            _logger.info("[PRIME] Created prime documents product(%s): %s", product.id, documents.ids)

        _logger.info("[PRIME] Detached prime documents product: %s", product.dr_document_ids.ids)
        product.dr_document_ids = False