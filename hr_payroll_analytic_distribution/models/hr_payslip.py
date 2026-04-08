# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Campos necesarios para el widget analytic_distribution
    analytic_distribution = fields.Json(
        string='Distribución Analítica',
        help='Distribución analítica para esta nómina. Permite distribuir los costos entre múltiples cuentas analíticas.'
    )
    
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env['decimal.precision'].precision_get("Percentage Analytic"),
    )

    @api.depends('analytic_distribution')
    def _compute_distribution_analytic_account_ids(self):
        """Calcular cuentas analíticas de la distribución"""
        for record in self:
            if record.analytic_distribution:
                account_ids = []
                for account_id in record.analytic_distribution.keys():
                    try:
                        account_ids.append(int(account_id))
                    except (ValueError, TypeError):
                        continue
                record.distribution_analytic_account_ids = account_ids
            else:
                record.distribution_analytic_account_ids = []

    distribution_analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        compute='_compute_distribution_analytic_account_ids',
        string='Cuentas Analíticas de Distribución'
    )

    @api.onchange('employee_id', 'contract_id')
    def _onchange_employee_analytic_distribution(self):
        """Establecer cuenta analítica por defecto desde el contrato"""
        if self.contract_id and self.contract_id.analytic_account_id and not self.analytic_distribution:
            # Si hay cuenta analítica en el contrato, establecerla al 100%
            self.analytic_distribution = {
                str(self.contract_id.analytic_account_id.id): 100.0
            }

    @api.constrains('analytic_distribution')
    def _check_analytic_distribution(self):
        """Validar que la distribución analítica sume 100%"""
        for payslip in self:
            if payslip.analytic_distribution:
                total = sum(payslip.analytic_distribution.values())
                if abs(total - 100.0) > 0.01:  # Tolerancia de 0.01%
                    raise ValidationError(
                        _('La distribución analítica debe sumar 100%%. Actual: %s%%') % total
                    )

    def get_effective_analytic_distribution(self):
        """Obtener la distribución analítica efectiva para esta nómina"""
        self.ensure_one()
        
        # 1. Si hay distribución específica en la nómina, usarla
        if self.analytic_distribution:
            return self.analytic_distribution
                
        # 2. Si hay cuenta analítica en el contrato, usarla al 100%
        if self.contract_id and self.contract_id.analytic_account_id:
            return {str(self.contract_id.analytic_account_id.id): 100.0}
            
        # 3. Si hay cuenta analítica directa (campo legacy), usarla
        if hasattr(self, 'analytic_account_id') and self.analytic_account_id:
            return {str(self.analytic_account_id.id): 100.0}
            
        return {}


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    def get_analytic_distribution(self):
        """Obtener distribución analítica para esta línea de nómina"""
        self.ensure_one()
        return self.slip_id.get_effective_analytic_distribution()


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    def get_analytic_distribution(self):
        """Obtener distribución analítica para esta línea de nómina"""
        self.ensure_one()
        return self.slip_id.get_effective_analytic_distribution()
