# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import base64
import zipfile
from io import BytesIO
from lxml import etree
import html
import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import unicodedata
import re
_logger = logging.getLogger(__name__)


class HospitalRIPS(models.Model):
    _name = "hospital.rips"
    _description = "Hospital RIPS - Generación de archivos planos"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="N° Radicado", 
        default="/", 
        required=True, 
        readonly=True,
        tracking=True
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('done', 'Procesado'),
        ('cancel', 'Cancelado')
    ], string="Estado", default='draft', readonly=True, tracking=True)
    
    # Fechas
    date_from = fields.Date(
        string="Fecha Inicial", 
        required=True,
        tracking=True
    )
    date_to = fields.Date(
        string="Fecha Final", 
        required=True,
        tracking=True
    )
    ratication_date = fields.Date(
        string="Fecha de Radicación",
        tracking=True
    )
    
    # Referencias principales
    partner_id = fields.Many2one(
        'res.partner', 
        string="Cliente/Aseguradora", 
        required=True,
        domain="[('is_insurance_company', '=', True)]",
        tracking=True
    )
    
    contract_id = fields.Many2one(
        'customer.contract', 
        string='Contrato',
        required=True,
        domain="[('partner_id', '=', partner_id)]",
        help='Contrato con la aseguradora',
        tracking=True
    )
    
    # Configuración
    company_id = fields.Many2one(
        'res.company', 
        string="Compañía", 
        default=lambda self: self.env.company,
        required=True
    )
    
    rips_config_id = fields.Many2one(
        'rips.configuration',
        string='Configuración RIPS',
        required=True,
        default=lambda self: self._get_default_rips_config()
    )
    
    cea_code = fields.Char(
        string="Código Prestador", 
        compute='_compute_cea_code',
        store=True
    )
    
    # Tipo de RIPS
    rips_type = fields.Selection([
        ('regular', 'RIPS Regular'),
        ('capita', 'RIPS Cápita'),
        ('evento', 'RIPS por Evento')
    ], string="Tipo de RIPS", default='regular', required=True)
    
    rips_directo = fields.Boolean(
        string="RIPS Directo", 
        help='Esta opción permite generar Rips sin haber facturado atenciones.'
    )
    
    # Filtros adicionales
    team_id = fields.Many2one(
        'crm.team', 
        string="Equipo de Ventas"
    )
    
    journal_id = fields.Many2one(
        'account.journal', 
        string="Diario de Facturación", 
        domain="[('type', '=', 'sale')]"
    )
    
    invoice_type_filter = fields.Selection([
        ('all', 'Todas'),
        ('insurance', 'Aseguradora'),
        ('copay', 'Copago'),
        ('regular', 'Regular')
    ], string='Filtrar por Tipo', default='insurance')
    
    # Facturas
    invoice_ids = fields.Many2many(
        'account.move', 
        'account_move_hospital_rips_rel', 
        'rips_id', 
        'move_id', 
        string="Facturas",
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('contract_id', '=', contract_id)]"
    )
    
    invoice_count = fields.Integer(
        string="Cantidad de Facturas", 
        compute="_compute_invoice_values"
    )
    
    amount_residual = fields.Float(
        string="Monto Pendiente", 
        compute="_compute_invoice_values"
    )
    
    amount_total = fields.Float(
        string="Monto Total", 
        compute="_compute_invoice_values"
    )
    
    # Archivos generados
    archive_zip = fields.Binary(
        string="Archivo ZIP",
        readonly=True,
        attachment=True
    )
    
    archive_zip_name = fields.Char(
        string="Nombre Archivo ZIP",
        readonly=True
    )
    
    # Información adicional
    observations = fields.Text(
        string='Observaciones',
        readonly=True
    )
    
    errors_detail = fields.Html(
        string='Detalle de Errores',
        readonly=True
    )
    
    # Estadísticas
    patient_count = fields.Integer(
        string="Pacientes", 
        compute="_compute_statistics"
    )
    
    service_count = fields.Integer(
        string="Servicios", 
        compute="_compute_statistics"
    )
    
    tipo_afiliacion = fields.Selection([
        ('contributory', 'Contributivo'), 
        ('subsidized', 'Subsidiado'), 
        ('linked', 'Vinculado')
    ], string="Tipo De Régimen", required=True, default='contributory')
    
    @api.model
    def _get_default_rips_config(self):
        """Obtiene la configuración RIPS por defecto"""
        return self.env['rips.configuration'].search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)
    
    @api.depends('company_id')
    def _compute_cea_code(self):
        """Calcula el código del prestador"""
        for record in self:
            record.cea_code = record.company_id.partner_id.ref or ''
    
    @api.depends('invoice_ids')
    def _compute_invoice_values(self):
        """Calcula valores de facturas"""
        for record in self:
            record.invoice_count = len(record.invoice_ids)
            record.amount_residual = sum(record.invoice_ids.mapped('amount_residual'))
            record.amount_total = sum(record.invoice_ids.mapped('amount_total'))
    
    @api.depends('invoice_ids')
    def _compute_statistics(self):
        """Calcula estadísticas del RIPS"""
        for record in self:
            # Contar pacientes únicos
            patients = set()
            services = 0
            
            for invoice in record.invoice_ids:
                # Paciente del encabezado
                if invoice.patient_id:
                    patients.add(invoice.patient_id.id)
                
                # Pacientes de las líneas
                for line in invoice.invoice_line_ids:
                    if line.patient_id:
                        patients.add(line.patient_id.id)
                    if line.product_id and line.product_id.rips_service_type != 'none':
                        services += 1
            
            record.patient_count = len(patients)
            record.service_count = services
    
    @api.model
    def create(self, vals):
        """Genera secuencia al crear"""
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('hospital.rips') or '/'
        return super().create(vals)
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Limpia el contrato al cambiar de partner"""
        self.contract_id = False
        self.invoice_ids = False
    
    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        """Limpia las facturas al cambiar de contrato"""
        self.invoice_ids = False
    
    def action_generate(self):
        """Busca facturas según los criterios"""
        self.ensure_one()
        
        if not self.contract_id:
            raise UserError(_("Debe seleccionar un contrato"))
        
        # Construir dominio de búsqueda
        domain = [
            ('company_id', '=', self.company_id.id),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
            ('partner_id', '=', self.partner_id.id),
            ('contract_id', '=', self.contract_id.id),  # Filtrar por contrato
            ('rips_generated', '=', False),  # No procesadas en RIPS
        ]
        
        # Filtros adicionales
        if self.team_id:
            domain.append(('team_id', '=', self.team_id.id))
        
        if self.journal_id:
            domain.append(('journal_id', '=', self.journal_id.id))
        
        if self.invoice_type_filter != 'all':
            domain.append(('invoice_type', '=', self.invoice_type_filter))
        
        # Buscar facturas
        invoices = self.env['account.move'].search(domain)
        
        if not invoices:
            raise UserError(_("No se encontraron facturas con los criterios especificados"))
        
        # Actualizar facturas
        self.invoice_ids = [(6, 0, invoices.ids)]
        
        # Mensaje informativo
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Búsqueda Completada'),
                'message': _('Se encontraron %d facturas del contrato %s') % (len(invoices), self.contract_id.name),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_confirm(self):
        """Confirma el RIPS"""
        self.ensure_one()
        if not self.invoice_ids:
            raise UserError(_("No hay facturas para procesar"))
        
        if self.name == '/':
            self.name = self.env['ir.sequence'].next_by_code('hospital.rips') or '/'
        
        self.write({
            'state': 'confirmed',
            'ratication_date': fields.Date.today()
        })
    
    def action_done(self):
        """Marca como procesado y actualiza facturas"""
        self.ensure_one()
        
        # Marcar facturas como procesadas en RIPS
        self.invoice_ids.write({'rips_generated': True})
        
        self.write({'state': 'done'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('RIPS Procesado'),
                'message': _('El RIPS ha sido procesado exitosamente'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_cancel(self):
        """Cancela el RIPS"""
        self.write({'state': 'cancel'})
    
    def action_draft(self):
        """Vuelve a borrador"""
        self.write({'state': 'draft'})
    
    def action_generate_zip(self):
        """Genera los archivos RIPS en formato ZIP"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            raise UserError(_("Solo se pueden generar archivos de RIPS confirmados"))
        
        # Validar datos
        errors = self._validate_rips_data()
        if errors:
            self._format_errors(errors)
            raise UserError(_("Hay errores en los datos. Revise el detalle de errores."))
        
        # Generar archivos
        files = self._generate_rips_files()
        
        # Crear ZIP
        zip_buffer = self._create_zip(files)
        zip_buffer.seek(0)
        
        # Guardar archivo
        self.write({
            'archive_zip': base64.b64encode(zip_buffer.read()),
            'archive_zip_name': f"RIPS_{self.name}.zip",
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Archivo ZIP Generado'),
                'message': _('Los archivos RIPS se generaron correctamente'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_download_zip(self):
        """Descarga el archivo ZIP"""
        self.ensure_one()
        
        if not self.archive_zip:
            raise UserError(_("No hay archivo ZIP generado"))
        
        # Crear attachment
        attachment = self.env['ir.attachment'].create({
            'name': self.archive_zip_name,
            'type': 'binary',
            'datas': self.archive_zip,
            'res_model': self._name,
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def action_view_invoices(self):
        """Ver facturas asociadas"""
        self.ensure_one()
        return {
            'name': _('Facturas RIPS'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': dict(self.env.context, create=False)
        }
    
    def _validate_rips_data(self):
        """Valida los datos antes de generar RIPS"""
        errors = []
        
        # Validar código prestador
        if not self.cea_code or len(self.cea_code) != 12:
            errors.append(f"El código del prestador debe tener 12 dígitos. Actual: {self.cea_code or 'vacío'}")
        
        # Validar contrato
        if not self.contract_id.contract_code:
            errors.append(f"El contrato {self.contract_id.name} no tiene código asignado")
        
        # Validar facturas
        for invoice in self.invoice_ids:
            # Validar paciente
            has_patient = bool(invoice.patient_id or any(line.patient_id for line in invoice.invoice_line_ids))
            if not has_patient:
                errors.append(f"Factura {invoice.name}: No tiene paciente asignado")
                continue
            
            # Validar líneas con servicios
            for line in invoice.invoice_line_ids:
                if line.product_id and line.product_id.rips_service_type != 'none':
                    # Obtener paciente
                    patient = line.patient_id or invoice.patient_id
                    if patient:
                        patient_partner = patient.partner_id if patient._name == 'hms.patient' else patient
                        
                        # Validar datos del paciente
                        if not patient_partner.vat:
                            errors.append(f"Paciente {patient_partner.name}: Sin número de documento")
                        if not patient_partner.birthday:
                            errors.append(f"Paciente {patient_partner.name}: Sin fecha de nacimiento")
                        if not patient_partner.gender:
                            errors.append(f"Paciente {patient_partner.name}: Sin género definido")
                    
                    # Validar autorización si es requerida
                    if self.contract_id.require_authorization and not line.autorizacion:
                        errors.append(f"Factura {invoice.name}, línea {line.product_id.name}: Sin número de autorización")
        
        # Formatear errores
        if errors:
            self.observations = "\n".join(errors)
        
        return errors
    
    def _format_errors(self, errors):
        """Formatea los errores para mostrar"""
        if not errors:
            self.errors_detail = False
            return
        
        html = '<div class="alert alert-danger">'
        html += '<h4><i class="fa fa-exclamation-triangle"/> Errores de Validación</h4>'
        html += '<ul>'
        for error in errors:
            html += f'<li>{error}</li>'
        html += '</ul>'
        html += '</div>'
        
        self.errors_detail = html
    
    @api.model
    def _remove_accents(self, text):
        """Remueve acentos y caracteres especiales"""
        if not text:
            return ''
        
        # Normalizar y remover acentos
        text = unicodedata.normalize('NFD', str(text))
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
        
        # Remover caracteres especiales
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        
        return text.upper()
    
    def _convert_gender(self, gender):
        """Convierte género al formato RIPS"""
        gender_map = {
            'H': 'M',
            'male': 'M',
            'M': 'F', 
            'female': 'F',
            'I': 'I',
            'other': 'I'
        }
        return gender_map.get(gender, 'M')
    
    def _calculate_age(self, birth_date, reference_date):
        """Calcula edad y unidad de medida"""
        if not birth_date:
            return 1, '1'  # Default: 1 año
        
        delta = relativedelta(reference_date, birth_date)
        days = (reference_date - birth_date).days
        
        if days >= 365:
            return delta.years, '1'  # Años
        elif days >= 30:
            return days // 30, '2'  # Meses
        else:
            return days, '3'  # Días
    
    def _generate_rips_files(self):
        """Genera los archivos RIPS según el estándar"""
        files = []
        
        # Diccionarios para almacenar datos
        dic = {
            'US': [[], ""],  # [ids_procesados, contenido]
            'AF': "",
            'AT': "",
            'CT': {'US': 0, 'AF': 0, 'AT': 0}
        }
        
        tipo_afiliacion = {
            'contributory': '1',
            'subsidized': '2',
            'linked': '3'
        }
        
        dic['CT']['AF'] = len(self.invoice_ids)
        
        # Procesar cada factura
        for invoice in self.invoice_ids:
            # Datos AF (Archivo de Facturas)
            dic['AF'] += self._generate_af_line(invoice)
            
            # Procesar líneas de factura
            for line in invoice.invoice_line_ids:
                if not line.product_id or line.product_id.rips_service_type == 'none':
                    continue
                
                # Obtener paciente (de la línea o del encabezado)
                patient = line.patient_id or invoice.patient_id
                if not patient:
                    continue
                
                # Convertir a partner si es necesario
                if patient._name == 'hms.patient':
                    patient_partner = patient.partner_id
                else:
                    patient_partner = patient
                
                # Generar línea US si el paciente no ha sido procesado
                if patient.id not in dic['US'][0]:
                    dic['US'][1] += self._generate_us_line(patient_partner, invoice)
                    dic['US'][0].append(patient.id)
                    dic['CT']['US'] += 1
                
                # Generar línea AT
                dic['AT'] += self._generate_at_line(line, invoice, patient_partner)
                dic['CT']['AT'] += 1
        
        # Generar archivo CT (Control)
        type_ct = ""
        for k, v in dic['CT'].items():
            type_ct += "%s,%s,%s,%s\n" % (
                self.cea_code,
                self.ratication_date.strftime('%d/%m/%Y') if self.ratication_date else '',
                "%s%s" % (k, self.name),
                v
            )
        
        # Crear archivos
        code = self.name
        
        if dic['US'][1]:
            files.append((f'US{code}.txt', dic['US'][1][:-1].encode('utf-8')))
        
        if dic['AF']:
            files.append((f'AF{code}.txt', dic['AF'][:-1].encode('utf-8')))
        
        if dic['AT']:
            files.append((f'AT{code}.txt', dic['AT'][:-1].encode('utf-8')))
        
        if type_ct:
            files.append((f'CT{code}.txt', type_ct[:-1].encode('utf-8')))
        
        return files
    
    def _generate_us_line(self, patient, invoice):
        """Genera línea para archivo US (Usuarios)"""
        # Tipo y número de documento
        tipo_doc = 'CC'
        if patient.l10n_latam_identification_type_id:
            tipo_doc = patient.l10n_latam_identification_type_id.heath_code or 'CC'
        
        numero_id = patient.vat or patient.ref or ''
        
        # Edad
        edad, uom_edad = self._calculate_age(patient.birthday, invoice.invoice_date)
        
        # Género
        sexo = self._convert_gender(patient.gender or 'I')
        
        # Ubicación
        cod_dpto = '11'  # Default Bogotá
        cod_municipio = '001'  # Default
        if patient.state_id:
            cod_dpto = patient.state_id.l10n_co_edi_code or patient.state_id.code or '11'
        if patient.city_id:
            cod_municipio = patient.city_id.l10n_co_edi_code[-3:] if patient.city_id.l10n_co_edi_code else '001'
        
        zona_residencia = patient.zona_territorial or 'U'
        
        # Tipo de usuario
        tipo_usuario = '1'  # Default contributivo
        tipo_afiliacion_map = {
            'contributory': '1',
            'subsidized': '2',
            'linked': '3'
        }
        if hasattr(patient, 'tipo_afiliacion'):
            tipo_usuario = tipo_afiliacion_map.get(patient.tipo_afiliacion, '1')
        elif patient.health_type:
            # Mapear health_type a tipo afiliación RIPS
            health_type_map = {
                '01': '1', '02': '1', '03': '1',  # Contributivo
                '04': '2',  # Subsidiado
                '05': '3',  # Vinculado
            }
            tipo_usuario = health_type_map.get(patient.health_type, '1')
        
        return "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (
            tipo_doc,
            numero_id,
            self.partner_id.ref or '',  # Código entidad
            tipo_usuario,
            self._remove_accents(getattr(patient, 'first_lastname', '') or patient.name.split()[-1] if patient.name else ''),
            self._remove_accents(getattr(patient, 'second_lastname', '') or ''),
            self._remove_accents(getattr(patient, 'first_name', '') or patient.name.split()[0] if patient.name else ''),
            self._remove_accents(getattr(patient, 'second_name', '') or ''),
            edad,
            uom_edad,
            sexo,
            cod_dpto,
            cod_municipio,
            zona_residencia
        )
    
    def _generate_af_line(self, invoice):
        """Genera línea para archivo AF (Facturas)"""
        # Calcular valores
        copago = int(invoice.copay_amount or 0)
        comision = 0
        descuento = int(sum(invoice.invoice_line_ids.mapped(lambda l: l.discount_line or 0)))
        valor_neto = int(invoice.amount_total)
        
        return "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (
            self.cea_code,
            self._remove_accents(self.company_id.name),
            "NI",
            self.company_id.partner_id.vat or '',
            invoice.name,
            invoice.invoice_date.strftime('%d/%m/%Y'),
            self.date_from.strftime('%d/%m/%Y'),
            self.date_to.strftime('%d/%m/%Y'),
            self.partner_id.ref or '',
            self._remove_accents(self.partner_id.name),
            self.contract_id.contract_code or '',
            getattr(self.contract_id, 'benefit_plan', '2'),  # Default POS
            getattr(self.contract_id, 'policy_number', '0'),
            copago,
            comision,
            descuento,
            valor_neto
        )
    
    def _generate_at_line(self, line, invoice, patient):
        """Genera línea para archivo AT (Servicios)"""
        # Tipo y número de documento
        tipo_doc = 'CC'
        if patient.l10n_latam_identification_type_id:
            tipo_doc = patient.l10n_latam_identification_type_id.heath_code or 'CC'
        
        numero_id = patient.vat or patient.ref or ''
        
        # Tipo de servicio
        tipo_servicio = '1'  # Default consulta
        if line.product_id.rips_service_type:
            service_map = {
                'consulta': '1',
                'procedimiento': '2',
                'medicamento': '3',
                'otro_servicio': '4'
            }
            tipo_servicio = service_map.get(line.product_id.rips_service_type, '1')
        
        # Valores
        cantidad = int(line.quantity)
        valor_unitario = int(line.price_unit)
        valor_total = int(line.price_subtotal)
        
        # Si incluye impuestos
        if invoice.rips_include_taxes and line.tax_ids:
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                currency=invoice.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=invoice.partner_id
            )
            valor_total = int(taxes['total_included'])
        
        return "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (
            invoice.name,
            self.cea_code,
            tipo_doc,
            numero_id,
            line.autorizacion or '',
            tipo_servicio,
            self._remove_accents(line.product_id.default_code or ''),
            self._remove_accents(line.product_id.name),
            cantidad,
            valor_unitario,
            valor_total
        )
    
    def _create_zip(self, files):
        """Crea archivo ZIP con los archivos"""
        output = BytesIO()
        with zipfile.ZipFile(output, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, content in files:
                zf.writestr(filename, content)
        return output



class RIPSExport(models.Model):
    _name = 'rips.export'
    _description = 'Exportación de RIPS'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    
    name = fields.Char('Nombre', readonly=True, copy=False)
    date = fields.Date('Fecha', default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company, readonly=True)
    move_ids = fields.Many2many('account.move', string='Facturas', required=True)
    zip_file = fields.Binary('Archivo ZIP')
    zip_filename = fields.Char('Nombre del archivo ZIP', readonly=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('rips_generated', 'RIPS Generados'),
        ('validated', 'Validado'),
        ('generated', 'ZIP Generado'),
        ('closed', 'Cerrado')
    ], default='draft', string='Estado', readonly=True)
    rips_count = fields.Integer('Cantidad de RIPS', compute='_compute_rips_count')
    pending_count = fields.Integer('Cantidad de Pendiente', compute='_compute_rips_count')
    # Campos existentes
    all_rips_validated = fields.Boolean(
        string='Todos los RIPS Validados',
        compute='_compute_all_rips_validated',
        store=True,
        help="Indica si todas las facturas tienen RIPS validados por el MinSalud"
    )
    
    validation_summary = fields.Text(
        string='Resumen de Validación',
        compute='_compute_validation_summary',
        help="Resumen del estado de validación de los RIPS"
    )
    
    json_data = fields.Text(
        string='JSON Data',
        readonly=True,
        help="Datos JSON de validación del lote"
    )
    
    validation_errors_count = fields.Integer(
        string='Facturas con Errores',
        compute='_compute_validation_errors_count'
    )
    
    validation_success_count = fields.Integer(
        string='Facturas Validadas',
        compute='_compute_validation_success_count'
    )
    
    # NUEVOS CAMPOS MANY2MANY COMPUTADOS
    validated_move_ids = fields.Many2many(
        'account.move',
        string='Facturas Validadas',
        compute='_compute_moves_by_status',
        relation='rips_export_validated_moves',
        column1='rips_export_id',
        column2='move_id'
    )
    
    pending_move_ids = fields.Many2many(
        'account.move',
        string='Facturas Pendientes',
        compute='_compute_moves_by_status',
        relation='rips_export_pending_moves',
        column1='rips_export_id',
        column2='move_id'
    )
    
    error_move_ids = fields.Many2many(
        'account.move',
        string='Facturas con Errores',
        compute='_compute_moves_by_status',
        relation='rips_export_error_moves',
        column1='rips_export_id',
        column2='move_id'
    )
    
    closed_date = fields.Datetime('Fecha de Cierre', readonly=True)
    closed_by = fields.Many2one('res.users', string='Cerrado por', readonly=True)
    
    has_zip = fields.Boolean('Tiene ZIP', compute='_compute_has_zip')
    
    has_non_validated = fields.Boolean(
        'Tiene Facturas No Validadas', 
        compute='_compute_has_non_validated'
    )
    
    @api.depends('zip_file')
    def _compute_has_zip(self):
        for record in self:
            record.has_zip = bool(record.zip_file)
    
    @api.depends('move_ids', 'move_ids.rips_validation_status')
    def _compute_has_non_validated(self):
        for record in self:
            record.has_non_validated = any(
                move.rips_validation_status != 'validated' 
                for move in record.move_ids
            )
    
    @api.depends('move_ids', 'move_ids.rips_validation_status')
    def _compute_moves_by_status(self):
        """Calcula las facturas por estado de validación"""
        for record in self:
            validated = record.move_ids.filtered(lambda m: m.rips_validation_status == 'validated')
            pending = record.move_ids.filtered(lambda m: m.rips_validation_status not in ['validated', 'rejected'])
            errors = record.move_ids.filtered(lambda m: m.rips_validation_status == 'rejected')
            
            record.validated_move_ids = validated
            record.pending_move_ids = pending
            record.error_move_ids = errors
    
    @api.depends('move_ids')
    def _compute_rips_count(self):
        for record in self:
            record.rips_count = len(record.move_ids)
            record.pending_count = len(record.pending_move_ids)
            
    @api.depends('move_ids', 'move_ids.rips_validation_status')
    def _compute_all_rips_validated(self):
        for record in self:
            if not record.move_ids:
                record.all_rips_validated = False
            else:
                record.all_rips_validated = all(
                    move.rips_validation_status == 'validated' 
                    for move in record.move_ids
                )
    
    @api.depends('move_ids', 'move_ids.rips_validation_status')
    def _compute_validation_summary(self):
        for record in self:
            if not record.move_ids:
                record.validation_summary = "Sin facturas"
                continue
            
            total = len(record.move_ids)
            validated = len(record.validated_move_ids)
            rejected = len(record.error_move_ids)
            pending = len(record.pending_move_ids)
            
            summary = f"Total: {total} facturas\n"
            summary += f"Validadas: {validated}\n"
            summary += f"Rechazadas: {rejected}\n"
            summary += f"Pendientes: {pending}"
            
            record.validation_summary = summary
    
    @api.depends('move_ids', 'move_ids.rips_validation_status')
    def _compute_validation_errors_count(self):
        for record in self:
            record.validation_errors_count = len(record.error_move_ids)
    
    @api.depends('move_ids', 'move_ids.rips_validation_status')
    def _compute_validation_success_count(self):
        for record in self:
            record.validation_success_count = len(record.validated_move_ids)
    
    @api.model
    def create(self, vals):
        sequence = self.env['ir.sequence'].next_by_code('rips.export.sequence') or 'RIP00001'
        vals['name'] = sequence
        return super(RIPSExport, self).create(vals)
    
    def action_close_batch(self):
        """Cierra el lote de RIPS"""
        self.ensure_one()
        
        if self.state == 'closed':
            raise UserError(_("Este lote ya está cerrado"))
        
        if not self.zip_file:
            raise UserError(_("Debe generar el archivo ZIP antes de cerrar el lote"))
        
        # Registrar cierre
        self.write({
            'state': 'closed',
            'closed_date': fields.Datetime.now(),
            'closed_by': self.env.user.id
        })
        
        # Mensaje en chatter
        self.message_post(
            body=_(
                "<p><b>Lote cerrado</b></p>"
                "<ul>"
                "<li>Cerrado por: %s</li>"
                "<li>Fecha: %s</li>"
                "<li>Total facturas: %s</li>"
                "<li>Validadas: %s</li>"
                "<li>Con errores: %s</li>"
                "<li>Pendientes: %s</li>"
                "</ul>"
            ) % (
                self.env.user.name,
                fields.Datetime.now().strftime('%d/%m/%Y %H:%M'),
                len(self.move_ids),
                len(self.validated_move_ids),
                len(self.error_move_ids),
                len(self.pending_move_ids)
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
        
        return True
    
    def action_exclude_rejected_invoices(self):
        """Excluye las facturas rechazadas y no válidas del lote"""
        self.ensure_one()
        
        if self.state in ['closed']:
            raise UserError(_("No puede modificar un lote cerrado"))
        
        # Obtener facturas a excluir (rechazadas o sin validar)
        rejected_moves = self.move_ids.filtered(
            lambda m: m.rips_validation_status != 'validated'
        )
        
        if not rejected_moves:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin facturas para excluir'),
                    'message': _('Todas las facturas están validadas'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Excluir facturas
        self.move_ids = [(3, move.id, 0) for move in rejected_moves]
        
        # Mensaje en chatter
        self.message_post(
            body=_(
                "<p><b>Facturas excluidas del lote</b></p>"
                "<ul>"
                "<li>Total excluidas: %s</li>"
                "<li>Facturas: %s</li>"
                "<li>Fecha: %s</li>"
                "<li>Usuario: %s</li>"
                "</ul>"
            ) % (
                len(rejected_moves),
                ', '.join(rejected_moves.mapped('name')[:10]),  # Limitar a 10 nombres
                fields.Datetime.now().strftime('%d/%m/%Y %H:%M'),
                self.env.user.name
            ),
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Facturas Excluidas'),
                'message': _('Se excluyeron %s facturas no validadas') % len(rejected_moves),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_exclude_closed_batch_invoices(self):
        """Excluye las facturas que ya están en un lote cerrado"""
        self.ensure_one()
        
        if self.state not in ['draft']:
            raise UserError(_("Solo puede excluir facturas en estado Borrador"))
        
        # Buscar facturas que están en lotes cerrados
        closed_batches = self.search([('state', '=', 'closed'), ('id', '!=', self.id)])
        invoices_in_closed_batches = closed_batches.mapped('move_ids')
        
        # Facturas a excluir
        moves_to_exclude = self.move_ids.filtered(lambda m: m in invoices_in_closed_batches)
        
        if not moves_to_exclude:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin facturas para excluir'),
                    'message': _('No hay facturas que ya estén en lotes cerrados'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Excluir facturas
        self.move_ids = [(3, move.id, 0) for move in moves_to_exclude]
        
        # Mensaje en chatter
        self.message_post(
            body=_(
                "<p><b>Facturas excluidas (ya en lotes cerrados)</b></p>"
                "<ul>"
                "<li>Total excluidas: %s</li>"
                "<li>Facturas: %s</li>"
                "</ul>"
            ) % (
                len(moves_to_exclude),
                ', '.join(moves_to_exclude.mapped('name'))
            ),
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Facturas Excluidas'),
                'message': _('Se excluyeron %s facturas que ya están en lotes cerrados') % len(moves_to_exclude),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_validate_all_cups(self):
        """Valida todos los códigos CUPS de las facturas del lote"""
        self.ensure_one()
        
        if not self.move_ids:
            raise UserError(_("No hay facturas en el lote"))
        
        validated_count = 0
        errors = []
        
        for move in self.move_ids:
            try:
                move.action_validate_cups_codes()
                validated_count += 1
            except Exception as e:
                errors.append(f"{move.name}: {str(e)}")
        
        message = f"CUPS validados en {validated_count} facturas."
        if errors:
            message += f"\n\nErrores encontrados:\n" + "\n".join(errors)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validación CUPS'),
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': True,
            }
        }
    
    def action_consult_and_send_missing_cuvs(self):
        """Consulta CUVs existentes y envía los que faltan"""
        self.ensure_one()
        
        if not self.move_ids:
            raise UserError(_("No hay facturas en el lote"))
        
        consulted = 0
        sent = 0
        validated = 0
        errors = []
        
        for move in self.move_ids:
            try:
                if move.rips_cuv:
                    # Consultar estado del CUV
                    move.action_consult_cuv()
                    consulted += 1
                    
                    if move.rips_validation_status == 'validated':
                        validated += 1
                else:
                    # No tiene CUV, generar y enviar
                    if not move.rips_generated:
                        move.action_generate_rips_json_improved()
                    
                    move.action_send_rips_to_minsalud_improved()
                    sent += 1
                    
                    # Registrar envío en chatter
                    self.message_post(
                        body=_(
                            "<p><b>RIPS enviado al MinSalud</b></p>"
                            "<ul>"
                            "<li>Factura: %s</li>"
                            "<li>Hora: %s</li>"
                            "<li>Estado: Enviado</li>"
                            "</ul>"
                        ) % (move.name, fields.Datetime.now().strftime('%H:%M:%S')),
                        message_type='notification'
                    )
                    
                    if move.rips_validation_status == 'validated':
                        validated += 1
                        
            except Exception as e:
                errors.append(f"{move.name}: {str(e)}")
                _logger.error(f"Error procesando {move.name}: {str(e)}")
        
        # Actualizar JSON Data
        self._update_json_data()
        
        # Actualizar estado
        if self.all_rips_validated:
            self.state = 'validated'
        
        message = f"Proceso completado:\n"
        message += f"- CUVs consultados: {consulted}\n"
        message += f"- RIPS enviados: {sent}\n"
        message += f"- Total validados: {validated}\n"
        
        if errors:
            message += f"\nErrores:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                message += f"\n... y {len(errors) - 5} errores más"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Consulta y Envío de CUVs'),
                'message': message,
                'type': 'info' if validated > 0 else 'warning',
                'sticky': True,
            }
        }
    
    def action_generate_rips_batch(self):
        """Genera y envía los RIPS de todas las facturas del lote"""
        self.ensure_one()
        
        if not self.move_ids:
            raise UserError(_("No hay facturas en el lote"))
        
        # Contador de resultados
        generated = 0
        sent = 0
        validated = 0
        errors = []
        json_results = []
        
        # Mensaje inicial en chatter
        self.message_post(
            body=_(
                "<p><b>Iniciando generación de RIPS en lote</b></p>"
                "<ul>"
                "<li>Total de facturas: %s</li>"
                "<li>Hora de inicio: %s</li>"
                "</ul>"
            ) % (len(self.move_ids), fields.Datetime.now().strftime('%d/%m/%Y %H:%M:%S')),
            message_type='notification'
        )
        
        for move in self.move_ids:
            try:
                # Generar RIPS si no existe o no está validado
                if not move.rips_generated or move.rips_validation_status != 'validated':
                    move.action_generate_rips_json_improved()
                    generated += 1
                
                # Enviar al MinSalud si no está validado
                if move.rips_validation_status != 'validated':
                    move.action_send_rips_to_minsalud_improved()
                    sent += 1
                    
                    # Registrar cada envío en el chatter
                    self.message_post(
                        body=_(
                            "<p><b>RIPS enviado al MinSalud</b></p>"
                            "<ul>"
                            "<li>Factura: %s</li>"
                            "<li>Hora: %s</li>"
                            "<li>CUV: %s</li>"
                            "</ul>"
                        ) % (
                            move.name, 
                            fields.Datetime.now().strftime('%H:%M:%S'),
                            move.rips_cuv or 'Pendiente'
                        ),
                        message_type='notification'
                    )
                
                # Verificar estado final
                if move.rips_validation_status == 'validated':
                    validated += 1
                    # Mensaje de validación exitosa
                    self.message_post(
                        body=_(
                            "<p><b>RIPS validado exitosamente</b></p>"
                            "<ul>"
                            "<li>Factura: %s</li>"
                            "<li>CUV: %s</li>"
                            "<li>Proceso ID: %s</li>"
                            "</ul>"
                        ) % (
                            move.name,
                            move.rips_cuv,
                            move.rips_proceso_id or 'N/A'
                        ),
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment'
                    )
                    
                    # Agregar resultado exitoso al JSON
                    json_results.append({
                        "ResultState": True,
                        "ProcesoId": move.rips_proceso_id or "N/A",
                        "NumFactura": move.name,
                        "CodigoUnicoValidacion": move.rips_cuv or "",
                        "FechaRadicacion": move.rips_validation_date.isoformat() if move.rips_validation_date else "",
                        "ResultadosValidacion": []
                    })
                else:
                    # Mensaje de error
                    validation_errors = self._extract_validation_errors(move)
                    error_message = "<p><b>Error en validación RIPS</b></p><ul><li>Factura: %s</li>" % move.name
                    
                    if validation_errors:
                        error_message += "<li>Errores:<ul>"
                        for error in validation_errors[:3]:  # Mostrar máximo 3 errores
                            if isinstance(error, dict):
                                error_message += "<li>%s</li>" % (error.get('Descripcion', str(error)))
                            else:
                                error_message += "<li>%s</li>" % str(error)
                        if len(validation_errors) > 3:
                            error_message += "<li>... y %s errores más</li>" % (len(validation_errors) - 3)
                        error_message += "</ul></li>"
                    
                    error_message += "</ul>"
                    
                    self.message_post(
                        body=error_message,
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment'
                    )
                    
                    # Agregar resultado con errores
                    json_results.append({
                        "ResultState": False,
                        "ProcesoId": move.rips_proceso_id or "N/A",
                        "NumFactura": move.name,
                        "CodigoUnicoValidacion": move.rips_cuv or "No aplica",
                        "FechaRadicacion": datetime.now().isoformat(),
                        "ResultadosValidacion": validation_errors
                    })
                
                # Commit después de cada factura procesada
                self.env.cr.commit()
                    
            except Exception as e:
                self.env.cr.rollback()
                errors.append(f"{move.name}: {str(e)}")
                _logger.error(f"Error procesando RIPS para {move.name}: {str(e)}")
                
                # Mensaje de error técnico
                self.message_post(
                    body=_(
                        "<p><b>Error técnico en RIPS</b></p>"
                        "<ul>"
                        "<li>Factura: %s</li>"
                        "<li>Error: %s</li>"
                        "</ul>"
                    ) % (move.name, str(e)),
                    message_type='notification'
                )
        
        # Actualizar JSON Data con resultados
        self.json_data = json.dumps(json_results, indent=2, ensure_ascii=False)
        
        # Actualizar estado
        if self.all_rips_validated:
            self.state = 'validated'
        else:
            self.state = 'rips_generated'
        
        # Commit final
        self.env.cr.commit()
        
        # Mensaje resumen final
        self.message_post(
            body=_(
                "<p><b>Proceso de generación RIPS completado</b></p>"
                "<ul>"
                "<li>Hora de finalización: %s</li>"
                "<li>RIPS generados: %s</li>"
                "<li>RIPS enviados: %s</li>"
                "<li>RIPS validados: %s</li>"
                "<li>Errores: %s</li>"
                "</ul>"
            ) % (
                fields.Datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                generated,
                sent,
                validated,
                len(errors)
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )
        
        # Mensaje de resultado
        message = f"Proceso completado:\n"
        message += f"- RIPS generados: {generated}\n"
        message += f"- RIPS enviados: {sent}\n"
        message += f"- RIPS validados: {validated}\n"
        
        if errors:
            message += f"\nErrores encontrados:\n"
            message += "\n".join(errors)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Generación de RIPS en Lote'),
                'message': message,
                'type': 'info' if validated > 0 else 'warning',
                'sticky': True,
            }
        }
    
    def _update_json_data(self):
        """Actualiza el JSON Data con el estado actual de las facturas"""
        json_results = []
        
        for move in self.move_ids:
            if move.rips_validation_status == 'validated':
                json_results.append({
                    "ResultState": True,
                    "ProcesoId": move.rips_proceso_id or "N/A",
                    "NumFactura": move.name,
                    "CodigoUnicoValidacion": move.rips_cuv or "",
                    "FechaRadicacion": move.rips_validation_date.isoformat() if move.rips_validation_date else "",
                    "ResultadosValidacion": []
                })
            else:
                json_results.append({
                    "ResultState": False,
                    "ProcesoId": move.rips_proceso_id or "N/A",
                    "NumFactura": move.name,
                    "CodigoUnicoValidacion": move.rips_cuv or "No aplica",
                    "FechaRadicacion": datetime.now().isoformat(),
                    "ResultadosValidacion": self._extract_validation_errors(move) if move.rips_response_json else []
                })
        
        self.json_data = json.dumps(json_results, indent=2, ensure_ascii=False)
    
    def _extract_validation_errors(self, move):
        """Extrae los errores de validación de una factura"""
        if not move.rips_response_json:
            return []
        
        try:
            response = json.loads(move.rips_response_json)
            return response.get('ResultadosValidacion', response.get('resultados_validacion', []))
        except:
            return []
    
    def action_check_validation_status(self):
        """Consulta el estado de validación de todos los RIPS"""
        self.ensure_one()
        
        updated = 0
        json_results = []
        
        # Mensaje inicial
        self.message_post(
            body=_(
                "<p><b>Consultando estado de validación</b></p>"
                "<p>Consultando %s CUVs...</p>"
            ) % len(self.move_ids.filtered('rips_cuv')),
            message_type='notification'
        )
        
        for move in self.move_ids:
            if move.rips_cuv:
                try:
                    # Consultar estado del CUV
                    old_status = move.rips_validation_status
                    move.action_consult_cuv()
                    updated += 1
                    
                    # Si cambió el estado, registrar
                    if old_status != move.rips_validation_status:
                        self.message_post(
                            body=_(
                                "<p><b>Cambio de estado</b></p>"
                                "<ul>"
                                "<li>Factura: %s</li>"
                                "<li>Estado anterior: %s</li>"
                                "<li>Estado nuevo: %s</li>"
                                "<li>CUV: %s</li>"
                                "</ul>"
                            ) % (
                                move.name,
                                dict(move._fields['rips_validation_status'].selection).get(old_status, old_status),
                                dict(move._fields['rips_validation_status'].selection).get(move.rips_validation_status, move.rips_validation_status),
                                move.rips_cuv
                            ),
                            message_type='notification'
                        )
                    
                    # Agregar resultado al JSON
                    json_results.append({
                        "ResultState": move.rips_validation_status == 'validated',
                        "ProcesoId": move.rips_proceso_id or "N/A",
                        "NumFactura": move.name,
                        "CodigoUnicoValidacion": move.rips_cuv,
                        "FechaRadicacion": move.rips_validation_date.isoformat() if move.rips_validation_date else "",
                        "ResultadosValidacion": self._extract_validation_errors(move) if move.rips_validation_status != 'validated' else []
                    })
                    
                    # Commit después de cada consulta
                    self.env.cr.commit()
                    
                except Exception as e:
                    self.env.cr.rollback()
                    _logger.error(f"Error consultando CUV para {move.name}: {str(e)}")
        
        # Actualizar JSON Data
        if json_results:
            self.json_data = json.dumps(json_results, indent=2, ensure_ascii=False)
        
        # Actualizar estado si todos están validados
        if self.all_rips_validated:
            self.state = 'validated'
        
        # Mensaje resumen
        self.message_post(
            body=_(
                "<p><b>Consulta de estado completada</b></p>"
                "<ul>"
                "<li>CUVs consultados: %s</li>"
                "<li>Validados: %s</li>"
                "<li>Con errores: %s</li>"
                "<li>Pendientes: %s</li>"
                "</ul>"
            ) % (
                updated,
                len(self.validated_move_ids),
                len(self.error_move_ids),
                len(self.pending_move_ids)
            ),
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Consulta de Estado'),
                'message': _('Se actualizó el estado de %s facturas') % updated,
                'type': 'success',
                'sticky': False,
            }
        }
        
    def action_generate_rips_batch(self):
        """Genera y envía los RIPS de todas las facturas del lote"""
        self.ensure_one()
        
        if not self.move_ids:
            raise UserError(_("No hay facturas en el lote"))
        
        # Contador de resultados
        generated = 0
        sent = 0
        validated = 0
        errors = []
        json_results = []
        
        for move in self.move_ids:
            try:
                # Generar RIPS si no existe o no está validado
                if not move.rips_generated or move.rips_validation_status != 'validated':
                    move.action_generate_rips_json_improved()
                    generated += 1
                
                # Enviar al MinSalud si no está validado
                if move.rips_validation_status != 'validated':
                    move.action_send_rips_to_minsalud_improved()
                    sent += 1
                
                # Verificar estado final
                if move.rips_validation_status == 'validated':
                    validated += 1
                    # Agregar resultado exitoso al JSON
                    json_results.append({
                        "ResultState": True,
                        "ProcesoId": move.rips_proceso_id or "N/A",
                        "NumFactura": move.name,
                        "CodigoUnicoValidacion": move.rips_cuv or "",
                        "FechaRadicacion": move.rips_validation_date.isoformat() if move.rips_validation_date else "",
                        "ResultadosValidacion": []
                    })
                else:
                    # Agregar resultado con errores
                    json_results.append({
                        "ResultState": False,
                        "ProcesoId": move.rips_proceso_id or "N/A",
                        "NumFactura": move.name,
                        "CodigoUnicoValidacion": move.rips_cuv or "No aplica",
                        "FechaRadicacion": datetime.now().isoformat(),
                        "ResultadosValidacion": self._extract_validation_errors(move)
                    })
                
                # Commit después de cada factura procesada
                self.env.cr.commit()
                    
            except Exception as e:
                self.env.cr.rollback()
                errors.append(f"{move.name}: {str(e)}")
                _logger.error(f"Error procesando RIPS para {move.name}: {str(e)}")
        
        # Actualizar JSON Data con resultados
        self.json_data = json.dumps(json_results, indent=2, ensure_ascii=False)
        
        # Actualizar estado
        if self.all_rips_validated:
            self.state = 'validated'
        else:
            self.state = 'rips_generated'
        
        # Commit final
        self.env.cr.commit()
        
        # Mensaje de resultado
        message = f"Proceso completado:\n"
        message += f"- RIPS generados: {generated}\n"
        message += f"- RIPS enviados: {sent}\n"
        message += f"- RIPS validados: {validated}\n"
        
        if errors:
            message += f"\nErrores encontrados:\n"
            message += "\n".join(errors)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Generación de RIPS en Lote'),
                'message': message,
                'type': 'info' if validated > 0 else 'warning',
                'sticky': True,
            }
        }
    
    def _update_json_data(self):
        """Actualiza el JSON Data con el estado actual de las facturas"""
        json_results = []
        
        for move in self.move_ids:
            if move.rips_validation_status == 'validated':
                json_results.append({
                    "ResultState": True,
                    "ProcesoId": move.rips_proceso_id or "N/A",
                    "NumFactura": move.name,
                    "CodigoUnicoValidacion": move.rips_cuv or "",
                    "FechaRadicacion": move.rips_validation_date.isoformat() if move.rips_validation_date else "",
                    "ResultadosValidacion": []
                })
            else:
                json_results.append({
                    "ResultState": False,
                    "ProcesoId": move.rips_proceso_id or "N/A",
                    "NumFactura": move.name,
                    "CodigoUnicoValidacion": move.rips_cuv or "No aplica",
                    "FechaRadicacion": datetime.now().isoformat(),
                    "ResultadosValidacion": self._extract_validation_errors(move) if move.rips_response_json else []
                })
        
        self.json_data = json.dumps(json_results, indent=2, ensure_ascii=False)
    
    def _extract_validation_errors(self, move):
        """Extrae los errores de validación de una factura"""
        if not move.rips_response_json:
            return []
        
        try:
            response = json.loads(move.rips_response_json)
            return response.get('ResultadosValidacion', response.get('resultados_validacion', []))
        except:
            return []
    
    def action_check_validation_status(self):
        """Consulta el estado de validación de todos los RIPS"""
        self.ensure_one()
        
        updated = 0
        json_results = []
        
        for move in self.move_ids:
            if move.rips_cuv:
                try:
                    # Consultar estado del CUV
                    move.action_consult_cuv()
                    updated += 1
                    
                    # Agregar resultado al JSON
                    json_results.append({
                        "ResultState": move.rips_validation_status == 'validated',
                        "ProcesoId": move.rips_proceso_id or "N/A",
                        "NumFactura": move.name,
                        "CodigoUnicoValidacion": move.rips_cuv,
                        "FechaRadicacion": move.rips_validation_date.isoformat() if move.rips_validation_date else "",
                        "ResultadosValidacion": self._extract_validation_errors(move) if move.rips_validation_status != 'validated' else []
                    })
                    
                    # Commit después de cada consulta
                    self.env.cr.commit()
                    
                except Exception as e:
                    self.env.cr.rollback()
                    _logger.error(f"Error consultando CUV para {move.name}: {str(e)}")
        
        # Actualizar JSON Data
        if json_results:
            self.json_data = json.dumps(json_results, indent=2, ensure_ascii=False)
        
        # Actualizar estado si todos están validados
        if self.all_rips_validated:
            self.state = 'validated'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Consulta de Estado'),
                'message': _('Se actualizó el estado de %s facturas') % updated,
                'type': 'success',
                'sticky': False,
            }
        }


    def generate_zip(self):
        """Genera un archivo ZIP con los documentos RIPS de todas las facturas del lote."""
        
        def clean_json_data(data):
            """Extrae y parsea el response_text del JSON RIPS de manera eficiente."""
            if not isinstance(data, (str, dict)):
                return data
                
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    return data
            
            # Si no es diccionario o no tiene response_text, retornar tal cual
            if not isinstance(data, dict) or 'response_text' not in data:
                return data
                
            # Intentar parsear response_text
            response_text = data.get('response_text')
            if response_text and isinstance(response_text, str):
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    pass
                    
            return data

        def process_rips_response(move):
            """Procesa la respuesta RIPS y genera el contenido del archivo de resultado."""
            if not move.rips_response_json:
                return None, None
            
            try:
                # Parsear y limpiar datos en un solo paso
                response_data = json.loads(move.rips_response_json)
                clean_data = clean_json_data(response_data)
                data_to_save = clean_data if clean_data != response_data else response_data
                
                # Determinar estado y proceso_id usando diccionarios para evitar múltiples if
                validation_keys = {
                    ('ResultState', 'ProcesoId', 'NumFactura'): lambda d: ('A' if d.get('ResultState') else 'R', d.get('ProcesoId', 'SIN_ID'), d.get('NumFactura', move.name)),
                    ('EsValido', 'ProcesoId', 'NumeroDocumento'): lambda d: ('A' if d.get('EsValido') else 'R', d.get('ProcesoId', 'SIN_ID'), d.get('NumeroDocumento', move.name))
                }
                
                estado, proceso_id, num_factura = 'RESP', 'COMPLETO', move.name
                
                for keys, extractor in validation_keys.items():
                    if all(k in data_to_save for k in keys[:2]):
                        estado, proceso_id, num_factura = extractor(data_to_save)
                        break
                
                filename = f"ResultadosMSPS_{num_factura}_ID{proceso_id}_{estado}_CUV.txt"
                content_bytes = json.dumps(data_to_save, indent=2, ensure_ascii=False).encode('utf-8')
                
                return filename, content_bytes
                
            except (json.JSONDecodeError, Exception) as e:
                _logger.error(f"Error procesando respuesta RIPS para {move.name}: {str(e)}")
                return None, None

        # Validaciones iniciales
        self.ensure_one()
        
        # Verificar RIPS generados
        moves_without_rips = self.move_ids.filtered(lambda m: not m.rips_generated)
        if moves_without_rips:
            raise UserError(_(
                "Las siguientes facturas no tienen RIPS generado:\n%s\n\n"
                "Use el botón 'Generar RIPS del Lote' primero."
            ) % '\n'.join(moves_without_rips.mapped('name')))
        
        # Log de advertencia para facturas no validadas (una sola operación)
        if not self.all_rips_validated:
            moves_not_validated = self.move_ids.filtered(lambda m: m.rips_validation_status != 'validated')
            if moves_not_validated:
                _logger.warning(
                    "Facturas no validadas por MinSalud: %s", 
                    ', '.join(moves_not_validated.mapped('name'))
                )
        
        # Preparar datos comunes
        company_vat = self.move_ids[0].company_id.partner_id.vat_co if self.move_ids else ''
        today = datetime.now().strftime('%Y%m%d')
        attachment_name = f'RIPS_{self.name}_{today}.zip'
        
        # Generar ZIP principal
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as main_zip:
            # Crear carpetas principales una sola vez
            main_zip.writestr("CUV/", "")
            main_zip.writestr("JSON/", "")
            
            # Procesar facturas
            successful_moves = []
            
            for move in self.move_ids:
                try:
                    # Cache de nombres de archivo
                    base_name = f"FVS_{company_vat}_{move.name}"
                    
                    # Obtener XML (evitar doble decodificación)
                    xml_content = None
                    if move.attached_document_xml:
                        xml_content = base64.b64decode(move.attached_document_xml)
                    else:
                        xml_content, error = move._get_attached_document()
                        if error:
                            _logger.warning(f"Error XML para {move.name}: {error}")
                    
                    # Generar PDF
                    pdf_content = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                        "account.account_invoices", move.id
                    )[0]
                    
                    # Crear ZIP interno directamente en el ZIP principal
                    inner_zip_name = f"{base_name}.zip"
                    inner_buffer = BytesIO()
                    
                    with zipfile.ZipFile(inner_buffer, 'w', zipfile.ZIP_DEFLATED) as inner_zip:
                        if xml_content:
                            inner_zip.writestr(f"{move.name}_AttachedDocument.xml", xml_content)
                        inner_zip.writestr(f"{base_name}.pdf", pdf_content)
                    
                    main_zip.writestr(inner_zip_name, inner_buffer.getvalue())
                    
                    # Procesar respuesta RIPS
                    result_filename, result_content = process_rips_response(move)
                    if result_content:
                        main_zip.writestr(f"CUV/{result_filename}", result_content)
                    
                    # Agregar JSON RIPS
                    if move.rips_json_binary:
                        json_content = base64.b64decode(move.rips_json_binary)
                        main_zip.writestr(f"JSON/{base_name}.json", json_content)
                    
                    successful_moves.append(move.id)
                    
                except Exception as e:
                    _logger.error(f"Error procesando factura {move.name}: {str(e)}", exc_info=True)
                    continue
        
        # Codificar ZIP final
        zip_data = base64.b64encode(zip_buffer.getvalue())
        zip_size_kb = len(zip_data) // 1024
        
        # Crear attachment
        attachment = self.env['ir.attachment'].create({
            'name': attachment_name,
            'type': 'binary',
            'datas': zip_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/zip'
        })
        
        # Actualizar referencias en una sola operación SQL
        if successful_moves:
            self.env.cr.execute("""
                UPDATE account_move 
                SET ripsjson_id = %s 
                WHERE id = ANY(%s)
            """, (self.id, successful_moves))
        
        # Actualizar estado del lote
        self.write({
            'zip_file': zip_data,
            'zip_filename': attachment_name,
            'state': 'generated'
        })
        
        # Mensaje en chatter
        if hasattr(self, 'message_post'):
            self.message_post(
                body=_("Archivo ZIP generado: %s (Tamaño: %s KB, Facturas procesadas: %s/%s)") % 
                    (attachment_name, zip_size_kb, len(successful_moves), len(self.move_ids)),
                message_type='notification'
            )
        
        # Retornar acción de descarga
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    def action_generate(self):
        """Acción para generar el archivo ZIP"""
        self.ensure_one()
        self.generate_zip()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rips.export',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
    
    def action_download(self):
        """Acción para descargar el archivo ZIP"""
        self.ensure_one()
        if not self.zip_file:
            raise UserError(_("No hay archivo ZIP generado. Use el botón 'Generar ZIP' primero."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=rips.export&id={self.id}&field=zip_file&filename={self.zip_filename}&download=true',
            'target': 'self',
        }
    
    def action_view_invoices(self):
        """Ver las facturas del lote"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas del Lote'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.move_ids.ids)],
            'context': self.env.context,
        }
    
    def action_filter_validated_invoices(self):
        """Muestra solo las facturas validadas que no están en otro lote"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas Validadas Disponibles'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [
                ('rips_validation_status', '=', 'validated'),
                ('ripsjson_id', '=', False),
                ('move_type', 'in', ['out_invoice', 'out_refund'])
            ],
            'context': {
                'search_default_validated_rips': 1,
                'search_default_not_in_batch': 1,
            },
        }

    def action_generate(self):
        """Acción para generar el archivo ZIP"""
        self.ensure_one()
        return self.generate_zip()
    
    def action_download(self):
        """Acción para descargar el archivo ZIP"""
        self.ensure_one()
        if not self.zip_file:
            raise UserError(_("No hay archivo ZIP generado. Use el botón 'Generar ZIP' primero."))
        
        # Buscar el attachment más reciente
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('name', '=', self.zip_filename)
        ], limit=1, order='id desc')
        
        if attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
        else:
            # Si no hay attachment, crear uno nuevo
            attachment = self.env['ir.attachment'].create({
                'name': self.zip_filename,
                'type': 'binary',
                'datas': self.zip_file,
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/zip'
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
    
    def action_view_invoices(self):
        """Ver las facturas del lote"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas del Lote'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.move_ids.ids)],
            'context': self.env.context,
        }
    
    def action_view_validated_invoices(self):
        """Ver solo las facturas validadas del lote"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas Validadas'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.validated_move_ids.ids)],
            'context': {
                'default_search_rips_validation_status': 'validated',
                'group_by': ['rips_validation_status']
            },
        }
    
    def action_view_pending_invoices(self):
        """Ver solo las facturas pendientes del lote"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas Pendientes'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.pending_move_ids.ids)],
            'context': {
                'group_by': ['rips_validation_status']
            },
        }
    
    def action_view_error_invoices(self):
        """Ver solo las facturas con errores del lote"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas con Errores'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.error_move_ids.ids)],
            'context': {
                'default_search_rips_validation_status': 'rejected',
                'group_by': ['rips_validation_status']
            },
        }