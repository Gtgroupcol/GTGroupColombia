# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import base64
import requests
import gzip
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging
import re
import xlsxwriter
from io import BytesIO
import ssl
import socket
import certifi
from urllib.parse import urlparse
import urllib3
import math
import os, zipfile
_logger = logging.getLogger(__name__)

# Configuración global RIPS
RIPS_ENDPOINTS = {
    'AUTH': '/api/Auth/LoginSISPRO',
    'CARGAR_FEV_RIPS': '/api/PaquetesFevRips/CargarFevRips',
    'CARGAR_NC': '/api/PaquetesFevRips/CargarNC',
    'CARGAR_NC_TOTAL': '/api/PaquetesFevRips/CargarNCTotal',
    'CARGAR_ND': '/api/PaquetesFevRips/CargarND',
    'CARGAR_NOTA_AJUSTE': '/api/PaquetesFevRips/CargarNotaAjuste',
    'CARGAR_RIPS_SIN_FACTURA': '/api/PaquetesFevRips/CargarRipsSinFactura',
    'CARGAR_NC_ACUERDO_VOLUNTADES': '/api/PaquetesFevRips/CargarNCAcuerdoVoluntades',
    'CARGAR_CAPITA_INICIAL': '/api/PaquetesFevRips/CargarCapitaInicial',
    'CARGAR_CAPITA_PERIODO': '/api/PaquetesFevRips/CargarCapitaPeriodo',
    'CARGAR_CAPITA_FINAL': '/api/PaquetesFevRips/CargarCapitaFinal',
    'CONSULTAR_CUV': '/api/ConsultasFevRips/ConsultarCUV',
    'DESCARGAR_ARCHIVOS': '/api/ConsultasFevRips/DescargarArchivosFevRipsCUV',
}

RIPS_DEFAULT_VALUES = {
    'CODIGO_PRESTADOR': '000000000000',
    'MODALIDAD_ATENCION': '01',
    'GRUPO_SERVICIO_CONSULTA': '01',
    'GRUPO_SERVICIO_PROCEDIMIENTO': '02',
    'GRUPO_SERVICIO_MEDICAMENTO': '02',
    'GRUPO_SERVICIO_OTRO': '04',
    'COD_SERVICIO_CONSULTA': 101,
    'COD_SERVICIO_PROCEDIMIENTO': 706,
    'COD_SERVICIO_MEDICAMENTO': 312,
    'COD_SERVICIO_OTRO': 950,
    'FINALIDAD_CONSULTA': '10',
    'FINALIDAD_PROCEDIMIENTO': '44',
    'CAUSA_EXTERNA': '13',
    'TIPO_DIAGNOSTICO': '01',
    'CONCEPTO_RECAUDO': '05',
    'VIA_INGRESO': '01',
    'DIAGNOSTICO_DEFAULT': 'Z000',
    'PROFESIONAL_DOC_TYPE': 'CC',
    'PROFESIONAL_DOC_NUMBER': '1234567890',
    'CUPS_CONSULTA': '890201',
    'CUPS_PROCEDIMIENTO': '000000',
    'TIPO_USUARIO': '01',
    'ZONA_TERRITORIAL': '01',
    'PAIS_DEFAULT': '170',
    'MUNICIPIO_DEFAULT': '11001',
}

LOAD_TYPE_MAPPING = {
    'CARGAR_FEV_RIPS': 'fev_rips',
    'CARGAR_NC': 'nc',
    'CARGAR_NC_TOTAL': 'nc_total',
    'CARGAR_ND': 'nd',
    'CARGAR_NOTA_AJUSTE': 'nota_ajuste',
    'CARGAR_RIPS_SIN_FACTURA': 'sin_factura',
    'CARGAR_NC_ACUERDO_VOLUNTADES': 'nc_acuerdo',
    'CARGAR_CAPITA_INICIAL': 'capita_inicial',
    'CARGAR_CAPITA_PERIODO': 'capita_periodo',
    'CARGAR_CAPITA_FINAL': 'capita_final',
}


