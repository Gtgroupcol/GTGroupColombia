# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class HrMedicalCertificate(models.Model):
    _name = 'hr.medical.certificate'
    _description = 'Certificado Medico'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date desc'

    name = fields.Char('Referencia', required=True, copy=False, default='New')
    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True, tracking=True)
    batch_id = fields.Many2one('hr.epp.batch', string='Lote', index=True)

    provider_id = fields.Many2one('hr.medical.provider', 'Proveedor', required=True)
    provider_type = fields.Selection(related='provider_id.provider_type')

    certificate_type_id = fields.Many2one(
        'hr.medical.certificate.type',
        string='Tipo',
        required=True,
        tracking=True,
        domain="[('parent_id', '!=', False)]",
        help="Tipo de certificado médico"
    )
    certificate_type_category_id = fields.Many2one(
        related='certificate_type_id.parent_id',
        string='Categoría',
        store=True
    )

    template_id = fields.Many2one('hr.medical.template', 'Plantilla Usada')
    configuration_id = fields.Many2one('hr.epp.configuration', string='Configuracion')

    schedule_date = fields.Datetime('Fecha Programada')
    exam_date = fields.Date('Fecha del Examen')
    issue_date = fields.Date('Fecha de Emision', required=True, default=fields.Date.today)
    expiry_date = fields.Date('Fecha de Vencimiento', required=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('scheduled', 'Programado'),
        ('in_process', 'En Proceso'),
        ('valid', 'Vigente'),
        ('expiring', 'Por Vencer'),
        ('expired', 'Vencido'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)

    result = fields.Selection([
        ('apt', 'Apto'),
        ('apt_restrictions', 'Apto con Restricciones'),
        ('not_apt', 'No Apto'),
        ('pending', 'Pendiente')
    ], string='Resultado', default='pending', tracking=True)

    restrictions = fields.Text('Restricciones')
    recommendations = fields.Text('Recomendaciones')
    observations = fields.Text('Observaciones')

    attachment_ids = fields.Many2many('ir.attachment', 'hr_medical_certificate_ir_attachment_rel', 'hr_medical_certificate_id', 'ir_attachment_id', string='Adjuntos')
    result_line_ids = fields.One2many('hr.medical.certificate.result', 'certificate_id', 'Resultados Detallados')
    service_ids = fields.Many2many('hr.medical.service', 'hr_medical_certificate_service_rel', 'certificate_id', 'service_id', string='Servicios Realizados')

    purchase_order_id = fields.Many2one('purchase.order', 'Orden de Compra')
    days_to_alert = fields.Integer('Dias para Alerta', default=30)
    alert_sent = fields.Boolean('Alerta Enviada')

    location = fields.Char('Ubicacion del Examen')
    doctor_name = fields.Char('Nombre del Doctor')
    cost = fields.Monetary('Costo', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    renewal_certificate_id = fields.Many2one('hr.medical.certificate', string='Renovacion de')
    renewed_by_certificate_id = fields.Many2one('hr.medical.certificate', string='Renovado por')
    is_renewal = fields.Boolean('Es Renovacion', compute='_compute_is_renewal', store=True)

    days_to_expiry = fields.Integer('Dias para Vencer', compute='_compute_days_to_expiry', store=True)
    expiry_status = fields.Selection([
        ('valid', 'Vigente'),
        ('warning', 'Por Vencer'),
        ('critical', 'Critico'),
        ('expired', 'Vencido'),
    ], string='Estado Vencimiento', compute='_compute_expiry_status', store=True)
    next_exam_date = fields.Date('Proximo Examen', compute='_compute_next_exam_date', store=True)

    reminder_30_sent = fields.Boolean('Recordatorio 30 dias')
    reminder_15_sent = fields.Boolean('Recordatorio 15 dias')
    reminder_7_sent = fields.Boolean('Recordatorio 7 dias')
    reminder_expired_sent = fields.Boolean('Notificacion vencido')
    responsible_user_id = fields.Many2one('res.users', string='Responsable')
    auto_renew = fields.Boolean('Renovacion Automatica', related='configuration_id.auto_renew', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.medical.certificate') or 'MED/001'
        return super().create(vals_list)

    @api.depends('renewal_certificate_id')
    def _compute_is_renewal(self):
        for cert in self:
            cert.is_renewal = bool(cert.renewal_certificate_id)

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        today = fields.Date.today()
        for cert in self:
            cert.days_to_expiry = (cert.expiry_date - today).days if cert.expiry_date else 0

    @api.depends('days_to_expiry', 'state')
    def _compute_expiry_status(self):
        for cert in self:
            if cert.state == 'expired' or cert.days_to_expiry < 0:
                cert.expiry_status = 'expired'
            elif cert.days_to_expiry <= 7:
                cert.expiry_status = 'critical'
            elif cert.days_to_expiry <= 30:
                cert.expiry_status = 'warning'
            else:
                cert.expiry_status = 'valid'

    @api.depends('expiry_date')
    def _compute_next_exam_date(self):
        for cert in self:
            cert.next_exam_date = cert.expiry_date - timedelta(days=7) if cert.expiry_date else False

    def action_schedule(self):
        self.ensure_one()
        self.state = 'scheduled'

    def action_start(self):
        self.ensure_one()
        self.state = 'in_process'

    def action_validate(self):
        self.ensure_one()
        if self.result == 'pending':
            raise UserError(_('Debe ingresar el resultado del examen'))
        self.state = 'valid'

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'

    def action_print_certificate(self):
        return self.env.ref('lavish_hr_employee.action_report_medical_certificate').report_action(self)

    def action_renew(self):
        self.ensure_one()
        if self.renewed_by_certificate_id:
            raise UserError(_('Este certificado ya fue renovado: %s') % self.renewed_by_certificate_id.name)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Renovar Certificado Medico'),
            'res_model': 'wizard.medical.certificate.renew',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_original_certificate_id': self.id,
                'default_employee_id': self.employee_id.id,
                'default_provider_id': self.provider_id.id,
                'default_certificate_type_id': self.certificate_type_id.id,
            }
        }

    @api.model
    def cron_update_certificate_states(self):
        """Cron: Actualizar estados de certificados y enviar recordatorios"""
        today = fields.Date.today()

        # Actualizar certificados expirados
        expired_certs = self.search([
            ('state', 'in', ['valid', 'expiring']),
            ('expiry_date', '<', today)
        ])
        for cert in expired_certs:
            cert.state = 'expired'
            if not cert.reminder_expired_sent:
                cert._send_reminder('expired')
                cert.reminder_expired_sent = True
                if cert.auto_renew:
                    cert._auto_renew_certificate()

        # Actualizar certificados por vencer (30 días o menos)
        expiring_certs = self.search([
            ('state', '=', 'valid'),
            ('expiry_date', '<=', today + timedelta(days=30)),
            ('expiry_date', '>=', today)
        ])
        expiring_certs.write({'state': 'expiring'})

        # Enviar recordatorios
        certs_to_remind = self.search([
            ('state', 'in', ['valid', 'expiring']),
            ('expiry_date', '!=', False)
        ])
        for cert in certs_to_remind:
            days_left = (cert.expiry_date - today).days
            cert._check_and_send_reminder(days_left)

    def _check_and_send_reminder(self, days_left):
        """Verificar y enviar recordatorio según días restantes"""
        self.ensure_one()
        if days_left == 30 and not self.reminder_30_sent:
            self._send_reminder('30_days')
            self.reminder_30_sent = True
        elif days_left == 15 and not self.reminder_15_sent:
            self._send_reminder('15_days')
            self.reminder_15_sent = True
        elif days_left == 7 and not self.reminder_7_sent:
            self._send_reminder('7_days')
            self.reminder_7_sent = True
            self._create_urgent_activity()

    def _send_reminder(self, reminder_type):
        """Enviar recordatorio de vencimiento según tipo de certificado"""
        self.ensure_one()
        cert_type_name = self.certificate_type_id.name if self.certificate_type_id else _('Certificado Médico')

        messages = {
            '30_days': _('El certificado de %(type)s vence en 30 días. Empleado: %(employee)s'),
            '15_days': _('ALERTA: El certificado de %(type)s vence en 15 días. Empleado: %(employee)s'),
            '7_days': _('URGENTE: El certificado de %(type)s vence en 7 días. Empleado: %(employee)s'),
            'expired': _('VENCIDO: El certificado de %(type)s ha expirado. Empleado: %(employee)s'),
        }

        message_template = messages.get(reminder_type, '')
        if message_template:
            message = message_template % {
                'type': cert_type_name,
                'employee': self.employee_id.name,
            }
            self.message_post(body=message, message_type='notification')

    def _create_urgent_activity(self):
        self.ensure_one()
        user_id = self.responsible_user_id or self.env.user
        if self.employee_id.parent_id and self.employee_id.parent_id.user_id:
            user_id = self.employee_id.parent_id.user_id

        cert_type_name = self.certificate_type_id.name if self.certificate_type_id else _('Certificado Médico')

        self.env['mail.activity'].create({
            'summary': _('URGENTE: Renovar %s') % cert_type_name,
            'note': _('El certificado de %(type)s del empleado %(employee)s vence en 7 días. Ref: %(ref)s') % {
                'type': cert_type_name,
                'employee': self.employee_id.name,
                'ref': self.name,
            },
            'date_deadline': fields.Date.today() + timedelta(days=7),
            'user_id': user_id.id,
            'res_model_id': self.env.ref('lavish_hr_employee.model_hr_medical_certificate').id,
            'res_id': self.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
        })

    def _auto_renew_certificate(self):
        self.ensure_one()
        if self.renewed_by_certificate_id:
            return

        new_issue_date = self.expiry_date + timedelta(days=1)
        validity_months = self.template_id.validity_months if self.template_id else 12
        new_expiry_date = new_issue_date + relativedelta(months=validity_months)

        new_cert = self.create({
            'employee_id': self.employee_id.id,
            'provider_id': self.provider_id.id,
            'template_id': self.template_id.id if self.template_id else False,
            'certificate_type_id': self.certificate_type_id.id,
            'configuration_id': self.configuration_id.id if self.configuration_id else False,
            'issue_date': new_issue_date,
            'expiry_date': new_expiry_date,
            'renewal_certificate_id': self.id,
            'state': 'scheduled',
            'result': 'pending',
            'responsible_user_id': self.responsible_user_id.id if self.responsible_user_id else False,
        })

        self.renewed_by_certificate_id = new_cert.id
        self.message_post(body=_('Certificado renovado automaticamente: %s') % new_cert.name)
        return new_cert


class HrMedicalCertificateResult(models.Model):
    _name = 'hr.medical.certificate.result'
    _description = 'Resultado de Certificado Medico'

    certificate_id = fields.Many2one('hr.medical.certificate', 'Certificado', ondelete='cascade')
    service_id = fields.Many2one('hr.medical.service', 'Servicio/Examen')
    name = fields.Char('Examen', required=True)
    result = fields.Text('Resultado')
    value = fields.Char('Valor')
    unit = fields.Char('Unidad')
    reference_range = fields.Char('Rango de Referencia')
    status = fields.Selection([('normal', 'Normal'), ('abnormal', 'Anormal'), ('critical', 'Critico')], default='normal')
    observations = fields.Text('Observaciones')
    attachment_ids = fields.Many2many('ir.attachment', 'hr_medical_certificate_result_ir_attachment_rel', 'hr_medical_certificate_result_id', 'ir_attachment_id', string='Adjuntos')
