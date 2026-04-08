from odoo import models, fields, api, _
import json

class AccountMove(models.Model):
    _inherit = 'account.move'

    related_partner_lines = fields.One2many(
        comodel_name='account.move.line',
        compute='_compute_related_partner_lines',
        string='Apuntes del Partner',
    )

    @api.depends('partner_id', 'line_ids', 'line_ids.account_id')
    def _compute_related_partner_lines(self):
        for move in self:
            if move.partner_id:
                # Obtener la primera cuenta por cobrar o por pagar del asiento
                current_line = move.line_ids.filtered(
                    lambda l: l.account_id.account_type in ['asset_receivable', 'liability_payable']
                )
                
                if current_line:
                    current_account = current_line[0].account_id
                    # Si es cuenta por cobrar, buscamos las por pagar y viceversa
                    target_type = 'liability_payable' if current_account.account_type == 'asset_receivable' else 'asset_receivable'
                    
                    domain = [
                        ('partner_id', '=', move.partner_id.id),
                        ('move_id', '!=', move.id),
                        ('parent_state', '=', 'posted'),
                        ('account_id.account_type', '=', target_type),
                        ('reconciled', '=', False),
                        ('amount_residual', '!=', 0.0),
                    ]
                    move.related_partner_lines = self.env['account.move.line'].search(domain)
                else:
                    move.related_partner_lines = self.env['account.move.line']
            else:
                move.related_partner_lines = self.env['account.move.line']

    def action_reconcile_all_related_lines(self):
        """Conciliar automáticamente todas las líneas relacionadas con esta factura"""
        self.ensure_one()
        
        lines_to_reconcile = self.related_partner_lines.filtered(
            lambda l: not l.reconciled and l.amount_residual != 0.0
                     and l.account_id.account_type in ['asset_receivable', 'liability_payable']
        )
        
        if lines_to_reconcile:
            return lines_to_reconcile.action_reconcile_13_22()
        else:
            return {
                'type': 'ir.actions.client', 
                'tag': 'display_notification',
                'params': {
                    'title': _('Información'),
                    'message': _('No hay líneas pendientes para conciliar.'),
                    'sticky': False,
                    'type': 'info',
                }
            }
