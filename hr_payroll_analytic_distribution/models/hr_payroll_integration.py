# -*- coding: utf-8 -*-

from odoo import models


class HrPayrollAccountMove(models.Model):
    """Integración con asientos contables de nómina para distribución analítica"""
    _inherit = 'hr.payslip'
    
    def _get_move_lines_for_payslip_accounting(self, date):
        """Sobrescribir para incluir distribución analítica en asientos"""
        # Llamar al método original
        result = super()._get_move_lines_for_payslip_accounting(date)
        
        # Obtener distribución analítica efectiva
        analytic_distribution = self.get_effective_analytic_distribution()
        
        # Aplicar distribución a todas las líneas de asiento
        if analytic_distribution and result:
            for line_vals in result:
                # Solo aplicar si no tiene distribución ya definida
                if 'analytic_distribution' not in line_vals or not line_vals['analytic_distribution']:
                    line_vals['analytic_distribution'] = analytic_distribution
        
        return result


class HrPayrollPosting(models.Model):
    """Integración con dispersiones de nómina para distribución analítica"""
    _inherit = 'hr.payroll.posting'
    
    def _prepare_move_line_values(self, payslip, account_id, amount, name):
        """Preparar valores de línea de asiento con distribución analítica"""
        vals = super()._prepare_move_line_values(payslip, account_id, amount, name)
        
        # Agregar distribución analítica si existe
        analytic_distribution = payslip.get_effective_analytic_distribution()
        if analytic_distribution:
            vals['analytic_distribution'] = analytic_distribution
            
        return vals
