# -*- coding: utf-8 -*-
"""
Modelo hr.labor.certificate.history - Historial de certificados laborales.
Con funcionalidad de terceros, estados y envío por correo.
"""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64


class hr_labor_certificate_history(models.Model):
    _name = 'hr.labor.certificate.history'
    _description = 'Histórico de certificados laborales generados'
    _order = 'date_generation desc, sequence desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Campos básicos
    contract_id = fields.Many2one(
        'hr.contract',
        string='Contrato',
        required=True,
        ondelete='cascade',
        tracking=True)
    sequence = fields.Char(
        string='Secuencia',
        default='/',
        readonly=True,
        copy=False)
    date_generation = fields.Date(
        string='Fecha generación',
        required=True,
        default=fields.Date.today,
        tracking=True)

    # Campos relacionados
    employee_id = fields.Many2one(
        related='contract_id.employee_id',
        string='Empleado',
        store=True,
        readonly=True)
    company_id = fields.Many2one(
        related='contract_id.company_id',
        string='Compañía',
        store=True,
        readonly=True)

    # Tercero/Destinatario (NUEVO)
    info_to = fields.Char(
        string='Dirigido a',
        help='Nombre del solicitante o texto libre')
    partner_id = fields.Many2one(
        'res.partner',
        string='Tercero/Destinatario',
        help='Seleccione un contacto como destinatario del certificado (opcional)',
        tracking=True)

    # Estado del certificado (NUEVO)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('generated', 'Generado'),
        ('sent', 'Enviado'),
    ], string='Estado', default='draft', tracking=True, copy=False)

    # Archivos
    pdf = fields.Binary(string='Certificado PDF')
    pdf_name = fields.Char(string='Nombre archivo PDF')

    _sql_constraints = [
        ('labor_certificate_history_uniq', 'unique(contract_id, sequence)',
         'Ya existe un certificado con esta secuencia, por favor verificar.')]

    @api.depends('sequence', 'contract_id', 'contract_id.name')
    def _compute_display_name(self):
        for record in self:
            contract_name = record.contract_id.name if record.contract_id else ''
            record.display_name = "Certificado {} de {}".format(record.sequence, contract_name)

    def get_hr_labor_certificate_template(self):
        """Obtiene la plantilla de certificado laboral para la compañía del empleado."""
        self.ensure_one()
        obj = self.env['hr.labor.certificate.template'].search([
            ('company_id', '=', self.contract_id.employee_id.company_id.id)
        ], limit=1)
        if not obj:
            raise ValidationError(_(
                'No tiene configurada plantilla de certificado laboral para la compañía %s. '
                'Por favor verifique en Configuración > Plantilla Certificado Laboral.'
            ) % self.contract_id.employee_id.company_id.name)
        return obj

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence', '/') == '/':
                vals['sequence'] = self.env['ir.sequence'].next_by_code(
                    'hr.labor.certificate.history.seq') or '/'
        return super().create(vals_list)

    def generate_report(self):
        """Genera el PDF del certificado laboral."""
        self.ensure_one()

        # Validar que exista plantilla
        self.get_hr_labor_certificate_template()

        datas = {
            'ids': self.contract_id.ids,
            'model': 'hr.labor.certificate.history'
        }

        report_name = 'lavish_hr_employee.report_certificacion_laboral'

        # Generar PDF
        pdf_content = self.env['ir.actions.report']._render_qweb_pdf(
            "lavish_hr_employee.report_certificacion_laboral_action",
            self.id
        )[0]
        pdf = base64.b64encode(pdf_content)

        # Guardar PDF
        self.write({
            'pdf': pdf,
            'pdf_name': f'Certificado - {self.contract_id.name} - {self.sequence}.pdf',
            'state': 'generated',
        })

        # Guardar en documentos si está configurado
        self._save_to_documents(pdf)

        return {
            'type': 'ir.actions.report',
            'report_name': report_name,
            'report_type': 'qweb-pdf',
            'datas': datas,
        }

    def _save_to_documents(self, pdf_content):
        """Guarda el certificado en el módulo de documentos."""
        self.ensure_one()

        if not self.contract_id.employee_id.work_contact_id:
            return

        name = f'Certificado - {self.contract_id.name} - {self.sequence}.pdf'

        # Crear adjunto
        obj_attachment = self.env['ir.attachment'].create({
            'name': name,
            'store_fname': name,
            'res_name': name,
            'type': 'binary',
            'res_model': 'res.partner',
            'res_id': self.contract_id.employee_id.work_contact_id.id,
            'datas': pdf_content,
        })

        # Asociar adjunto a documento de Odoo si está configurado
        if hasattr(self.env.user.company_id, 'documents_hr_folder') and \
           self.env.user.company_id.documents_hr_folder:
            cert = self.env.user.company_id.validated_certificate
            tag_ids = [int(cert)] if cert and str(cert).isdigit() else []
            doc_vals = {
                'name': name,
                'owner_id': self.contract_id.employee_id.user_id.id if self.contract_id.employee_id.user_id else self.env.user.id,
                'partner_id': self.contract_id.employee_id.work_contact_id.id,
                'folder_id': self.env.user.company_id.documents_hr_folder.id,
                'tag_ids': tag_ids,
                'type': 'binary',
                'attachment_id': obj_attachment.id
            }
            self.env['documents.document'].sudo().create(doc_vals)

    def action_send_by_email(self):
        """Envía el certificado laboral por correo electrónico al empleado."""
        self.ensure_one()

        if not self.pdf:
            raise UserError(_('Debe generar el certificado antes de enviarlo.'))

        # Obtener email del empleado
        email_to = self.employee_id.work_email or self.employee_id.private_email
        if not email_to:
            raise UserError(_(
                'El empleado %s no tiene configurado un correo electrónico.'
            ) % self.employee_id.name)

        # Buscar template de correo
        template = self.env.ref(
            'lavish_hr_employee.email_template_labor_certificate',
            raise_if_not_found=False
        )

        if template:
            # Usar template de correo
            template.send_mail(self.id, force_send=True)
        else:
            # Envío manual si no hay template
            self._send_email_manual(email_to)

        self.write({'state': 'sent'})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Certificado Enviado'),
                'message': _('El certificado ha sido enviado a %s') % email_to,
                'type': 'success',
                'sticky': False,
            }
        }

    def _send_email_manual(self, email_to):
        """Envía el correo manualmente sin usar template."""
        self.ensure_one()

        attachment = self.env['ir.attachment'].create({
            'name': self.pdf_name,
            'type': 'binary',
            'datas': self.pdf,
            'res_model': self._name,
            'res_id': self.id,
        })

        mail_values = {
            'subject': _('Certificado Laboral - %s') % self.employee_id.name,
            'body_html': _('''
                <p>Estimado(a) <strong>%s</strong>,</p>
                <p>Adjunto encontrará su certificado laboral solicitado.</p>
                <p>Certificado No. <strong>%s</strong></p>
                <p>Fecha de generación: <strong>%s</strong></p>
                <br/>
                <p>Cordialmente,</p>
                <p><strong>%s</strong></p>
            ''') % (
                self.employee_id.name,
                self.sequence,
                self.date_generation,
                self.company_id.name
            ),
            'email_from': self.company_id.email or self.env.user.email,
            'email_to': email_to,
            'attachment_ids': [(4, attachment.id)],
            'auto_delete': True,
        }

        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()

    def action_print_pdf(self):
        """Imprime el PDF del certificado."""
        self.ensure_one()

        if not self.pdf:
            # Generar primero si no existe
            self.generate_report()

        return {
            'type': 'ir.actions.report',
            'report_name': 'lavish_hr_employee.report_certificacion_laboral',
            'report_type': 'qweb-pdf',
            'datas': {
                'ids': [self.id],
                'model': 'hr.labor.certificate.history'
            },
        }

    def action_set_draft(self):
        """Regresa el certificado a estado borrador."""
        self.write({'state': 'draft'})

    def action_regenerate(self):
        """Regenera el certificado PDF."""
        self.ensure_one()
        self.write({
            'pdf': False,
            'pdf_name': False,
            'state': 'draft',
        })
        return self.generate_report()

    # ============================================
    # Métodos para generación masiva
    # ============================================

    @api.model
    def generate_certificates_batch(self, contract_ids, info_to=False, partner_id=False, date_generation=False):
        """
        Genera certificados laborales de forma masiva.

        Args:
            contract_ids: Lista de IDs de contratos
            info_to: Texto 'Dirigido a'
            partner_id: ID del tercero/destinatario
            date_generation: Fecha de generación

        Returns:
            recordset: Registros de certificados creados
        """
        if not contract_ids:
            raise UserError(_('Debe seleccionar al menos un contrato.'))

        contracts = self.env['hr.contract'].browse(contract_ids)
        date_gen = date_generation or fields.Date.today()
        certificates = self.env['hr.labor.certificate.history']

        for contract in contracts:
            cert_vals = {
                'contract_id': contract.id,
                'date_generation': date_gen,
                'info_to': info_to or '',
                'partner_id': partner_id,
                'state': 'draft',
            }
            certificates += self.create(cert_vals)

        return certificates

    def action_generate_batch(self):
        """Genera los PDFs para múltiples certificados."""
        for cert in self:
            cert.generate_report()
        return True

    def action_send_batch(self):
        """Envía múltiples certificados por correo."""
        for cert in self:
            if cert.pdf and cert.state == 'generated':
                try:
                    cert.action_send_by_email()
                except UserError:
                    continue  # Continuar con el siguiente si hay error
        return True

    def action_print_batch(self):
        """Imprime múltiples certificados en un solo PDF."""
        if not self:
            raise UserError(_('No hay certificados seleccionados.'))

        # Asegurar que todos tienen PDF generado
        for cert in self.filtered(lambda c: not c.pdf):
            cert.generate_report()

        return {
            'type': 'ir.actions.report',
            'report_name': 'lavish_hr_employee.report_certificacion_laboral',
            'report_type': 'qweb-pdf',
            'datas': {
                'ids': self.ids,
                'model': 'hr.labor.certificate.history'
            },
        }
