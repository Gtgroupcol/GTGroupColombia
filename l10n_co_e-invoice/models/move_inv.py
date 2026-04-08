# -*- coding: utf-8 -*-
import datetime
from datetime import timedelta, date
import hashlib
import logging
import pyqrcode
import zipfile
import pytz
import json
from unidecode import unidecode
from collections import defaultdict
from contextlib import contextmanager
from functools import lru_cache
from odoo import api, fields, models, Command, _
import base64
from odoo.tools.misc import formatLang, format_date, get_lang, groupby
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError
from lxml import etree
from io import BytesIO
from xml.sax import saxutils
import xml.etree.ElementTree as ET
import html
_logger = logging.getLogger(__name__)
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.ERROR)
from . import global_functions
from pytz import timezone
from requests import post, exceptions
from lxml import etree
from odoo import models, fields, _, api
import logging
_logger = logging.getLogger(__name__)
import unicodedata
from odoo.tools.image import image_data_uri
import ssl
from html2text import html2text
import logging

from decimal import Decimal, ROUND_HALF_UP
from odoo.tools import convert_file, html2plaintext, is_html_empty
ssl._create_default_https_context = ssl._create_unverified_context
DIAN = {'wsdl-hab': 'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc?wsdl',
        'wsdl': 'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl',
        'catalogo-hab': 'https://catalogo-vpfe-hab.dian.gov.co/Document/FindDocument?documentKey={}&partitionKey={}&emissionDate={}',
        'catalogo': 'https://catalogo-vpfe.dian.gov.co/Document/FindDocument?documentKey={}&partitionKey={}&emissionDate={}'}

TYPE_DOC_NAME = {
    'invoice': _('Invoice'),
    'credit': _('Credit Note'),
    'debit': _('Debit Note')
}

EDI_OPERATION_TYPE = [
    ('10', 'Estandar'),
    ('09', 'AIU'),
    ('11', 'Mandatos'),
]
from . import xml_utils
from lxml.etree import CDATA
from markupsafe import Markup

from base64 import b64encode, b64decode
import io
import zipfile

from odoo.tools import html_escape, cleanup_xml_node
EVENT_CODES = [
    ('02', '[02] Documento validado por la DIAN'),
    ('04', '[03] Documento rechazado por la DIAN'),
    ('030', '[030] Acuse de recibo'),
    ('031', '[031] Reclamo'),
    ('032', '[032] Recibo del bien'),
    ('033', '[033] Aceptación expresa'),
    ('034', '[034] Aceptación Tácita'),
    ('other', 'Otro')
]

