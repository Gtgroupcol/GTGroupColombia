# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class WizardEppBatchGenerate(models.TransientModel):
    _name = 'wizard.epp.batch.generate'
    _description = 'Wizard Generar Solicitudes/Examenes'

    batch_id = fields.Many2one('hr.epp.batch', string='Lote', required=True, ondelete='cascade')
    batch_type = fields.Selection(related='batch_id.batch_type', readonly=True)
    company_id = fields.Many2one(related='batch_id.company_id', readonly=True)

    selection_mode = fields.Selection([
        ('all', 'Todos los Empleados'),
        ('department', 'Por Departamento'),
        ('job', 'Por Puesto de Trabajo'),
        ('manual', 'Seleccion Manual'),
        ('filters', 'Filtros Combinados'),
    ], string='Modo de Seleccion', default='all', required=True)

    department_ids = fields.Many2many('hr.department', 'wizard_epp_batch_department_rel', 'wizard_id', 'department_id', string='Departamentos')
    job_ids = fields.Many2many('hr.job', 'wizard_epp_batch_job_rel', 'wizard_id', 'job_id', string='Puestos de Trabajo')
    employee_type = fields.Selection([('employee', 'Empleado'), ('contractor', 'Contratista'), ('intern', 'Aprendiz')], string='Tipo de Empleado')
    employee_ids = fields.Many2many('hr.employee', 'wizard_epp_batch_employee_rel', 'wizard_id', 'employee_id', string='Empleados Seleccionados')

    config_id = fields.Many2one('hr.epp.configuration', string='Configuracion a Aplicar')
    medical_exam_type = fields.Selection([
        ('ingress', 'Examen de Ingreso'),
        ('periodic', 'Examen Periodico'),
        ('retirement', 'Examen de Retiro'),
        ('occupational', 'Ocupacional'),
    ], string='Tipo de Examen')
    medical_provider_id = fields.Many2one('hr.medical.provider', string='Proveedor Medico')
    certificate_validity_months = fields.Integer(string='Vigencia (meses)', default=12)

    employee_count = fields.Integer(string='Empleados Encontrados', compute='_compute_employee_preview')
    employee_preview_ids = fields.Many2many('hr.employee', 'wizard_epp_batch_preview_rel', 'wizard_id', 'employee_id', string='Preview', compute='_compute_employee_preview')

    @api.depends('selection_mode', 'department_ids', 'job_ids', 'employee_type', 'employee_ids')
    def _compute_employee_preview(self):
        for wizard in self:
            employees = wizard._get_filtered_employees()
            wizard.employee_preview_ids = employees
            wizard.employee_count = len(employees)

    def _get_filtered_employees(self):
        self.ensure_one()
        domain = [('company_id', '=', self.company_id.id), ('active', '=', True)]

        if self.selection_mode == 'department' and self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        elif self.selection_mode == 'job' and self.job_ids:
            domain.append(('job_id', 'in', self.job_ids.ids))
        elif self.selection_mode == 'manual' and self.employee_ids:
            domain.append(('id', 'in', self.employee_ids.ids))
        elif self.selection_mode == 'filters':
            if self.department_ids:
                domain.append(('department_id', 'in', self.department_ids.ids))
            if self.job_ids:
                domain.append(('job_id', 'in', self.job_ids.ids))
            if self.employee_type:
                domain.append(('employee_type', '=', self.employee_type))

        return self.env['hr.employee'].search(domain)

    def action_generate(self):
        self.ensure_one()
        employees = self._get_filtered_employees()
        if not employees:
            raise UserError(_('No se encontraron empleados con los filtros aplicados'))

        if self.batch_type in ('epp', 'dotacion'):
            generated_count = self._generate_epp_requests(employees)
        else:
            generated_count = self._generate_medical_certificates(employees)

        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': _('Generacion Exitosa'), 'message': _('Se generaron %d registros') % generated_count, 'type': 'success', 'next': {'type': 'ir.actions.act_window_close'}}}

    def _generate_epp_requests(self, employees):
        self.ensure_one()
        generated = 0

        for employee in employees:
            existing = self.env['hr.epp.request'].search([('employee_id', '=', employee.id), ('batch_id', '=', self.batch_id.id)], limit=1)
            if existing:
                continue

            request = self.env['hr.epp.request'].create({
                'employee_id': employee.id,
                'type': self.batch_type,
                'batch_id': self.batch_id.id,
                'configuration_id': self.config_id.id if self.config_id else False,
                'state': 'draft',
            })

            if self.config_id:
                for kit_line in self.config_id.kit_line_ids:
                    size = self._get_employee_size(employee, kit_line.item_type_id)
                    self.env['hr.epp.request.line'].create({
                        'request_id': request.id,
                        'item_type_id': kit_line.item_type_id.id if kit_line.item_type_id else False,
                        'product_id': kit_line.product_id.id if kit_line.product_id else False,
                        'name': kit_line.name,
                        'quantity': kit_line.quantity,
                        'size': size,
                    })
            generated += 1
        return generated

    def _generate_medical_certificates(self, employees):
        self.ensure_one()
        generated = 0
        expiry_date = fields.Date.today() + relativedelta(months=self.certificate_validity_months)

        for employee in employees:
            existing = self.env['hr.medical.certificate'].search([('employee_id', '=', employee.id), ('batch_id', '=', self.batch_id.id)], limit=1)
            if existing:
                continue

            self.env['hr.medical.certificate'].create({
                'employee_id': employee.id,
                'batch_id': self.batch_id.id,
                'provider_id': self.medical_provider_id.id if self.medical_provider_id else False,
                'certificate_type': self.medical_exam_type or 'occupational',
                'issue_date': fields.Date.today(),
                'expiry_date': expiry_date,
            })
            generated += 1
        return generated

    def _get_employee_size(self, employee, item_type_id):
        """Obtiene la talla del empleado según el tipo de item."""
        if not item_type_id:
            return False

        size_type = item_type_id.size_type
        if size_type == 'clothing':
            return employee.shirt_size or 'M'
        elif size_type == 'shoes':
            return employee.shoe_size or '40'
        elif size_type == 'gloves':
            return employee.gloves_size if hasattr(employee, 'gloves_size') else '8'
        elif size_type == 'helmet':
            return employee.helmet_size if hasattr(employee, 'helmet_size') else 'M'
        return False
