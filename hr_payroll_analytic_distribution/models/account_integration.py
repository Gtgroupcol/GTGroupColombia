# -*- coding: utf-8 -*-

from odoo import models


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def _get_analytic_distribution_for_moves(self, payslips):
        """Obtener distribución analítica para asientos contables"""
        if not payslips:
            return {}
        
        # Si todos los payslips tienen la misma distribución, usarla
        first_distribution = payslips[0].get_effective_analytic_distribution()
        
        # Verificar si todos tienen la misma distribución
        for payslip in payslips[1:]:
            if payslip.get_effective_analytic_distribution() != first_distribution:
                # Si hay diferencias, no usar distribución global
                return {}
        
        return first_distribution


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _prepare_move_line_values_from_payslip(self, payslip, account, amount, name=None):
        """Preparar valores de línea de asiento con distribución analítica"""
        vals = {
            'name': name or payslip.name,
            'account_id': account.id,
            'debit': amount if amount > 0 else 0.0,
            'credit': abs(amount) if amount < 0 else 0.0,
            'partner_id': payslip.employee_id.partner_id.id,
        }
        
        # Agregar distribución analítica si existe
        analytic_distribution = payslip.get_effective_analytic_distribution()
        if analytic_distribution:
            vals['analytic_distribution'] = analytic_distribution
            
        return vals
