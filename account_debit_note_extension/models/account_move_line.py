from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
import logging

_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    def action_reconcile_13_22(self):
        """Método para manejar la conciliación entre cuentas por cobrar y por pagar"""
        if not self:
            return {'type': 'ir.actions.client', 'tag': 'reload'}
        
        reconciled_count = 0
        skipped_count = 0
        
        # Buscar el diario con código NCV
        ncv_journal = self.env['account.journal'].search([('code', '=', 'NCV')], limit=1)
        if not ncv_journal:
            return {
                'type': 'ir.actions.client', 
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se encontró el diario con código NCV. Por favor, cree este diario antes de continuar.'),
                    'sticky': True,
                    'type': 'danger',
                }
            }
        
        # Caso para una sola línea - mostrar wizard de selección
        if len(self) == 1:
            line = self[0]
            
            # Verificar si la cuenta es por cobrar o por pagar
            if not line.account_id.account_type in ['asset_receivable', 'liability_payable']:
                return {
                    'type': 'ir.actions.client', 
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Advertencia'),
                        'message': _('La línea seleccionada no es una cuenta por cobrar o por pagar.'),
                        'sticky': False,
                        'type': 'warning',
                    }
                }
            
            # Si no hay saldo residual, no hay nada que reconciliar
            if float_is_zero(line.amount_residual, precision_rounding=line.company_currency_id.rounding):
                return {
                    'type': 'ir.actions.client', 
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Advertencia'),
                        'message': _('La línea seleccionada no tiene saldo pendiente para conciliar.'),
                        'sticky': False,
                        'type': 'warning',
                    }
                }
            
            # Determinar el tipo de cuenta complementaria
            target_type = 'liability_payable' if line.account_id.account_type == 'asset_receivable' else 'asset_receivable'
            
            # Buscar líneas complementarias del mismo partner con saldo pendiente
            complementary_lines = self.env['account.move.line'].search([
                ('partner_id', '=', line.partner_id.id),
                ('account_id.account_type', '=', target_type),
                ('amount_residual', '!=', 0.0),
                ('move_id.state', '=', 'posted'),
                ('id', 'not in', line.full_reconcile_id.reconciled_line_ids.ids if line.full_reconcile_id else []),
            ])
            
            if not complementary_lines:
                return {
                    'type': 'ir.actions.client', 
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Advertencia'),
                        'message': _('No se encontraron líneas complementarias para conciliar con esta línea.'),
                        'sticky': False,
                        'type': 'warning',
                    }
                }
            
            # Abrir wizard de selección de líneas - CORREGIDO
            return {
                'name': _('Seleccionar línea para conciliar'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move.line',
                'view_mode': 'tree',
                'views': [(self.env.ref('account_debit_note_extension.view_move_line_reconcile_tree').id, 'tree')],
                'domain': [('id', 'in', complementary_lines.ids)],
                'target': 'new',
                'context': {
                    'default_original_line_id': line.id,
                    'search_default_group_by_move': 1,
                    'search_default_posted': 1,
                    'reconcile_mode': True,
                    'reconcile_original_line_id': line.id,
                }
            }
        
        # Caso para múltiples líneas - usar el comportamiento actual
        if len(self) > 1:
            receivable_lines = self.filtered(lambda l: l.account_id.account_type == 'asset_receivable' 
                                                 and not l.reconciled 
                                                 and l.amount_residual != 0)
            payable_lines = self.filtered(lambda l: l.account_id.account_type == 'liability_payable' 
                                              and not l.reconciled 
                                              and l.amount_residual != 0)
                                              
            # Si tenemos ambos tipos de líneas seleccionadas, podemos conciliar específicamente entre ellas
            if receivable_lines and payable_lines:
                # Agrupar por partner para conciliar solo entre el mismo partner
                partners = self.mapped('partner_id')
                for partner in partners:
                    partner_receivables = receivable_lines.filtered(lambda l: l.partner_id == partner)
                    partner_payables = payable_lines.filtered(lambda l: l.partner_id == partner)
                    
                    if partner_receivables and partner_payables:
                        for rec_line in partner_receivables:
                            for pay_line in partner_payables:
                                if float_is_zero(rec_line.amount_residual, precision_rounding=rec_line.company_currency_id.rounding) or \
                                   float_is_zero(pay_line.amount_residual, precision_rounding=pay_line.company_currency_id.rounding):
                                    continue
                                    
                                # Calcular el monto a reconciliar (siempre el menor)
                                amount_to_reconcile = min(
                                    abs(rec_line.amount_residual),
                                    abs(pay_line.amount_residual)
                                )
                                
                                if self._create_reconciliation_entry(rec_line, pay_line, amount_to_reconcile, ncv_journal):
                                    reconciled_count += 1
                                    
                                # Si alguna de las líneas ya no tiene saldo, no seguir reconciliando
                                if float_is_zero(rec_line.amount_residual, precision_rounding=rec_line.company_currency_id.rounding) or \
                                   float_is_zero(pay_line.amount_residual, precision_rounding=pay_line.company_currency_id.rounding):
                                    break
                
                if reconciled_count > 0:
                    return self._show_reconciliation_result(reconciled_count, skipped_count)
            else:
                return {
                    'type': 'ir.actions.client', 
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Advertencia'),
                        'message': _('Debe seleccionar al menos una línea por cobrar y una línea por pagar para realizar la conciliación.'),
                        'sticky': False,
                        'type': 'warning',
                    }
                }
        
        return self._show_reconciliation_result(reconciled_count, skipped_count)
    
    def _create_reconciliation_entry(self, line1, line2, amount, journal):
        """Crear un asiento de reconciliación entre dos líneas"""
        try:
            # Determinar cuál línea es por pagar y cuál por cobrar
            if line1.account_id.account_type == 'asset_receivable':
                receivable_line = line1
                payable_line = line2
            else:
                receivable_line = line2
                payable_line = line1
                
            # Obtener referencias de documentos para nombres descriptivos
            origin_doc_ref = receivable_line.move_id.name or 'Sin referencia'
            comp_doc_ref = payable_line.move_id.name or 'Sin referencia'
            
            # Crear asiento de traspaso directo entre cuentas - USANDO DIARIO NCV
            move_vals = {
                'date': fields.Date.context_today(receivable_line),
                'journal_id': journal.id,
                'ref': f'Traspaso entre {receivable_line.account_id.code} y {payable_line.account_id.code} (Cruce de saldos)',
                'line_ids': [
                    (0, 0, {
                        'name': f'De: {origin_doc_ref} - {receivable_line.name or ""}',
                        'account_id': receivable_line.account_id.id,
                        'debit': 0.0,
                        'credit': amount,
                        'partner_id': receivable_line.partner_id.id,
                    }),
                    (0, 0, {
                        'name': f'A: {comp_doc_ref} - {payable_line.name or ""}',
                        'account_id': payable_line.account_id.id,
                        'debit': amount,
                        'credit': 0.0,
                        'partner_id': payable_line.partner_id.id,
                    })
                ]
            }
            
            # Crear y publicar el asiento
            transfer_move = self.env['account.move'].create(move_vals)
            transfer_move.action_post()
            
            # Reconciliar las líneas correspondientes al monto
            rec_lines = receivable_line | transfer_move.line_ids.filtered(
                lambda l: l.account_id == receivable_line.account_id
            )
            pay_lines = payable_line | transfer_move.line_ids.filtered(
                lambda l: l.account_id == payable_line.account_id
            )
            
            # Realizar reconciliación parcial
            rec_lines.with_context(partial_reconcile=True).reconcile()
            pay_lines.with_context(partial_reconcile=True).reconcile()
            
            return True
        except Exception as e:
            self.env.cr.rollback()
            _logger.error(f"Error en la conciliación: {e}")
            return False
    
    def _show_reconciliation_result(self, reconciled_count, skipped_count):
        """Mostrar resultado de la reconciliación"""
        if reconciled_count > 0 and skipped_count > 0:
            return {
                'type': 'ir.actions.client', 
                'tag': 'display_notification',
                'params': {
                    'title': _('Conciliación completada'),
                    'message': _('%s líneas conciliadas, %s líneas omitidas.') % (reconciled_count, skipped_count),
                    'sticky': False,
                    'type': 'success',
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }
        elif reconciled_count > 0:
            return {
                'type': 'ir.actions.client', 
                'tag': 'display_notification',
                'params': {
                    'title': _('Conciliación completada'),
                    'message': _('%s líneas conciliadas correctamente.') % reconciled_count,
                    'sticky': False,
                    'type': 'success',
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }
        else:
            return {
                'type': 'ir.actions.client', 
                'tag': 'display_notification',
                'params': {
                    'title': _('Advertencia'),
                    'message': _('No se pudo conciliar ninguna línea.'),
                    'sticky': False,
                    'type': 'warning',
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }
    
    def action_reconcile_with_line(self):
        """Método para conciliar la línea seleccionada con la línea original"""
        self.ensure_one()
        
        # Obtener la línea original del contexto
        original_line_id = self.env.context.get('reconcile_original_line_id')
        if not original_line_id:
            return {
                'type': 'ir.actions.client', 
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se encontró la línea original para conciliar.'),
                    'sticky': False,
                    'type': 'danger',
                }
            }
        
        original_line = self.env['account.move.line'].browse(original_line_id)
        
        # Buscar el diario con código NCV
        ncv_journal = self.env['account.journal'].search([('code', '=', 'NCV')], limit=1)
        if not ncv_journal:
            return {
                'type': 'ir.actions.client', 
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se encontró el diario con código NCV. Por favor, cree este diario antes de continuar.'),
                    'sticky': True,
                    'type': 'danger',
                }
            }
        
        # Calcular el monto a reconciliar (siempre el menor)
        amount_to_reconcile = min(
            abs(original_line.amount_residual),
            abs(self.amount_residual)
        )
        
        if amount_to_reconcile > 0:
            if self._create_reconciliation_entry(original_line, self, amount_to_reconcile, ncv_journal):
                return {
                    'type': 'ir.actions.client', 
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Conciliación completada'),
                        'message': _('La línea se ha conciliado correctamente.'),
                        'sticky': False,
                        'type': 'success',
                        'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                    }
                }
        
        return {
            'type': 'ir.actions.client', 
            'tag': 'display_notification',
            'params': {
                'title': _('Advertencia'),
                'message': _('No se pudo conciliar la línea seleccionada.'),
                'sticky': False,
                'type': 'warning',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