class AbstractRipsFevMixin(models.AbstractModel):
    _name = 'abstract.rips.fev.mixin'
    _description = 'Abstract RIPS FEV Mixin'
    
    # =====================================================
    # CAMPOS RIPS
    # =====================================================
    
    rips_cuv = fields.Char(
        string='CUV (Código Único de Validación)',
        readonly=True,
        copy=False,
        help="Código único asignado por el Ministerio de Salud que certifica la validación del RIPS"
    )
    
    rips_validation_date = fields.Datetime(
        string='Fecha de Validación RIPS',
        readonly=True
    )
    
    rips_validation_status = fields.Selection([
        ('draft', 'Borrador'),
        ('generated', 'Generado'),
        ('sent', 'Enviado'),
        ('validated', 'Validado'),
        ('rejected', 'Rechazado'),
        ('error', 'Error')
    ], string='Estado RIPS', default='draft', readonly=True)
    
    rips_proceso_id = fields.Char(
        string='ID Proceso RIPS',
        readonly=True,
        help="ID del proceso asignado por el Ministerio de Salud"
    )
    
    rips_response_json = fields.Text(
        string='Respuesta JSON del Ministerio',
        readonly=True
    )
    
    rips_errors = fields.Text(
        string='Errores de Validación',
        readonly=True
    )
    
    rips_consultation_history = fields.Text(
        string='Histórico de Consultas RIPS',
        readonly=True,
        help="Registro histórico de todas las consultas realizadas al sistema RIPS"
    )
    
    rips_last_load_type = fields.Selection([
        ('fev_rips', 'Factura con RIPS'),
        ('nc', 'Nota Crédito'),
        ('nc_total', 'Nota Crédito Total'),
        ('nd', 'Nota Débito'),
        ('nota_ajuste', 'Nota de Ajuste'),
        ('sin_factura', 'RIPS sin Factura'),
        ('nc_acuerdo', 'NC Acuerdo Voluntades'),
        ('capita_inicial', 'Cápita Inicial'),
        ('capita_periodo', 'Cápita Período'),
        ('capita_final', 'Cápita Final'),
    ], string='Último Tipo de Carga', readonly=True)
    
    # Campos JSON
    rips_json = fields.Text(
        string='RIPS JSON',
        readonly=True
    )
    
    rips_json_binary = fields.Binary(
        string='Archivo RIPS JSON',
        readonly=True,
        attachment=True
    )
    
    rips_json_filename = fields.Char(
        string='Nombre Archivo RIPS',
        readonly=True
    )
    
    rips_generated = fields.Boolean(
        string='RIPS Generado',
        readonly=True
    )
    
    rips_result_binary = fields.Binary(
        string='Archivo de Resultado RIPS',
        readonly=True,
        attachment=True
    )
    
    rips_result_filename = fields.Char(
        string='Nombre Archivo Resultado',
        readonly=True
    )
    
    rips_errors_html_binary = fields.Binary(
        string='Reporte HTML de Errores',
        readonly=True,
        attachment=True
    )
    
    rips_errors_html_filename = fields.Char(
        string='Nombre Archivo HTML Errores',
        readonly=True
    )
    
    rips_errors_html = fields.Html(
        string='Errores de Validación HTML',
        readonly=True,
        sanitize=False,
        default=False
    )
    
    # =====================================================
    # MÉTODOS PRINCIPALES DE ENVÍO
    # =====================================================
    
    def action_retry_rips_validation(self):
        """Reintenta la validación de un RIPS rechazado"""
        self.ensure_one()
        
        if self.rips_validation_status not in ['rejected', 'error']:
            raise UserError(_("Solo se puede reintentar la validación para RIPS rechazados o con error"))
        
        self.write({
            'rips_validation_status': 'generated',
            'rips_cuv': False,
            'rips_validation_date': False,
            'rips_errors': False,
            'rips_proceso_id': False,
            'rips_result_binary': False,
            'rips_result_filename': False,
            'rips_errors_html_binary': False,
            'rips_errors_html_filename': False,
            'rips_errors_html': False
        })
        
        self.action_send_rips_to_minsalud()
    
    def mass_action_send_rips_to_min(self):
        for rec in self:
            rec.action_send_rips_to_minsalud()
    
    def action_send_rips_to_minsalud(self):
        """Envía RIPS al Ministerio de Salud"""
        self.ensure_one()
        
        try:
            config = self._get_rips_config()
            

            self.generate_rips_json_api()
            
            endpoint_key, payload = self._determine_rips_endpoint_and_payload()
            
            self.rips_last_load_type = LOAD_TYPE_MAPPING.get(endpoint_key)
            
            result = self._send_to_sispro_endpoint(endpoint_key, payload, config)
            
            self._log_rips_consultation(endpoint_key, payload, result, result['success'])
            
            if result['success']:
                self._process_successful_response(result)
                return self._show_success_notification(result['cuv'])
            else:
                if self._check_cuv_already_approved(result):
                    extracted_cuv = self._extract_cuv_from_error(result)
                    if extracted_cuv:
                        self.rips_cuv = extracted_cuv
                        self.rips_proceso_id = str(result.get('proceso_id', ''))
                        self.rips_validation_status = 'validated'
                        self.rips_validation_date = fields.Datetime.now()
                        try:
                            cuv_status = self._consult_cuv_status_internal(extracted_cuv, config)
                            data = cuv_status.get('data', {})
                            if data.get('ResultState') == True or data.get('EsValido') == True:
                                self.write({
                                    'rips_validation_status': 'validated',
                                    'rips_validation_date': fields.Datetime.now(),
                                    'rips_errors': False,
                                    'rips_errors_html': False
                                })
                            else:
                                validaciones = data.get('ResultadosValidacion', [])
                                if validaciones:
                                    self._create_errors_html_file(data, validaciones)
                            
                            self._create_result_file(data)
                            
                            if data.get('ResultState') == True:
                                return self._show_success_notification(extracted_cuv)
                        except Exception as e:
                            _logger.warning(f"Error al consultar CUV: {str(e)}")
                        return self._show_faill_notification(extracted_cuv)
                else:
                    self._process_error_response(result)
                    
        except Exception as e:
            self._log_rips_consultation(
                endpoint_key if 'endpoint_key' in locals() else 'UNKNOWN',
                {},
                {'error': str(e), 'status_code': None},
                False
            )
            raise
    
    def action_send_fev_rips(self):
        """Enviar factura con RIPS"""
        self._force_endpoint_and_send('CARGAR_FEV_RIPS')
    
    def action_send_nota_credito(self):
        """Enviar Nota Crédito"""
        self._force_endpoint_and_send('CARGAR_NC')
    
    def action_send_nota_credito_total(self):
        """Enviar Nota Crédito Total"""
        self._force_endpoint_and_send('CARGAR_NC_TOTAL')
    
    def action_send_nota_debito(self):
        """Enviar Nota Débito"""
        self._force_endpoint_and_send('CARGAR_ND')
    
    def action_send_nota_ajuste(self):
        """Enviar Nota de Ajuste"""
        self._force_endpoint_and_send('CARGAR_NOTA_AJUSTE')
    
    def action_send_rips_sin_factura(self):
        """Enviar RIPS sin Factura"""
        self._force_endpoint_and_send('CARGAR_RIPS_SIN_FACTURA')
    
    def action_send_nc_acuerdo_voluntades(self):
        """Enviar NC Acuerdo de Voluntades"""
        self._force_endpoint_and_send('CARGAR_NC_ACUERDO_VOLUNTADES')
    
    def action_send_capita_inicial(self):
        """Enviar Cápita Inicial"""
        self._force_endpoint_and_send('CARGAR_CAPITA_INICIAL')
    
    def action_send_capita_periodo(self):
        """Enviar Cápita Período"""
        self._force_endpoint_and_send('CARGAR_CAPITA_PERIODO')
    
    def action_send_capita_final(self):
        """Enviar Cápita Final"""
        self._force_endpoint_and_send('CARGAR_CAPITA_FINAL')
    
    def action_consult_cuv(self):
        """Consultar CUV específico"""
        if not self.rips_cuv:
            raise UserError(_("No hay CUV para consultar"))
        
        config = self._get_rips_config()
        
        try:
            cuv_status = self._consult_cuv_status_internal(self.rips_cuv, config)
            
            if cuv_status.get('success'):
                data = cuv_status.get('data', {})
                
                # Actualizar estado si está validado
                if data.get('ResultState') == True:
                    self.write({
                        'rips_validation_status': 'validated',
                        'rips_proceso_id': str(data.get('ProcesoId', '')) if data.get('ProcesoId') else False
                    })
                
                # Crear archivo de resultado
                self._create_result_file(data)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Consulta CUV'),
                        'message': _('Estado: %s\nFecha: %s') % (
                            'VALIDADO' if data.get('ResultState') else 'RECHAZADO',
                            data.get('FechaRadicacion', 'N/A')
                        ),
                        'type': 'info',
                        'sticky': True,
                    }
                }
            else:
                raise UserError(_("Error al consultar CUV. Por favor revise la pestaña RIPS para ver los detalles."))
                
        except Exception as e:
            raise UserError(_("Error de conexión: %s") % str(e))
    
    def action_download_rips_files(self):
        """Descargar archivos RIPS validados"""
        if not self.rips_cuv:
            raise UserError(_("No hay CUV para descargar archivos"))
        
        config = self._get_rips_config()
        attachment = self._download_rips_files(self.rips_cuv, config)
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def action_download_result_file(self):
        """Descargar archivo de resultado"""
        self.ensure_one()
        
        if not self.rips_result_binary:
            raise UserError(_("No hay archivo de resultado para descargar"))
        
        # Crear attachment temporal para descargar
        attachment = self.env['ir.attachment'].create({
            'name': self.rips_result_filename or f'ResultadosMSPS_{self.name.replace("/", "_")}.txt',
            'type': 'binary',
            'datas': self.rips_result_binary,
            'res_model': self._name,
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def action_view_rips_errors_html(self):
        """Muestra los errores de RIPS en formato HTML"""
        self.ensure_one()
        
        # Si ya existe el HTML guardado, usarlo
        if self.rips_errors_html_binary:
            attachment = self.env['ir.attachment'].create({
                'name': self.rips_errors_html_filename,
                'type': 'binary',
                'datas': self.rips_errors_html_binary,
                'res_model': self._name,
                'res_id': self.id,
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}',
                'target': 'new',
            }
        
        # Si no existe, generar el HTML ahora
        if not self.rips_response_json:
            raise UserError(_("No hay respuesta para mostrar"))
        
        try:
            response_data = json.loads(self.rips_response_json)
            resultados = response_data.get('ResultadosValidacion', response_data.get('resultados_validacion', []))
            
            if not resultados:
                raise UserError(_("No hay resultados de validación para mostrar"))
            
            # Generar el HTML
            self._create_errors_html_file(response_data, resultados)
            
            # Ahora descargar el archivo generado
            if self.rips_errors_html_binary:
                attachment = self.env['ir.attachment'].create({
                    'name': self.rips_errors_html_filename,
                    'type': 'binary',
                    'datas': self.rips_errors_html_binary,
                    'res_model': self._name,
                    'res_id': self.id,
                })
                
                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/{attachment.id}',
                    'target': 'new',
                }
            
        except Exception as e:
            raise UserError(_("Error al generar reporte: %s") % str(e))
    
    def action_view_rips_json(self):
        """Muestra el JSON RIPS en una ventana emergente"""
        self.ensure_one()
        
        if not self.rips_json:
            raise UserError(_("No hay RIPS JSON generado"))
        
        try:
            json_data = json.loads(self.rips_json)
            formatted_json = json.dumps(json_data, indent=2, ensure_ascii=False)
        except:
            formatted_json = self.rips_json
        
        attachment = self.env['ir.attachment'].create({
            'name': f'RIPS_{self.name.replace("/", "_")}.json',
            'type': 'binary',
            'datas': base64.b64encode(formatted_json.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def action_download_rips_json(self):
        """Descarga el archivo JSON RIPS"""
        self.ensure_one()
        
        if not self.rips_json:
            raise UserError(_("No hay RIPS JSON generado. Genere el RIPS primero."))
        
        # Crear attachment para descargar
        attachment = self.env['ir.attachment'].create({
            'name': self.rips_json_filename or f'RIPS_{self.name.replace("/", "_")}.json',
            'type': 'binary',
            'datas': self.rips_json_binary,
            'res_model': self._name,
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def action_validate_rips(self):
        """Valida el RIPS antes de enviar"""
        self.ensure_one()
        
        if not self.rips_json:
            raise UserError(_("No hay RIPS generado para validar"))
        
        # Ejecutar validaciones
        errors = self._validate_invoice_for_rips(self) if hasattr(self, '_validate_invoice_for_rips') else []
        
        if errors:
            # Crear mensaje de error formateado
            error_msg = _("Se encontraron %d errores de validación:\n\n") % len(errors)
            for error in errors[:10]:  # Mostrar máximo 10 errores
                error_msg += f"• {error['tipo']}: {error['descripcion']}\n"
            
            if len(errors) > 10:
                error_msg += f"\n... y {len(errors) - 10} errores más"
            
            raise ValidationError(error_msg)
        
        # Validar estructura
        try:
            rips_data = json.loads(self.rips_json)
        except ValueError:
            raise ValidationError(_("Error al decodificar el JSON RIPS. Verifique el formato."))
        
        success, message = self._validate_rips_data_json(rips_data)
        
        if not success:
            raise ValidationError(message)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validación Exitosa'),
                'message': _('El RIPS ha sido validado correctamente'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    # =====================================================
    # MÉTODOS INTERNOS DE PROCESAMIENTO
    # =====================================================
    
    def _force_endpoint_and_send(self, endpoint_key):
        """Fuerza el uso de un endpoint específico y envía"""
        self.ensure_one()
        
        try:
            config = self._get_rips_config()
            
            # Generar RIPS automáticamente si no existe
            if not self.rips_generated:
                self.generate_rips_json_api()
            
            payload = self._prepare_payload_for_endpoint(endpoint_key)
            
            self.rips_last_load_type = LOAD_TYPE_MAPPING.get(endpoint_key)
            
            result = self._send_to_sispro_endpoint(endpoint_key, payload, config)
            
            self._log_rips_consultation(endpoint_key, payload, result, result['success'])
            
            if result['success']:
                self._process_successful_response(result)
                return self._show_success_notification(result['cuv'])
            else:
                # Verificar si es error RVG18
                if self._check_cuv_already_approved(result):
                    extracted_cuv = self._extract_cuv_from_error(result)
                    _logger.error(extracted_cuv)
                    if extracted_cuv:
                        self.rips_cuv = extracted_cuv
                        self.rips_proceso_id = str(result.get('proceso_id', ''))
                        
                        # Intentar consultar
                        try:
                            cuv_status = self._consult_cuv_status_internal(extracted_cuv, config)
                            if cuv_status.get('success'):
                                data = cuv_status.get('data', {})
                                if data.get('ResultState') == True:
                                    self.write({
                                        'rips_validation_status': 'validated',
                                        'rips_validation_date': fields.Datetime.now(),
                                        'rips_errors': False,
                                        'rips_errors_html': False
                                    })
                                else:
                                    # Generar HTML de errores si hay
                                    validaciones = data.get('ResultadosValidacion', [])
                                    if validaciones:
                                        self._create_errors_html_file(data, validaciones)
                                
                                self._create_result_file(data)
                                
                                if data.get('ResultState') == True:
                                    return self._show_success_notification(extracted_cuv)
                        except:
                            pass
                    
                    return self._show_faill_notification(extracted_cuv)
                else:
                    self._process_error_response(result)
                
        except Exception as e:
            self._log_rips_consultation(endpoint_key, {}, {'error': str(e)}, False)
            raise
    
    def _send_to_sispro_endpoint(self, endpoint_key, payload, config):
        """Envía datos a SISPRO con autenticación"""
        token = config.authenticate()
        
        endpoint = RIPS_ENDPOINTS.get(endpoint_key)
        if not endpoint:
            raise UserError(_("Endpoint no válido: %s") % endpoint_key)
        
        url = f"{config.api_url_base}{endpoint}"
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        if config.verify_ssl:
            ssl_valid, ssl_message = self._validate_ssl_certificate(config.api_url_base)
            if not ssl_valid:
                _logger.error(f"Error de validación SSL: {ssl_message}")
                return {
                    'success': False,
                    'errors': [f'Error de certificado SSL: {ssl_message}'],
                    'status_code': None,
                    'response_text': ssl_message,
                    'endpoint_used': endpoint_key
                }
        
        try:
            session = self._configure_request_session(config)
            
            json_data = json.dumps(payload, ensure_ascii=False)
            json_size = len(json_data.encode('utf-8'))
            
            if json_size > 50 * 1024 * 1024:  # 50MB
                compressed_data = gzip.compress(json_data.encode('utf-8'))
                headers['Content-Encoding'] = 'gzip'
                response = session.post(
                    url,
                    data=compressed_data,
                    headers=headers,
                    timeout=config.timeout or 300
                )
            else:
                response = session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=config.timeout or 300
                )
            
            session.close()
            
            return self._process_sispro_response(response, endpoint_key)
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'errors': [str(e)],
                'status_code': None,
                'response_text': str(e),
                'endpoint_used': endpoint_key
            }
    
    def _configure_request_session(self, config):
        """Configura sesión HTTP"""
        session = requests.Session()
        
        if config.verify_ssl:
            session.verify = certifi.where()
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("https://", adapter)
        else:
            session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        return session
    
    def _validate_ssl_certificate(self, url):
        """Valida el certificado SSL del servidor"""
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            
            parsed_url = urlparse(url)
            hostname = parsed_url.netloc
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    not_after = ssl.cert_time_to_seconds(cert['notAfter'])
                    if datetime.now().timestamp() > not_after:
                        return False, "Certificado SSL expirado"
                    
                    not_before = ssl.cert_time_to_seconds(cert['notBefore'])
                    if datetime.now().timestamp() < not_before:
                        return False, "Certificado SSL aún no es válido"
                    
                    # Validar CN (Common Name) o SAN (Subject Alternative Names)
                    if 'subjectAltName' in cert:
                        valid_names = [name[1] for name in cert['subjectAltName'] if name[0] == 'DNS']
                    else:
                        # Buscar CN en subject
                        subject = dict(x[0] for x in cert['subject'])
                        valid_names = [subject.get('commonName', '')]
                    
                    # Verificar que el hostname coincida
                    hostname_valid = any(
                        hostname == name or 
                        (name.startswith('*.') and hostname.endswith(name[2:])) 
                        for name in valid_names
                    )
                    
                    if not hostname_valid:
                        return False, f"Hostname {hostname} no coincide con el certificado"
                    
                    return True, "Certificado SSL válido"
                    
        except Exception as e:
            return False, str(e)
    
    def _process_sispro_response(self, response, endpoint_key):
        """Procesa respuesta de SISPRO"""
        result = {
            'status_code': response.status_code,
            'response_text': response.text,
            'success': False,
            'cuv': None,
            'errors': [],
            'endpoint_used': endpoint_key,
            'proceso_id': None
        }
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                
                if 'CodigoUnicoValidacion' in response_data and response_data.get('ResultState') == True:
                    result['success'] = True
                    result['cuv'] = response_data['CodigoUnicoValidacion']
                    result['proceso_id'] = str(response_data.get('ProcesoId', ''))
                    result['validation_date'] = response_data.get('FechaRadicacion')
                    result['status'] = 'VALIDADO'
                    result['num_factura'] = response_data.get('NumFactura')
                else:
                    if 'ResultadosValidacion' in response_data:
                        result['errors'] = []
                        result['proceso_id'] = str(response_data.get('ProcesoId', ''))
                        result['num_factura'] = response_data.get('NumFactura')
                        result['resultados_validacion'] = response_data.get('ResultadosValidacion', [])
                        result['ResultadosValidacion'] = response_data.get('ResultadosValidacion', [])
                        
                        for val in response_data.get('ResultadosValidacion', []):
                            error_msg = f"{val.get('Codigo', '')}: {val.get('Descripcion', '')}"
                            if val.get('Observaciones'):
                                error_msg += f" - {val['Observaciones']}"
                            result['errors'].append(error_msg)
                    else:
                        result['errors'] = ['Respuesta sin CUV ni errores claros']
                        
            except ValueError:
                result['errors'] = ['Error al procesar respuesta JSON']
        else:
            result['errors'] = [f'Error HTTP {response.status_code}: {response.text[:200]}']
        
        return result
    
    def _check_cuv_already_approved(self, result):
        """Verifica si CUV ya fue aprobado"""
        if 'resultados_validacion' in result:
            for val in result['resultados_validacion']:
                if val.get('Codigo') == 'RVG18':
                    return True
        
        for error in result.get('errors', []):
            if 'RVG18' in error:
                return True
        
        return False
    
    def _extract_cuv_from_error(self, result):
        """Extrae CUV del error RVG18"""
        if 'resultados_validacion' in result:
            for val in result['resultados_validacion']:
                if val.get('Codigo') == 'RVG18':
                    obs = val.get('Observaciones', '')
                    if obs and len(obs) == 96:
                        return obs
        
        for error in result.get('errors', []):
            if 'RVG18' in error and '-' in error:
                parts = error.split('-')
                for part in parts:
                    part = part.strip()
                    if len(part) == 96:
                        return part
        
        return None
    
    def _consult_cuv_status_internal(self, cuv, config):
        """Consulta interna del estado de un CUV"""
        try:
            token = config.authenticate()
            
            url = f"{config.api_url_base}{RIPS_ENDPOINTS['CONSULTAR_CUV']}"
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                "codigoUnicoValidacion": cuv
            }
            
            session = self._configure_request_session(config)
            response = session.post(
                url,
                json=payload,
                headers=headers,
                timeout=config.timeout or 300
            )
            session.close()
            
            if response.status_code == 200:
                data = response.json()
                
                # Guardar respuesta
                self.rips_response_json = json.dumps(data, indent=2)
                
                return {
                    'success': True,
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'error': f"Error HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _log_rips_consultation(self, endpoint, request_data, response_data, success=True):
        """Registra consultas RIPS"""
        timestamp = fields.Datetime.now()
        log_entry = {
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'endpoint': endpoint,
            'success': success,
            'cuv': response_data.get('cuv') if success else None,
            'proceso_id': response_data.get('proceso_id'),
            'errors': response_data.get('errors', []) if not success else None,
            'status_code': response_data.get('status_code'),
        }
        
        current_history = []
        if self.rips_consultation_history:
            try:
                current_history = json.loads(self.rips_consultation_history)
            except:
                current_history = []
        
        current_history.append(log_entry)
        
        if len(current_history) > 50:
            current_history = current_history[-50:]
        
        self.rips_consultation_history = json.dumps(current_history, indent=2)
    
    def _process_successful_response(self, result):
        """Procesa una respuesta exitosa de SISPRO"""
        self.write({
            'rips_cuv': result['cuv'],
            'rips_validation_date': fields.Datetime.now(),
            'rips_validation_status': 'validated',
            'rips_response_json': json.dumps(result, indent=2),
            'rips_errors': False,
            'rips_errors_html': False,
            'rips_proceso_id': str(result.get('proceso_id', '')) if result.get('proceso_id') else False
        })
        
        self._save_response_attachment(result)
        
        # Crear archivo de resultado
        self._create_result_file(result)
    
    def _save_response_attachment(self, result):
        """Guarda la respuesta como archivo adjunto"""
        response_filename = f"{self.name.replace('/', '_')}_RIPS_Response.json"
        
        self.env['ir.attachment'].create({
            'name': response_filename,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'datas': base64.b64encode(json.dumps(result, indent=2).encode('utf-8')),
        })
    
    def _save_rips_json(self, rips_data):
        """Guarda el JSON RIPS generado"""
        json_str = json.dumps(rips_data, default=self._json_serial, indent=2)
        
        # Limpiar archivos antiguos al generar nuevo RIPS
        self.write({
            'rips_json': json_str,
            'rips_json_binary': base64.b64encode(json_str.encode('utf-8')),
            'rips_json_filename': f"{self.name.replace('/', '_')}_RIPS.json",
            'rips_generated': True,
            'rips_validation_status': 'generated',
            # Limpiar archivos de resultado anteriores
            'rips_result_binary': False,
            'rips_result_filename': False,
            'rips_errors_html_binary': False,
            'rips_errors_html_filename': False,
            'rips_errors_html': False,
            'rips_errors': False,
            'rips_response_json': False,
            'rips_cuv': False,
            'rips_proceso_id': False,
            'rips_validation_date': False
        })
    
    def _show_success_notification(self, cuv):
        """Muestra notificación de éxito"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('RIPS Validado'),
                'message': _('RIPS validado exitosamente. CUV: %s') % cuv,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _show_faill_notification(self, cuv):
        """Muestra notificación de validación previa"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('RIPS Previamente Validado'),
                'message': _('RIPS validado Previamente. CUV: %s') % cuv,
                'type': 'success',
                'sticky': False,
            }
        }
        
    def _process_error_response(self, result):
        """Procesa una respuesta con errores de SISPRO"""
        errors_text = '\n'.join(result.get('errors', ['Error desconocido']))
        self.write({
            'rips_validation_status': 'rejected',
            'rips_response_json': json.dumps(result, indent=2),
            'rips_errors': errors_text,
            'rips_proceso_id': str(result.get('proceso_id', '')) if result.get('proceso_id') else False
        })
        
        # Crear archivo de resultado
        self._create_result_file(result)
        
        # Generar HTML de errores si hay validaciones
        validaciones = result.get('resultados_validacion') or result.get('ResultadosValidacion', [])
        if validaciones:
            self._create_errors_html_file(result, validaciones)
        
        self.env.cr.commit()
        raise ValidationError(_("Error al validar RIPS. Por favor revise la pestaña RIPS para ver los detalles del error."))
    
    def _create_result_file(self, result):
        """Crea archivo TXT con el resultado del proceso"""
        try:
            # Determinar el estado
            if result.get('success') or result.get('ResultState') == True:
                estado = 'A'  # Aprobado
            else:
                estado = 'R'  # Rechazado
            
            # Construir nombre del archivo
            num_factura = result.get('num_factura') or result.get('NumFactura') or self.name.replace('/', '')
            proceso_id = result.get('proceso_id') or result.get('ProcesoId') or 'SIN_ID'
            
            filename = f"ResultadosMSPS_{num_factura}_ID{proceso_id}_{estado}_CUV.txt"
            
            # Construir contenido del archivo
            content = f"RESULTADOS VALIDACIÓN RIPS - MINISTERIO DE SALUD\n"
            content += f"{'='*60}\n\n"
            content += f"Fecha Generación: {fields.Datetime.now()}\n"
            content += f"Estado: {'APROBADO' if estado == 'A' else 'RECHAZADO'}\n"
            content += f"Número Factura: {num_factura}\n"
            content += f"Proceso ID: {proceso_id}\n"
            content += f"CUV: {result.get('cuv') or result.get('CodigoUnicoValidacion', 'N/A')}\n"
            content += f"Fecha Radicación: {result.get('validation_date') or result.get('FechaRadicacion', 'N/A')}\n\n"
            
            # Agregar resultados de validación si existen
            validaciones = result.get('resultados_validacion') or result.get('ResultadosValidacion', [])
            if validaciones:
                content += f"RESULTADOS DE VALIDACIÓN:\n"
                content += f"{'-'*60}\n"
                for idx, val in enumerate(validaciones, 1):
                    content += f"\n{idx}. {val.get('Clase', '')}: {val.get('Codigo', '')}\n"
                    content += f"   Descripción: {val.get('Descripcion', '')}\n"
                    if val.get('Observaciones'):
                        content += f"   Observaciones: {val.get('Observaciones')}\n"
                    if val.get('PathFuente'):
                        content += f"   Path: {val.get('PathFuente')}\n"
            
            # Agregar respuesta completa en formato JSON
            content += f"\n\nRESPUESTA COMPLETA JSON:\n"
            content += f"{'-'*60}\n"
            content += json.dumps(result, indent=2, ensure_ascii=False)
            
            # Guardar en campo binario de la factura
            self.write({
                'rips_result_binary': base64.b64encode(content.encode('utf-8')),
                'rips_result_filename': filename
            })
            
            # También crear archivo adjunto para compatibilidad
            self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(content.encode('utf-8')),
                'res_model': self._name,
                'res_id': self.id,
                'description': f'Resultado validación RIPS - {estado}'
            })
            
            # Si hay errores, generar también el HTML
            if validaciones and estado == 'R':
                self._create_errors_html_file(result, validaciones)
            
            _logger.info(f"Archivo de resultado creado: {filename}")
            
        except Exception as e:
            _logger.error(f"Error creando archivo de resultado: {str(e)}")
    
    def _create_errors_html_file(self, result, validaciones):
        """Crea archivo HTML con los errores formateados"""
        try:
            # Crear HTML con los errores
            html_content = f"""
            <style>
                .o_rips_validation_container {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
                .o_rips_validation_container .rips-error {{ background-color: #ffebee; border-left: 4px solid #f44336; padding: 12px; margin: 8px 0; border-radius: 4px; }}
                .o_rips_validation_container .rips-warning {{ background-color: #fff3e0; border-left: 4px solid #ff9800; padding: 12px; margin: 8px 0; border-radius: 4px; }}
                .o_rips_validation_container .rips-info {{ background-color: #e3f2fd; border-left: 4px solid #2196f3; padding: 12px; margin: 8px 0; border-radius: 4px; }}
                .o_rips_validation_container .rips-code {{ font-weight: 600; color: #333; font-size: 14px; }}
                .o_rips_validation_container .rips-desc {{ margin: 8px 0 4px 0; color: #555; }}
                .o_rips_validation_container .rips-obs {{ font-style: italic; color: #666; font-size: 13px; margin-top: 4px; }}
                .o_rips_validation_container .rips-path {{ font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace; background: #f5f5f5; padding: 3px 6px; font-size: 12px; border-radius: 3px; }}
                .o_rips_validation_container .rips-summary {{ background: #f8f9fa; padding: 16px; margin-bottom: 24px; border-radius: 8px; border: 1px solid #e9ecef; }}
                .o_rips_validation_container .rips-section-title {{ font-size: 18px; font-weight: 600; margin: 24px 0 12px 0; }}
            </style>
            <div class="o_rips_validation_container">
                <div class="rips-summary">
                    <strong>Factura:</strong> {self.name}<br/>
                    <strong>Proceso ID:</strong> {result.get('proceso_id') or result.get('ProcesoId', 'N/A')}<br/>
                    <strong>Fecha:</strong> {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>
                    <strong>Estado:</strong> <span style="color: #d32f2f; font-weight: bold;">RECHAZADO</span>
                </div>
            """
            
            # Agrupar validaciones por tipo
            rechazados = []
            notificaciones = []
            otros = []
            cuv_ya_aprobado = False
            cuv_existente = None
            
            for val in validaciones:
                clase = val.get('Clase', '')
                codigo = val.get('Codigo', '')
                
                # Detectar si es RVG18 (CUV ya aprobado)
                if codigo == 'RVG18':
                    cuv_ya_aprobado = True
                    # Intentar extraer el CUV de las observaciones
                    obs = val.get('Observaciones', '')
                    if obs and len(obs) == 96:
                        cuv_existente = obs
                
                if clase == 'RECHAZADO':
                    rechazados.append(val)
                elif clase == 'NOTIFICACION':
                    notificaciones.append(val)
                else:
                    otros.append(val)
            
            # Si el CUV ya fue aprobado, mostrar mensaje especial
            if cuv_ya_aprobado:
                html_content += f"""
                <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 6px; padding: 16px; margin: 16px 0;">
                    <h4 style="color: #856404; margin: 0 0 8px 0;">
                        <i class="fa fa-exclamation-triangle" style="margin-right: 8px;"/> CUV Ya Aprobado Previamente
                    </h4>
                    <p style="color: #856404; margin: 0;">
                        Este RIPS ya fue validado anteriormente. {'CUV: <strong style="font-family: monospace;">' + cuv_existente + '</strong>' if cuv_existente else ''}
                    </p>
                    <p style="color: #856404; margin: 8px 0 0 0;">
                        Use el botón <strong>"Consultar CUV"</strong> para verificar el estado actual.
                    </p>
                </div>
                """
            
            # Mostrar rechazos primero
            if rechazados:
                html_content += '<h4 class="rips-section-title" style="color: #d32f2f;">Rechazos</h4>'
                for val in rechazados:
                    html_content += f"""
                    <div class="rips-error">
                        <div class="rips-code">{val.get('Codigo', '')}</div>
                        <div class="rips-desc">{val.get('Descripcion', '')}</div>
                    """
                    if val.get('Observaciones'):
                        html_content += f'<div class="rips-obs">Observación: {val["Observaciones"]}</div>'
                    if val.get('PathFuente'):
                        html_content += f'<div>Ubicación: <span class="rips-path">{val["PathFuente"]}</span></div>'
                    html_content += '</div>'
            
            # Luego notificaciones
            if notificaciones:
                html_content += '<h4 class="rips-section-title" style="color: #ff6f00;">Notificaciones</h4>'
                for val in notificaciones:
                    html_content += f"""
                    <div class="rips-warning">
                        <div class="rips-code">{val.get('Codigo', '')}</div>
                        <div class="rips-desc">{val.get('Descripcion', '')}</div>
                    """
                    if val.get('Observaciones'):
                        html_content += f'<div class="rips-obs">Observación: {val["Observaciones"]}</div>'
                    if val.get('PathFuente'):
                        html_content += f'<div>Ubicación: <span class="rips-path">{val["PathFuente"]}</span></div>'
                    html_content += '</div>'
            
            # Otros
            if otros:
                html_content += '<h4 class="rips-section-title" style="color: #1976d2;">Información</h4>'
                for val in otros:
                    html_content += f"""
                    <div class="rips-info">
                        <div class="rips-code">{val.get('Codigo', '')}</div>
                        <div class="rips-desc">{val.get('Descripcion', '')}</div>
                    """
                    if val.get('Observaciones'):
                        html_content += f'<div class="rips-obs">Observación: {val["Observaciones"]}</div>'
                    if val.get('PathFuente'):
                        html_content += f'<div>Ubicación: <span class="rips-path">{val["PathFuente"]}</span></div>'
                    html_content += '</div>'
            
            html_content += '</div>'
            
            # HTML completo para el archivo descargable
            html_file_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Resultados de Validación RIPS - {self.name}</title>
    <style>
        body {{ margin: 20px; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""
            
            filename = f'RIPS_Errores_{self.name.replace("/", "_")}.html'
            
            # Guardar en campos
            self.write({
                'rips_errors_html': html_content,  # Solo el contenido para mostrar en la vista
                'rips_errors_html_binary': base64.b64encode(html_file_content.encode('utf-8')),
                'rips_errors_html_filename': filename
            })
            
        except Exception as e:
            _logger.error(f"Error creando archivo HTML de errores: {str(e)}")
    
    def _prepare_payload_for_endpoint(self, endpoint_key):
        """Prepara el payload según el endpoint"""
        rips_data = json.loads(self.rips_json) if self.rips_json else self._generate_empty_rips()
        xml_fev = self._get_xml_fev_file()
        
        # Guardar el archivo XML usado
        if xml_fev:
            self._save_attached_document_used(xml_fev)
        
        if endpoint_key == 'CARGAR_FEV_RIPS':
            return {
                'rips': rips_data,
                'xmlFevFile': xml_fev
            }
        elif endpoint_key == 'CARGAR_NC':
            return {
                'rips': rips_data,
                'xmlFevFile': xml_fev
            }
        elif endpoint_key == 'CARGAR_NC_TOTAL':
            return {
                'rips': None,  # NC Total no requiere RIPS
                'xmlFevFile': xml_fev
            }
        elif endpoint_key == 'CARGAR_ND':
            return {
                'rips': rips_data,
                'xmlFevFile': xml_fev
            }
        elif endpoint_key == 'CARGAR_NOTA_AJUSTE':
            return {
                'rips': rips_data,
                'xmlFevFile': xml_fev
            }
        elif endpoint_key == 'CARGAR_NC_ACUERDO_VOLUNTADES':
            return {
                'rips': None,
                'xmlFevFile': xml_fev
            }
        elif endpoint_key == 'CARGAR_RIPS_SIN_FACTURA':
            return {
                'rips': rips_data,
                'xmlFevFile': None
            }
        elif endpoint_key in ['CARGAR_CAPITA_INICIAL', 'CARGAR_CAPITA_PERIODO', 'CARGAR_CAPITA_FINAL']:
            return {
                'rips': self._generate_capita_rips(endpoint_key),
                'xmlFevFile': None
            }
        else:
            raise UserError(_("Endpoint no reconocido: %s") % endpoint_key)
    
    def _save_attached_document_used(self, xml_fev):
        """Guarda el AttachedDocument usado en el envío"""
        try:
            # Buscar si ya existe
            existing = self.env['ir.attachment'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('name', 'like', '%AttachedDocument_Used%')
            ])
            existing.unlink()
            
            # Crear nuevo
            self.env['ir.attachment'].create({
                'name': f'AttachedDocument_Used_{self.name.replace("/", "_")}.xml',
                'type': 'binary',
                'datas': xml_fev if isinstance(xml_fev, str) else base64.b64encode(xml_fev),
                'res_model': self._name,
                'res_id': self.id,
            })
        except Exception as e:
            _logger.warning(f"Error guardando AttachedDocument: {str(e)}")
    
    def _download_rips_files(self, cuv, config):
        """Descarga archivos RIPS por CUV"""
        url = f"{config.api_url_base}{RIPS_ENDPOINTS['DESCARGAR_ARCHIVOS']}"
        
        payload = {
            "codigoUnicoValidacion": cuv
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=config.timeout or 300
            )
            
            if response.status_code == 200:
                attachment = self.env['ir.attachment'].create({
                    'name': f'RIPS_Files_{cuv}.zip',
                    'type': 'binary',
                    'datas': base64.b64encode(response.content),
                    'res_model': self._name,
                    'res_id': self.id,
                })
                return attachment
            else:
                raise UserError(_("Error al descargar archivos: %s") % response.text)
                
        except Exception as e:
            raise UserError(_("Error de conexión: %s") % str(e))
    
    # =====================================================
    # MÉTODOS DE VALIDACIÓN DE DATOS
    # =====================================================
    
    def _validate_rips_structure(self, rips_data):
        """Valida la estructura del RIPS"""
        errors = []
        
        required_root = ['numDocumentoIdObligado', 'numFactura']
        for field in required_root:
            if field not in rips_data or not rips_data[field]:
                errors.append(_("Campo obligatorio faltante: %s") % field)
        
        if 'usuarios' in rips_data and rips_data['usuarios']:
            for idx, usuario in enumerate(rips_data['usuarios']):
                user_errors = self._validate_usuario_structure(usuario, idx + 1)
                errors.extend(user_errors)
        
        return len(errors) == 0, errors
    
    def _validate_usuario_structure(self, usuario, index):
        """Valida la estructura de un usuario"""
        errors = []
        
        required_fields = [
            'tipoDocumentoIdentificacion',
            'numDocumentoIdentificacion',
            'tipoUsuario',
            'fechaNacimiento',
            'codSexo',
            'codPaisResidencia',
            'codMunicipioResidencia',
            'codZonaTerritorialResidencia',
            'consecutivo'
        ]
        
        for field in required_fields:
            if field not in usuario or usuario[field] is None:
                errors.append(_("Usuario #%s: Campo obligatorio faltante: %s") % (index, field))
        
        if 'servicios' not in usuario or not usuario['servicios']:
            errors.append(_("Usuario #%s: No contiene servicios") % index)
        
        return errors
    
    def _validate_rips_data_json(self, rips_data):
        """Valida la estructura y campos del RIPS JSON"""
        if not rips_data:
            return False, _("No hay datos RIPS para validar")
        
        errors = []
        
        required_fields = ['numDocumentoIdObligado', 'numFactura']
        for field in required_fields:
            if field not in rips_data or not rips_data[field]:
                errors.append(_("Campo requerido faltante: %s") % field)
        
        if 'usuarios' not in rips_data or not rips_data['usuarios']:
            errors.append(_("El RIPS no contiene usuarios"))
        else:
            for i, usuario in enumerate(rips_data['usuarios']):
                self._validate_usuario_json(usuario, i+1, errors)
        
        if errors:
            return False, "\n".join(errors)
        return True, _("Validación RIPS exitosa")
    
    def _validate_usuario_json(self, usuario, index, errors):
        """Valida los datos de un usuario"""
        required_fields = [
            'tipoDocumentoIdentificacion', 
            'numDocumentoIdentificacion',
            'tipoUsuario',
            'fechaNacimiento',
            'codSexo'
        ]
        
        for field in required_fields:
            if field not in usuario or not usuario[field]:
                errors.append(_("Usuario #%s: Campo requerido faltante: %s") % (index, field))
        
        if 'servicios' not in usuario or not usuario['servicios']:
            errors.append(_("Usuario #%s: No contiene servicios") % index)
    
    # =====================================================
    # MÉTODOS DE UTILIDADES
    # =====================================================
    
    def _validate_string(self, value, min_length=None, max_length=None, no_leading_zero=False, 
                         no_spaces=False, default=None, allow_null=False):
        """Validate and format string values according to specifications."""
        if value is None:
            return None if allow_null else default
        
        value_str = str(value).strip()
        
        if value_str == "null" and allow_null or value_str == '':
            return None
        
        if value_str == "null" and not allow_null:
            return default
        
        if no_spaces:
            value_str = value_str.replace(' ', '')
        
        if no_leading_zero and value_str.startswith('0'):
            value_str = '1' + value_str[1:]
        
        if min_length and len(value_str) < min_length:
            value_str = value_str.ljust(min_length, '0')
        
        if max_length and len(value_str) > max_length:
            value_str = value_str[:max_length]
        
        return value_str
    
    def _validate_numeric(self, value, min_digits=None, max_digits=None, 
                         default=0, allow_null=False, force_integer=True,
                         decimals=0, min_value=0, max_value=None):
        """
        Valida valores numéricos según reglas RIPS
        
        Args:
            value: Valor a validar
            min_digits: Mínimo número de dígitos
            max_digits: Máximo número de dígitos
            default: Valor por defecto
            allow_null: Si permite null
            force_integer: Si forzar a entero (True para RIPS)
            decimals: Número de decimales permitidos
            min_value: Valor mínimo permitido
            max_value: Valor máximo permitido
        
        Returns:
            int o None según configuración
        """
        # Manejar valores null
        if value is None or value == '':
            if allow_null:
                return None
            return default
        
        try:
            # Convertir a float primero para manejar decimales
            value_float = float(value)
            
            # Si es negativo, convertir a 0 (RIPS no acepta negativos)
            if value_float < 0:
                value_float = 0
            
            # Validar rango
            if min_value is not None and value_float < min_value:
                value_float = min_value
            
            if max_value is not None and value_float > max_value:
                value_float = max_value
            
            # Convertir según configuración
            if force_integer or decimals == 0:
                # Redondear según regla contable (ROUND_HALF_UP)
                value_int = int(Decimal(str(value_float)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            else:
                # Mantener decimales especificados
                quantize_str = '0.' + '0' * decimals
                value_decimal = Decimal(str(value_float)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
                return float(value_decimal)
            
            # Validar número de dígitos
            value_str = str(value_int)
            
            # Si excede el máximo de dígitos, usar el máximo permitido
            if max_digits and len(value_str) > max_digits:
                # Crear el número máximo permitido (999...9)
                value_int = int('9' * max_digits)
            
            # Si es menor al mínimo de dígitos, rellenar con ceros
            if min_digits and len(value_str) < min_digits:
                value_str = value_str.zfill(min_digits)
                value_int = int(value_str)
            
            return value_int
            
        except (ValueError, TypeError):
            return default
    
    def _validate_date(self, value, format_str='%Y-%m-%d', default=None):
        """
        Valida y formatea fecha según reglas RIPS
        
        Args:
            value: Valor de fecha a validar
            format_str: Formato de salida deseado
            default: Valor por defecto si la validación falla
        
        Returns:
            Fecha formateada como string o valor por defecto
        """
        if not value:
            return default
        
        try:
            date_value = None
            
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return default
                    
                # Intentar varios formatos comunes
                formats_to_try = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M',
                    '%Y-%m-%d',
                    '%d/%m/%Y',
                    '%m/%d/%Y',
                ]
                
                for fmt in formats_to_try:
                    try:
                        date_value = datetime.strptime(value, fmt)
                        break
                    except ValueError:
                        continue
                
                if date_value is None:
                    return default
            
            elif isinstance(value, datetime):
                date_value = value
            
            elif isinstance(value, date):
                date_value = datetime.combine(value, datetime.min.time())
            
            elif hasattr(value, 'strftime'):
                # Para campos fields.Date o fields.Datetime de Odoo
                date_value = value
            
            else:
                return default
            
            # Formatear según el formato solicitado
            if date_value:
                return date_value.strftime(format_str)
            
            return default
            
        except Exception as e:
            _logger.warning(f"Error al validar fecha: {e}")
            return default
    
    def _json_serial(self, obj):
        """Serializa objetos para JSON con soporte para Decimal"""
        if isinstance(obj, (datetime, fields.Date, fields.Datetime)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, date):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable for RIPS")
    
    # =====================================================
    # MÉTODOS ABSTRACTOS A IMPLEMENTAR
    # =====================================================
    
    @api.model
    def _get_rips_config(self):
        """Obtiene la configuración RIPS activa"""
        raise NotImplementedError("Debe implementar _get_rips_config")
    
    def _determine_rips_endpoint_and_payload(self):
        """Determina endpoint y payload según tipo de documento"""
        raise NotImplementedError("Debe implementar _determine_rips_endpoint_and_payload")
    
    def generate_rips_json_api(self):
        """Genera el JSON RIPS según configuración"""
        raise NotImplementedError("Debe implementar generate_rips_json_api")
    
    def _generate_rips_base_structure(self):
        """Genera la estructura base del RIPS"""
        raise NotImplementedError("Debe implementar _generate_rips_base_structure")
    
    def _should_include_users(self):
        """Determina si debe incluir usuarios en el RIPS"""
        raise NotImplementedError("Debe implementar _should_include_users")
    
    def _generate_rips_users(self):
        """Genera la lista de usuarios para el RIPS"""
        raise NotImplementedError("Debe implementar _generate_rips_users")
    
    def _get_xml_fev_file(self):
        """Obtiene el XML de la factura electrónica"""
        raise NotImplementedError("Debe implementar _get_xml_fev_file")
    
    def _generate_empty_rips(self):
        """Genera un RIPS vacío"""
        raise NotImplementedError("Debe implementar _generate_empty_rips")
    
    def _generate_capita_rips(self, endpoint_key):
        """Genera RIPS específico para cápita"""
        raise NotImplementedError("Debe implementar _generate_capita_rips")


class RipsConfiguration(models.Model):
    """Configuración de RIPS SISPRO"""
    _name = 'rips.configuration'
    _description = 'Configuración RIPS SISPRO'
    _rec_name = 'name'
    
    SISPRO_PRODUCTION_URL = 'https://validador.sispro.gov.co'
    SISPRO_TEST_URL = 'https://pruebasvalidador.sispro.gov.co'
    SISPRO_DOCKER_URL = 'https://localhost:9443'
    
    name = fields.Char(string='Nombre', required=True, default='Configuración RIPS')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(string='Activo', default=True)
    
    # Credenciales SISPRO
    sispro_tipo_documento = fields.Selection([
        ('CC', 'Cédula de Ciudadanía'),
        ('CE', 'Cédula de Extranjería'),
        ('PA', 'Pasaporte'),
        ('NI', 'NIT')
    ], string='Tipo Documento SISPRO', required=True, default='NI')
    sispro_numero_documento = fields.Char(string='Número Documento SISPRO', required=True)
    sispro_nit = fields.Char(string='NIT Entidad', required=True, help='NIT de la entidad prestadora')
    sispro_password = fields.Char(string='Contraseña SISPRO', required=True)
    sispro_tipo_usuario = fields.Selection([
        ('1', 'IPS'),
        ('2', 'EPS'),
        ('3', 'Profesional Independiente')
    ], string='Tipo Usuario SISPRO', required=True, default='1',
       help='Tipo de usuario para autenticación en SISPRO')

    # URLs de servicio
    api_url_base = fields.Char(string='URL Base API', required=True, help='URL base para el servicio RIPS')
    environment_type = fields.Selection([
        ('production', 'Producción'),
        ('test', 'Pruebas'),
        ('docker', 'Docker Local')
    ], string='Tipo de Ambiente', default='test', required=True)
    
    # Token de autenticación
    auth_token = fields.Text(string='Token de Autenticación', readonly=True)
    token_expiry = fields.Datetime(string='Expiración del Token', readonly=True)
    
    # Configuración adicional
    timeout = fields.Integer(string='Timeout (segundos)', default=300)
    verify_ssl = fields.Boolean(string='Verificar SSL', default=True)
    
    @api.onchange('environment_type')
    def _onchange_environment_type(self):
        """Actualiza la URL según el ambiente"""
        if self.environment_type == 'production':
            self.api_url_base = self.SISPRO_PRODUCTION_URL
        elif self.environment_type == 'docker':
            self.api_url_base = self.SISPRO_DOCKER_URL
        else:
            self.api_url_base = self.SISPRO_TEST_URL
    
    @api.constrains('active', 'company_id')
    def _check_unique_active(self):
        for record in self:
            if record.active:
                domain = [
                    ('company_id', '=', record.company_id.id),
                    ('active', '=', True),
                    ('id', '!=', record.id)
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(_("Solo puede haber una configuración RIPS activa por empresa."))
    
    @api.model
    def get_config(self):
        """Obtiene la configuración activa para la compañía actual"""
        config = self.search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)
        if not config:
            raise UserError(_("No se ha configurado RIPS SISPRO para esta compañía. Por favor configure las credenciales."))
        return config
    
    def test_connection(self):
        """Prueba la conexión con SISPRO"""
        self.ensure_one()
        try:
            self.authenticate()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexión Exitosa'),
                    'message': _('La conexión con SISPRO fue exitosa.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("Error en la conexión: %s") % str(e))
    
    def authenticate(self):
        """Autentica con SISPRO y obtiene el token"""
        self.ensure_one()

        url = f"{self.api_url_base}{RIPS_ENDPOINTS['AUTH']}"

        # Payload diferente según el ambiente
        if self.environment_type == 'docker':
            # Formato para API Docker Local
            payload = {
                "nit": self.sispro_nit,
                "tipoDocumento": self.sispro_tipo_documento,
                "numeroDocumento": self.sispro_numero_documento,
                "clave": self.sispro_password,
                "tipoUsuario": self.sispro_tipo_usuario or '1'
            }
        else:
            # Formato para API SISPRO produccion/pruebas
            payload = {
                "persona": {
                    "identificacion": {
                        "tipo": self.sispro_tipo_documento,
                        "numero": self.sispro_numero_documento
                    }
                },
                "clave": self.sispro_password,
                "nit": self.sispro_nit,
                "tipoUsuario": self.sispro_tipo_usuario or '1'
            }

        headers = {
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=60,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                # El token puede venir en diferentes campos segun el API
                token = data.get('token') or data.get('Token')
                if token:
                    self.auth_token = token
                    self.token_expiry = fields.Datetime.now() + timedelta(hours=1)
                    return self.auth_token
                elif data.get('login') == False:
                    # API Docker devuelve login: false cuando falla
                    errors = data.get('errors', ['Error de autenticacion'])
                    raise UserError(_("Error de autenticación: %s") % ', '.join(errors))
            else:
                raise UserError(_("Error de autenticación: %s") % response.text)

        except requests.exceptions.RequestException as e:
            raise UserError(_("Error de conexión: %s") % str(e))


class RipsValidatorMixin(models.AbstractModel):
    """Mixin para validación de RIPS según resolución 2275"""
    _name = 'rips.validator.mixin'
    _description = 'RIPS Validator Mixin'
    
    def _validate_invoice_for_rips(self, invoice):
        """Valida factura para RIPS"""
        errores = []
        
        # Validar empresa
        if not invoice.company_id.partner_id.vat_co:
            errores.append({
                'tipo': 'Datos Empresa',
                'descripcion': 'NIT de la empresa no configurado',
                'campo': 'company_id.partner_id.vat_co',
                'valor_actual': '',
                'valor_sugerido': 'Configurar NIT en la empresa',
                'severidad': 'Alta'
            })
        
        if not invoice.company_id.partner_id.ref:
            errores.append({
                'tipo': 'Datos Empresa',
                'descripcion': 'Código prestador no configurado',
                'campo': 'company_id.partner_id.ref',
                'valor_actual': '',
                'valor_sugerido': 'Configurar código prestador (12 dígitos)',
                'severidad': 'Alta'
            })
        elif invoice.company_id.partner_id.ref:
            ref_code = str(invoice.company_id.partner_id.ref).strip()
            if not re.match(r'^\d{12}$', ref_code):
                errores.append({
                    'tipo': 'Código Prestador',
                    'descripcion': 'Código prestador debe tener exactamente 12 dígitos',
                    'campo': 'company_id.partner_id.ref',
                    'valor_actual': ref_code,
                    'valor_sugerido': 'Código de 12 dígitos',
                    'severidad': 'Alta'
                })
        
        # Validar líneas
        for line_num, line in enumerate(invoice.invoice_line_ids, 1):
            if line.product_id and line.product_id.rips_service_type and line.product_id.rips_service_type != 'none':
                line_errors = self._validate_invoice_line_rips(line)
                for error in line_errors:
                    error['linea'] = f'Línea {line_num}'
                    error['producto'] = line.product_id.name if line.product_id else ''
                    error['paciente'] = f"{line.patient_doc_type or ''} {line.patient_document or ''}"
                    errores.append(error)
        
        return errores
    
    def _validate_invoice_line_rips(self, line):
        """Valida línea de factura para RIPS"""
        errors = []
        
        # Validar datos del paciente
        if not line.patient_doc_type:
            errors.append({
                'tipo': 'Datos Paciente',
                'descripcion': 'Tipo de documento del paciente requerido',
                'campo': 'patient_doc_type',
                'valor_actual': '',
                'valor_sugerido': 'Seleccionar tipo de documento',
                'severidad': 'Alta'
            })
        
        if not line.patient_document:
            errors.append({
                'tipo': 'Datos Paciente',
                'descripcion': 'Número de documento del paciente requerido',
                'campo': 'patient_document',
                'valor_actual': '',
                'valor_sugerido': 'Ingresar número de documento',
                'severidad': 'Alta'
            })
        
        # Validar según tipo de servicio
        if line.product_id.rips_service_type == 'consulta':
            if not line.diagnostico_principal:
                errors.append({
                    'tipo': 'Consulta',
                    'descripcion': 'Diagnóstico principal requerido para consultas',
                    'campo': 'diagnostico_principal',
                    'valor_actual': '',
                    'valor_sugerido': 'Ingresar código CIE-10',
                    'severidad': 'Alta'
                })
        
        elif line.product_id.rips_service_type == 'medicamento':
            if not line.dias_tratamiento or line.dias_tratamiento <= 0:
                errors.append({
                    'tipo': 'Medicamento',
                    'descripcion': 'Días de tratamiento debe ser mayor a 0',
                    'campo': 'dias_tratamiento',
                    'valor_actual': str(line.dias_tratamiento or 0),
                    'valor_sugerido': '1',
                    'severidad': 'Alta'
                })
        
        return errors


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'rips.validator.mixin', 'abstract.rips.fev.mixin']
    

    # Campos para tipos especiales
    is_adjustment_note = fields.Boolean(string='Es Nota de Ajuste')
    is_voluntary_agreement = fields.Boolean(string='Es Acuerdo de Voluntades')
    is_total_credit_note = fields.Boolean(string='Es Nota Crédito Total')
    rips_without_invoice = fields.Boolean(string='RIPS sin Factura')
    capita_type = fields.Selection([
        ('initial', 'Inicial'),
        ('period', 'Período'),
        ('final', 'Final')
    ], string='Tipo de Cápita')
    
    # Campo para configurar uso de impuestos en RIPS
    rips_include_taxes = fields.Boolean(
        string='Incluir impuestos en valores RIPS',
        default=True,
        help='Si está marcado, los valores reportados en RIPS incluirán los impuestos calculados'
    )
    rips_force_integer_values = fields.Boolean(
        string='Forzar valores enteros en RIPS',
        default=True,
        help='Si está marcado, todos los valores monetarios se enviarán como enteros (sin decimales)'
    )
    
    # Campos médicos
    patient_id = fields.Many2one('hms.patient', string='Paciente')
    physician_id = fields.Many2one('hms.physician', string='Médico')
    department_id = fields.Many2one('hr.department', string='Departamento')
    diagnosis_id = fields.Many2one('hms.diseases', string='Diagnóstico')
    authorization_number = fields.Char(string='Número de Autorización')
    date_start = fields.Date(string='Fecha Inicio', default=fields.Date.today)
    date_end = fields.Date(string='Fecha Fin')
    
    # Campos de paciente para RIPS desde encabezado
    header_patient_document = fields.Char(string='Documento Paciente')
    header_patient_doc_type = fields.Selection([
        ('CC', 'Cédula de Ciudadanía'),
        ('TI', 'Tarjeta de Identidad'),
        ('CE', 'Cédula de Extranjería'),
        ('PA', 'Pasaporte'),
        ('RC', 'Registro Civil'),
        ('MS', 'Menor sin identificación'),
        ('AS', 'Adulto sin identificación'),
        ('PE', 'Permiso especial de permanencia'),
        ('SC', 'Salvoconducto de permanencia'),
        ('PT', 'Permiso por protección temporal')
    ], string='Tipo Doc Paciente')
    header_patient_name = fields.Char(string='Nombre Paciente')
    header_patient_birth_date = fields.Date(string='Fecha Nacimiento')
    header_patient_gender = fields.Selection([
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('I', 'Indeterminado')
    ], string='Género')
    header_patient_user_type = fields.Selection([
        ('01', 'Contributivo cotizante'),
        ('02', 'Contributivo beneficiario'),
        ('03', 'Contributivo adicional'),
        ('04', 'Subsidiado'),
        ('05', 'Sin régimen'),
        ('06', 'Especiales o de Excepción cotizante'),
        ('07', 'Especiales o de Excepción beneficiario'),
        ('08', 'Particular'),
        ('09', 'Tomador/Amparado ARL'),
        ('10', 'Tomador/Amparado SOAT'),
        ('11', 'Tomador/Amparado Planes voluntarios de salud'),
    ], string='Tipo Usuario', default='01')
    header_patient_country_id = fields.Many2one('res.country', string='País')
    header_patient_city_id = fields.Many2one('res.city', string='Ciudad')
    header_patient_zone = fields.Selection([
        ('01', 'Urbano'),
        ('02', 'Rural')
    ], string='Zona', default='01')
    header_patient_nationality = fields.Char(string='Nacionalidad')
    
    # Campos para prepagos del sector salud
    copay_amount = fields.Float(string='Valor Copago')
    moderator_fee_amount = fields.Float(string='Valor Cuota Moderadora')
    shared_payment_amount = fields.Float(string='Valor Pago Compartido')
    recovery_fee_amount = fields.Float(string='Valor Cuota de Recuperación')
    health_prepaid_amount = fields.Float(string='Total Prepagos Salud', compute='_compute_health_prepaid_amount')

    attached_document_xml = fields.Binary(
        string='Archivo XML AttachedDocument',
        readonly=True,
        attachment=True,
        help="XML de la factura electrónica almacenado para reutilización"
    )

    attached_document_xml_filename = fields.Char(
        string='Nombre Archivo XML',
        readonly=True
    )

    rips_validated_cups = fields.Boolean(
        string='CUPS Validados',
        readonly=True,
        help="Indica si los códigos CUPS de la factura han sido validados"
    )

    rips_validation_cups_date = fields.Datetime(
        string='Fecha Validación CUPS',
        readonly=True
    )

    rips_validation_cups_result = fields.Text(
        string='Resultado Validación CUPS',
        readonly=True
    )

    # Campo computado para saber si está en otro lote RIPS
    is_in_rips_export = fields.Boolean(
        string='En Lote RIPS',
        compute='_compute_is_in_rips_export',
        search='_search_is_in_rips_export',
        help="Indica si la factura está incluida en algún lote de exportación RIPS"
    )

    ripsjson_id = fields.Many2one(
        'rips.export',
        string='Lote RIPS',
        readonly=True,
        help="Lote de exportación RIPS al que pertenece esta factura"
    )
    
    @api.depends('copay_amount', 'moderator_fee_amount', 'shared_payment_amount', 'recovery_fee_amount', 'health_prepaid_references.amount')
    def _compute_health_prepaid_amount(self):
        for record in self:
            record.health_prepaid_amount = (
                record.copay_amount +
                record.moderator_fee_amount +
                record.shared_payment_amount +
                record.recovery_fee_amount +
                sum(record.health_prepaid_references.mapped('amount'))
            )
    
    def generate_pdf_zip(self):
        today = datetime.now().strftime('%Y%m%d')
        attachment_name = f'PDFs_{today}.zip'
        
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for move in self:
                try:
                    company_vat = move.company_id.partner_id.vat_co 
                    pdf_content = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                        "account.account_invoices", move.id)[0]
                    
                    pdf_filename = f"FVS_{company_vat}_{move.name}.pdf"
                    zip_file.writestr(pdf_filename, pdf_content)
                    
                except Exception as e:
                    _logger.error(f"Error generando PDF para factura {move.name}: {str(e)}")
                    continue
        
        zip_data = base64.b64encode(zip_buffer.getvalue())
        attachment = self.env['ir.attachment'].create({
            'name': attachment_name,
            'type': 'binary',
            'datas': zip_data,
            'res_model': self._name if len(self) == 1 else False,
            'res_id': self.id if len(self) == 1 else False,
            'mimetype': 'application/zip'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    @api.depends('ripsjson_id')
    def _compute_is_in_rips_export(self):
        for record in self:
            record.is_in_rips_export = bool(record.ripsjson_id)

    def _search_is_in_rips_export(self, operator, value):
        if operator == '=' and value is False:
            return [('ripsjson_id', '=', False)]
        elif operator == '=' and value is True:
            return [('ripsjson_id', '!=', False)]
        else:
            return [('ripsjson_id', operator, value)]
        
    def _collect_prepaid_payments_data(self):
        """Recolecta datos de pagos anticipados incluyendo sector salud"""
        data = {}
        
        # Si existe el método en el padre, llamarlo
        if hasattr(super(AccountMove, self), '_collect_prepaid_payments_data'):
            data = super()._collect_prepaid_payments_data()
        
        # Campo is_health_sector podría no existir, verificar condiciones
        is_health = getattr(self, 'is_health_sector', False)
        fe_operation = getattr(self, 'fe_operation_type', '')
        
        if is_health and fe_operation in ['SS-CUFE', 'SS-CUDE', 'SS-POS', 'SS-SNum']:
            if 'prepaid_payments' not in data:
                data['prepaid_payments'] = []
            
            counter = len(data['prepaid_payments']) + 1
            
            # Agregar prepagos del sector salud con schemeID
            if self.copay_amount > 0:
                data['prepaid_payments'].append({
                    'id': str(counter),
                    'scheme_id': '01',
                    'amount': self.copay_amount,
                    'received_date': str(self.invoice_date),
                    'paid_date': str(self.invoice_date),
                    'invoice_reference': self.name,
                })
                counter += 1
            
            if self.moderator_fee_amount > 0:
                data['prepaid_payments'].append({
                    'id': str(counter),
                    'scheme_id': '02',
                    'amount': self.moderator_fee_amount,
                    'received_date': str(self.invoice_date),
                    'paid_date': str(self.invoice_date),
                    'invoice_reference': self.name,
                })
                counter += 1
            
            if self.shared_payment_amount > 0:
                data['prepaid_payments'].append({
                    'id': str(counter),
                    'scheme_id': '03',
                    'amount': self.shared_payment_amount,
                    'received_date': str(self.invoice_date),
                    'paid_date': str(self.invoice_date),
                    'invoice_reference': self.name,
                })
                counter += 1
            
            if self.recovery_fee_amount > 0:
                data['prepaid_payments'].append({
                    'id': str(counter),
                    'scheme_id': '04',
                    'amount': self.recovery_fee_amount,
                    'received_date': str(self.invoice_date),
                    'paid_date': str(self.invoice_date),
                    'invoice_reference': self.name,
                })
                counter += 1
            
            # Referencias de prepago con número de factura
            for ref in self.health_prepaid_references:
                if ref.amount > 0:
                    data['prepaid_payments'].append({
                        'id': str(counter),
                        'scheme_id': ref.collection_concept_code or '01',
                        'amount': ref.amount,
                        'received_date': str(ref.received_date or self.invoice_date),
                        'paid_date': str(ref.paid_date or self.invoice_date),
                        'invoice_reference': ref.invoice_reference or self.name,
                    })
                    counter += 1
            
            data['health_prepaid_amount'] = self.health_prepaid_amount
        
        return data
    
    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        """Actualiza campos del paciente en el encabezado"""
        if self.patient_id:
            # Si es hms.patient, usar partner_id, si no es res.partner directo
            patient = self.patient_id.partner_id if self.patient_id._name == 'hms.patient' else self.patient_id
            
            self.header_patient_document = patient.vat or patient.ref or ''
            self.header_patient_name = patient.name or ''
            self.header_patient_birth_date = patient.birthday
            self.header_patient_gender = self._convert_gender(patient.gender or 'I')
            
            if patient.l10n_latam_identification_type_id:
                # Mapear tipo de documento
                heath_code = patient.l10n_latam_identification_type_id.heath_code
                if heath_code:
                    self.header_patient_doc_type = heath_code
                else:
                    doc_type_mapping = {
                        '1': 'CC',
                        '2': 'TI',
                        '3': 'CE',
                        '4': 'PA',
                        '5': 'RC',
                    }
                    code = patient.l10n_latam_identification_type_id.code or ''
                    self.header_patient_doc_type = doc_type_mapping.get(code, 'CC')
            
            self.header_patient_user_type = patient.health_type or '01'
            self.header_patient_city_id = patient.city_id
            self.header_patient_country_id = patient.country_id
            self.header_patient_zone = patient.zona_territorial or '01'
            
            if patient.nationality_id:
                self.header_patient_nationality = patient.nationality_id.numeric_code or ''
    
    def _convert_gender(self, gender):
        """Convierte género entre formatos"""
        gender_mapping = {
            'H': 'M',
            'male': 'M',
            'M': 'F',
            'female': 'F',
            'I': 'I',
            'other': 'I'
        }
        return gender_mapping.get(gender, 'I')
    
    def action_validate_cups_codes(self):
        """Valida todos los códigos CUPS de la factura"""
        self.ensure_one()
        
        errors = []
        warnings = []
        validated_count = 0
        
        for line in self.invoice_line_ids:
            if not line.product_id:
                continue
                
            # Solo validar productos de tipo consulta o procedimiento
            if hasattr(line.product_id, 'rips_service_type') and line.product_id.rips_service_type in ['consulta', 'procedimiento']:
                # Obtener el código CUPS
                cups_code = None
                
                if hasattr(line.product_id, 'code_type') and line.product_id.code_type == 'cups':
                    if hasattr(line.product_id, 'cups_id') and line.product_id.cups_id:
                        cups_code = line.product_id.cups_id.code
                elif hasattr(line.product_id, 'custom_code') and line.product_id.custom_code:
                    cups_code = line.product_id.custom_code
                elif line.product_id.default_code:
                    cups_code = line.product_id.default_code
                
                if not cups_code:
                    warnings.append(f"Producto '{line.product_id.name}' sin código CUPS")
                    continue
                
                # Validar formato del código CUPS (6 dígitos)
                if not cups_code.isdigit() or len(cups_code) != 6:
                    errors.append(f"Producto '{line.product_id.name}': Código CUPS '{cups_code}' debe ser de 6 dígitos")
                else:
                    validated_count += 1
        
        # Preparar resultado
        result_text = f"Códigos CUPS validados: {validated_count}\n"
        
        if warnings:
            result_text += f"\nAdvertencias:\n" + "\n".join(warnings)
        
        if errors:
            result_text += f"\nErrores:\n" + "\n".join(errors)
            validation_status = False
        else:
            validation_status = True
        
        # Guardar resultado
        self.write({
            'rips_validated_cups': validation_status,
            'rips_validation_cups_date': fields.Datetime.now(),
            'rips_validation_cups_result': result_text
        })
        
        # Commit después de validar
        self.env.cr.commit()
        
        if errors:
            raise ValidationError(_("Se encontraron errores en la validación CUPS:\n%s") % '\n'.join(errors))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validación CUPS'),
                'message': result_text,
                'type': 'success' if validation_status else 'warning',
                'sticky': True,
            }
        }
    
    # =====================================================
    # IMPLEMENTACIÓN DE MÉTODOS ABSTRACTOS
    # =====================================================
    
    @api.model
    def _get_rips_config(self):
        """Obtiene la configuración RIPS activa"""
        config = self.env['rips.configuration'].search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)
        if not config:
            raise UserError(_("No se ha configurado RIPS SISPRO. Configure las credenciales."))
        return config
    
    def _determine_rips_endpoint_and_payload(self):
        """Determina endpoint y payload según tipo de documento"""
        if self.is_adjustment_note:
            return 'CARGAR_NOTA_AJUSTE', self._prepare_payload_for_endpoint('CARGAR_NOTA_AJUSTE')
        
        if self.is_voluntary_agreement:
            return 'CARGAR_NC_ACUERDO_VOLUNTADES', self._prepare_payload_for_endpoint('CARGAR_NC_ACUERDO_VOLUNTADES')
        
        if self.capita_type:
            if self.capita_type == 'initial':
                return 'CARGAR_CAPITA_INICIAL', self._prepare_payload_for_endpoint('CARGAR_CAPITA_INICIAL')
            elif self.capita_type == 'period':
                return 'CARGAR_CAPITA_PERIODO', self._prepare_payload_for_endpoint('CARGAR_CAPITA_PERIODO')
            elif self.capita_type == 'final':
                return 'CARGAR_CAPITA_FINAL', self._prepare_payload_for_endpoint('CARGAR_CAPITA_FINAL')
        
        if self.rips_without_invoice:
            return 'CARGAR_RIPS_SIN_FACTURA', self._prepare_payload_for_endpoint('CARGAR_RIPS_SIN_FACTURA')
        
        if self.move_type == 'out_invoice':
            return 'CARGAR_FEV_RIPS', self._prepare_payload_for_endpoint('CARGAR_FEV_RIPS')
        elif self.move_type == 'out_refund':
            if self.is_total_credit_note:
                return 'CARGAR_NC_TOTAL', self._prepare_payload_for_endpoint('CARGAR_NC_TOTAL')
            else:
                return 'CARGAR_NC', self._prepare_payload_for_endpoint('CARGAR_NC')
        elif self.move_type == 'in_refund':
            return 'CARGAR_ND', self._prepare_payload_for_endpoint('CARGAR_ND')
        
        return 'CARGAR_RIPS_SIN_FACTURA', self._prepare_payload_for_endpoint('CARGAR_RIPS_SIN_FACTURA')
    
    # =====================================================
    # MÉTODOS DE GENERACIÓN DE RIPS
    # =====================================================
    
    def generate_rips_json_api(self):
        """Genera el JSON RIPS según configuración"""
        self.ensure_one()
        
        # Si ya existe JSON y está validado, usarlo directamente
        if self.rips_json and self.rips_validation_status == 'validated':
            _logger.info(f"RIPS JSON ya existe y está validado para {self.name}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('RIPS Existente'),
                    'message': _('El RIPS ya está generado y validado'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        try:
            rips_data = self._generate_rips_base_structure()
            
            if self._should_include_users():
                usuarios = self._generate_rips_users()
                if usuarios:
                    rips_data['usuarios'] = usuarios
            
            is_valid, errors = self._validate_rips_structure(rips_data)
            #if not is_valid:
            #    raise ValidationError(_("Errores en la estructura RIPS:\n%s") % '\n'.join(errors))
            
            self._save_rips_json(rips_data)
            
            # Hacer commit después de guardar el JSON
            self.env.cr.commit()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('RIPS Generado'),
                    'message': _('RIPS JSON generado exitosamente'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.env.cr.rollback()
            raise
    
    def _generate_rips_base_structure(self):
        """Genera estructura base del RIPS"""
        doc_type = self._get_document_type()
        
        rips_data = {
            "numDocumentoIdObligado": self._validate_string(
                self.company_id.partner_id.vat_co or '', 
                min_length=9, max_length=9
            ),
            "numFactura": self._validate_string(
                self.name or '', 
                min_length=1, max_length=20, 
                no_leading_zero=True, 
                no_spaces=True
            ),
            "tipoNota": None,
            "numNota": None,
            "usuarios": []
        }
        
        if doc_type in ['credit_note', 'debit_note']:
            original_invoice = self.reversed_entry_id or getattr(self, 'debit_origin_id', None)
            if original_invoice:
                rips_data["numFactura"] = self._validate_string(
                    original_invoice.name or '', 
                    min_length=1, max_length=20, 
                    no_leading_zero=True, 
                    no_spaces=True
                )
                rips_data["tipoNota"] = self._get_rips_note_type(doc_type)
                rips_data["numNota"] = self._validate_string(
                    self.name or '', 
                    min_length=1, max_length=20, 
                    no_leading_zero=True, 
                    no_spaces=True
                )
        
        return rips_data
    
    def _should_include_users(self):
        """Determina si incluir usuarios"""
        return not (self.is_total_credit_note or self.is_voluntary_agreement)
    
    def _generate_rips_users(self):
        """Genera lista de usuarios para RIPS"""
        usuarios = []
        
        # Obtener datos de pacientes
        patient_data = self._collect_patient_data()
        
        consecutivo = 1
        for patient_key, lines in patient_data.items():
            usuario = self._prepare_usuario_data(lines[0], lines, consecutivo)
            if usuario:
                usuarios.append(usuario)
                consecutivo += 1
        
        return usuarios
    
    def _collect_patient_data(self):
        """Recolecta datos de pacientes según la lógica solicitada"""
        patient_data = {}
        
        # Verificar si hay pacientes en las líneas
        has_line_patients = any(
            line.patient_id or (line.patient_doc_type and line.patient_document)
            for line in self.invoice_line_ids
        )
        
        # Si no hay pacientes en líneas pero sí en encabezado
        if not has_line_patients and (self.patient_id or (self.header_patient_document and self.header_patient_doc_type)):
            # Usar datos del encabezado para todas las líneas
            patient_key = None
            patient_line = None
            
            if self.patient_id:
                # Priorizar campo relacionado
                # Si es hms.patient, usar partner_id, si no es res.partner directo
                if self.patient_id._name == 'hms.patient':
                    partner = self.patient_id.partner_id
                else:
                    partner = self.patient_id
                    
                patient_key = (
                    self._get_patient_doc_type(partner),
                    partner.vat or partner.ref or ''
                )
                patient_line = self._create_virtual_line_from_patient(self.patient_id)
            elif self.header_patient_document and self.header_patient_doc_type:
                # Usar campos manuales del encabezado
                patient_key = (self.header_patient_doc_type, self.header_patient_document)
                patient_line = self._create_virtual_line_from_header()
            
            if patient_key and patient_line:
                patient_data[patient_key] = [patient_line] + list(self.invoice_line_ids)
        else:
            # Si hay pacientes en líneas, agrupar por paciente
            for line in self.invoice_line_ids:
                patient_key = None
                
                # Priorizar campo relacionado patient_id
                if line.patient_id:
                    # Si es hms.patient, usar partner_id, si no es res.partner directo
                    if line.patient_id._name == 'hms.patient':
                        partner = line.patient_id.partner_id
                    else:
                        partner = line.patient_id
                        
                    patient_key = (
                        self._get_patient_doc_type(partner),
                        partner.vat or partner.ref or ''
                    )
                elif line.patient_doc_type and line.patient_document:
                    # Usar campos manuales
                    patient_key = (line.patient_doc_type, line.patient_document)
                
                if patient_key:
                    if patient_key not in patient_data:
                        patient_data[patient_key] = []
                    patient_data[patient_key].append(line)
                elif line.product_id and line.product_id.rips_service_type != 'none':
                    raise ValidationError(
                        _("La línea con producto '%s' requiere datos del paciente para RIPS.") % line.product_id.name
                    )
        
        return patient_data
    
    def _create_virtual_line_from_patient(self, patient):
        """Crea línea virtual desde patient_id"""
        # Si es hms.patient, usar partner_id, si no es res.partner directo
        if patient._name == 'hms.patient':
            partner = patient.partner_id
        else:
            partner = patient
            
        return type('obj', (object,), {
            'patient_id': patient,
            'patient_doc_type': self._get_patient_doc_type(partner),
            'patient_document': partner.vat or partner.ref or '',
            'patient_name': partner.name or '',
            'patient_birth_date': partner.birthday,
            'patient_gender': self._convert_gender(partner.gender or 'I'),
            'patient_user_type': partner.health_type or '01',
            'patient_country_id': partner.country_id,
            'patient_city_id': partner.city_id,
            'patient_zone': partner.zona_territorial or '01',
            'patient_nationality': partner.nationality_id.numeric_code if partner.nationality_id else None,
            'product_id': False,
        })()
    
    def _create_virtual_line_from_header(self):
        """Crea línea virtual desde campos del encabezado"""
        return type('obj', (object,), {
            'patient_id': False,
            'patient_doc_type': self.header_patient_doc_type,
            'patient_document': self.header_patient_document,
            'patient_name': self.header_patient_name,
            'patient_birth_date': self.header_patient_birth_date,
            'patient_gender': self.header_patient_gender,
            'patient_user_type': self.header_patient_user_type,
            'patient_country_id': self.header_patient_country_id,
            'patient_city_id': self.header_patient_city_id,
            'patient_zone': self.header_patient_zone,
            'patient_nationality': self.header_patient_nationality,
            'product_id': False,
        })()
    
    def _get_patient_doc_type(self, patient):
        """Obtiene tipo documento del paciente"""
        if patient.l10n_latam_identification_type_id:
            # Priorizar heath_code si existe
            heath_code = patient.l10n_latam_identification_type_id.heath_code
            if heath_code:
                return heath_code
            
            # Si no, usar mapeo
            doc_type_mapping = {
                '1': 'CC',
                '2': 'TI',
                '3': 'CE',
                '4': 'PA',
                '5': 'RC',
            }
            code = patient.l10n_latam_identification_type_id.code or ''
            return doc_type_mapping.get(code, 'CC')
        return 'CC'
    
    def _prepare_usuario_data(self, patient_line, service_lines, consecutivo):
        """Prepara datos de usuario con validaciones según resolución 2275"""
        # Inicializar variables
        doc_type = None
        doc_number = None
        birth_date = None
        gender = None
        user_type = None
        country_id = None
        city_id = None
        zone = None
        nationality = None
        
        # Priorizar datos del campo relacionado patient_id si existe
        if patient_line.patient_id:
            # Si es hms.patient, usar partner_id, si no es res.partner directo
            if patient_line.patient_id._name == 'hms.patient':
                patient = patient_line.patient_id.partner_id
            else:
                patient = patient_line.patient_id
                
            doc_type = self._get_patient_doc_type(patient)
            doc_number = patient.vat or patient.ref or ''
            birth_date = patient.birthday
            gender = self._convert_gender(patient.gender or 'I')
            user_type = patient.health_type or '01'
            country_id = patient.country_id
            city_id = patient.city_id
            zone = patient.zona_territorial or '01'
            nationality = patient.nationality_id.numeric_code if patient.nationality_id else None
        
        # Si no hay patient_id o si queremos sobrescribir con campos manuales
        # Los campos manuales tienen prioridad si están llenos
        if patient_line.patient_doc_type:
            doc_type = patient_line.patient_doc_type
        if patient_line.patient_document:
            doc_number = patient_line.patient_document
        if patient_line.patient_birth_date:
            birth_date = patient_line.patient_birth_date
        if patient_line.patient_gender:
            gender = patient_line.patient_gender
        if patient_line.patient_user_type:
            user_type = patient_line.patient_user_type
        if patient_line.patient_country_id:
            country_id = patient_line.patient_country_id
        if patient_line.patient_city_id:
            city_id = patient_line.patient_city_id
        if patient_line.patient_zone:
            zone = patient_line.patient_zone
        if patient_line.patient_nationality:
            nationality = patient_line.patient_nationality
        
        # Obtener valores con defaults
        country_code = country_id.numeric_code if country_id else RIPS_DEFAULT_VALUES['PAIS_DEFAULT']
        city_code = city_id.code if city_id else None
        
        usuario = {
            "tipoDocumentoIdentificacion": self._validate_string(
                doc_type or 'CC', 
                min_length=2, max_length=2
            ),
            "numDocumentoIdentificacion": self._validate_string(
                doc_number or '', 
                min_length=4, max_length=20, 
                no_leading_zero=True, 
                no_spaces=True
            ),
            "tipoUsuario": self._validate_string(
                user_type or RIPS_DEFAULT_VALUES['TIPO_USUARIO'], 
                min_length=2, max_length=2
            ),
            "fechaNacimiento": self._validate_date(
                birth_date, 
                format_str='%Y-%m-%d',
                default="1900-01-01"
            ),
            "codSexo": self._validate_string(
                gender or 'I', 
                min_length=1, max_length=1
            ),
            "codPaisResidencia": self._validate_string(
                country_code,
                min_length=3, max_length=3
            ),
            "codMunicipioResidencia": self._validate_string(
                city_code,
                min_length=5, max_length=5,
                allow_null=True
            ),
            "codZonaTerritorialResidencia": self._validate_string(
                zone or RIPS_DEFAULT_VALUES['ZONA_TERRITORIAL'],
                min_length=2, max_length=2,
                allow_null=True
            ),
            "incapacidad": "NO",
            "consecutivo": self._validate_numeric(
                consecutivo,
                min_digits=1, max_digits=7
            ),
            "codPaisOrigen": self._validate_string(
                nationality or country_code,
                min_length=3, max_length=3
            ),
            "servicios": {}
        }
        
        # Procesar servicios
        servicios = self._prepare_servicios(service_lines)
        if servicios:
            usuario["servicios"] = servicios
        
        return usuario if usuario["servicios"] else None
    
    def _prepare_servicios(self, lines):
        """Prepara todos los servicios del usuario"""
        servicios = {}
        consecutivos = {
            'consultas': 1,
            'procedimientos': 1,
            'medicamentos': 1,
            'otrosServicios': 1
        }
        
        for line in lines:
            if not line.product_id:
                continue
                
            service_type = line.product_id.rips_service_type
            if service_type == 'none':
                continue
            
            service_data = self._prepare_service_data(line, service_type, consecutivos)
            if service_data:
                service_key = self._get_service_key(service_type)
                if service_key not in servicios:
                    servicios[service_key] = []
                servicios[service_key].append(service_data)
                consecutivos[service_key] += 1
        
        return servicios
    
    def _get_service_key(self, service_type):
        """Mapea tipo de servicio a clave JSON"""
        mapping = {
            'consulta': 'consultas',
            'procedimiento': 'procedimientos',
            'medicamento': 'medicamentos',
            'otro_servicio': 'otrosServicios'
        }
        return mapping.get(service_type, 'otrosServicios')
    
    def _prepare_service_data(self, line, service_type, consecutivos):
        """Prepara datos de servicio según tipo"""
        if service_type == 'consulta':
            return self._prepare_consulta_data(line, consecutivos['consultas'])
        elif service_type == 'procedimiento':
            return self._prepare_procedimiento_data(line, consecutivos['procedimientos'])
        elif service_type == 'medicamento':
            return self._prepare_medicamento_data(line, consecutivos['medicamentos'])
        elif service_type == 'otro_servicio':
            return self._prepare_otro_servicio_data(line, consecutivos['otrosServicios'])
        return None
    
    def _prepare_consulta_data(self, line, consecutivo):
        amounts = self._calculate_service_amounts(line)
        
        num_fev = None
        if line.valor_pago_moderador and line.valor_pago_moderador > 0:
            num_fev = self._validate_string(
                line.num_fev_pago_moderador or self.name,
                max_length=20,
                allow_null=False
            )
        
        return {
            "codPrestador": self._validate_string(
                self.company_id.partner_id.ref or RIPS_DEFAULT_VALUES['CODIGO_PRESTADOR'],
                min_length=12, max_length=12
            ),
            "fechaInicioAtencion": self._validate_date(
                line.fecha_atencion or self.date,
                format_str='%Y-%m-%d %H:%M'
            ),
            "numAutorizacion": self._validate_string(
                line.autorizacion,
                max_length=30,
                allow_null=True
            ),
            "codConsulta": self._validate_string(
                self._get_product_code(line.product_id, 'consulta'),
                min_length=6, max_length=6
            ),
            "modalidadGrupoServicioTecSal": self._validate_string(
                line.modalidad or RIPS_DEFAULT_VALUES['MODALIDAD_ATENCION'],
                min_length=2, max_length=2
            ),
            "grupoServicios": self._validate_string(
                line.grupo_servicio or RIPS_DEFAULT_VALUES['GRUPO_SERVICIO_CONSULTA'],
                min_length=2, max_length=2
            ),
            "codServicio": self._validate_numeric(
                line.cod_servicio or RIPS_DEFAULT_VALUES['COD_SERVICIO_CONSULTA'],
                min_digits=3, max_digits=4
            ),
            "finalidadTecnologiaSalud": self._validate_string(
                line.finalidad or RIPS_DEFAULT_VALUES['FINALIDAD_CONSULTA'],
                min_length=2, max_length=2
            ),
            "causaMotivoAtencion": self._validate_string(
                line.causa_externa or RIPS_DEFAULT_VALUES['CAUSA_EXTERNA'],
                min_length=2, max_length=2
            ),
            "codDiagnosticoPrincipal": self._validate_string(
                line.diagnostico_principal or RIPS_DEFAULT_VALUES['DIAGNOSTICO_DEFAULT'],
                min_length=4, max_length=25
            ),
            "codDiagnosticoRelacionado1": self._validate_string(
                line.diagnostico_relacionado1,
                min_length=4, max_length=25,
                allow_null=True
            ),
            "codDiagnosticoRelacionado2": self._validate_string(
                line.diagnostico_relacionado2,
                min_length=4, max_length=25,
                allow_null=True
            ),
            "codDiagnosticoRelacionado3": self._validate_string(
                line.diagnostico_relacionado3,
                min_length=4, max_length=25,
                allow_null=True
            ),
            "tipoDiagnosticoPrincipal": self._validate_string(
                line.tipo_diagnostico or RIPS_DEFAULT_VALUES['TIPO_DIAGNOSTICO'],
                min_length=2, max_length=2
            ),
            "tipoDocumentoIdentificacion": self._validate_string(
                self._get_professional_doc_type(line),
                min_length=2, max_length=2
            ),
            "numDocumentoIdentificacion": self._validate_string(
                self._get_professional_doc_number(line),
                min_length=4, max_length=20
            ),
            "vrServicio": self._validate_numeric(
                amounts['total'],  # Usar total con impuestos
                min_digits=1, max_digits=10
            ),
            "conceptoRecaudo": self._validate_string(
                line.tipo_pago_moderador or RIPS_DEFAULT_VALUES['CONCEPTO_RECAUDO'],
                min_length=2, max_length=2
            ),
            "valorPagoModerador": self._validate_numeric(
                line.valor_pago_moderador or 0,
                min_digits=1, max_digits=10
            ),
            "numFEVPagoModerador": num_fev,
            "consecutivo": self._validate_numeric(
                consecutivo,
                min_digits=1, max_digits=7
            )
        }
    
    def _prepare_procedimiento_data(self, line, consecutivo):
        amounts = self._calculate_service_amounts(line)
        
        num_fev = None
        if line.valor_pago_moderador and line.valor_pago_moderador > 0:
            num_fev = self._validate_string(
                line.num_fev_pago_moderador or self.name,
                max_length=20,
                allow_null=False
            )
        
        return {
            "codPrestador": self._validate_string(
                self.company_id.partner_id.ref or RIPS_DEFAULT_VALUES['CODIGO_PRESTADOR'],
                min_length=12, max_length=12
            ),
            "fechaInicioAtencion": self._validate_date(
                line.fecha_procedimiento or self.date,
                format_str='%Y-%m-%d %H:%M'
            ),
            "idMIPRES": self._validate_string(
                line.id_mipres,
                max_length=15,
                allow_null=True
            ),
            "numAutorizacion": self._validate_string(
                line.autorizacion,
                max_length=30,
                allow_null=True
            ),
            "codProcedimiento": self._validate_string(
                self._get_product_code(line.product_id, 'procedimiento'),
                min_length=6, max_length=6
            ),
            "viaIngresoServicioSalud": self._validate_string(
                getattr(line.product_id, 'rips_via_ingreso', '') or RIPS_DEFAULT_VALUES['VIA_INGRESO'],
                min_length=2, max_length=2
            ),
            "modalidadGrupoServicioTecSal": self._validate_string(
                getattr(line.product_id, 'rips_modalidad', '') or RIPS_DEFAULT_VALUES['MODALIDAD_ATENCION'],
                min_length=2, max_length=2
            ),
            "grupoServicios": self._validate_string(
                getattr(line.product_id, 'rips_grupo_servicio', '') or RIPS_DEFAULT_VALUES['GRUPO_SERVICIO_PROCEDIMIENTO'],
                min_length=2, max_length=2
            ),
            "codServicio": self._validate_numeric(
                getattr(line.product_id, 'rips_cod_servicio', 0) or RIPS_DEFAULT_VALUES['COD_SERVICIO_PROCEDIMIENTO'],
                min_digits=3, max_digits=4
            ),
            "finalidadTecnologiaSalud": self._validate_string(
                getattr(line.product_id, 'rips_finalidad', '') or RIPS_DEFAULT_VALUES['FINALIDAD_PROCEDIMIENTO'],
                min_length=2, max_length=2
            ),
            "tipoDocumentoIdentificacion": self._validate_string(
                self._get_professional_doc_type(line),
                min_length=2, max_length=2
            ),
            "numDocumentoIdentificacion": self._validate_string(
                self._get_professional_doc_number(line),
                min_length=4, max_length=20
            ),
            "codDiagnosticoPrincipal": self._validate_string(
                line.diagnostico_principal or RIPS_DEFAULT_VALUES['DIAGNOSTICO_DEFAULT'],
                min_length=4, max_length=25
            ),
            "codDiagnosticoRelacionado": self._validate_string(
                line.diagnostico_relacionado,
                min_length=4, max_length=25,
                allow_null=True
            ),
            "codComplicacion": self._validate_string(
                line.complicacion,
                min_length=4, max_length=25,
                allow_null=True
            ),
            "vrServicio": self._validate_numeric(
                amounts['total'],  # Usar total con impuestos
                min_digits=1, max_digits=15
            ),
            "conceptoRecaudo": self._validate_string(
                line.tipo_pago_moderador or RIPS_DEFAULT_VALUES['CONCEPTO_RECAUDO'],
                min_length=2, max_length=2
            ),
            "valorPagoModerador": self._validate_numeric(
                line.valor_pago_moderador or 0,
                min_digits=1, max_digits=10
            ),
            "numFEVPagoModerador": num_fev,
            "consecutivo": self._validate_numeric(
                consecutivo,
                min_digits=1, max_digits=7
            )
        }
    
    def _prepare_medicamento_data(self, line, consecutivo):
        amounts = self._calculate_service_amounts(line)
        
        tipo_medicamento = self._validate_string(
            line.tipo_medicamento or '01',
            min_length=2, max_length=2
        )
        
        concentracion = None
        unidad_medida = None
        forma_farmaceutica = None
        
        if tipo_medicamento == '03':
            concentracion = self._validate_numeric(
                line.concentracion or 0,
                max_digits=3,
                allow_null=True
            )
            unidad_medida = self._validate_numeric(
                line.unidad_medida or 0,
                max_digits=4,
                allow_null=True
            )
            forma_farmaceutica = self._validate_string(
                line.forma_farmaceutica,
                min_length=6, max_length=8,
                allow_null=True
            )
        
        num_fev = None
        if line.valor_pago_moderador and line.valor_pago_moderador > 0:
            num_fev = self._validate_string(
                line.num_fev_pago_moderador or self.name,
                max_length=20,
                allow_null=False
            )
        
        return {
            "codPrestador": self._validate_string(
                self.company_id.partner_id.ref,
                min_length=12, max_length=12,
                allow_null=True
            ),
            "numAutorizacion": self._validate_string(
                line.autorizacion,
                max_length=30,
                allow_null=True
            ),
            "idMIPRES": self._validate_string(
                line.id_mipres,
                max_length=15,
                allow_null=True
            ),
            "fechaDispensAdmon": self._validate_date(
                line.fecha_dispensacion or self.date,
                format_str='%Y-%m-%d %H:%M'
            ),
            "codDiagnosticoPrincipal": self._validate_string(
                line.diagnostico_principal or RIPS_DEFAULT_VALUES['DIAGNOSTICO_DEFAULT'],
                min_length=4, max_length=25
            ),
            "codDiagnosticoRelacionado": self._validate_string(
                line.diagnostico_relacionado1,
                min_length=4, max_length=25,
                allow_null=True
            ),
            "tipoMedicamento": tipo_medicamento,
            "codTecnologiaSalud": self._validate_string(
                self._get_product_code(line.product_id, 'medicamento'),
                min_length=1, max_length=20
            ),
            "nomTecnologiaSalud": self._validate_string(
                line.product_id.name if line.product_id else "",
                max_length=30,
                allow_null=True
            ),
            "concentracionMedicamento": concentracion,
            "unidadMedida": unidad_medida,
            "formaFarmaceutica": forma_farmaceutica,
            "unidadMinDispensa": self._validate_numeric(
                line.unidad_min_dispensacion or 1,
                min_digits=1, max_digits=2
            ),
            "cantidadMedicamento": self._validate_numeric(
                line.quantity or 1,
                min_digits=1, max_digits=10
            ),
            "diasTratamiento": self._validate_numeric(
                line.dias_tratamiento or 1,
                min_digits=1, max_digits=3
            ),
            "tipoDocumentoIdentificacion": self._validate_string(
                self._get_professional_doc_type(line),
                min_length=2, max_length=2
            ),
            "numDocumentoIdentificacion": self._validate_string(
                self._get_professional_doc_number(line),
                min_length=4, max_length=20
            ),
            "vrUnitMedicamento": self._validate_numeric(
                amounts['unit_price'],
                min_digits=1, max_digits=15
            ),
            "vrServicio": self._validate_numeric(
                amounts['total'],  # Usar total con impuestos
                min_digits=1, max_digits=15
            ),
            "conceptoRecaudo": self._validate_string(
                line.tipo_pago_moderador or RIPS_DEFAULT_VALUES['CONCEPTO_RECAUDO'],
                min_length=2, max_length=2
            ),
            "valorPagoModerador": self._validate_numeric(
                line.valor_pago_moderador or 0,
                min_digits=1, max_digits=10
            ),
            "numFEVPagoModerador": num_fev,
            "consecutivo": self._validate_numeric(
                consecutivo,
                min_digits=1, max_digits=7
            )
        }
    
    def _prepare_otro_servicio_data(self, line, consecutivo):
        amounts = self._calculate_service_amounts(line)
        
        num_fev = None
        if line.valor_pago_moderador and line.valor_pago_moderador > 0:
            num_fev = self._validate_string(
                line.num_fev_pago_moderador or self.name,
                max_length=20,
                allow_null=False
            )
        
        cantidad_os = self._validate_numeric(
            line.quantity or 1,
            min_digits=5, max_digits=5  # Tamaño fijo de 5 dígitos
        )
        
        return {
            "codPrestador": self._validate_string(
                self.company_id.partner_id.ref,
                min_length=12, max_length=12,
                allow_null=True
            ),
            "numAutorizacion": None,
            "idMIPRES": None,
            "fechaSuministroTecnologia": self._validate_date(
                line.fecha_suministro or self.date_start or self.date,
                format_str='%Y-%m-%d %H:%M'
            ),
            "tipoOS": self._validate_string(
                line.tipo_servicio or '01',
                min_length=2, max_length=2
            ),
            "codTecnologiaSalud": self._validate_string(
                self._get_product_code(line.product_id, 'otro_servicio'),
                min_length=1, max_length=20
            ),
            "nomTecnologiaSalud": self._validate_string(
                line.product_id.name if line.product_id else "",
                min_length=60, max_length=60,
                allow_null=True
            ),
            "cantidadOS": cantidad_os,
            "tipoDocumentoIdentificacion": self._validate_string(
                self._get_professional_doc_type(line),
                min_length=2, max_length=2,
                allow_null=True
            ),
            "numDocumentoIdentificacion": self._validate_string(
                self._get_professional_doc_number(line),
                min_length=4, max_length=20,
                allow_null=True
            ),
            "vrUnitOS": self._validate_numeric(
                amounts['unit_price'],
                min_digits=1, max_digits=15
            ),
            "vrServicio": self._validate_numeric(
                amounts['total'],  # Usar total con impuestos
                min_digits=1, max_digits=15
            ),
            "conceptoRecaudo": self._validate_string(
                line.tipo_pago_moderador or RIPS_DEFAULT_VALUES['CONCEPTO_RECAUDO'],
                min_length=2, max_length=2
            ),
            "valorPagoModerador": self._validate_numeric(
                line.valor_pago_moderador or 0,
                min_digits=1, max_digits=10
            ),
            "numFEVPagoModerador": num_fev,
            "consecutivo": self._validate_numeric(
                consecutivo,
                min_digits=1, max_digits=7
            )
        }

    def action_preview_rips_amounts(self):
        """Muestra vista previa de los montos RIPS con impuestos"""
        self.ensure_one()
        
        # Recolectar información de montos por línea
        lines_info = []
        total_subtotal = 0
        total_iva = 0
        total_ic = 0
        total_ica = 0
        total_inc = 0
        total_otros = 0
        total_general = 0
        
        for line in self.invoice_line_ids:
            if line.product_id and line.product_id.rips_service_type != 'none':
                amounts = self._calculate_service_amounts(line)
                
                lines_info.append({
                    'product': line.product_id.name,
                    'quantity': line.quantity,
                    'subtotal': amounts['subtotal'],
                    'iva': amounts['iva_amount'],
                    'ic': amounts['ic_amount'],
                    'ica': amounts['ica_amount'],
                    'inc': amounts['inc_amount'],
                    'otros': amounts['other_taxes'],
                    'total': amounts['total']
                })
                
                total_subtotal += amounts['subtotal']
                total_iva += amounts['iva_amount']
                total_ic += amounts['ic_amount']
                total_ica += amounts['ica_amount']
                total_inc += amounts['inc_amount']
                total_otros += amounts['other_taxes']
                total_general += amounts['total']
        
        # Crear mensaje de vista previa
        message = _("""
<h3>Vista Previa de Montos RIPS</h3>
<p><strong>Configuración:</strong></p>
<ul>
    <li>Incluir impuestos: %s</li>
    <li>Forzar valores enteros: %s</li>
</ul>

<p><strong>Resumen de Impuestos:</strong></p>
<table style="width:100%%; border-collapse: collapse;">
    <tr style="background-color: #f0f0f0;">
        <th style="border: 1px solid #ddd; padding: 8px;">Concepto</th>
        <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Valor</th>
    </tr>
    <tr>
        <td style="border: 1px solid #ddd; padding: 8px;">Subtotal</td>
        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">%s</td>
    </tr>
    <tr>
        <td style="border: 1px solid #ddd; padding: 8px;">IVA</td>
        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">%s</td>
    </tr>
    <tr>
        <td style="border: 1px solid #ddd; padding: 8px;">IC</td>
        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">%s</td>
    </tr>
    <tr>
        <td style="border: 1px solid #ddd; padding: 8px;">ICA</td>
        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">%s</td>
    </tr>
    <tr>
        <td style="border: 1px solid #ddd; padding: 8px;">INC</td>
        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">%s</td>
    </tr>
    <tr>
        <td style="border: 1px solid #ddd; padding: 8px;">Otros Impuestos</td>
        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">%s</td>
    </tr>
    <tr style="background-color: #f0f0f0; font-weight: bold;">
        <td style="border: 1px solid #ddd; padding: 8px;">TOTAL</td>
        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">%s</td>
    </tr>
</table>

<p><small>Nota: Los valores mostrados son los que se reportarán en el archivo RIPS.</small></p>
""") % (
            _('Sí') if self.rips_include_taxes else _('No'),
            _('Sí') if self.rips_force_integer_values else _('No'),
            '{:,.0f}'.format(total_subtotal),
            '{:,.0f}'.format(total_iva),
            '{:,.0f}'.format(total_ic),
            '{:,.0f}'.format(total_ica),
            '{:,.0f}'.format(total_inc),
            '{:,.0f}'.format(total_otros),
            '{:,.0f}'.format(total_general)
        )
        
        # Mostrar wizard con la información
        return {
            'name': _('Vista Previa RIPS'),
            'type': 'ir.actions.act_window',
            'res_model': 'rips.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_message': message,
            }
        }
    
    # =====================================================
    # MÉTODOS AUXILIARES
    # =====================================================
    
    def _get_document_type(self):
        """Determina tipo de documento"""
        if self.move_type == 'out_invoice':
            return 'invoice'
        elif self.move_type == 'out_refund':
            return 'credit_note'
        elif self.move_type == 'in_refund':
            return 'debit_note'
        return 'invoice'
    
    def _get_rips_note_type(self, doc_type):
        """Obtiene tipo de nota RIPS"""
        if doc_type == 'credit_note':
            return "NC"
        elif doc_type == 'debit_note':
            return "ND"
        return None
    
    def _get_xml_fev_file(self):
        """Obtiene XML de factura electrónica"""
        if self.attached_document_xml:
            return self.attached_document_xml.decode() if isinstance(self.attached_document_xml, bytes) else self.attached_document_xml
        
        try:
            if hasattr(self, '_get_attached_document'):
                attached_document, error = self._get_attached_document()
                if not error and attached_document:
                    xml_base64 = base64.b64encode(attached_document).decode('utf-8')
                    self.write({
                        'attached_document_xml': xml_base64,
                        'attached_document_xml_filename': f'{self.name}_AttachedDocument.xml'
                    })
                    self.env.cr.commit()
                    return xml_base64
        except Exception as e:
            _logger.warning(f"Error al obtener AttachedDocument: {str(e)}")
        
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'account.move'),
            ('res_id', '=', self.id),
            '|', '|',
            ('name', 'ilike', '%AttachedDocument%'),
            ('name', 'ilike', '%attached_document%'),
            ('name', 'ilike', '%.xml'),
        ], limit=1, order='id desc')
        
        if xml_attachment:
            self.write({
                'attached_document_xml': xml_attachment.datas,
                'attached_document_xml_filename': xml_attachment.name
            })
            return xml_attachment.datas.decode() if isinstance(xml_attachment.datas, bytes) else xml_attachment.datas
        
        return None
    
    def _generate_empty_rips(self):
        """Genera un RIPS vacío"""
        return {
            "numDocumentoIdObligado": self.company_id.partner_id.vat_co or "",
            "numFactura": self.name,
            "tipoNota": None,
            "numNota": None,
            "usuarios": []
        }
    
    def _generate_capita_rips(self, endpoint_key):
        """Genera RIPS para cápita"""
        capita_type_map = {
            'CARGAR_CAPITA_INICIAL': 'initial',
            'CARGAR_CAPITA_PERIODO': 'period',
            'CARGAR_CAPITA_FINAL': 'final'
        }
        
        return {
            "numDocumentoIdObligado": self.company_id.partner_id.vat_co or "",
            "numFactura": self.name,
            "tipoCapita": capita_type_map.get(endpoint_key, 'period'),
            "usuarios": []
        }
    
    def _calculate_service_amounts(self, line):
        """
        Calcula los montos del servicio incluyendo impuestos
        
        Args:
            line: Línea de factura
            
        Returns:
            dict: Diccionario con los montos calculados
        """
        amounts = {
            'subtotal': 0,
            'tax_amount': 0,
            'total': 0,
            'unit_price': 0,
            'iva_amount': 0,
            'ic_amount': 0,
            'ica_amount': 0,
            'inc_amount': 0,
            'other_taxes': 0
        }
        
        if not line:
            return amounts
        
        amounts['unit_price'] = line.price_unit or 0
        amounts['subtotal'] = line.price_subtotal or 0
        
        include_taxes = getattr(self, 'rips_include_taxes', True)
        
        if include_taxes and line.tax_ids:
            currency = line.move_id.currency_id or line.company_id.currency_id
            
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                currency=currency,
                quantity=line.quantity,
                product=line.product_id,
                partner=line.move_id.partner_id
            )
            
            for tax in taxes['taxes']:
                tax_record = self.env['account.tax'].browse(tax['id'])
                
                if getattr(tax_record, 'tributes', None):
                    if tax_record.tributes == '01':  # IVA
                        amounts['iva_amount'] += tax['amount']
                    elif tax_record.tributes == '02':  # IC
                        amounts['ic_amount'] += tax['amount']
                    elif tax_record.tributes == '03':  # ICA
                        amounts['ica_amount'] += tax['amount']
                    elif tax_record.tributes == '04':  # INC
                        amounts['inc_amount'] += tax['amount']
                    else:
                        amounts['other_taxes'] += tax['amount']
                else:
                    amounts['other_taxes'] += tax['amount']
                
                amounts['tax_amount'] += tax['amount']
            
            amounts['total'] = taxes['total_included']
        else:
            amounts['total'] = amounts['subtotal']
        
        force_integer = self.rips_force_integer_values
        
        for key in amounts:
            amounts[key] = self._convert_to_rips_integer(amounts[key], use_rips_config=force_integer)
        
        return amounts
    
    def _convert_to_rips_integer(self, amount, use_rips_config=True):
        """
        Convierte montos a enteros para RIPS
        
        Args:
            amount: Monto a convertir
            use_rips_config: Si usar configuración de forzar enteros
        
        Returns:
            int: Monto como entero
        """
        if amount is None:
            return 0
        
        try:
            force_integer = use_rips_config
            
            decimal_amount = Decimal(str(amount))
            
            if force_integer:
                return int(decimal_amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            else:
                decimal_amount = decimal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                return float(decimal_amount)
                
        except (ValueError, TypeError):
            return 0
    
    def _get_product_code(self, product, service_type):
        """Obtiene código del producto según tipo"""
        if not product:
            return RIPS_DEFAULT_VALUES.get(f'CUPS_{service_type.upper()}', '')
        
        code = getattr(product, 'rips_code', '') or getattr(product, 'default_code', '')
        
        return code or ''
    
    def _get_professional_doc_type(self, line):
        """Obtiene tipo documento profesional"""
        if line.professional_id and line.professional_id.l10n_latam_identification_type_id:
            heath_code = getattr(line.professional_id.l10n_latam_identification_type_id, 'heath_code', '')
            return heath_code or 'CC'
        return RIPS_DEFAULT_VALUES['PROFESIONAL_DOC_TYPE']
    
    def _get_professional_doc_number(self, line):
        """Obtiene número documento profesional"""
        if line.professional_id and line.professional_id.vat:
            return line.professional_id.vat
        return RIPS_DEFAULT_VALUES['PROFESIONAL_DOC_NUMBER']


class RipsPreviewWizard(models.TransientModel):
    """Wizard para mostrar vista previa de RIPS"""
    _name = 'rips.preview.wizard'
    _description = 'Vista Previa RIPS'
    
    invoice_id = fields.Many2one('account.move', string='Factura')
    message = fields.Html(string='Vista Previa', readonly=True)
    
    def action_generate_rips(self):
        """Genera el RIPS desde la vista previa"""
        if self.invoice_id:
            return self.invoice_id.generate_rips_json_api()
    
    def action_close(self):
        """Cierra el wizard"""
        return {'type': 'ir.actions.act_window_close'}


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    # Campos del paciente
    patient_id = fields.Many2one('hms.patient', string='Paciente')
    patient_document = fields.Char(string='Documento Paciente')
    patient_name = fields.Char(string='Nombre Paciente')
    patient_city_id = fields.Many2one('res.city', string='Ciudad Paciente')
    patient_nationality = fields.Char(string='Nacionalidad Paciente')
    patient_country_id = fields.Many2one('res.country', string='País Paciente')
    patient_user_type = fields.Selection([
        ('01', 'Contributivo cotizante'),
        ('02', 'Contributivo beneficiario'),
        ('03', 'Contributivo adicional'),
        ('04', 'Subsidiado'),
        ('05', 'Sin régimen'),
        ('06', 'Especiales o de Excepción cotizante'),
        ('07', 'Especiales o de Excepción beneficiario'),
        ('08', 'Particular'),
        ('09', 'Tomador/Amparado ARL'),
        ('10', 'Tomador/Amparado SOAT'),
        ('11', 'Tomador/Amparado Planes voluntarios de salud'),
    ], string='Tipo de Usuario')
    patient_gender = fields.Selection([
        ('M', 'Hombre'),
        ('F', 'Mujer'),
        ('I', 'Indeterminado')
    ], string='Género Paciente')
    patient_zone = fields.Selection([
        ('01', 'Urbano'),
        ('02', 'Rural')
    ], string='Zona Paciente')
    patient_birth_date = fields.Date(string='Fecha Nacimiento Paciente')
    patient_doc_type = fields.Selection([
        ('CC', 'Cédula de Ciudadanía'),
        ('TI', 'Tarjeta de Identidad'),
        ('CE', 'Cédula de Extranjería'),
        ('PA', 'Pasaporte'),
        ('RC', 'Registro Civil'),
        ('MS', 'Menor sin identificación'),
        ('AS', 'Adulto sin identificación'),
        ('PE', 'Permiso especial de permanencia'),
        ('SC', 'Salvoconducto de permanencia'),
        ('PT', 'Permiso por protección temporal')
    ], string='Tipo Documento Paciente')
    
    # Campos de servicio
    treatment_id = fields.Many2one('hms.treatment', string='Tratamiento')
    autorizacion = fields.Char(string='Número de Autorización')
    id_mipres = fields.Char(string='ID MIPRES')
    professional_id = fields.Many2one('res.partner', string='Profesional', domain=[('is_company', '=', False)])
    
    # Fechas
    fecha_atencion = fields.Datetime(string='Fecha de Atención')
    fecha_procedimiento = fields.Datetime(string='Fecha de Procedimiento')
    fecha_dispensacion = fields.Datetime(string='Fecha de Dispensación')
    fecha_suministro = fields.Datetime(string='Fecha de Suministro')
    
    # Campos comunes
    tipo_pago_moderador = fields.Selection([
        ('01', 'Copago'),
        ('02', 'Cuota moderadora'),
        ('03', 'Pagos compartidos planes voluntarios'),
        ('04', 'Anticipos'),
        ('05', 'No aplica')
    ], string='Tipo de Pago Moderador', default='05')
    valor_pago_moderador = fields.Float(string='Valor Pago Moderador', default=0.0)
    num_fev_pago_moderador = fields.Char(string='Número FEV Pago Moderador')
    
    # Campos para consultas
    modalidad = fields.Char(string='Modalidad de Atención', default='01')
    grupo_servicio = fields.Char(string='Grupo de Servicio', default='01')
    cod_servicio = fields.Integer(string='Código de Servicio', default=101)
    finalidad = fields.Char(string='Finalidad', default='10')
    causa_externa = fields.Char(string='Causa Externa', default='13')
    diagnostico_principal = fields.Char(string='Diagnóstico Principal')
    diagnostico_relacionado1 = fields.Char(string='Diagnóstico Relacionado 1')
    diagnostico_relacionado2 = fields.Char(string='Diagnóstico Relacionado 2')
    diagnostico_relacionado3 = fields.Char(string='Diagnóstico Relacionado 3')
    tipo_diagnostico = fields.Selection([
        ('01', 'Impresión diagnóstica'),
        ('02', 'Confirmado nuevo'),
        ('03', 'Confirmado repetido')
    ], string='Tipo de Diagnóstico', default='01')
    
    # Campos para procedimientos
    via_ingreso = fields.Selection([
        ('01', 'Por consulta'),
        ('02', 'Por urgencias'),
        ('03', 'Por hospitalización'),
        ('04', 'Por remisión')
    ], string='Vía de Ingreso', default='01')
    diagnostico_relacionado = fields.Char(string='Diagnóstico Relacionado')
    complicacion = fields.Char(string='Código Complicación')
    
    # Campos para medicamentos
    tipo_medicamento = fields.Selection([
        ('01', 'Medicamento PBS'),
        ('02', 'Medicamento No PBS'),
        ('03', 'Preparación Magistral')
    ], string='Tipo de Medicamento', default='01')
    concentracion = fields.Float(string='Concentración')
    unidad_medida = fields.Integer(string='Unidad de Medida')
    forma_farmaceutica = fields.Char(string='Forma Farmacéutica')
    unidad_min_dispensacion = fields.Integer(string='Unidad Min. Dispensación', default=1)
    dias_tratamiento = fields.Integer(string='Días de Tratamiento', default=1)
    
    # Campos para otros servicios
    tipo_servicio = fields.Selection([
        ('01', 'Dispositivos médicos e insumos'),
        ('02', 'Traslados'),
        ('03', 'Estancias'),
        ('04', 'Servicios complementarios'),
        ('05', 'Honorarios')
    ], string='Tipo de Otro Servicio', default='01')
    
    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        """Actualizar campos del paciente cuando se selecciona"""
        if self.patient_id:
            # Si es hms.patient, usar partner_id
            patient = self.patient_id.partner_id if self.patient_id._name == 'hms.patient' else self.patient_id
            
            self.patient_document = patient.vat or patient.ref or ''
            self.patient_name = patient.name or ''
            self.patient_city_id = patient.city_id
            self.patient_country_id = patient.country_id
            self.patient_birth_date = patient.birthday
            self.patient_gender = self.move_id._convert_gender(patient.gender or 'I') if self.move_id else 'I'
            self.patient_user_type = patient.health_type or '01'
            self.patient_zone = patient.zona_territorial or '01'
            
            if patient.l10n_latam_identification_type_id:
                # Mapear tipo de documento
                heath_code = patient.l10n_latam_identification_type_id.heath_code
                if heath_code:
                    self.patient_doc_type = heath_code
                else:
                    doc_type_mapping = {
                        '1': 'CC',
                        '2': 'TI',
                        '3': 'CE',
                        '4': 'PA',
                        '5': 'RC',
                    }
                    code = patient.l10n_latam_identification_type_id.code or ''
                    self.patient_doc_type = doc_type_mapping.get(code, 'CC')
            
            if patient.nationality_id:
                self.patient_nationality = patient.nationality_id.numeric_code or ''


class RipsErrorViewerWizard(models.TransientModel):
    _name = 'rips.error.viewer.wizard'
    _description = 'Visor de Errores RIPS'
    
    name = fields.Char('Título', readonly=True)
    html_content = fields.Html('Contenido', readonly=True, sanitize=False)