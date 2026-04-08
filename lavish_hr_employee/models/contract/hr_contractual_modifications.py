# -*- coding: utf-8 -*-
"""
Modelo hr.contractual.modifications - Modificaciones contractuales y prorrogas.
"""
from odoo import models, fields, api, _


class hr_contractual_modifications(models.Model):
    _name = 'hr.contractual.modifications'
    _description = 'Modificaciones contractuales'

    contract_id = fields.Many2one('hr.contract', 'Contrato', required=True, ondelete='cascade', index=True, auto_join=True)
    date = fields.Date('Fecha', required=True)
    description = fields.Char('Descripción de modificacion contractual', required=True)
    attached = fields.Many2one('documents.document', string='Adjunto')
    prorroga = fields.Boolean(string='Prórroga')
    wage = fields.Float('Salario basico', help='Seguimento de los cambios en el salario basico')
    sequence = fields.Integer('Numero de Prórroga')
    date_from = fields.Date('Fecha de Inicio Prórroga')
    date_to = fields.Date('Fecha de Fin Prórroga')

    @api.onchange('wage')
    def _change_wage(self):
        for line in self:
            if line.wage != 0:
                line.contract_id.change_wage_ids.create({
                    'wage': line.wage,
                    'date_start': self.date_from,
                    'contract_id': line.contract_id.id,
                })
                line.contract_id.change_wage()