class Invoice(models.Model):
    _inherit = "account.move"

          
    fecha_envio = fields.Datetime(string='Fecha de envío en UTC',copy=False)
    fecha_entrega = fields.Datetime(string='Fecha de entrega',copy=False)
    fecha_xml = fields.Datetime(string='Fecha de factura Publicada',copy=False)
    total_withholding_amount = fields.Float(string='Total de retenciones')
    invoice_trade_sample = fields.Boolean(string='Tiene muestras comerciales',)
    receipt = fields.Boolean(string='Tiene ordenes de entrega?',)
    trade_sample_price = fields.Selection([('01', 'Valor comercial')],   string='Referencia a precio real',  )
    application_response_ids = fields.One2many('dian.application.response','move_id')
    get_status_event_status_code = fields.Selection([('00', 'Procesado Correctamente'),
                                                   ('66', 'NSU no encontrado'),
                                                   ('90', 'TrackId no encontrado'),
                                                   ('99', 'Validaciones contienen errores en campos mandatorios'),
                                                   ('other', 'Other')], string='StatusCode', default=False)
    get_status_event_response = fields.Text(string='Response')
    response_message_dian = fields.Text(string='Response Dian')
    response_eve_dian = fields.Text(string='Response Dian')
    message_error_DIAN_event = fields.Text(string='Response Dian error')
    receipts = fields.One2many("receipt.code","move_id", string="Codigo de entrega")
    titulo_state = fields.Selection([
        ('grey', 'No Titulo Valor'),
        ('red', 'Proceso'),
        ('green', 'Titulo Valor')], string='Titulo Valor', default='grey')

    fe_type = fields.Selection(
        [('01', 'Factura de venta'),
         ('02', 'Factura de exportación'),
         ('03', 'Documento electrónico de transmisión - tipo 03'),
         ('04', 'Factura electrónica de Venta - tipo 04'), 
         ],
        'Tipo De Factura Electronica',
        required=False,
        default='01',
        readonly=False,
    )
    fe_type_ei_ref = fields.Selection(
        [('01', 'Factura de venta'),
         ('02', 'Factura de exportación'),
        # ('03', 'Documento electrónico de transmisión - tipo 03'),
         #('04', 'Factura electrónica de Venta - tipo 04'),
         ('91', 'Nota Crédito'),
         ('92', 'Nota Débito'),
         ('96', 'Eventos (ApplicationResponse)'), ],
        'Tipo de Documento Electronico',
        required=False,
        readonly=True,
        compute='_type_ei_default',
        
    )
    fe_operation_type = fields.Selection(EDI_OPERATION_TYPE,
                                         'Tipo de Operacion',
                                         default='10',
                                         required=True)
    supplier_claim_concept = fields.Selection(
        [
            ('01', 'Documento con inconsistencias'),
            ('02', 'Mercancia no entregada totalmente'),
            ('03', 'Mercancia no entregada parcialmente'),
            ('04', 'Servicio no prestado'),
        ],
        string="Concepto de Reclamo", tracking=True)
    zip_file = fields.Binary('Archivo Zip')
    zip_file_name = fields.Char('File name')
    xml_text = fields.Text('Contenido XML')
    invoice_xml = fields.Text('Factura XML')
    credit_note_count = fields.Integer('# NC', compute='_compute_credit_count')

    def _get_einv_warning(self):
        warn_remaining = False
        inactive_resolution = False
        sequence_id = self.journal_id.sequence_id

        if sequence_id.use_dian_control:
            remaining_numbers = max(5,sequence_id.remaining_numbers)
            remaining_days = max(5,sequence_id.remaining_days)
            date_range = self.env['ir.sequence.dian_resolution'].search(
                [('sequence_id', '=', sequence_id.id),
                 ('active_resolution', '=', True)])
            today = datetime.datetime.strptime(
                str(fields.Date.today(self)),
                '%Y-%m-%d'
            )
            if date_range:
                date_range.ensure_one()
                date_to = datetime.datetime.strptime(
                    str(date_range.date_to),
                    '%Y-%m-%d'
                )
                days = (date_to - today).days
                numbers = date_range.number_to - self.sequence_number
                if numbers < remaining_numbers or days < remaining_days:
                    warn_remaining = True
            else:
                inactive_resolution = True
        self.is_inactive_resolution = inactive_resolution
        self.fe_warning = warn_remaining

    fe_warning = fields.Boolean('¿Advertir por rangos de resolución?',
                                compute='_get_einv_warning',
                                store=False)
    is_inactive_resolution = fields.Boolean('¿Advertir resolución inactiva?',
                                            compute='_get_einv_warning',
                                            store=False)

    last_event_status = fields.Char(string="Último evento exitoso", compute="_compute_last_event_status")

    @api.depends('application_response_ids.status', 'application_response_ids.response_code')
    def _compute_last_event_status(self):
        for record in self:
            last_successful_event = record.application_response_ids.filtered(lambda r: r.status == 'exitoso').sorted(key=lambda r: r.create_date, reverse=True)
            record.last_event_status = last_successful_event[0].response_code if last_successful_event else False

    @api.depends('reversal_move_id')
    def _compute_credit_count(self):
        credit_data = self.env['account.move'].read_group(
            [('reversed_entry_id', 'in', self.ids)],
            ['reversed_entry_id'],
            ['reversed_entry_id']
        )
        data_map = {
            datum['reversed_entry_id'][0]:
            datum['reversed_entry_id_count'] for datum in credit_data
        }
        for inv in self:
            inv.credit_note_count = data_map.get(inv.id, 0.0)

    def action_view_credit_notes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Credit Notes'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('reversed_entry_id', '=', self.id)],
        }

    @api.depends('move_type','partner_id')
    def _type_ei_default(self):
        for rec in self:
            if rec.move_type in ('out_invoice','in_invoice') and not rec.is_debit_note:
                rec.fe_type_ei_ref = '01'
            elif rec.move_type in ('out_invoice','in_invoice') and rec.is_debit_note:
                rec.fe_type_ei_ref =  '92'
            elif rec.move_type in ('out_refund','in_refund'):
                rec.fe_type_ei_ref =  '91'  
            else:
                rec.fe_type_ei_ref =  '01'
    
    def validate_event(self):
        sql = """SELECT am.id 
                FROM account_move am
                WHERE am.titulo_state != 'green' 
                    AND am.move_type = 'out_invoice'
                    AND am.state = 'posted';"""
        self.env.cr.execute(sql)
        sql_result = self.env.cr.dictfetchall()

        # Crear lotes de 40 registros cada uno
        batch_size = 40
        for i in range(0, len(sql_result), batch_size):
            batch = sql_result[i:i + batch_size]
            inv_to_validate_dian = (
                self.env["account.move"].sudo().browse([n.get("id") for n in batch])
            )

            # Procesar cada registro en el lote
            for idian in inv_to_validate_dian:
                try:
                    # Creando un punto de guardado
                    with self.env.cr.savepoint():
                        idian.action_GetStatusevent()
                except Exception as e:
                    _logger.info(f"Error procesando el registro {idian.name}: {e}")


    def _get_status(self):
        return xml_utils._build_and_send_request(
            self,
            payload={
                'track_id': self.cufe,
                'soap_body_template': "l10n_co_e-invoice.get_status",
            },
            service="GetStatus",
            company=self.company_id,
        )

    def _get_attached_document_values(self, original_xml_etree, application_response_etree):
        scheme_mapping = {
            'out_invoice': 'CUFE-SHA384',
            'out_refund': 'CUDE-SHA384',
            'in_invoice': 'CUDS-SHA384',
            'in_refund': 'CUDS-SHA384',
        }
        return {
            'profile_execution_id': original_xml_etree.findtext('./{*}ProfileExecutionID'),
            'id': original_xml_etree.findtext('./{*}ID'),
            'uuid': self.cufe,
            'uuid_attrs': {
                'scheme_name': str(scheme_mapping.get(self.move_type, "CUFE-SHA384")),
            },
            'issue_date': original_xml_etree.findtext('./{*}IssueDate'),
            'issue_time': original_xml_etree.findtext('./{*}IssueTime'),
            'document_type': "Contenedor de Factura Electrónica",
            'parent_document_id': original_xml_etree.findtext('./{*}ID'),
            'parent_document': {
                'id': original_xml_etree.findtext('./{*}ID'),
                'uuid': self.cufe,
                'uuid_attrs': {
                    'scheme_name': str(scheme_mapping.get(self.move_type, "CUFE-SHA384")),
                },
                'issue_date': application_response_etree.findtext('./{*}IssueDate'),
                'issue_time': application_response_etree.findtext('./{*}IssueTime'),
                'response_code': application_response_etree.findtext('.//{*}Response/{*}ResponseCode'),
                'validation_date': application_response_etree.findtext('./{*}IssueDate'),
                'validation_time': application_response_etree.findtext('./{*}IssueTime'),
            },
        }
        
    def _update_uuid_values(self,move, xml_content):
        """Reemplaza los valores UUID en el XML con el valor correcto"""
        if not self.cufe:
            return xml_content
        
        if not isinstance(xml_content, str):
            xml_content = xml_content.decode('utf-8')
        
        import re
        
        qr_pattern = r'(CUFE=)[a-f0-9]+'
        xml_content = re.sub(qr_pattern, r'\1' + move.cufe, xml_content)
        
        url_pattern = r'(documentkey=)[a-f0-9]+'
        xml_content = re.sub(url_pattern, r'\1' + move.cufe, xml_content)
        
        uuid_pattern = r'(<cbc:UUID[^>]*>)[a-f0-9]+(<\/cbc:UUID>)'
        xml_content = re.sub(uuid_pattern, r'\1' + self.cufe + r'\2', xml_content)
        
        return xml_content 
    
    def _get_attached_document(self, xml=False):
        """ Return a tuple: (the attached document xml, an error message) """
        self.ensure_one()
        
        status_response = self._get_status()
        if status_response['status_code'] != 200:
            return "", _(
                "Error %(code)s when calling the DIAN server: %(response)s",
                code=status_response['status_code'],
                response=status_response['response'],
            )
        status_etree = etree.fromstring(status_response['response'])
        application_response = b64decode(status_etree.findtext(".//{*}XmlBase64Bytes"))
        original_xml_etree = etree.fromstring(self.diancode_id.invoice_id.raw)
        if xml:
            original_xml_etree = etree.fromstring(xml)
        
        vals = self._get_attached_document_values(
            original_xml_etree=original_xml_etree,
            application_response_etree=etree.fromstring(application_response),
        )
        attached_document = self.env['ir.qweb']._render('l10n_co_e-invoice.attached_document_template', vals)
        attached_doc_etree = etree.fromstring(attached_document)
        
        import copy
        
        supplier_node = original_xml_etree.find('./{*}AccountingSupplierParty//{*}PartyTaxScheme')
        customer_node = original_xml_etree.find('./{*}AccountingCustomerParty//{*}PartyTaxScheme')
        
        if supplier_node is not None:
            supplier_copy = copy.deepcopy(supplier_node)
            attached_doc_etree.find('./{*}SenderParty').append(supplier_copy)
        
        if customer_node is not None:
            customer_copy = copy.deepcopy(customer_node)
            attached_doc_etree.find('./{*}ReceiverParty').append(customer_copy)
        
        # Convertir a CDATA
        attached_doc_etree.find('./{*}Attachment/{*}ExternalReference/{*}Description').text = CDATA(etree.tostring(original_xml_etree).decode())
        attached_doc_etree.find('./{*}ParentDocumentLineReference//{*}Description').text = CDATA(application_response.decode())
        
        return etree.tostring(cleanup_xml_node(attached_doc_etree), encoding="UTF-8", xml_declaration=True), ""

    def action_get_attached_document(self):
        self.ensure_one()
        attached_document, error = self._get_attached_document()
        if error:
            raise UserError(error)
        attachment = self.env['ir.attachment'].create({
            'raw': attached_document,
            'name': self.name + '_manual.xml',
            'res_model': 'account.move',
            'res_id': self.id,
        })
        return attachment



    def action_send_and_print(self):
        self.ensure_one()
        
        if any(not x.is_sale_document(include_receipts=True) for x in self):
            raise UserError(_("You can only send sales documents"))
        
        template = self.env.ref('l10n_co_e-invoice.email_template_edi_invoice_dian', raise_if_not_found=False)
        
        xml_document, error = self._get_attached_document()
        if error:
            raise UserError(error)
            
        name_xml = self.diancode_id.xml_file_name
        zip_file_name = name_xml.split(".")[0]
        pdf_file_name = f"{zip_file_name}.pdf"
        
        with BytesIO() as zip_buffer:
            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(name_xml, xml_document)
                
                pdf_content = self.env['ir.actions.report'].sudo()._render_qweb_pdf("account.account_invoices", self.id)[0]
                zip_file.writestr(pdf_file_name, pdf_content)
                
            zip_content = zip_buffer.getvalue()
        
        zip_base64 = base64.b64encode(zip_content).decode()
        
        attachment_data = {
            "res_id": self.id,
            "res_model": "account.move",
            "type": "binary",
            "name": f"{zip_file_name}.zip",
            "datas": zip_base64,
        }
        
        # Actualizar adjuntos en la plantilla
        if template:
            template.sudo().write({
                'attachment_ids': [(5, 0, 0), (0, 0, attachment_data)]
            })
        
        # Crear registro del documento XML
        self.env['ir.attachment'].create({
            'raw': xml_document,
            'name': f'{self.name}_manual.xml',
            'res_model': 'account.move',
            'res_id': self.id,
        })
        
        # Retornar acción para enviar correo
        return {
            'name': _("Send"),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.move.send',
            'target': 'new',
            'context': {
                'active_ids': self.ids,
                'default_mail_template_id': template and template.id or False,
            },
        }


   
   
    
    def dian_preview(self):
        for rec in self:
            if rec.cufe:
                return {
                    'type': 'ir.actions.act_url',
                    'target': 'new',
                    'url': 'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey=' + rec.cufe,
                }

    def dian_pdf_view(self):
        for rec in self:
            if rec.cufe:
                return {
                    'type': 'ir.actions.act_url',
                    'target': 'new',
                    'url': 'https://catalogo-vpfe.dian.gov.co/Document/DownloadPDF?trackId=' + rec.cufe,
                }

    def action_open_dian_page(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('dian.verification_page_url', 'https://catalogo-vpfe.dian.gov.co/document/searchqr')
        if not base_url:
            self.env['ir.config_parameter'].sudo().set_param('dian.verification_page_url', 'https://catalogo-vpfe.dian.gov.co/document/searchqr')
        return {
            'type': 'ir.actions.act_url',
            'url': f"{base_url}?documentkey={self.cufe_cuds_other_system}",
            'target': 'new',
        }

    @api.depends('application_response_ids')
    def _compute_titulo_state(self):
        kanban_state = 'grey'
        for rec in self:
            for event in rec.application_response_ids:
                if event.response_code in ('034','033') and event.status == "exitoso":
                    kanban_state = 'green'
            rec.titulo_state = kanban_state

    def add_application_response(self):
        for rec in self:
            response_code = rec._context.get('response_code')
            ar = self.env['dian.application.response'].generate_from_electronic_invoice(rec.id, response_code)


    def _get_GetStatus_values(self):
        xml_soap_values = global_functions.get_xml_soap_values(
            self.company_id.certificate_file,
            self.company_id.certificate_key)
        cufe = self.cufe or self.ei_uuid
        if self.move_type == "in_invoice":
            cufe = self.cufe_cuds_other_system
        xml_soap_values['trackId'] = cufe
        return xml_soap_values

    def action_GetStatus(self):
        wsdl = DIAN['wsdl-hab']
        if self.company_id.production:
            wsdl = DIAN['wsdl']
        GetStatus_values = self._get_GetStatus_values()
        GetStatus_values['To'] = wsdl.replace('?wsdl', '')
        xml_soap_with_signature = global_functions.get_xml_soap_with_signature(
            global_functions.get_template_xml(GetStatus_values, 'GetStatus'),
            GetStatus_values['Id'],
            self.company_id.certificate_file,
            self.company_id.certificate_key)
        response = post(
            wsdl,
            headers={'content-type': 'application/soap+xml;charset=utf-8'},
            data=etree.tostring(xml_soap_with_signature, encoding="unicode"))

        if response.status_code == 200:
            self._get_status_response(response,send_mail=False)
        else:
            raise ValidationError(response.status_code)

        return True

    def action_GetStatusevent(self):
        wsdl = DIAN['wsdl-hab']

        if self.company_id.production:
            wsdl = DIAN['wsdl']

        GetStatus_values = self._get_GetStatus_values()
        GetStatus_values['To'] = wsdl.replace('?wsdl', '')
        xml_soap_with_signature = global_functions.get_xml_soap_with_signature(
            global_functions.get_template_xml(GetStatus_values, 'GetStatusEvent'),
            GetStatus_values['Id'],
            self.company_id.certificate_file,
            self.company_id.certificate_key)

        response = post(
            wsdl,
            headers={'content-type': 'application/soap+xml;charset=utf-8'},
            data=etree.tostring(xml_soap_with_signature, encoding="unicode"))

        if response.status_code == 200:
            self._get_status_response(response,send_mail=False)
        else:
            raise ValidationError(response.status_code)

        return True

    def create_records_from_xml(self):
        if not hasattr(self, 'message_error_DIAN_event') or not self.message_error_DIAN_event:
            return
        ar = self.env['dian.application.response']
        xml_string = self.message_error_DIAN_event  # Your XML string
        xml_bytes = xml_string.encode('utf-8')  # Convert to bytes
        root = etree.fromstring(xml_bytes)
        document_responses = []
        titulo_value = 'grey'
        for doc_response in root.findall('.//cac:DocumentResponse', namespaces=root.nsmap):
            if doc_response.find('.//cbc:ResponseCode', namespaces=root.nsmap).text in ['034', '033']:
                titulo_value = 'green'
            response_data = {
                'response_code': doc_response.find('.//cbc:ResponseCode', namespaces=root.nsmap).text,
                'name': doc_response.find('.//cbc:Description', namespaces=root.nsmap).text,
                'issue_date': doc_response.find('.//cbc:EffectiveDate', namespaces=root.nsmap).text,
                'move_id': self.id,
                'status': "exitoso",
                'dian_get': True,
                'response_message_dian': 'Procesado Correctamente',
            }
            doc_reference = doc_response.find('.//cac:DocumentReference', namespaces=root.nsmap)
            response_data['number'] = doc_reference.find('.//cbc:ID', namespaces=root.nsmap).text
            response_data['cude'] = doc_reference.find('.//cbc:UUID', namespaces=root.nsmap).text
            existing_record = ar.search([('cude', '=', response_data['cude'])], limit=1)
            if not existing_record:
                document_responses.append(response_data)
            else:
                continue 
        if document_responses or doc_response:
            if document_responses:
                ar.create(document_responses)
            self.titulo_state = titulo_value


    def _get_status_response(self, response, send_mail):
        b = "http://schemas.datacontract.org/2004/07/DianResponse"
        c = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"
        s = "http://www.w3.org/2003/05/soap-envelope"
        strings = ''
        to_return = True
        status_code = 'other'
        root = etree.fromstring(response.content)
        date_invoice = self.invoice_date
        root2 = etree.tostring(root, pretty_print=True).decode()
        if not date_invoice:
            date_invoice = fields.Date.today()

        for element in root.iter("{%s}StatusCode" % b):
            if element.text in ('0', '00', '66', '90', '99'):
                # if element.text == '00':
                #     self.write({'state': 'exitoso'})

                    # if self.get_status_zip_status_code != '00':
                    #     if (self.move_type == "out_invoice"):
                    #         #self.company_id.out_invoice_sent += 1
                    #     elif (self.move_type == "out_refund" and self.document_type != "d"):
                    #         #self.company_id.out_refund_sent += 1
                    #     elif (self.move_type == "out_invoice" and self.document_type == "d"):
                    #         #self.company_id.out_refund_sent += 1

                status_code = element.text
        if status_code == '0':
            self.action_GetStatus()
            return True
        if status_code == '00':
            for element in root.iter("{%s}StatusMessage" % b):
                strings = element.text
            for element in root.iter("{%s}XmlBase64Bytes" % b):
                self.write({'message_error_DIAN_event': base64.b64decode(element.text).decode('utf-8') })
            #if not self.mail_sent:
            #    self.action_send_mail()
            to_return = True
        else:
            if send_mail:
                #self.send_failure_email()
            #self.send_failure_email()
                to_return = True
        for element in root.iter("{%s}string" % c):
            if strings == '':
                strings = '- ' + element.text
            else:
                strings += '\n\n- ' + element.text
        if strings == '':
            for element in root.iter("{%s}Body" % s):
                strings = etree.tostring(element, pretty_print=True)
            if strings == '':
                strings = etree.tostring(root, pretty_print=True)
        self.write({
            'get_status_event_status_code': status_code,
            'get_status_event_response': strings,
            'response_eve_dian' : strings})
        self.create_records_from_xml()
        return True

    @api.model
    def _get_time(self):
        fmt = "%H:%M:%S"
        now_utc = datetime.now(timezone("UTC"))
        now_time = now_utc.strftime(fmt)
        return now_time

    @api.model
    def _get_time_colombia(self):
        fmt = "%H:%M:%S-05:00"
        now_utc = datetime.datetime.now(timezone("UTC"))
        now_time = now_utc.strftime(fmt)
        return now_time

    def calcular_texto_descuento(self, id):

        if id == '00':
            return 'Descuento no condicionado'
        elif id == '01':
            return 'Descuento condicionado'
        else:
            return ''
    
    @staticmethod
    def _str_to_datetime(date):
        date = date.replace(tzinfo=pytz.timezone('UTC'))
        return date
        
    def generar_invoice_tax(self, invoice):
        invoice.fecha_xml = fields.Datetime.to_string(datetime.datetime.now(tz=timezone('America/Bogota')))
        invoice.fecha_entrega = invoice.fecha_entrega or fields.Datetime.to_string(datetime.datetime.now(tz=timezone('America/Bogota')))
        
        calculation_rate = invoice.currency_id.inverse_rate if invoice.currency_id.name != 'COP' else 1
        
        tax_total_values = {}
        ret_total_values = {}
        invoice_lines = []
        tax_exclusive_amount = 0
        tax_exclusive_amount_discount = 0
        total_impuestos = 0
        invoice.total_withholding_amount = 0.0

        rete_cop = {'rete_fue_cop': 0.0, 'rete_iva_cop': 0.0, 'rete_ica_cop': 0.0}
        tax_cop = {'tot_iva_cop': 0.0, 'tot_inc_cop': 0.0, 'tot_bol_cop': 0.0, 'imp_otro_cop': 0.0}

        def update_tax_values(tax_dict, tax, line):
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = tax.compute_all(price_unit, line.currency_id, line.quantity, line.product_id, invoice.partner_id)
            
            if tax.codigo_dian not in tax_dict:
                tax_dict[tax.codigo_dian] = {'total': 0, 'info': {}}
            
            if tax.amount not in tax_dict[tax.codigo_dian]['info']:
                tax_dict[tax.codigo_dian]['info'][tax.amount] = {
                    'taxable_amount': abs(taxes['total_excluded'] * calculation_rate),
                    'value': abs(sum(t['amount'] for t in taxes['taxes']) * calculation_rate),
                    'technical_name': tax.nombre_dian,
                    'amount_type': tax.amount_type,
                    'per_unit_amount': abs(tax.amount),
                }
            else:
                info = tax_dict[tax.codigo_dian]['info'][tax.amount]
                info['taxable_amount'] += abs(taxes['total_excluded'] * calculation_rate)
                info['value'] += abs(sum(t['amount'] for t in taxes['taxes']) * calculation_rate)
            
            tax_dict[tax.codigo_dian]['total'] += abs(sum(t['amount'] for t in taxes['taxes']) * calculation_rate)

        for line in invoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product' and not l.product_id.enable_charges):
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_ids.filtered(lambda t: t.tributes != 'ZZ').compute_all(price_unit, line.currency_id, line.quantity, line.product_id, invoice.partner_id)
            
            tax_exclusive_amount += taxes['total_excluded'] * calculation_rate

            for tax in line.tax_ids:
                if tax.tributes == 'ZZ':
                    continue
                if tax.amount >= 0:
                    update_tax_values(tax_total_values, tax, line)
                else:
                    update_tax_values(ret_total_values, tax, line)

        invoice.total_withholding_amount = round(sum(abs(ret['total']) for ret in ret_total_values.values()), 2)
        total_impuestos += sum(value['total'] for tax, value in tax_total_values.items())

        for index, line in enumerate(invoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product' and l.price_unit >= 0)):
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_ids.filtered(lambda t: t.tributes != 'ZZ').compute_all(price_unit, line.currency_id, line.quantity, line.product_id, invoice.partner_id)

            tax_info = {}
            ret_info = {}
            for tax in line.tax_ids:
                if tax.amount >= 0 and tax.tributes != 'ZZ':
                    update_tax_values(tax_info, tax, line)
                elif tax.tributes == '06':
                    update_tax_values(ret_info, tax, line)

            discount_line = round(line.price_unit * line.quantity * line.discount / 100 * calculation_rate,2) if line.discount else 0
            discount_percentage = line.discount or 0
            base_discount = line.price_unit * line.quantity * calculation_rate if line.discount else 0
            tax_exclusive_amount_discount += discount_line
            if not line.product_id.enable_charges:
                code = invoice._get_product_code(line)
                mapa_line = invoice._prepare_invoice_line_data(line, index, tax_info, ret_info, discount_line, 
                                                            discount_percentage, base_discount, code, taxes, calculation_rate)
                invoice_lines.append(mapa_line)
        
        amount_untaxed_signed = abs(invoice.amount_untaxed_signed)
        tax_exclusive_amount_decimal = tax_exclusive_amount
        rounding_difference = 0.0
        rounding_discount = 0.0
        rounding_charge = 0.0
        rounding_lines = invoice.line_ids.filtered(lambda line:
            line.display_type == 'rounding' or
            (line.product_id.default_code == 'RED' and line.product_id.enable_charges)
        )

        total_rounding = sum(rounding_lines.mapped('balance'))
        if invoice.move_type == 'out_refund':
            total_rounding = total_rounding *-1
        if total_rounding < 0:
            rounding_charge = float(total_rounding)
        else:
            rounding_discount = float(abs(total_rounding))
            tax_exclusive_amount_decimal += rounding_discount
        is_charge = total_rounding < 0
        adjustment_amount = abs(total_rounding)
        rounding_adjustment_data = None
        if adjustment_amount != 0:
            multiplier = round(((adjustment_amount / tax_exclusive_amount_decimal) * 100), 6) if tax_exclusive_amount_decimal != 0 else 0
            rounding_adjustment_data = {
                'ID': '3' if is_charge else '2',
                'ChargeIndicator': 'true' if is_charge else 'false',
                'AllowanceChargeReason': 'Cargo por ajuste al peso' if is_charge else 'Descuento por ajuste al peso',
                'MultiplierFactorNumeric': '{:.6f}'.format(multiplier),
                'Amount': '{:.2f}'.format(abs(adjustment_amount)),
                'BaseAmount': '{:.2f}'.format(abs(tax_exclusive_amount_decimal)),
                'CurrencyID': invoice.currency_id.name
            }
        #tax_exclusive_amount += rounding_difference
        # Cálculo de CUFE/CUDS y QR
        cufe_cuds, qr, cude_seed, qr_code = invoice.calcular_cufe_cuds(tax_total_values, abs(tax_exclusive_amount), rounding_charge, rounding_discount,total_impuestos)
        
        # Generación de XML para impuestos y retenciones
        tax_xml = invoice.generate_tax_xml(tax_total_values, invoice_lines, invoice.company_id.currency_id.name)
        ret_xml = invoice.generate_ret_xml(ret_total_values, invoice.company_id.currency_id.name)
        line = invoice.create_invoice_lines(invoice_lines,invoice.company_id.currency_id.name)
        if invoice.currency_id.name != 'COP':
            rete_cop, tax_cop = invoice.calculate_cop_taxes(tax_total_values, ret_total_values, calculation_rate)
        return {
            'cufe': cufe_cuds,
            'cude_seed': cude_seed,
            'qr': qr,
            'qr_code': qr_code,
            'tax_xml': tax_xml,
            'ret_xml': ret_xml,
            'rounding_discount':abs(rounding_discount),
            'rounding_charge': abs(rounding_charge),
            'ret_total_values': ret_total_values,
            'tax_total_values': tax_total_values,
            'invoice_lines': invoice_lines,
            'line': line,
            'invoice_note': invoice.remove_accents(html2plaintext(invoice.narration)) if not is_html_empty(invoice.narration) else '',
            'invoice_customer_commercial_registration': invoice.get_customer_commercial_registration(),
            'ContactName': invoice.partner_contact_id.name,
            'ContactTelephone': invoice.partner_contact_id.phone or '',
            'ContactElectronicMail': invoice.partner_contact_id.email or '',
            'line_extension_amount': '{:.2f}'.format(tax_exclusive_amount),
            'tax_inclusive_amount': '{:.2f}'.format(tax_exclusive_amount + total_impuestos),
            'tax_exclusive_amount': '{:.2f}'.format(tax_exclusive_amount),
            'payable_amount': '{:.2f}'.format(abs(tax_exclusive_amount + total_impuestos - rounding_discount + rounding_charge)), #'{:.2f}'.format(abs(tax_exclusive_amount + total_impuestos - rounding_discount + rounding_charge)),
            'rete_fue_cop': rete_cop['rete_fue_cop'],
            'rete_iva_cop': rete_cop['rete_iva_cop'],
            'rete_ica_cop': rete_cop['rete_ica_cop'],
            'tot_iva_cop': tax_cop['tot_iva_cop'],
            'tot_inc_cop': tax_cop['tot_inc_cop'],
            'tot_bol_cop': tax_cop['tot_bol_cop'],
            'imp_otro_cop': tax_cop['imp_otro_cop'],
            'rounding_adjustment_data': rounding_adjustment_data,
            'fixed_taxes': {},  # Campo para futura implementación de impuestos fijos
        }

    def _get_product_code(self, line):
        if line.move_id.fe_type == '02':
            if not line.product_id.product_UNSPSC_id:
                raise UserError(_('Las facturas de exportación requieren un código aduanero en todos los productos, completa esta información antes de validar la factura.'))
            return [line.product_id.product_UNSPSC_id.product, '020', '195', 'Partida Arancelarias']
        if line.product_id.barcode:
            return [line.product_id.barcode, '010', '9', 'GTIN']
        elif line.product_id.unspsc_code_id:
            return [line.product_id.unspsc_code_id.code, '001', '10', 'UNSPSC']
        elif line.product_id.default_code:
            return [line.product_id.default_code, '999', '', 'Estándar de adopción del contribuyente']
        return ['NA', '999', '', 'Estándar de adopción del contribuyente']

    def _prepare_invoice_line_data(self, line, index, tax_info, ret_info, discount_line, discount_percentage, base_discount, code, taxes, calculation_rate):
        if not line.name:
            raise ValidationError('Verificar que todas las líneas de la factura tenga el campo etiqueta')
        return {
            'id': index + 1,
            'product_id': line.product_id,
            'invoiced_quantity': line.quantity,
            'uom_product_id': line.product_uom_id,
            'line_extension_amount': taxes['total_excluded'] * calculation_rate,
            'item_description': saxutils.escape(line.name),
            'price': (taxes['total_excluded'] / line.quantity) * calculation_rate,
            'total_amount_tax': sum(tax['amount'] for tax in taxes['taxes'] if tax['amount'] > 0) * calculation_rate,
            'tax_info': tax_info,
            'ret_info': ret_info,
            'discount': discount_line,
            'discount_percentage': discount_percentage,
            'base_discount': base_discount,
            'invoice_start_date': datetime.datetime.now().astimezone(pytz.timezone("America/Bogota")).strftime('%Y-%m-%d'),
            'transmission_type_code': 1,
            'transmission_description': 'Por operación',
            'discount_text': self.calcular_texto_descuento(line.invoice_discount_text),
            'discount_code': line.invoice_discount_text,
            'multiplier_discount': discount_percentage,
            'line_trade_sample_price': line.line_trade_sample_price * calculation_rate,
            'line_price_reference': (line.line_price_reference * line.quantity) * calculation_rate,
            'brand_name': line.product_id.brand_id.name,
            'model_name': line.product_id.model_id.name,
            'StandardItemIdentificationID': code[0],
            'StandardItemIdentificationschemeID': code[1],
            'StandardItemIdentificationschemeAgencyID': code[2],
            'StandardItemIdentificationschemeName': code[3]
        }

    def get_customer_commercial_registration(self):
        if self.partner_id and self.partner_id.business_name:
            return self.partner_id.business_name
        elif not self.partner_id and self.partner_id.parent_id.business_name:
            return self.partner_id.parent_id.business_name
        else:
            return 0

    def calculate_cop_taxes(self, tax_total_values, ret_total_values, calculation_rate):
        rete_cop = {'rete_fue_cop': 0.0, 'rete_iva_cop': 0.0, 'rete_ica_cop': 0.0}
        tax_cop = {'tot_iva_cop': 0.0, 'tot_inc_cop': 0.0, 'tot_bol_cop': 0.0, 'imp_otro_cop': 0.0}
        
        for tax_type, ret_total in ret_total_values.items():
            if tax_type == '05':
                rete_cop['rete_iva_cop'] = abs(ret_total['total']) * calculation_rate
            elif tax_type == '06':
                rete_cop['rete_fue_cop'] = abs(ret_total['total']) * calculation_rate
            elif tax_type == '07':
                rete_cop['rete_ica_cop'] = abs(ret_total['total']) * calculation_rate
        
        for tax_type, tax_total in tax_total_values.items():
            if tax_type == '01':
                tax_cop['tot_iva_cop'] = tax_total['total'] * calculation_rate
            elif tax_type == '04':
                tax_cop['tot_inc_cop'] = tax_total['total'] * calculation_rate
            elif tax_type == '22':
                tax_cop['tot_bol_cop'] = tax_total['total'] * calculation_rate
            else:
                tax_cop['imp_otro_cop'] += tax_total['total'] * calculation_rate
        
        return rete_cop, tax_cop

    def calcular_cufe_cuds(self, tax_total_values, amount_untaxed, rounding_charge, rounding_discount,total_impuestos):
        if self.move_type in ["out_invoice", "out_refund"]:
            return self.calcular_cufe(tax_total_values, amount_untaxed, rounding_charge, rounding_discount,total_impuestos)
        elif self.move_type in ["in_invoice", "in_refund"]:
            return self.calcular_cuds(tax_total_values, amount_untaxed, rounding_charge, rounding_discount,total_impuestos)

    def _generate_qr_code(self, silent_errors=False):
        self.ensure_one()
        if self.company_id.country_code == 'CO':
            payment_url = self.diancode_id.qr_data or self.cufe_seed
            barcode = self.env['ir.actions.report'].barcode(barcode_type="QR", value=payment_url, width=120, height=120)
            return image_data_uri(base64.b64encode(barcode))
        return super()._generate_qr_code(silent_errors)

    def calcular_cufe(self, tax_total_values, amount_untaxed, rounding_charge, rounding_discount, total_impuestos):
        rec_active_resolution = (self.journal_id.sequence_id.dian_resolution_ids.filtered(lambda r: r.active_resolution))
        create_date = self._str_to_datetime(self.fecha_xml)
        tax_computed_values = {tax: value['total'] for tax, value in tax_total_values.items()}

        numfac = self.name
        fecfac = self.fecha_xml.date().isoformat()
        horfac = self.fecha_xml.strftime("%H:%M:%S-05:00")
        valfac = '{:.2f}'.format(amount_untaxed)
        codimp1 = '01'
        valimp1 = '{:.2f}'.format(tax_computed_values.get('01', 0))
        codimp2 = '04'
        valimp2 = '{:.2f}'.format(tax_computed_values.get('04', 0))
        codimp3 = '03'
        valimp3 = '{:.2f}'.format(tax_computed_values.get('03', 0))
        valtot = '{:.2f}'.format(abs(amount_untaxed + total_impuestos - rounding_discount + rounding_charge))
        contacto_compañia = self.company_id.partner_id
        nitofe = str(contacto_compañia.vat_co)
        if self.company_id.production:
            tipoambiente = '1'
        else:
            tipoambiente = '2'
        numadq = str(self.partner_id.vat_co) or str(self.partner_id.parent_id.vat_co)
        if self.move_type == 'out_invoice' and not self.is_debit_note:
            citec = rec_active_resolution.technical_key
        else:
            citec = self.company_id.software_pin

        total_otros_impuestos = sum([value for key, value in tax_computed_values.items() if key != '01'])
        iva = tax_computed_values.get('01', '0.00')
        #1
        cufe = unidecode(
            str(numfac) + str(fecfac) + str(horfac) + str(valfac) + str(codimp1) + str(valimp1) + str(codimp2) +
            str(valimp2) + str(codimp3) + str(valimp3) + str(valtot) + str(nitofe) + str(numadq) + str(citec) +
            str(tipoambiente))
        cufe_seed = cufe

        sha384 = hashlib.sha384()
        sha384.update(cufe.encode())
        cufe = sha384.hexdigest()

        qr_code = 'NumFac: {}\n' \
                  'FecFac: {}\n' \
                  'HorFac: {}\n' \
                  'NitFac: {}\n' \
                  'DocAdq: {}\n' \
                  'ValFac: {}\n' \
                  'ValIva: {}\n' \
                  'ValOtroIm: {:.2f}\n' \
                  'ValFacIm: {}\n' \
                  'CUFE: {}'.format(
                    numfac,
                    fecfac,
                    horfac,
                    nitofe,
                    numadq,
                    valfac,
                    iva,
                    total_otros_impuestos,
                    valtot,
                    cufe
                    )

        qr = pyqrcode.create(qr_code, error='L')
        return cufe, qr.png_as_base64_str(scale=2), cufe_seed, qr_code

    def calcular_cuds(self, tax_total_values, amount_untaxed, rounding_charge, rounding_discount,total_impuestos):
        create_date = self._str_to_datetime(self.fecha_xml)
        tax_computed_values = {tax: value['total'] for tax, value in tax_total_values.items()}
        numfac = self.name
        fecfac = self.fecha_xml.date().isoformat()
        horfac = self.fecha_xml.strftime("%H:%M:%S-05:00")
        valfac = '{:.2f}'.format(amount_untaxed)
        codimp1 = '01'
        valimp1 = '{:.2f}'.format(tax_computed_values.get('01', 0))
        valtot = '{:.2f}'.format(abs(amount_untaxed + total_impuestos - rounding_discount + rounding_charge)) if self.move_type != 'entry' else '{:.2f}'.format(abs(self.amount_total))
        company_contact = self.company_id.partner_id
        nitofe = str(company_contact.vat_co)
        if self.company_id.production:
            tipoambiente = '1'
        else:
            tipoambiente = '2'
        numadq = str(self.partner_id.vat_co) or str(self.partner_id.parent_id.vat_co)
        citec = self.company_id.software_pin

        total_otros_impuestos = sum([value for key, value in tax_computed_values.items() if key != '01'])
        iva = tax_computed_values.get('01', '0.00')

        cuds =  unidecode(
            str(numfac) + str(fecfac) + str(horfac) + str(valfac) + str(codimp1) + str(valimp1) + str(valtot) +
            str(numadq) + str(nitofe) + str(citec) + str(tipoambiente)
        )
        cuds_seed = cuds

        sha384 = hashlib.sha384()
        sha384.update(cuds.encode())
        cuds = sha384.hexdigest()

        if not self.company_id.production:
            qr_code = 'NumFac: {}\n' \
                    'FecFac: {}\n' \
                    'HorFac: {}\n' \
                    'NitFac: {}\n' \
                    'DocAdq: {}\n' \
                    'ValFac: {}\n' \
                    'ValIva: {}\n' \
                    'ValOtroIm: {:.2f}\n' \
                    'ValFacIm: {}\n' \
                    'CUDS: {}\n' \
                    'https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey={}'.format(
                    numfac,
                    fecfac,
                    horfac,
                    nitofe,
                    numadq,
                    valfac,
                    iva,
                    total_otros_impuestos,
                    valtot,
                    cuds,
                    cuds
                    )
        else:
            qr_code = 'NumFac: {}\n' \
                  'FecFac: {}\n' \
                  'HorFac: {}\n' \
                  'NitFac: {}\n' \
                  'DocAdq: {}\n' \
                  'ValFac: {}\n' \
                  'ValIva: {}\n' \
                  'ValOtroIm: {:.2f}\n' \
                  'ValFacIm: {}\n' \
                  'CUDS: {}\n' \
                  'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={}'.format(
                    numfac,
                    fecfac,
                    horfac,
                    nitofe,
                    numadq,
                    valfac,
                    iva,
                    total_otros_impuestos,
                    valtot,
                    cuds,
                    cuds
                    )

        qr = pyqrcode.create(qr_code, error='L')

        return cuds, qr.png_as_base64_str(scale=2),cuds_seed,qr_code

    @api.model
    def generate_tax_xml(self, tax_total_values, invoice_lines, currency_id):
        xml_content = ""
        total = 0.0
        for tax_id, data in tax_total_values.items():
            if tax_id in ('02','34','33'):
                for invoice_line in invoice_lines:
                    for tax_id, data in invoice_line['tax_info'].items():
                        if tax_id == '02':
                            total += data['total']
                xml_content += "<cac:TaxTotal>\n"
                xml_content += f"   <cbc:TaxAmount currencyID=\"{currency_id}\">{'{:0.2f}'.format(total)}</cbc:TaxAmount>\n"
                xml_content += f"   <cbc:RoundingAmount currencyID=\"{currency_id}\">0</cbc:RoundingAmount>\n"
                for invoice_line in invoice_lines:
                    for tax_id, data in invoice_line['tax_info'].items():
                        if tax_id == '02':
                            for amount, info in data['info'].items():
                                xml_content += "   <cac:TaxSubtotal>\n"
                                xml_content += f"      <cbc:TaxableAmount currencyID=\"{currency_id}\">{info['taxable_amount']}</cbc:TaxableAmount>\n"
                                xml_content += f"      <cbc:TaxAmount currencyID=\"{currency_id}\">{info['value']}</cbc:TaxAmount>\n"
                                xml_content += f"      <cbc:BaseUnitMeasure unitCode=\"NIU\">1</cbc:BaseUnitMeasure>\n"
                                xml_content += f"      <cbc:PerUnitAmount currencyID=\"{currency_id}\">{info['fixed']}</cbc:PerUnitAmount>\n"
                                xml_content += "      <cac:TaxCategory>\n"
                                # xml_content += f"         <cbc:Percent>{'%.2f' % float(amount)}</cbc:Percent>\n"
                                xml_content += "         <cac:TaxScheme>\n"
                                xml_content += f"            <cbc:ID>{tax_id}</cbc:ID>\n"
                                xml_content += f"            <cbc:Name>{info['technical_name']}</cbc:Name>\n"
                                xml_content += "         </cac:TaxScheme>\n"
                                xml_content += "      </cac:TaxCategory>\n"
                                xml_content += "   </cac:TaxSubtotal>\n"
                xml_content += "</cac:TaxTotal>\n"

        # Loop for all other tax IDs
        for tax_id, data in tax_total_values.items():
            if tax_id != '02':
                xml_content += "<cac:TaxTotal>\n"
                xml_content += f"   <cbc:TaxAmount currencyID=\"{currency_id}\">{data['total']}</cbc:TaxAmount>\n"
                xml_content += f"   <cbc:RoundingAmount currencyID=\"{currency_id}\">0</cbc:RoundingAmount>\n"

                for amount, info in data['info'].items():
                    xml_content += "   <cac:TaxSubtotal>\n"
                    xml_content += f"      <cbc:TaxableAmount currencyID=\"{currency_id}\">{info['taxable_amount']}</cbc:TaxableAmount>\n"
                    xml_content += f"      <cbc:TaxAmount currencyID=\"{currency_id}\">{info['value']}</cbc:TaxAmount>\n"
                    xml_content += "      <cac:TaxCategory>\n"
                    xml_content += f"         <cbc:Percent>{'%.2f' % float(amount)}</cbc:Percent>\n"
                    xml_content += "         <cac:TaxScheme>\n"
                    xml_content += f"            <cbc:ID>{tax_id}</cbc:ID>\n"
                    xml_content += f"            <cbc:Name>{info['technical_name']}</cbc:Name>\n"
                    xml_content += "         </cac:TaxScheme>\n"
                    xml_content += "      </cac:TaxCategory>\n"
                    xml_content += "   </cac:TaxSubtotal>\n"

                xml_content += "</cac:TaxTotal>\n"

        return xml_content

    @api.model
    def generate_ret_xml(self, ret_total_values, currency_id):
        all_with_tax_totals = []

        if ret_total_values and self.move_type in ["out_invoice", "in_invoice"] and not self.is_debit_note:
            for tax_id, data in ret_total_values.items():
                # Crear un nuevo nodo WithholdingTaxTotal para cada tipo de impuesto
                with_tax_total = ET.Element('cac:WithholdingTaxTotal')
                ET.SubElement(with_tax_total, 'cbc:TaxAmount', {'currencyID': currency_id}).text = f'{round(data["total"], 2):.2f}'

                for amount, info in data['info'].items():
                    tax_subtotal = ET.SubElement(with_tax_total, 'cac:TaxSubtotal')
                    if tax_id == '06':
                        ET.SubElement(tax_subtotal, 'cbc:TaxableAmount', {'currencyID': currency_id}).text = '%0.2f' %  float(info['taxable_amount'])
                        ET.SubElement(tax_subtotal, 'cbc:TaxAmount', {'currencyID': currency_id}).text = '%0.2f' % float(info['value'])
                    else:
                        ET.SubElement(tax_subtotal, 'cbc:TaxableAmount', {'currencyID': currency_id}).text = '%0.3f' %  float(info['taxable_amount'])
                        ET.SubElement(tax_subtotal, 'cbc:TaxAmount', {'currencyID': currency_id}).text = '%0.3f' % float(info['value'])
                    tax_category = ET.SubElement(tax_subtotal, 'cac:TaxCategory')
                    if tax_id == '06':
                       ET.SubElement(tax_category, 'cbc:Percent').text = '%0.2f' % float(abs(amount))
                    else:
                       ET.SubElement(tax_category, 'cbc:Percent').text = '%0.3f' % float(abs(amount))

                    tax_scheme = ET.SubElement(tax_category, 'cac:TaxScheme')
                    ET.SubElement(tax_scheme, 'cbc:ID').text = str(tax_id)
                    ET.SubElement(tax_scheme, 'cbc:Name').text = str(info['technical_name'])

                # Convertir el nodo WithholdingTaxTotal a una cadena
                with_tax_total_str = ET.tostring(with_tax_total, encoding='utf-8', method='xml').decode('utf-8')
                all_with_tax_totals.append(with_tax_total_str)

        else:
            all_with_tax_totals.append(" ")

        # Unir todos los nodos WithholdingTaxTotal en una sola cadena
        return ''.join(all_with_tax_totals)
    
    @api.model
    def create_invoice_lines(self, invoice_lines, currency_id):
        invoice_lines_tags = []  # Lista para almacenar las etiquetas XML de cada línea de factura

        for invoice_line in invoice_lines:
            if (self.move_type == "out_invoice" and not self.is_debit_note)  or (self.move_type == "in_invoice" and not self.is_debit_note):
                invoice_line_tag = ET.Element('cac:InvoiceLine')
            if  self.is_debit_note:
                invoice_line_tag = ET.Element('cac:DebitNoteLine')
            if self.move_type == "out_refund" or self.move_type == "in_refund":
                invoice_line_tag = ET.Element('cac:CreditNoteLine')
            ET.SubElement(invoice_line_tag, 'cbc:ID').text = str(int(invoice_line.get('id', 0)))
            ET.SubElement(invoice_line_tag, 'cbc:Note').text = str(invoice_line.get('note', ''))
            if (self.move_type == "out_invoice" and not self.is_debit_note)  or (self.move_type == "in_invoice" and not self.is_debit_note):
                if invoice_line.get('uom_product_id') and invoice_line['uom_product_id'].dian_uom_id:
                    ET.SubElement(invoice_line_tag, 'cbc:InvoicedQuantity', {'unitCode': invoice_line['uom_product_id'].dian_uom_id.dian_code}).text = str(invoice_line['invoiced_quantity']) #{'unitCode': invoice_line['uom_product_id'].name}).text = str(invoice_line['invoiced_quantity'])
                else:
                    ET.SubElement(invoice_line_tag, 'cbc:InvoicedQuantity', {'unitCode': "EA"}).text = str(invoice_line['invoiced_quantity'])
            if self.is_debit_note:
                if invoice_line.get('uom_product_id') and invoice_line['uom_product_id'].dian_uom_id:
                    ET.SubElement(invoice_line_tag, 'cbc:DebitedQuantity', {'unitCode': invoice_line['uom_product_id'].dian_uom_id.dian_code}).text = str(invoice_line['invoiced_quantity']) #{'unitCode': invoice_line['uom_product_id'].name}).text = str(invoice_line['invoiced_quantity'])
                else:
                    ET.SubElement(invoice_line_tag, 'cbc:DebitedQuantity', {'unitCode': "EA"}).text = str(invoice_line['invoiced_quantity'])
            if self.move_type == "out_refund" or self.move_type == "in_refund":
                if invoice_line.get('uom_product_id') and invoice_line['uom_product_id'].dian_uom_id:
                    ET.SubElement(invoice_line_tag, 'cbc:CreditedQuantity', {'unitCode': invoice_line['uom_product_id'].dian_uom_id.dian_code}).text = str(invoice_line['invoiced_quantity']) #{'unitCode': invoice_line['uom_product_id'].name}).text = str(invoice_line['invoiced_quantity'])
                else:
                    ET.SubElement(invoice_line_tag, 'cbc:CreditedQuantity', {'unitCode': "EA"}).text = str(invoice_line['invoiced_quantity'])
            ET.SubElement(invoice_line_tag, 'cbc:LineExtensionAmount', {'currencyID': currency_id}).text = str(invoice_line['line_extension_amount'])
            if self.move_type == "in_invoice" and not self.is_debit_note:
                invoice_period = ET.SubElement(invoice_line_tag, "cac:InvoicePeriod")
                ET.SubElement(invoice_period, "cbc:StartDate").text = str(invoice_line['invoice_start_date'])
                ET.SubElement(invoice_period, "cbc:DescriptionCode").text = str(invoice_line['transmission_type_code'])
                ET.SubElement(invoice_period, "cbc:Description").text = str(invoice_line['transmission_description'])
            if invoice_line['line_extension_amount'] == 0:
                pricing_ref = ET.SubElement(invoice_line_tag, 'cac:PricingReference')
                alt_condition_price = ET.SubElement(pricing_ref, 'cac:AlternativeConditionPrice')
                ET.SubElement(alt_condition_price, 'cbc:PriceAmount', {'currencyID': currency_id}).text = str(invoice_line['line_price_reference'])
                ET.SubElement(alt_condition_price, 'cbc:PriceTypeCode').text = str(invoice_line['line_trade_sample_price'])

            if (self.move_type == "out_invoice" and not self.is_debit_note)  or (self.move_type == "in_invoice" and not self.is_debit_note):
                if float(invoice_line.get('line_extension_amount', 0)) > 0 and float(invoice_line.get('discount', 0)) > 0:
                    amount_base = float(invoice_line['line_extension_amount']) + float(invoice_line['discount'])
                    allowance_charge = ET.SubElement(invoice_line_tag, 'cac:AllowanceCharge')
                    ET.SubElement(allowance_charge, 'cbc:ID').text = '1'
                    ET.SubElement(allowance_charge, 'cbc:ChargeIndicator').text = 'false'
                    ET.SubElement(allowance_charge, 'cbc:AllowanceChargeReasonCode').text = invoice_line.get('discount_code')
                    ET.SubElement(allowance_charge, 'cbc:AllowanceChargeReason').text = invoice_line.get('discount_text')
                    ET.SubElement(allowance_charge, 'cbc:MultiplierFactorNumeric').text = str(invoice_line.get('discount_percentage'))
                    ET.SubElement(allowance_charge, 'cbc:Amount', {'currencyID': currency_id}).text = str(invoice_line.get('discount'))
                    ET.SubElement(allowance_charge, 'cbc:BaseAmount', {'currencyID': currency_id}).text = str(amount_base)

                for tax_id, data in invoice_line['tax_info'].items():
                    tax_total = ET.SubElement(invoice_line_tag, 'cac:TaxTotal')
                    ET.SubElement(tax_total, 'cbc:TaxAmount', {'currencyID': currency_id}).text = str(data['total'])
                    ET.SubElement(tax_total, 'cbc:RoundingAmount', {'currencyID': currency_id}).text = '0'
                    for amount, info in data['info'].items():
                        tax_subtotal = ET.SubElement(tax_total, 'cac:TaxSubtotal')
                        ET.SubElement(tax_subtotal, 'cbc:TaxableAmount', {'currencyID': currency_id}).text = '%0.2f' % float(info['taxable_amount'])
                        ET.SubElement(tax_subtotal, 'cbc:TaxAmount', {'currencyID': currency_id}).text = '%0.2f' % float(info['value'])
                        tax_category = ET.SubElement(tax_subtotal, 'cac:TaxCategory')
                        ET.SubElement(tax_category, 'cbc:Percent').text = '{:0.2f}'.format(float(amount))
                        tax_scheme = ET.SubElement(tax_category, 'cac:TaxScheme')
                        ET.SubElement(tax_scheme, 'cbc:ID').text = tax_id
                        ET.SubElement(tax_scheme, 'cbc:Name').text = info['technical_name']
        
            else:
                for tax_id, data in invoice_line['tax_info'].items():
                    tax_total = ET.SubElement(invoice_line_tag, 'cac:TaxTotal')
                    ET.SubElement(tax_total, 'cbc:TaxAmount', {'currencyID': currency_id}).text = '%0.2f' % float(data['total'])
                    ET.SubElement(tax_total, 'cbc:RoundingAmount', {'currencyID': currency_id}).text = '0'
                    for amount, info in data['info'].items():
                        tax_subtotal = ET.SubElement(tax_total, 'cac:TaxSubtotal')
                        ET.SubElement(tax_subtotal, 'cbc:TaxableAmount', {'currencyID': currency_id}).text = '%0.2f' % float(info['taxable_amount'])
                        ET.SubElement(tax_subtotal, 'cbc:TaxAmount', {'currencyID': currency_id}).text = '%0.2f' % float(info['value'])
                        tax_category = ET.SubElement(tax_subtotal, 'cac:TaxCategory')
                        ET.SubElement(tax_category, 'cbc:Percent').text = '{:0.2f}'.format(float(amount))
                        tax_scheme = ET.SubElement(tax_category, 'cac:TaxScheme')
                        ET.SubElement(tax_scheme, 'cbc:ID').text = tax_id
                        ET.SubElement(tax_scheme, 'cbc:Name').text = info['technical_name']
                if float(invoice_line.get('line_extension_amount', 0)) > 0 and float(invoice_line.get('discount', 0)) > 0:
                    amount_base = float(invoice_line['line_extension_amount']) + float(invoice_line['discount'])
                    allowance_charge = ET.SubElement(invoice_line_tag, 'cac:AllowanceCharge')
                    ET.SubElement(allowance_charge, 'cbc:ID').text = '1'
                    ET.SubElement(allowance_charge, 'cbc:ChargeIndicator').text = 'false'
                    ET.SubElement(allowance_charge, 'cbc:AllowanceChargeReasonCode').text = invoice_line.get('discount_code')
                    ET.SubElement(allowance_charge, 'cbc:AllowanceChargeReason').text = invoice_line.get('discount_text')
                    ET.SubElement(allowance_charge, 'cbc:MultiplierFactorNumeric').text = str(invoice_line.get('discount_percentage'))
                    ET.SubElement(allowance_charge, 'cbc:Amount', {'currencyID': currency_id}).text = '%0.2f' % float(invoice_line.get('discount'))
                    ET.SubElement(allowance_charge, 'cbc:BaseAmount', {'currencyID': currency_id}).text = '%0.2f' % float(amount_base)
                    
            item = ET.SubElement(invoice_line_tag, 'cac:Item')
            ET.SubElement(item, 'cbc:Description').text = invoice_line['item_description']
            SellersItemIdentification = ET.SubElement(item, 'cac:SellersItemIdentification')
            ET.SubElement(SellersItemIdentification, 'cbc:ID').text = str(invoice_line['product_id'].default_code)
            standard_item_identification = ET.SubElement(item, 'cac:StandardItemIdentification')
            if self.move_type == "out_invoice" or self.move_type == "out_refund":
                ET.SubElement(standard_item_identification, 'cbc:ID', {'schemeID': str(invoice_line['StandardItemIdentificationschemeID']), 'schemeAgencyID':str(invoice_line['StandardItemIdentificationschemeAgencyID']), 'schemeName':str(invoice_line['StandardItemIdentificationschemeName'])}).text = str(invoice_line['StandardItemIdentificationID'])
            if self.move_type == "in_invoice" or self.move_type == "in_refund":
                ET.SubElement(standard_item_identification, 'cbc:ID', {'schemeID': str(invoice_line['StandardItemIdentificationschemeID']), 'schemeAgencyID':str(invoice_line['StandardItemIdentificationschemeAgencyID']), 'schemeName':str(invoice_line['StandardItemIdentificationschemeName'])}).text = str(invoice_line['StandardItemIdentificationID'])

            price = ET.SubElement(invoice_line_tag, 'cac:Price')
            ET.SubElement(price, 'cbc:PriceAmount', {'currencyID': currency_id}).text = str(invoice_line['price'])
            if invoice_line.get('uom_product_id') and invoice_line['uom_product_id'].dian_uom_id:
                ET.SubElement(price, 'cbc:BaseQuantity', {'unitCode': invoice_line['uom_product_id'].dian_uom_id.dian_code}).text = str(invoice_line['invoiced_quantity'])
            else:
                ET.SubElement(price, 'cbc:BaseQuantity', {'unitCode': "EA"}).text = str(invoice_line['invoiced_quantity'])

            invoice_lines_tags.append(invoice_line_tag)  # Agregar la etiqueta de la línea a la lista

        #return invoice_lines_tags
        xml_str = [ET.tostring(tag, encoding='utf-8', method='xml') for tag in invoice_lines_tags]

        #_logger.info(xml_str)
        #xml_str = ET.tostring(invoice_lines_element, encoding='utf-8', method='xml')
        str_decoded = ''
        for byte_str in xml_str:
            str_decoded += byte_str.decode('utf-8')
            #_logger.info(str_decoded)
        return str_decoded

    def remove_accents(self, chain):
        s = ''.join((c for c in unicodedata.normalize('NFD', chain) if unicodedata.category(c) != 'Mn'))
        return s
class InvoiceLine(models.Model):
    _inherit = "account.move.line"
    line_price_reference = fields.Float(string='Precio de referencia')
    line_trade_sample_price = fields.Selection(string='Tipo precio de referencia',
                                               related='move_id.trade_sample_price')
    line_trade_sample = fields.Boolean(string='Muestra comercial', related='move_id.invoice_trade_sample')
    invoice_discount_text = fields.Selection(
        selection=[
            ('00', 'Descuento no condicionado'),
            ('01', 'Descuento condicionado')
        ],
        string='Motivo de Descuento',
    )

    def _l10n_co_dian_net_price_subtotal(self):
        """ Returns the price subtotal after discount in company currency. """
        self.ensure_one()
        return self.move_id.direction_sign * self.balance

    def _l10n_co_dian_gross_price_subtotal(self):
        """ Returns the price subtotal without discount in company currency. """
        self.ensure_one()
        if self.discount == 100.0:
            return 0.0
        else:
            net_price_subtotal = self._l10n_co_dian_net_price_subtotal()
            return self.company_id.currency_id.round(net_price_subtotal / (1.0 - (self.discount or 0.0) / 100.0))


class receiptCode(models.Model):
    _name = 'receipt.code'
    _description = 'Receipt'

    name = fields.Char('Name')
    move_id = fields.Many2one("account.move")