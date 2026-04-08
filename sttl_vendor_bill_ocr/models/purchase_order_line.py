# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    created_by_ocr_unmodified = fields.Boolean(
        compute="_compute_created_by_ocr_unmodified", store=True, default=False)

    @api.depends('product_qty', 'qty_received')
    def _compute_created_by_ocr_unmodified(self):
        for line in self.filtered(lambda line: line.created_by_ocr_unmodified):
            if line.order_id.state not in ['purchase']:
                continue
            if line.created_by_ocr_unmodified and line.qty_received != 0:
                line.created_by_ocr_unmodified = False

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity', 'qty_received', 'product_uom_qty', 'order_id.state')
    def _compute_qty_invoiced(self):
        super(PurchaseOrderLine, self)._compute_qty_invoiced()
        for line in self.filtered(lambda line: line.created_by_ocr_unmodified):
            if line.created_by_ocr_unmodified:
                line.qty_to_invoice = line.product_qty - line.qty_invoiced
