# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import base64
import io
import zipfile
import logging

_logger = logging.getLogger(__name__)


class HrEppBatch(models.Model):
    _name = 'hr.epp.batch'
    _description = 'Lote de Entregas EPP/Dotacion'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Numero de Lote', required=True, copy=False, readonly=True, default='Nuevo')

    batch_type = fields.Selection([
        ('epp', 'EPP - Elementos de Proteccion Personal'),
        ('dotacion', 'Dotacion - Uniformes'),
        ('medical_exam', 'Examenes Medicos Masivos'),
    ], string='Tipo de Lote', required=True, tracking=True)

    company_id = fields.Many2one('res.company', string='Compania', required=True, default=lambda self: self.env.company)
    batch_date = fields.Date(string='Fecha del Lote', required=True, default=fields.Date.today, tracking=True)
    delivery_planned_date = fields.Date(string='Fecha Entrega Planeada')

    total_employees = fields.Integer(string='Total Empleados', compute='_compute_totals', store=True)
    request_ids = fields.One2many('hr.epp.request', 'batch_id', string='Solicitudes Generadas')
    certificate_ids = fields.One2many('hr.medical.certificate', 'batch_id', string='Certificados Medicos')

    use_stock_location = fields.Boolean(string='Usar Control de Inventario', default=False)
    default_location_id = fields.Many2one('stock.location', string='Bodega por Defecto', domain="[('usage', '=', 'internal')]")
    allow_employee_location = fields.Boolean(string='Permitir Bodega por Empleado', default=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('in_progress', 'En Proceso'),
        ('delivered', 'Entregado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', required=True, tracking=True)

    requests_draft = fields.Integer(string='Borradores', compute='_compute_statistics', store=True)
    requests_approved = fields.Integer(string='Aprobadas', compute='_compute_statistics', store=True)
    requests_delivered = fields.Integer(string='Entregadas', compute='_compute_statistics', store=True)
    progress_percentage = fields.Float(string='% Progreso', compute='_compute_statistics', store=True)
    notes = fields.Text(string='Notas')

    @api.depends('request_ids', 'certificate_ids')
    def _compute_totals(self):
        for batch in self:
            if batch.batch_type in ('epp', 'dotacion'):
                batch.total_employees = len(batch.request_ids)
            else:
                batch.total_employees = len(batch.certificate_ids)

    @api.depends('request_ids.state', 'certificate_ids.state')
    def _compute_statistics(self):
        for batch in self:
            if batch.batch_type in ('epp', 'dotacion'):
                all_requests = batch.request_ids
                batch.requests_draft = len(all_requests.filtered(lambda r: r.state == 'draft'))
                batch.requests_approved = len(all_requests.filtered(lambda r: r.state in ('approved', 'picking')))
                batch.requests_delivered = len(all_requests.filtered(lambda r: r.state == 'delivered'))
                total = len(all_requests)
                batch.progress_percentage = (batch.requests_delivered / total * 100) if total else 0
            else:
                all_certs = batch.certificate_ids
                batch.requests_draft = len(all_certs.filtered(lambda c: c.state == 'scheduled'))
                batch.requests_approved = len(all_certs.filtered(lambda c: c.state == 'in_process'))
                batch.requests_delivered = len(all_certs.filtered(lambda c: c.state == 'valid'))
                total = len(all_certs)
                batch.progress_percentage = (batch.requests_delivered / total * 100) if total else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                batch_type = vals.get('batch_type')
                if batch_type == 'epp':
                    vals['name'] = self.env['ir.sequence'].next_by_code('hr.epp.batch') or 'BATCH-EPP'
                elif batch_type == 'dotacion':
                    vals['name'] = self.env['ir.sequence'].next_by_code('hr.dotacion.batch') or 'BATCH-DOT'
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('hr.medical.batch') or 'BATCH-MED'
        return super().create(vals_list)

    def action_confirm(self):
        self.ensure_one()
        if not self.request_ids and not self.certificate_ids:
            raise UserError(_('Debe generar solicitudes/certificados primero'))
        self.state = 'confirmed'

    def action_start(self):
        self.ensure_one()
        if self.batch_type in ('epp', 'dotacion'):
            for request in self.request_ids.filtered(lambda r: r.state == 'draft'):
                request.action_approve()
        self.state = 'in_progress'

    def action_deliver_all(self):
        self.ensure_one()
        if self.batch_type in ('epp', 'dotacion'):
            for request in self.request_ids.filtered(lambda r: r.state != 'delivered'):
                request.action_deliver()
        self.state = 'delivered'

    def action_cancel(self):
        self.ensure_one()
        for request in self.request_ids.filtered(lambda r: r.state not in ('delivered', 'cancelled')):
            request.action_cancel()
        self.state = 'cancelled'

    def action_create_batch_stock_moves(self):
        self.ensure_one()
        if not self.use_stock_location:
            raise UserError(_('El control de inventario no esta activado'))
        if self.batch_type not in ('epp', 'dotacion'):
            raise UserError(_('Solo aplica para EPP y Dotacion'))

        moves_grouped = defaultdict(lambda: {'quantity': 0, 'location_id': None, 'product_id': None, 'product_name': '', 'uom_id': None, 'request_ids': []})

        for request in self.request_ids.filtered(lambda r: r.state == 'approved'):
            location_id = self._get_request_location(request)
            if not location_id:
                continue
            for line in request.line_ids:
                if not line.product_id:
                    continue
                key = (line.product_id.id, location_id.id)
                moves_grouped[key]['quantity'] += line.quantity
                moves_grouped[key]['location_id'] = location_id
                moves_grouped[key]['product_id'] = line.product_id
                moves_grouped[key]['product_name'] = line.name
                moves_grouped[key]['uom_id'] = line.product_id.uom_id
                moves_grouped[key]['request_ids'].append(request.id)

        if not moves_grouped:
            raise UserError(_('No hay productos para crear movimientos'))

        location_dest_id = self.env.ref('stock.stock_location_customers').id
        created_moves = []

        for (product_id, location_id), data in moves_grouped.items():
            move = self.env['stock.move'].create({
                'name': f"{self.name} - {data['product_name']}",
                'product_id': data['product_id'].id,
                'product_uom_qty': data['quantity'],
                'product_uom': data['uom_id'].id,
                'location_id': location_id,
                'location_dest_id': location_dest_id,
                'origin': self.name,
                'company_id': self.company_id.id,
                'state': 'draft',
            })
            move._action_confirm()
            move._action_assign()
            created_moves.append(move.id)

            for req_id in set(data['request_ids']):
                request = self.env['hr.epp.request'].browse(req_id)
                request.stock_move_ids = [(4, move.id)]
                request.state = 'picking'

        self.state = 'in_progress'
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': _('Movimientos Creados'), 'message': _('Se crearon %d movimientos') % len(created_moves), 'type': 'success'}}

    def _get_request_location(self, request):
        if request.employee_location_id and self.allow_employee_location:
            return request.employee_location_id
        elif self.default_location_id:
            return self.default_location_id
        elif request.configuration_id and request.configuration_id.location_id:
            return request.configuration_id.location_id
        return False

    def action_generate_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generar Solicitudes/Examenes'),
            'res_model': 'wizard.epp.batch.generate',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_batch_id': self.id, 'default_batch_type': self.batch_type}
        }

    def action_print_all(self):
        self.ensure_one()
        if self.batch_type in ('epp', 'dotacion'):
            return self.env.ref('lavish_hr_employee.action_report_epp_delivery').report_action(self.request_ids)
        else:
            return self.env.ref('lavish_hr_employee.action_report_medical_certificate').report_action(self.certificate_ids)

    def action_download_all_zip(self):
        self.ensure_one()
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            if self.batch_type in ('epp', 'dotacion'):
                report = self.env.ref('lavish_hr_employee.action_report_epp_delivery')
                for request in self.request_ids:
                    pdf_content, _ = report._render_qweb_pdf(request.ids)
                    filename = f"{request.name}_{request.employee_id.name}.pdf".replace('/', '_').replace(' ', '_')
                    zip_file.writestr(filename, pdf_content)
            else:
                report = self.env.ref('lavish_hr_employee.action_report_medical_certificate')
                for cert in self.certificate_ids:
                    pdf_content, _ = report._render_qweb_pdf(cert.ids)
                    filename = f"{cert.name}_{cert.employee_id.name}.pdf".replace('/', '_').replace(' ', '_')
                    zip_file.writestr(filename, pdf_content)

        zip_buffer.seek(0)
        zip_data = base64.b64encode(zip_buffer.read())

        attachment = self.env['ir.attachment'].create({
            'name': f'{self.name}_Documentos.zip',
            'type': 'binary',
            'datas': zip_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/zip'
        })

        return {'type': 'ir.actions.act_url', 'url': f'/web/content/{attachment.id}?download=true', 'target': 'self'}

    def action_send_emails(self):
        self.ensure_one()
        sent_count = 0

        if self.batch_type in ('epp', 'dotacion'):
            template = self.env.ref('lavish_hr_employee.email_template_epp_delivery', False)
            if not template:
                raise UserError(_('No se encontro plantilla de correo para EPP'))
            for request in self.request_ids:
                if request.employee_id.work_email:
                    template.send_mail(request.id, force_send=False)
                    sent_count += 1
        else:
            template = self.env.ref('lavish_hr_employee.email_template_medical_certificate', False)
            if not template:
                raise UserError(_('No se encontro plantilla para certificados'))
            for cert in self.certificate_ids:
                if cert.employee_id.work_email:
                    template.send_mail(cert.id, force_send=False)
                    sent_count += 1

        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': _('Correos Enviados'), 'message': _('Se enviaron %d correos') % sent_count, 'type': 'success'}}
