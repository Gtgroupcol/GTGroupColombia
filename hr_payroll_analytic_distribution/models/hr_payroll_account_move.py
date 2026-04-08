# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _action_create_account_move(self):
        """
        Override para aplicar distribución analítica personalizada
        """
        # Ejecutar el método original primero
        result = super()._action_create_account_move()
        
        # Luego actualizar la distribución analítica
        for payslip in self:
            if payslip.move_id:
                payslip._update_move_analytic_distribution()
        
        return result
    
    def _update_move_analytic_distribution(self):
        """
        Actualizar distribución analítica en las líneas del asiento contable
        usando la distribución del recibo de nómina en lugar de la del empleado
        """
        if not self.move_id:
            return
        
        # Obtener la distribución analítica efectiva del recibo
        effective_distribution = self.get_effective_analytic_distribution()
        
        # Obtener todas las cuentas contables asociadas a las reglas salariales de este recibo
        payslip_accounts = set()
        for line in self.line_ids:
            if line.salary_rule_id:
                # Agregar cuentas débito y crédito de la regla
                if line.salary_rule_id.account_debit:
                    payslip_accounts.add(line.salary_rule_id.account_debit.id)
                if line.salary_rule_id.account_credit:
                    payslip_accounts.add(line.salary_rule_id.account_credit.id)
                
                # También agregar cuentas de las reglas de contabilización específicas
                for account_rule in line.salary_rule_id.salary_rule_accounting:
                    if account_rule.debit_account:
                        payslip_accounts.add(account_rule.debit_account.id)
                    if account_rule.credit_account:
                        payslip_accounts.add(account_rule.credit_account.id)
        
        # Procesar cada línea del asiento
        for move_line in self.move_id.line_ids:
            # Solo actualizar líneas que pertenezcan a las cuentas contables 
            # de las reglas salariales de este recibo (sin importar la codificación)
            if move_line.account_id.id in payslip_accounts:
                
                # Si hay distribución personalizada en el recibo, usarla
                if effective_distribution:
                    move_line.write({
                        'analytic_distribution': effective_distribution
                    })
                # Si NO hay distribución en el recibo, remover la distribución
                else:
                    move_line.write({
                        'analytic_distribution': False
                    })
