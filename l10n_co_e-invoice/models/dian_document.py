import logging
import math
import zipfile
from datetime import datetime, timedelta
from random import randint
import pytz
from odoo import _, api, fields, models, tools, Command
from odoo.exceptions import UserError,ValidationError
from pytz import timezone
from unidecode import unidecode
from hashlib import sha384
from odoo.tools import float_repr,cleanup_xml_node
_logger = logging.getLogger(__name__)
import html
try:
    from lxml import etree
except ImportError:
    _logger.info("Cannot import  etree *************************************")

try:
    import pyqrcode
except ImportError:
    _logger.info("Cannot import pyqrcode library ***************************")

try:
    import png
except ImportError:
    _logger.info("Cannot import png library ********************************")

try:
    import hashlib
except ImportError:
    _logger.info("Cannot import hashlib library ****************************")

try:
    import base64
except ImportError:
    _logger.info("Cannot import base64 library *****************************")

try:
    import textwrap
except ImportError:
    _logger.info("no se ha cargado textwrap ********************************")

try:
    import gzip
except ImportError:
    _logger.info("no se ha cargado gzip ***********************")

try:
    import zlib

    compression = zipfile.ZIP_DEFLATED
except ImportError:
    compression = zipfile.ZIP_STORED

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography import x509
except ImportError:
    _logger.info("Cannot import OpenSSL library")

try:
    import requests
except ImportError:
    _logger.info("no se ha cargado requests")

try:
    import xmltodict
except ImportError:
    _logger.info("Cannot import xmltodict library")

try:
    import uuid
except ImportError:
    _logger.info("Cannot import uuid library")

try:
    import re
except ImportError:
    _logger.info("Cannot import re library")

server_url = {
    "HABILITACION": "https://facturaelectronica.dian.gov.co/habilitacion/B2BIntegrationEngine/FacturaElectronica/facturaElectronica.wsdl",
    "PRODUCCION": "https://facturaelectronica.dian.gov.co/operacion/B2BIntegrationEngine/FacturaElectronica/facturaElectronica.wsdl",
    "HABILITACION_CONSULTA": "https://facturaelectronica.dian.gov.co/habilitacion/B2BIntegrationEngine/FacturaElectronica/consultaDocumentos.wsdl",
    "PRODUCCION_CONSULTA": "https://facturaelectronica.dian.gov.co/operacion/B2BIntegrationEngine/FacturaElectronica/consultaDocumentos.wsdl",
    "PRODUCCION_VP": "https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl",
    # 'PRODUCCION_VP':'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc?wsdl',
    "HABILITACION_VP": "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc?wsdl",
}

tipo_ambiente = {
    "PRODUCCION": "1",
    "PRUEBA": "2",
}

tributes = {
    "01": "IVA",
    "02": "IC",
    "03": "ICA",
    "04": "INC",
    "05": "ReteIVA",
    "06": "ReteFuente",
    "07": "ReteICA",
    "08": "ReteCREE",
    "20": "FtoHorticultura",
    "21": "Timbre",
    "22": "Bolsas",
    "23": "INCarbono",
    "24": "INCombustibles",
    "25": "Sobretasa Combustibles",
    "26": "Sordicom",
    "ZY": "No causa",
    "ZZ": "Nombre de la figura tributaria",
}


class DianDocument(models.Model):
    _name = "dian.document"
    _rec_name = "dian_code"
    _description = "Dian Document"

    document_id = fields.Many2one(
        "account.move", string="Número de documento", required=True
    )
    state = fields.Selection(
        [
            ("por_notificar", "Por notificar"),
            ("error", "Error"),
            ("por_validar", "Por validar"),
            ("exitoso", "Exitoso"),
            ("rechazado", "Rechazado"),
        ],
        string="Estatus",
        readonly=True,
        default="por_notificar",
        required=True,
    )
    date_document_dian = fields.Char(string="Fecha envio al DIAN", readonly=True)
    shipping_response = fields.Selection(
        [
            ("100", "100 Error al procesar la solicitud WS entrante"),
            ("101","101 El formato de los datos del ejemplar recibido no es correcto: Las entradas de directorio no están permitidos"),
            ("102","102 El formato de los datos del ejemplar recibido no es correcto: Tamaño de archivo comprimido zip es 0 o desconocido"),
            ("103","103 Tamaño de archivo comprimido zip es 0 o desconocido"),
            ("104","104 Sólo un archivo es permitido por archivo Zip"),
            ("200","200 Ejemplar recibido exitosamente pasará a verificación"),
            ("300","300 Archivo no soportado: Solo reconoce los tipos Invoice, DebitNote o CreditNote"),
            ("310", "310 El ejemplar contiene errores de validación semantica"),
            ("320", "320 Parámetros de solicitud de servicio web, no coincide contra el archivo"),
            ("500", "500 Error interno del servicio intentar nuevamente"),
        ],
        string="Respuesta de envío",
    )
    transaction_code = fields.Integer(string="Código de la Transacción de validación")
    transaction_description = fields.Char(string="Descripción de la transacción de validación")
    response_document_dian = fields.Selection(
        [
            ("7200001", "7200001 Recibida"),
            ("7200002", "7200002 Exitosa"),
            ("7200003", "7200003 En proceso de validación"),
            ("7200004", "7200004 Fallida (Documento no cumple 1 o más validaciones de DIAN)"),
            ("7200005", "7200005 Error (El xml no es válido)"),
        ],
        string="Respuesta de consulta")
    dian_code = fields.Char(string="Código DIAN")
    xml_document = fields.Text(string="Contenido XML del documento")
    xml_document_contingency = fields.Text(
        string="Contenido XML del documento de contigencia", readonly=True
    )
    xml_file_name = fields.Char(string="Nombre archivo xml", )
    zip_file_name = fields.Char(string="Nombre archivo zip", )
    cufe_seed = fields.Char(string="CUFE SEED",)
    date_request_dian = fields.Datetime(string="Fecha consulta DIAN", readonly=True)
    cufe = fields.Char(string="CUFE")
    QR_code = fields.Binary(string="Código QR", readonly=True)
    date_email_send = fields.Datetime(string="Fecha envío email", readonly=True)
    date_email_acknowledgment = fields.Datetime(string="Fecha acuse email",)
    response_message_dian = fields.Text(string="Respuesta DIAN", readonly=True)
    last_shipping = fields.Boolean(string="Ultimo envío", default=True)
    customer_name = fields.Char(
        string="Cliente", readonly=True, related="document_id.partner_id.name"
    )
    date_document = fields.Date(
        string="Fecha documento", readonly=True, related="document_id.invoice_date"
    )
    customer_email = fields.Char(
        string="Email cliente", readonly=True, related="document_id.partner_id.email"
    )
    document_type = fields.Selection(
        [("f", "Factura"), ("c", "Nota/Credito"), ("d", "Nota/Debito")],
        string="Tipo de documento",
        readonly=True,
    )
    resend = fields.Boolean(string="Autorizar reenvio?", default=False)
    email_response = fields.Selection(
        [("accepted", "ACEPTADA"), ("rejected", "RECHAZADA"), ("pending", "PENDIENTE")],
        string="Decisión del cliente",
        required=True,
        default="pending",
        readonly=True,
    )
    email_reject_reason = fields.Char(string="Motivo del rechazo", readonly=True)
    ZipKey = fields.Char(string="Identificador del docuemnto enviado", readonly=True)
    xml_response_dian = fields.Text(
        string="Contenido XML de la respuesta DIAN", readonly=True
    )
    xml_send_query_dian = fields.Text(
        string="Contenido XML de envío de consulta de documento DIAN", readonly=True
    )
    xml_response_contingency_dian = fields.Text(
        string="Mensaje de respuesta DIAN al envío de la contigencia", 
    )
    state_contingency = fields.Selection(
        [
            ("por_notificar", "por_notificar"),
            ("exitosa", "Exitosa"),
            ("rechazada", "Rechazada"),
        ],
        string="Estatus de contingencia",
        default="por_notificar",
        required=True,
    )
    contingency_3 = fields.Boolean(
        string="Contingencia tipo 3", related="document_id.contingency_3"
    )
    contingency_4 = fields.Boolean(
        string="Contingencia tipo 4", related="document_id.contingency_4"
    )
    count_error_DIAN = fields.Integer(
        string="contador de intentos fallidos por problemas de la DIAN", default=0
    )
    date_error_DIAN_1 = fields.Datetime(string="Fecha del 1er. mensaje de error DIAN")
    message_error_DIAN_1 = fields.Text(
        string="Mensaje del 1er. error de respuesta DIAN"
    )
    date_error_DIAN_2 = fields.Datetime(string="Fecha del 2do. mensaje de error DIAN")
    message_error_DIAN_2 = fields.Text(
        string="Mensaje del 2do. error de respuesta DIAN"
    )
    date_error_DIAN_3 = fields.Datetime(string="Fecha del 3er. mensaje de error DIAN")
    message_error_DIAN_3 = fields.Text(
        string="Mensaje del 3er. error de respuesta DIAN"
    )
    qr_data = fields.Text(string="qr Data")


    def reset_rejected_dian_data(self):
        self.response_message_dian = " "
        self.xml_response_dian = " "
        self.xml_send_query_dian = " "
        self.response_message_dian = " "
        self.xml_document = " "
        self.xml_file_name = " "
        self.zip_file_name = " "
        self.cufe = " "
        self.date_document_dian = " "
        self.write({"state": "por_notificar", "resend": False})


    def action_GetStatus(self):
        pass
    @api.model
    def _get_resolution_dian(self, data_header_doc):
        # rec_active_resolution = self.env['ir.sequence.dian_resolution'].search([('resolution_number', '=', data_header_doc.resolution_number)])
        rec_active_resolution = (
            data_header_doc.journal_id.sequence_id.dian_resolution_ids.filtered(
                lambda r: r.active_resolution
            )
        )
        dict_resolution_dian = {}
        if rec_active_resolution:
            rec_dian_sequence = self.env["ir.sequence"].search(
                [("id", "=", rec_active_resolution.sequence_id.id)]
            )
            dict_resolution_dian[
                "Prefix"
            ] = rec_dian_sequence.prefix  # Prefijo de número de factura
            if data_header_doc.move_type in ["out_refund", "in_refund"]:
                dict_resolution_dian[
                    "Prefix"
                ] = data_header_doc.journal_id.refund_sequence_id.prefix
            dict_resolution_dian[
                "InvoiceAuthorization"
            ] = rec_active_resolution.resolution_number  # Número de resolución
            dict_resolution_dian[
                "StartDate"
            ] = rec_active_resolution.date_from  # Fecha desde resolución
            dict_resolution_dian[
                "EndDate"
            ] = rec_active_resolution.date_to  # Fecha hasta resolución
            dict_resolution_dian[
                "From"
            ] = rec_active_resolution.number_from  # Desde la secuencia
            dict_resolution_dian[
                "To"
            ] = rec_active_resolution.number_to  # Hasta la secuencia
            dict_resolution_dian["TechnicalKey"] = (
                rec_active_resolution.technical_key
                if rec_active_resolution.technical_key != "false"
                else ""
            )  # Clave técnica de la resolución de rango
            dict_resolution_dian[
                "InvoiceID"
            ] = data_header_doc.name  # Codigo del documento
            # 13FEB dict_resolution_dian['ContingencyID'] = data_header_doc.contingency_invoice_number
            dict_resolution_dian[
                "ContingencyID"
            ] = data_header_doc.name  # Número de fcatura de contingencia

            if data_header_doc.journal_id.refund_sequence_id:
                dict_resolution_dian[
                    "PrefixNC"
                ] = data_header_doc.journal_id.refund_sequence_id.prefix

            if data_header_doc.is_debit_note:
                nd_sequence = data_header_doc.journal_id.debit_note_sequence_id
                dict_resolution_dian["PrefixND"] = nd_sequence.prefix
                dict_resolution_dian["Prefix"] = nd_sequence.prefix

        else:
            raise UserError(
                _("El número de resolución DIAN asociada a la factura no existe")
            )
        return dict_resolution_dian

    @api.model
    def request_validating_dian(self, document_id):
        company = (
            self.env["res.company"].sudo().search([("id", "=", self.env.company.id)])
        )
        dian_document = self.env["dian.document"].search([("id", "=", document_id)])
        data_header_doc = self.env["account.move"].search(
            [("id", "=", dian_document.document_id.id)]
        )
        dian_constants = self._get_dian_constants(data_header_doc)
        trackId = dian_document.ZipKey
        identifier = uuid.uuid4()
        identifierTo = uuid.uuid4()
        identifierSecurityToken = uuid.uuid4()
        timestamp = self._generate_datetime_timestamp()
        Created = timestamp["Created"]
        Expires = timestamp["Expires"]
        template_GetStatus_xml = self._template_GetStatus_xml()
        data_xml_send = self._generate_GetStatus_send_xml(
            template_GetStatus_xml,
            identifier,
            Created,
            Expires,
            dian_constants["Certificate"],
            identifierSecurityToken,
            identifierTo,
            trackId,
        )

        parser = etree.XMLParser(remove_blank_text=True)
        data_xml_send = etree.tostring(etree.XML(data_xml_send, parser=parser))
        data_xml_send = data_xml_send.decode()
        #   Generar DigestValue Elemento to y lo reemplaza en el xml
        ElementTO = etree.fromstring(data_xml_send)
        ElementTO = etree.tostring(ElementTO[0])
        ElementTO = etree.fromstring(ElementTO)
        ElementTO = etree.tostring(ElementTO[2])
        DigestValueTO = self._generate_digestvalue_to(ElementTO)
        data_xml_send = data_xml_send.replace(
            "<ds:DigestValue/>", "<ds:DigestValue>%s</ds:DigestValue>" % DigestValueTO
        )
        #   Generar firma para el header de envío con el Signedinfo
        Signedinfo = etree.fromstring(data_xml_send)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[2])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = Signedinfo.decode()
        Signedinfo = Signedinfo.replace(
            '<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
            'xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" '
            'xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" '
            'xmlns:wsa="http://www.w3.org/2005/08/addressing" xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
            'xmlns:wcf="http://wcf.dian.colombia">',
            '<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
            'xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
            'xmlns:wcf="http://wcf.dian.colombia" xmlns:wsa="http://www.w3.org/2005/08/addressing">',
        )
        SignatureValue = self._generate_SignatureValue_GetStatus(Signedinfo)
        data_xml_send = data_xml_send.replace(
            "<ds:SignatureValue/>",
            "<ds:SignatureValue>%s</ds:SignatureValue>" % SignatureValue,
        )
        #   Contruye XML de envío de petición
        headers = {"content-type": "application/soap+xml"}
        URL_WEBService_DIAN = (
            server_url["PRODUCCION_VP"]
            if company.production
            else server_url["HABILITACION_VP"]
        )
        try:
            response = requests.post(
                URL_WEBService_DIAN, data=data_xml_send, headers=headers
            )
        except Exception:
            raise UserError(
                _(
                    "No existe comunicación con la DIAN para el servicio de recepción de Facturas Electrónicas. Por favor, revise su red o el acceso a internet."
                )
            )
        #   Respuesta de petición
        if response.status_code != 200:  # Respuesta de envío no exitosa
            if response.status_code == 500:
                raise UserError(_("Error 500 = Error de servidor interno."))
            elif response.status_code == 503:
                raise UserError(_("Error 503 = Servicio no disponible."))
            elif response.status_code == 507:
                raise UserError(_("Error 507 = Espacio insuficiente."))
            elif response.status_code == 508:
                raise UserError(_("Error 508 = Ciclo detectado."))
            else:
                raise UserError(
                    _("Se ha producido un error de comunicación con la DIAN.")
                )
        response_dict = xmltodict.parse(response.content)
        dian_document.xml_response_dian = response.content
        if (
            response_dict["s:Envelope"]["s:Body"]["GetStatusZipResponse"][
                "GetStatusZipResult"
            ]["b:DianResponse"]["b:StatusCode"]
            == "00"
        ):
            data_header_doc.write({"diancode_id": dian_document.id})
            dian_document.response_message_dian += (
                "- Respuesta consulta estado del documento: Procesado correctamente \n"
            )
            dian_document.write({"state": "exitoso", "resend": False})
            # Envío de correo
            if not dian_document.contingency_4:
                self.env.cr.commit()

                if self.enviar_email_attached_document(
                    response.content,
                    dian_document=dian_document,
                    dian_constants=dian_constants,
                    data_header_doc=data_header_doc,
                ):
                    dian_document.date_email_send = fields.Datetime.now()
        else:
            data_header_doc.write({"diancode_id": dian_document.id})
            if (
                response_dict["s:Envelope"]["s:Body"]["GetStatusZipResponse"][
                    "GetStatusZipResult"
                ]["b:DianResponse"]["b:StatusCode"]
                == "90"
            ):
                dian_document.response_message_dian += (
                    "- Respuesta consulta estado del documento: TrackId no encontrado"
                )
                dian_document.write({"state": "por_validar", "resend": False})
            elif (
                response_dict["s:Envelope"]["s:Body"]["GetStatusZipResponse"][
                    "GetStatusZipResult"
                ]["b:DianResponse"]["b:StatusCode"]
                == "99"
            ):
                dian_document.response_message_dian += (
                    "- Respuesta consulta estado del documento: Validaciones "
                    "contiene errores en campos mandatorios "
                )
                dian_document.write({"state": "rechazado", "resend": True})
            elif (
                response_dict["s:Envelope"]["s:Body"]["GetStatusZipResponse"][
                    "GetStatusZipResult"
                ]["b:DianResponse"]["b:StatusCode"]
                == "66"
            ):
                dian_document.response_message_dian += (
                    "- Respuesta consulta estado del documento: NSU no encontrado"
                )
                dian_document.write({"state": "por_validar", "resend": False})

            dian_document.xml_send_query_dian = data_xml_send
        return True

    @api.model
    def exist_dian(self, document_id):
        dic_result_verify_status = {}
        company = self.env["res.company"].search([("id", "=", self.env.company.id)])

        dian_document = self.env["dian.document"].search([("id", "=", document_id)])
        data_header_doc = self.env["account.move"].search(
            [("id", "=", dian_document.document_id.id)]
        )
        dian_constants = self._get_dian_constants(data_header_doc)
        trackId = dian_document.ZipKey
        identifier = uuid.uuid4()
        identifierTo = uuid.uuid4()
        identifierSecurityToken = uuid.uuid4()
        timestamp = self._generate_datetime_timestamp()
        Created = timestamp["Created"]
        Expires = timestamp["Expires"]

        if company.production:
            template_GetStatus_xml = self._template_GetStatusExist_xml()
        else:
            template_GetStatus_xml = self._template_GetStatusExistTest_xml()

        data_xml_send = self._generate_GetStatus_send_xml(
            template_GetStatus_xml,
            identifier,
            Created,
            Expires,
            dian_constants["Certificate"],
            identifierSecurityToken,
            identifierTo,
            trackId,
        )

        parser = etree.XMLParser(remove_blank_text=True)
        data_xml_send = etree.tostring(etree.XML(data_xml_send, parser=parser))
        data_xml_send = data_xml_send.decode()
        #   Generar DigestValue Elemento to y lo reemplaza en el xml
        ElementTO = etree.fromstring(data_xml_send)
        ElementTO = etree.tostring(ElementTO[0])
        ElementTO = etree.fromstring(ElementTO)
        ElementTO = etree.tostring(ElementTO[2])
        DigestValueTO = self._generate_digestvalue_to(ElementTO)
        data_xml_send = data_xml_send.replace(
            "<ds:DigestValue/>", "<ds:DigestValue>%s</ds:DigestValue>" % DigestValueTO
        )
        #   Generar firma para el header de envío con el Signedinfo
        Signedinfo = etree.fromstring(data_xml_send)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[2])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = Signedinfo.decode()
        Signedinfo = Signedinfo.replace(
            '<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
            'xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" '
            'xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" '
            'xmlns:wsa="http://www.w3.org/2005/08/addressing" xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
            'xmlns:wcf="http://wcf.dian.colombia">',
            '<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
            'xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia" '
            'xmlns:wsa="http://www.w3.org/2005/08/addressing">',
        )
        SignatureValue = self._generate_SignatureValue_GetStatus(Signedinfo)
        data_xml_send = data_xml_send.replace(
            "<ds:SignatureValue/>",
            "<ds:SignatureValue>%s</ds:SignatureValue>" % SignatureValue,
        )
        #   Contruye XML de envío de petición
        headers = {"content-type": "application/soap+xml"}
        URL_WEBService_DIAN = (
            server_url["PRODUCCION_VP"]
            if company.production
            else server_url["HABILITACION_VP"]
        )
        try:
            response = requests.post(
                URL_WEBService_DIAN, data=data_xml_send, headers=headers
            )
        except Exception:
            raise UserError(
                _(
                    "No existe comunicación con la DIAN para el servicio de recepción de Facturas Electrónicas. Por favor, revise su red o el acceso a internet."
                )
            )
        #   Respuesta de petición
        if response.status_code != 200:  # Respuesta de envío no exitosa
            if response.status_code == 500:
                raise UserError(_("Error 500 = Error de servidor interno."))
            elif response.status_code == 503:
                raise UserError(_("Error 503 = Servicio no disponible."))
            elif response.status_code == 507:
                raise UserError(_("Error 507 = Espacio insuficiente."))
            elif response.status_code == 508:
                raise UserError(_("Error 508 = Ciclo detectado."))
            else:
                raise UserError(
                    _("Se ha producido un error de comunicación con la DIAN.")
                )
        response_dict = xmltodict.parse(response.content)
        dian_document.xml_response_dian = response.content
        NitSinDV = dian_constants["NitSinDV"]

        data_resolution = self._get_resolution_dian(data_header_doc)
        # Generar nombre del archvio xml
        dian_document.xml_file_name = self._generate_xml_filename(
            data_resolution,
            NitSinDV,
            data_header_doc.move_type,
            data_header_doc.debit_origin_id,
        )

        dic_result_verify_status["result_verify_status"] = False
        if (
            response_dict["s:Envelope"]["s:Body"]["GetStatusResponse"][
                "GetStatusResult"
            ]["b:StatusCode"]
            == "00"
        ):
            dic_result_verify_status["result_verify_status"] = True

        dic_result_verify_status["response_message_dian"] = (
            response_dict["s:Envelope"]["s:Body"]["GetStatusResponse"][
                "GetStatusResult"
            ]["b:StatusCode"]
            + " "
        )
        dic_result_verify_status["response_message_dian"] += (
            response_dict["s:Envelope"]["s:Body"]["GetStatusResponse"][
                "GetStatusResult"
            ]["b:StatusDescription"]
            + "\n"
        )
        dic_result_verify_status["ZipKey"] = response_dict["s:Envelope"]["s:Body"][
            "GetStatusResponse"
        ]["GetStatusResult"]["b:XmlDocumentKey"]
        return dic_result_verify_status


    def action_GetStatus(self):
        return True
        
    def _get_identificador_set_pruebas(self):
        company = (
            self.env["res.company"].sudo().search([("id", "=", self.env.company.id)])
        )
        return company.identificador_set_pruebas
    @api.model
    def send_pending_dian(self, document_id, document_type, rec):
        if not document_id.exist_dian(self.id)["result_verify_status"]:
            company = rec.company_id
            if document_type == "f":
                document_id._send_pending_dian_document(document_id, company,rec)
            elif document_type == "c":
                document_id._send_pending_dian_credit_note(document_id, company,rec)
            elif document_type == "d":
                document_id._send_pending_dian_debit_note(document_id, company,rec)
            elif document_type == "contingency" and self.contingency_3:
                document_id._send_pending_dian_contingency_invoice(document_id, company,rec)

    def _send_pending_dian_document(self, document_id, company, data_header_doc):
        docs_send_dian = document_id._get_docs_send_dian("f", document_id)
        for doc_send_dian in docs_send_dian:
            dian_constants = document_id._get_dian_constants(data_header_doc)
            data_constants_document = document_id._generate_data_constants_document(data_header_doc, dian_constants, "f", company.in_contingency_4)
            data_xml_document = document_id._generate_data_xml_document(data_header_doc, dian_constants, "f", company,docs_send_dian,data_constants_document)
            document_id._send_dian_request(company, doc_send_dian, data_xml_document, dian_constants, data_header_doc,data_constants_document)

    def _send_pending_dian_credit_note(self, document_id, company, data_header_doc):
        docs_send_dian = document_id._get_docs_send_dian("c", document_id)
        for doc_send_dian in docs_send_dian:
            dian_constants = document_id._get_dian_constants(data_header_doc)
            data_constants_document = document_id._generate_data_constants_document(data_header_doc, dian_constants, "c", company.in_contingency_4)
            data_xml_document = document_id._generate_data_xml_document(data_header_doc, dian_constants, "c", company,docs_send_dian,data_constants_document)
            document_id._send_dian_request(company, doc_send_dian, data_xml_document, dian_constants, data_header_doc,data_constants_document)

    def _send_pending_dian_debit_note(self, document_id, company, data_header_doc):

        docs_send_dian = self._get_docs_send_dian("d", document_id)
        for doc_send_dian in docs_send_dian:
            dian_constants = self._get_dian_constants(data_header_doc)
            data_constants_document = self._generate_data_constants_document(data_header_doc, dian_constants, "d", company.in_contingency_4)
            data_xml_document = self._generate_data_xml_document(data_header_doc, dian_constants, "d", company,docs_send_dian,data_constants_document)
            self._send_dian_request(company, doc_send_dian, data_xml_document, dian_constants, data_header_doc,data_constants_document)


    def _get_docs_send_dian(self, document_type, document_id):
        document_id = document_id.id
        if document_type == "f":
            by_validate_invoices = self.env["dian.document"].search([("id", "=", document_id), ("document_type", "=", document_type)])
            if by_validate_invoices:
                return by_validate_invoices
            else:
                raise UserError(_("La factura no está en proceso de envío a la DIAN. Contacte al administrador del sistema"))
        elif document_type == "c":
            by_validate_credit_notes = self.env["dian.document"].search([("id", "=", document_id), ("document_type", "=", document_type)])
            cn_with_validated_invoices_ids = []
            for by_validate_cn in by_validate_credit_notes:
                invoice_validated = self.env["account.move"].search([("name", "=", by_validate_cn.document_id.reversed_entry_id.name), ("move_type", "in", ["out_invoice", "in_invoice"]), ("state_dian_document", "=", "exitoso")])
                if invoice_validated:
                    cn_with_validated_invoices_ids.append(by_validate_cn.id)
                else:
                    cn_with_validated_invoices_ids.append(by_validate_cn.id)
                    if not self.document_id.cufe_cuds_other_system and not self.document_id.document_without_reference:
                        raise UserError(_("La factura a la que se le va a aplicar la nota de crédito, no ha sido enviada o aceptada por la DIAN"))
            return self.env["dian.document"].browse(cn_with_validated_invoices_ids)
        elif document_type == "d":
            by_validate_debit_notes = self.env["dian.document"].search([("id", "=", document_id), ("document_type", "=", document_type)])
            cn_with_validated_invoices_ids = []
            for by_validate_cn in by_validate_debit_notes:
                invoice_validated = self.env["account.move"].search([("name", "=", by_validate_cn.document_id.debit_origin_id.name), ("move_type", "in", ["out_invoice", "out_refund"]), ("company_id", "=", self.env.company.id), ("state_dian_document", "=", "exitoso")])
                if invoice_validated:
                    cn_with_validated_invoices_ids.append(by_validate_cn.id)
                else:
                    raise UserError(_("La factura a la que se le va a aplicar la nota de débito, no ha sido enviada o aceptada por la DIAN"))
            return self.env["dian.document"].browse(cn_with_validated_invoices_ids)
        elif document_type == "contingency" and self.contingency_3:
            by_validate_invoices = self.env["dian.document"].search([("id", "=", document_id), ("document_type", "=", "f")])
            if by_validate_invoices:
                return by_validate_invoices
            else:
                raise UserError(_("La factura no está en proceso de envío a la DIAN. Contacte al administrador del sistema"))

    def _generate_data_xml_document(self, data_header_doc, dian_constants, document_type, company,doc_send_dian,data_constants_document):
        data_xml_document = ""
        parser = etree.XMLParser(remove_blank_text=True)
        data_taxs_xml = data_constants_document['data_taxs_xml']
        data_lines_xml = data_constants_document['data_lines_xml']
        CUFE = data_constants_document['UUID']
        doc_send_dian.QR_code = data_constants_document['QR_code'] 
        doc_send_dian.qr_data = data_constants_document['qr_data'] 
        doc_send_dian.cufe = CUFE
        if document_type == "f":
            # Generar documento XML de factura
            data_xml = self._generate_data_invoice_document_xml(dian_constants, data_constants_document, data_taxs_xml, data_lines_xml, CUFE)
            xml_invoice = self.generate_xml_invoice(data_xml)
            data_xml_document = etree.tostring(etree.XML(xml_invoice, parser=parser))
            data_xml_document = data_xml_document.decode()
        elif document_type == "c":
            # Generar documento XML de nota de crédito
            data_xml = self._generate_data_invoice_document_xml(dian_constants, data_constants_document, data_taxs_xml, data_lines_xml, CUFE)
            xml_nc = self.generate_xml_nc(data_xml)
            data_xml_document = etree.tostring(etree.XML(xml_nc, parser=parser))
            data_xml_document = data_xml_document.decode()
        elif document_type == "d":
            # Generar documento XML de nota de débito
            template_basic_data_nd_xml = '<?xml version="1.0"?>' + self._template_basic_data_nd_xml()
            template_basic_data_nd_xml = etree.tostring(etree.XML(template_basic_data_nd_xml, parser=parser))
            template_basic_data_nd_xml = template_basic_data_nd_xml.decode()
            data_xml_document = self._generate_data_nd_document_xml(template_basic_data_nd_xml, dian_constants, data_constants_document, data_lines_xml, CUFE, data_taxs_xml)
            data_xml_document = etree.tostring(etree.XML(data_xml_document, parser=parser))
            data_xml_document = data_xml_document.decode()
        else:
            raise UserError(f"Tipo de documento no admitido: {document_type}")
        return data_xml_document

    def _send_dian_request(self, company, doc_send_dian, data_xml_document, dian_constants, data_header_doc,data_constants_document):
        parser = etree.XMLParser(remove_blank_text=True)
        template_signature_data_xml = self._template_signature_data_xml()
        data_xml_document = data_xml_document.replace(
            "<ext:ExtensionContent/>",
            "<ext:ExtensionContent></ext:ExtensionContent>",
        )
        
        data_xml_signature = self._generate_signature(
            data_xml_document,
            template_signature_data_xml,
            dian_constants,
            data_constants_document,
        )
        data_xml_signature = etree.tostring(
            etree.XML(data_xml_signature, parser=parser),
            encoding='unicode',
            method='xml'
        )
        data_xml_signature = html.unescape(data_xml_signature)
        data_xml_document = data_xml_document.replace(
            "<ext:ExtensionContent></ext:ExtensionContent>",
            f"<ext:ExtensionContent>{data_xml_signature}</ext:ExtensionContent>"
        )
        data_xml_document = '<?xml version="1.0" encoding="UTF-8"?>' + data_xml_document
        root = etree.fromstring(data_xml_document.encode('UTF-8'), parser=parser)
        data_xml_document = etree.tostring(root, encoding='unicode', method='xml')
        doc_send_dian.dian_code = data_constants_document["InvoiceID"]
        doc_send_dian.xml_file_name = data_constants_document["FileNameXML"]
        doc_send_dian.xml_document = data_xml_document
        doc_send_dian.zip_file_name = data_constants_document["FileNameZIP"]
        invoice_attachment = self.env['ir.attachment'].create({
            'name': data_constants_document["FileNameXML"],
            'type': 'binary',
            'datas': base64.b64encode(data_xml_document.encode()),
            'res_model': self._name,
            'res_id': self.id,
        })
        doc_send_dian.invoice_id = invoice_attachment.id
        doc_send_dian.zip_file_name = data_constants_document["FileNameZIP"]
        Document = self._generate_zip_content(
            data_constants_document["FileNameXML"],
            data_constants_document["FileNameZIP"],
            data_xml_document,
            dian_constants["document_repository"],
        )
        fileName = data_constants_document["FileNameZIP"][:-4]
        timestamp = self._generate_datetime_timestamp()
        Created = timestamp["Created"]
        Expires = timestamp["Expires"]
        doc_send_dian.date_document_dian = data_constants_document["IssueDateSend"]
        testSetId = self._get_identificador_set_pruebas()
        identifierSecurityToken = uuid.uuid4()
        identifierTo = uuid.uuid4()
        if company.production:
            template_SendBillSyncsend_xml = (
                self._template_SendBillSyncsend_xml()
            )
            data_xml_send = self._generate_SendBillSync_send_xml(
                template_SendBillSyncsend_xml,
                fileName,
                Document,
                Created,
                testSetId,
                data_constants_document["identifier"],
                Expires,
                dian_constants["Certificate"],
                identifierSecurityToken,
                identifierTo,
            )
        else:
            template_SendTestSetAsyncsend_xml = (
                self._template_SendBillSyncTestsend_xml()
            )
            data_xml_send = self._generate_SendTestSetAsync_send_xml(
                template_SendTestSetAsyncsend_xml,
                fileName,
                Document,
                Created,
                testSetId,
                data_constants_document["identifier"],
                Expires,
                dian_constants["Certificate"],
                identifierSecurityToken,
                identifierTo,
            )

        data_xml_send = etree.tostring(etree.XML(data_xml_send, parser=parser))
        data_xml_send = data_xml_send.decode()
        #   Generar DigestValue Elemento to y lo reemplaza en el xml
        ElementTO = etree.fromstring(data_xml_send)
        ElementTO = etree.tostring(ElementTO[0])
        ElementTO = etree.fromstring(ElementTO)
        ElementTO = etree.tostring(ElementTO[2])
        DigestValueTO = self._generate_digestvalue_to(ElementTO)
        data_xml_send = data_xml_send.replace(
            "<ds:DigestValue/>",
            "<ds:DigestValue>%s</ds:DigestValue>" % DigestValueTO,
        )
        #   Generar firma para el header de envío con el Signedinfo
        Signedinfo = etree.fromstring(data_xml_send)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[2])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = Signedinfo.decode()
        Signedinfo = Signedinfo.replace(
            '<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
            'xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" '
            'xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" '
            'xmlns:wsa="http://www.w3.org/2005/08/addressing" '
            'xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">',
            '<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
            'xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia" '
            'xmlns:wsa="http://www.w3.org/2005/08/addressing">',
        )
        SignatureValue = self._generate_SignatureValue_GetStatus(Signedinfo)
        data_xml_send = data_xml_send.replace(
            "<ds:SignatureValue/>",
            "<ds:SignatureValue>%s</ds:SignatureValue>" % SignatureValue,
        )
        headers = {"content-type": "application/soap+xml"}
        URL_WEBService_DIAN = (server_url["PRODUCCION_VP"] if company.production else server_url["HABILITACION_VP"])
        try:
            response = requests.post(URL_WEBService_DIAN, data=data_xml_send, headers=headers)
        except Exception:
            raise UserError(_("No existe comunicación con la DIAN para el servicio de recepción de Facturas Electrónicas. Por favor, revise su red o el acceso a internet."))
        if not response:
            return doc_send_dian.write({'state': 'error',
                'message_json': {'status': _("La servidor de la dian DIAN no respondió.")},
            })
        root = etree.fromstring(response.content)
        namespaces = {
                's': 'http://www.w3.org/2003/05/soap-envelope',
                'b': 'http://schemas.datacontract.org/2004/07/DianResponse',
                'c': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays'
            }
        xml_base64_bytes = root.xpath('//b:XmlBase64Bytes', namespaces=namespaces)
        xml_document_key = root.xpath('//b:XmlDocumentKey', namespaces=namespaces)
        xml_file_name = root.xpath('//b:XmlFileName', namespaces=namespaces)
        error_message = root.xpath('//b:ErrorMessage/c:string', namespaces=namespaces)

        document_key = ''
        if xml_base64_bytes:
            base64_content = xml_base64_bytes[0].text
            decoded_content = base64.b64decode(base64_content)
            document_key = xml_document_key[0].text if xml_document_key else ''
            file_name = xml_file_name[0].text if xml_file_name else 'DIAN_Response'
            if not file_name.lower().endswith('.xml'):
                file_name += '.xml'
            
            # Guardar respuesta DIAN como adjunto
            response_attachment = self.env['ir.attachment'].create({
                'name': file_name,
                'type': 'binary',
                'datas': base64.b64encode(decoded_content),
                'res_model': doc_send_dian._name,
                'res_id': doc_send_dian.id,
            })
            doc_send_dian.response_id = response_attachment.id
            doc_send_dian.xml_response_dian = decoded_content

            if response.status_code != 200:
                return doc_send_dian.write({
                    'state': 'error',
                    'message_json': self._build_message(root),
                    'xml_send_query_dian': data_xml_send,
                })
            elif root.findtext('.//{*}IsValid') != 'true':
                error_descriptions = []
                for error in error_message:
                    error_text = error.text
                    error_descriptions.append(error_text)
                    if 'Regla: 90' in error_text and 'Documento procesado anteriormente' in error_text:
                        doc_send_dian.write({'cufe': document_key, 'state': 'exitoso'})
                        self._action_get__xml(file_name,document_key)
                        doc_send_dian.write({'message_json': self._build_message(root)})
                # Si la DIAN respondió pero el documento es inválido, debe quedar como rechazado y
                # persistir el request para facilitar diagnóstico/reintento.
                if doc_send_dian.state not in ('exitoso', 'rechazado'):
                    vals = {
                        'state': 'rechazado',
                        'resend': True,
                        'xml_send_query_dian': data_xml_send,
                        'message_json': {
                            'status': _("Documento rechazado por la DIAN"),
                            'errors': error_descriptions,
                        },
                    }
                    if document_key:
                        vals['ZipKey'] = document_key
                    # Mantener compatibilidad con pantallas/exports que lean este campo
                    if error_descriptions:
                        vals['response_message_dian'] = "\n".join(error_descriptions)
                    doc_send_dian.write(vals)
            else:
                doc_send_dian.write({'message_json': self._build_message(root)})
                self._process_dian_response(response, company, doc_send_dian, data_xml_send, dian_constants, data_header_doc)
            
  

    def _process_dian_response(self, response, company, doc_send_dian, data_xml_send, dian_constants, data_header_doc):
        response_dict = xmltodict.parse(response.content)
        dict_mensaje = {}
        if company.production:
            dict_result_verify_status = self.exist_dian(self.id)
            if dict_result_verify_status["result_verify_status"]:
                return
            dict_mensaje = response_dict["s:Envelope"]["s:Body"][
                "SendBillSyncResponse"
            ]["SendBillSyncResult"]["b:IsValid"]
            doc_send_dian.response_message_dian = " "
            if (
                response_dict["s:Envelope"]["s:Body"][
                    "SendBillSyncResponse"
                ]["SendBillSyncResult"]["b:StatusCode"]
                == "00"
            ):
                doc_send_dian.response_message_dian = (
                    response_dict["s:Envelope"]["s:Body"][
                        "SendBillSyncResponse"
                    ]["SendBillSyncResult"]["b:StatusCode"]
                    + " "
                )
                doc_send_dian.response_message_dian += (
                    response_dict["s:Envelope"]["s:Body"][
                        "SendBillSyncResponse"
                    ]["SendBillSyncResult"]["b:StatusDescription"]
                    + "\n"
                )
                doc_send_dian.response_message_dian += response_dict[
                    "s:Envelope"
                ]["s:Body"]["SendBillSyncResponse"][
                    "SendBillSyncResult"
                ][
                    "b:StatusMessage"
                ]
                doc_send_dian.ZipKey = response_dict["s:Envelope"][
                    "s:Body"
                ]["SendBillSyncResponse"]["SendBillSyncResult"][
                    "b:XmlDocumentKey"
                ]
                doc_send_dian.xml_response_dian = response.content
                doc_send_dian.xml_send_query_dian = data_xml_send
                doc_send_dian.write(
                    {"state": "exitoso", "resend": False}
                )
                if doc_send_dian.contingency_3:
                    doc_send_dian.write(
                        {"state_contingency": "exitosa"}
                    )
                data_header_doc.write({"diancode_id": doc_send_dian.id})
                # Generar código QR
                #doc_send_dian.QR_code = resultado['qr'] 
                # Envío de correo
                if not doc_send_dian.contingency_4:
                    self.env.cr.commit()
                    if self.enviar_email_attached_document(
                        doc_send_dian.xml_response_dian
                        or response.content,
                        dian_document=doc_send_dian,
                        dian_constants=dian_constants,
                        data_header_doc=data_header_doc,
                    ):
                        doc_send_dian.date_email_send = (
                            fields.Datetime.now()
                        )
            else:
                doc_send_dian.response_message_dian = (
                    response_dict["s:Envelope"]["s:Body"][
                        "SendBillSyncResponse"
                    ]["SendBillSyncResult"]["b:StatusCode"]
                    + " "
                )
                doc_send_dian.response_message_dian += (
                    response_dict["s:Envelope"]["s:Body"][
                        "SendBillSyncResponse"
                    ]["SendBillSyncResult"]["b:StatusDescription"]
                    + "\n"
                )
                StatusMessage = str(
                    response_dict["s:Envelope"]["s:Body"][
                        "SendBillSyncResponse"
                    ]["SendBillSyncResult"]["b:StatusMessage"]
                )
                if isinstance(StatusMessage, str):
                    doc_send_dian.response_message_dian += StatusMessage

                doc_send_dian.ZipKey = response_dict["s:Envelope"][
                    "s:Body"
                ]["SendBillSyncResponse"]["SendBillSyncResult"][
                    "b:XmlDocumentKey"
                ]
                doc_send_dian.xml_response_dian = response.content
                doc_send_dian.xml_send_query_dian = data_xml_send
                doc_send_dian.write(
                    {"state": "rechazado", "resend": True}
                )
                if doc_send_dian.contingency_3:
                    doc_send_dian.write(
                        {"state_contingency": "rechazada"}
                    )
                data_header_doc.write({"diancode_id": doc_send_dian.id})
                # Generar código QR
                #doc_send_dian.QR_code = resultado['qr'] 
        else:  # Ambiente de pruebas
            dict_mensaje = response_dict["s:Envelope"]["s:Body"][
                "SendTestSetAsyncResponse"
            ]["SendTestSetAsyncResult"]["b:ErrorMessageList"]
            if "@i:nil" in dict_mensaje:
                if (
                    response_dict["s:Envelope"]["s:Body"][
                        "SendTestSetAsyncResponse"
                    ]["SendTestSetAsyncResult"]["b:ErrorMessageList"][
                        "@i:nil"
                    ]
                    == "true"
                ):
                    doc_send_dian.response_message_dian = "- Respuesta envío: Documento enviado con éxito. Falta validar su estado \n"
                    doc_send_dian.ZipKey = response_dict["s:Envelope"][
                        "s:Body"
                    ]["SendTestSetAsyncResponse"][
                        "SendTestSetAsyncResult"
                    ][
                        "b:ZipKey"
                    ]
                    doc_send_dian.state = "por_validar"
                else:
                    doc_send_dian.response_message_dian = "- Respuesta envío: Documento enviado con éxito, pero la DIAN detectó errores \n"
                    doc_send_dian.ZipKey = response_dict["s:Envelope"][
                        "s:Body"
                    ]["SendTestSetAsyncResponse"][
                        "SendTestSetAsyncResult"
                    ][
                        "b:ZipKey"
                    ]
                    doc_send_dian.state = "por_notificar"
            elif "i:nil" in dict_mensaje:
                if (
                    response_dict["s:Envelope"]["s:Body"][
                        "SendTestSetAsyncResponse"
                    ]["SendTestSetAsyncResult"]["b:ErrorMessageList"][
                        "i:nil"
                    ]
                    == "true"
                ):
                    doc_send_dian.response_message_dian = "- Respuesta envío: Documento enviado con éxito. Falta validar su estado \n"
                    doc_send_dian.ZipKey = response_dict["s:Envelope"][
                        "s:Body"
                    ]["SendTestSetAsyncResponse"][
                        "SendTestSetAsyncResult"
                    ][
                        "b:ZipKey"
                    ]
                    doc_send_dian.state = "por_validar"
                else:
                    doc_send_dian.response_message_dian = "- Respuesta envío: Documento enviado con éxito, pero la DIAN detectó errores \n"
                    doc_send_dian.ZipKey = response_dict["s:Envelope"][
                        "s:Body"
                    ]["SendTestSetAsyncResponse"][
                        "SendTestSetAsyncResult"
                    ][
                        "b:ZipKey"
                    ]
                    doc_send_dian.state = "por_notificar"
            else:
                raise UserError(
                    _(
                        "Mensaje de respuesta cambió en su estructura xml"
                    )
                )
        return True

    def _handle_dian_error(self, response, company, doc_send_dian, data_header_doc):
        message_error_DIAN = str(response.status_code) + " " + response.content.decode()
        if response.status_code in (500, 503, 507, 508):
            data_header_doc.write({"diancode_id": doc_send_dian.id})
        if doc_send_dian.count_error_DIAN == 0:
            doc_send_dian.date_error_DIAN_1 = self._get_datetime()
            doc_send_dian.message_error_DIAN_1 = message_error_DIAN
            doc_send_dian.count_error_DIAN = 1
        elif doc_send_dian.count_error_DIAN == 1:
            doc_send_dian.date_error_DIAN_2 = self._get_datetime()
            doc_send_dian.message_error_DIAN_2 = message_error_DIAN
            doc_send_dian.count_error_DIAN = 2
        elif doc_send_dian.count_error_DIAN == 2:
            doc_send_dian.date_error_DIAN_3 = self._get_datetime()
            doc_send_dian.message_error_DIAN_3 = message_error_DIAN
            doc_send_dian.count_error_DIAN = 3
        elif doc_send_dian.count_error_DIAN == 3:
            #company.in_contingency_4 = True
            company.date_init_contingency_4 = self._get_datetime()
            doc_send_dian.count_error_DIAN = 0
            if company.in_contingency_4 and not self.contingency_3:
                document_type = self.document_type
            else:
                document_type = self.document_type if not self.contingency_3 else "contingency"
                self.send_pending_dian(self.id, document_type, data_header_doc )
        else:
            raise UserError(message_error_DIAN)


    
    def enviar_email(self, data_xml_document, invoice_id, fileName):

        rs_invoice = self.env["account.move"].sudo().browse(invoice_id)
        rs_invoice.xml_adjunto_ids = [(6, 0, [])]
        adjuntos = rs_invoice.attachment_ids
        plantilla_correo = self.env.ref(
            "l10n_co_e-invoice.email_template_edi_invoice_dian", False
        )
        pdf = self.env['ir.actions.report'].sudo()._render_qweb_pdf("account.account_invoices", rs_invoice.id)[0]
        dian_xml = base64.b64encode(data_xml_document.encode())
        rs_adjunto = self.env["ir.attachment"].sudo()
        dictxmlAdjunto = {
            "res_id": rs_invoice.id,
            "res_model": "account.move",
            "type": "binary",
            "name": fileName,
            "datas": dian_xml,
        }
        nuevo_adjunto_xml = rs_adjunto.create(dictxmlAdjunto)
        for adj in adjuntos:
            if adj.name[::-1][0:3] == "piz":
                continue
            if adj.name not in [
                f"{rs_invoice.name}.pdf",
                fileName,
            ] and adj.name not in rs_invoice.xml_adjunto_ids.mapped("name"):
                rs_invoice.xml_adjunto_ids += adj
        rs_invoice.xml_adjunto_ids += nuevo_adjunto_xml
        zip_file_name = fileName.split(".")[0] + ".zip"
        zip_file = self._generate_zip_multiple_files(
            [(f"{rs_invoice.name}.pdf", pdf)]
            + [
                (att.name, base64.b64decode(att.datas))
                for att in rs_invoice.xml_adjunto_ids
            ],
            zip_file_name,
        )
        dictAdjunto = {
            "res_id": rs_invoice.id,
            "res_model": "account.move",
            "type": "binary",
            "name": zip_file_name,
            "datas": zip_file,
        }
        nuevo_adjunto = rs_adjunto.create(dictAdjunto)
        if not nuevo_adjunto:
            _logger.info("No existe xml generado / Error al procesar envio")

        rs_invoice.archivo_xml_invoice = dian_xml

        if plantilla_correo:
            plantilla_correo.sudo().send_mail(
                rs_invoice.id,
                force_send=True,
                email_values={
                    "attachment_ids": nuevo_adjunto.ids
                },
            )

            rs_invoice.message_post()

        else:
            raise UserError(
                _(
                    "No existe la plantilla de correo email_template_edi_invoice_dian para el email"
                )
            )
        return True

    def enviar_email_attached_document_xml(
        self, xml_response_dian, dian_document, dian_constants, data_header_doc
    ):
        application_response = self.get_application_response(xml_response_dian)
        xml_attached_document = self.generate_attached_document(
            dian_constants,
            dian_document.xml_document,
            application_response=application_response,
            data_header_doc=data_header_doc,
            cufe=dian_document.cufe,
        )

        xml_file_name = (
            "ad%s" % (dian_document.xml_file_name[6:] if dian_document.xml_file_name else "000000.xml")
        )
        return unidecode(xml_attached_document), xml_file_name

    def enviar_email_attached_document_fe_xml(
        self, xml_response_dian, dian_document, dian_constants, data_header_doc
    ):
        #application_response = self.get_application_response(xml_response_dian)
        xml_attached_document = self.generate_attached_document(
            dian_constants,
            dian_document.xml_document,
            application_response=xml_response_dian,
            data_header_doc=data_header_doc,
            cufe=dian_document.cufe,
        )

        xml_file_name = (
            "ad%s" % (dian_document.xml_file_name[6:] if dian_document.xml_file_name else "000000.xml")
        )
        return unidecode(xml_attached_document), xml_file_name

    def enviar_email_attached_document(
        self, xml_response_dian, dian_document, dian_constants, data_header_doc
    ):
        try:
            application_response = self.get_application_response(xml_response_dian)
            if not application_response:
                _logger.info("ERROR CON APLICATION RESPONSE")
                return
            xml_attached_docuement = self.generate_attached_document(
                dian_constants,
                dian_document.xml_document,
                application_response=application_response,
                data_header_doc=data_header_doc,
                cufe=dian_document.cufe,
            )
            return self.enviar_email(
                unidecode(xml_attached_docuement),
                dian_document.document_id.id,
                "ad%s"
                % (
                    dian_document.xml_file_name[6:]
                    if dian_document.xml_file_name
                    else "000000.xml"
                ),
            )
        except Exception as e:
            raise e 

    @staticmethod
    def get_application_response(data_xml):
        response_dict = xmltodict.parse(data_xml)
        body = response_dict.get("s:Envelope", {}).get("s:Body", {})
        datab64 = False
        if "SendBillSyncResponse" in body:
            SendBillSyncResponse = body.get("SendBillSyncResponse", {})
            datab64 = SendBillSyncResponse.get("SendBillSyncResult", {}).get(
                "b:XmlBase64Bytes", ""
            )
        elif "GetStatusZipResponse" in body:
            GetStatusZipResponse = body.get("GetStatusZipResponse", {}).get(
                "GetStatusZipResult", {}
            )
            datab64 = GetStatusZipResponse.get("b:DianResponse", {}).get(
                "b:XmlBase64Bytes", ""
            )
        elif "GetStatusResponse" in body:
            GetStatusZipResponse = body.get("GetStatusResponse", {}).get(
                "GetStatusResult", {}
            )
            datab64 = GetStatusZipResponse.get("b:XmlBase64Bytes", "")
        if datab64 and isinstance(datab64, (str, bytes)):
            return base64.b64decode(datab64)

    def generate_attached_document(
        self, dian_constants, document_xml, application_response, data_header_doc, cufe
    ):
        response_data = xmltodict.parse(application_response).get(
            "ApplicationResponse", {}
        )
        application_response = etree.fromstring(application_response)
        application_response = etree.tostring(application_response)
        if isinstance(application_response, bytes):
            application_response = application_response.decode()
        response_code = (
            response_data.get("cac:DocumentResponse", {})
            .get("cac:Response", {})
            .get("cbc:ResponseCode", "")
        )
        issue_date = response_data.get("cbc:IssueDate")
        issue_time = response_data.get("cbc:IssueTime")
        template_signature_data_xml = self._template_signature_data_xml()
        data_constants_document = self._generate_data_constants_document(
            data_header_doc,
            dian_constants,
            "",
            data_header_doc.company_id.in_contingency_4,
        )
        data_constants_document.update(
            {
                "InvoiceTypeCode": "99",
            }
        )
        data_xml_document = self._template_attached_document() % {
            "UBLVersionID": dian_constants["UBLVersionID"],
            "CustomizationID": dian_constants["CustomizationID"],
            "ProfileID": dian_constants["ProfileID"],
            "ProfileExecutionID": dian_constants["ProfileExecutionID"],
            "InvoiceID": data_constants_document["InvoiceID"],
            "IssueDate": data_constants_document["IssueDate"],
            "IssueTime": data_constants_document["IssueTime"],
            "SupplierPartyName": dian_constants["SupplierPartyName"],
            "schemeID": dian_constants["schemeID"],
            "ProviderID": dian_constants["ProviderID"],
            "SoftwareProviderID": dian_constants["SoftwareProviderID"],
            "SoftwareProviderSchemeID": dian_constants["SoftwareProviderSchemeID"],
            "SupplierTaxLevelCode": dian_constants["SupplierTaxLevelCode"],
            "TaxSchemeID": dian_constants["TaxSchemeID"],
            "TaxSchemeName": dian_constants["TaxSchemeName"],
            "CustomerPartyName": data_constants_document["CustomerPartyName"],
            "CustomerschemeID": data_constants_document["CustomerschemeID"],
            "CustomerID": data_constants_document["CustomerID"],
            "CustomerTaxLevelCode": data_constants_document["CustomerTaxLevelCode"],
            "document_xml": document_xml,
            "UUID": cufe,
            "ApplicationResponse": application_response,
            "ValidationResultCode": response_code,
            "ValidationDate": issue_date,
            "ValidationTime": issue_time,
        }
        data_xml_signature = self._generate_signature(
            data_xml_document,
            template_signature_data_xml,
            dian_constants,
            data_constants_document,
        )
        parser = etree.XMLParser(remove_blank_text=True)
        data_xml_signature = etree.tostring(
            etree.XML(data_xml_signature, parser=parser)
        )
        data_xml_signature = data_xml_signature.decode()
        # Construye el documento XML con firma
        data_xml_document = data_xml_document.replace(
            "<ext:ExtensionContent></ext:ExtensionContent>",
            "<ext:ExtensionContent>%s</ext:ExtensionContent>" % data_xml_signature,
        )
        data_xml_document = '<?xml version="1.0" encoding="UTF-8"?>' + data_xml_document
        return data_xml_document

    def get_key(self):
        company = self.env.company
        password = company.certificate_key
        try:
            archivo_key = base64.b64decode(company.certificate_file)
            
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                archivo_key, password.encode(), backend=default_backend()
            )
           
            return private_key, certificate
        except Exception as ex:
            raise UserError(_("Failed to load certificate: %s") % tools.ustr(ex))





    def get_pem(self):
        company = self.env.company
        try:
            archivo_pem = base64.b64decode(company.pem_file)
            certificate = x509.load_pem_x509_certificate(archivo_pem, default_backend())
            return certificate.public_key()
        except Exception as ex:
            raise UserError(_("Failed to load PEM file: %s") % tools.ustr(ex))

    def _generate_SignatureValue_GetStatus(self, data_xml_SignedInfo_generate):
        data_xml_SignatureValue_c14n = etree.tostring(
            etree.fromstring(data_xml_SignedInfo_generate), method="c14n"
        )
        
        private_key, _ = self.get_key() 
        
        try:
            signature = private_key.sign(
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except Exception as ex:
            raise UserError(_("Failed to sign the document: %s") % tools.ustr(ex))
        
        SignatureValue = base64.b64encode(signature).decode()
        

        public_key = self.get_pem() 
        
        try:
            public_key.verify(
                signature,
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except Exception:
            raise UserError(_("Firma para el GestStatus no fué validada exitosamente"))
        return SignatureValue

    @api.model
    def _generate_signature(
        self,
        data_xml_document,
        template_signature_data_xml,
        dian_constants,
        data_constants_document,
    ):
        data_xml_keyinfo_base = ""
        data_xml_politics = ""
        data_xml_SignedProperties_base = ""
        data_xml_SigningTime = ""
        data_xml_SignatureValue = ""
        # Generar clave de referencia 0 para la firma del documento (referencia ref0)
        # Actualizar datos de signature
        #    Generar certificado publico para la firma del documento en el elemento keyinfo
        data_public_certificate_base = dian_constants["Certificate"]
        #    Generar clave de politica de firma para la firma del documento (SigPolicyHash)
        data_xml_politics = self._generate_signature_politics(
            dian_constants["document_repository"]
        )
        #    Obtener la hora de Colombia desde la hora del pc
        data_xml_SigningTime = fields.datetime.now(tz=timezone('America/Bogota')).isoformat(timespec='milliseconds')#self._generate_signature_signingtime()
        #    Generar clave de referencia 0 para la firma del documento (referencia ref0)
        #    1ra. Actualización de firma ref0 (leer todo el xml sin firma)
        data_xml_signature_ref_zero = self._generate_signature_ref0(
            data_xml_document,
            dian_constants["document_repository"],
            dian_constants["CertificateKey"],
        )
        data_xml_signature = self._update_signature(
            template_signature_data_xml,
            data_xml_signature_ref_zero,
            data_public_certificate_base,
            data_xml_keyinfo_base,
            data_xml_politics,
            data_xml_SignedProperties_base,
            data_xml_SigningTime,
            dian_constants,
            data_xml_SignatureValue,
            data_constants_document,
        )
        parser = etree.XMLParser(remove_blank_text=True)
        data_xml_signature = etree.tostring(
            etree.XML(data_xml_signature, parser=parser)
        )
        data_xml_signature = data_xml_signature.decode()
        #    Actualiza Keyinfo
        KeyInfo = etree.fromstring(data_xml_signature)
        KeyInfo = etree.tostring(KeyInfo[2])
        KeyInfo = KeyInfo.decode()
        _logger.error(data_constants_document["InvoiceTypeCode"])
        if data_constants_document["InvoiceTypeCode"] in ("01", "03"):  # Factura
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            )
            KeyInfo = KeyInfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )
        if data_constants_document["InvoiceTypeCode"] in ("05", "02"):  # Factura
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"'
            )
            KeyInfo = KeyInfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )

        if data_constants_document["InvoiceTypeCode"] in ["91"]:  # Nota de crédito
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            )
            KeyInfo = KeyInfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )

        if data_constants_document["InvoiceTypeCode"] in ["95"]:  # Nota de crédito
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"'
            )
            KeyInfo = KeyInfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )
        if data_constants_document["InvoiceTypeCode"] == "92":  # Nota de débito
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            )
            KeyInfo = KeyInfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )
        if data_constants_document["InvoiceTypeCode"] == "99":
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ccts="urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"'
            )
            KeyInfo = KeyInfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )
        data_xml_keyinfo_base = self._generate_signature_ref1(
            KeyInfo,
            dian_constants["document_repository"],
            dian_constants["CertificateKey"],
        )
        data_xml_signature = data_xml_signature.replace(
            "<ds:DigestValue/>",
            "<ds:DigestValue>%s</ds:DigestValue>" % data_xml_keyinfo_base,
            1,
        )
        #    Actualiza SignedProperties
        SignedProperties = etree.fromstring(data_xml_signature)
        SignedProperties = etree.tostring(SignedProperties[3])
        SignedProperties = etree.fromstring(SignedProperties)
        SignedProperties = etree.tostring(SignedProperties[0])
        SignedProperties = etree.fromstring(SignedProperties)
        SignedProperties = etree.tostring(SignedProperties[0])
        SignedProperties = SignedProperties.decode()
        if data_constants_document["InvoiceTypeCode"] in ("01", "03"):
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            )
            SignedProperties = SignedProperties.replace(
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"',
                "%s" % xmlns,
            )
        if data_constants_document["InvoiceTypeCode"] in ("05", "02"):
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"'
            )
            SignedProperties = SignedProperties.replace(
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"',
                "%s" % xmlns,
            )

        if data_constants_document["InvoiceTypeCode"] in ["91"]:
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            )
            SignedProperties = SignedProperties.replace(
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"',
                "%s" % xmlns,
            )

        if data_constants_document["InvoiceTypeCode"] in ["95"]:
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"'
            )
            SignedProperties = SignedProperties.replace(
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"',
                "%s" % xmlns,
            )
        if data_constants_document["InvoiceTypeCode"] == "92":  # Nota de débito
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            )
            SignedProperties = SignedProperties.replace(
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"',
                "%s" % xmlns,
            )
        if data_constants_document["InvoiceTypeCode"] == "99":
            # attached document
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ccts="urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"'
            )
            SignedProperties = SignedProperties.replace(
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"',
                "%s" % xmlns,
            )
        data_xml_SignedProperties_base = self._generate_signature_ref2(SignedProperties)
        data_xml_signature = data_xml_signature.replace(
            "<ds:DigestValue/>",
            "<ds:DigestValue>%s</ds:DigestValue>" % data_xml_SignedProperties_base,
            1,
        )
        #    Actualiza Signeinfo
        Signedinfo = etree.fromstring(data_xml_signature)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = Signedinfo.decode()
        if data_constants_document["InvoiceTypeCode"] in ("01", "03"):
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            )
            Signedinfo = Signedinfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )

        if data_constants_document["InvoiceTypeCode"] in ("05", "02"):
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"'
            )
            Signedinfo = Signedinfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )

        if data_constants_document["InvoiceTypeCode"] == "91":
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            )
            Signedinfo = Signedinfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )
        if data_constants_document["InvoiceTypeCode"] == "92":  # Nota de débito
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            )
            Signedinfo = Signedinfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )

        if data_constants_document["InvoiceTypeCode"] == "95":  # Nota de débito
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"'
            )
            Signedinfo = Signedinfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )
        if data_constants_document["InvoiceTypeCode"] == "99":
            # attached document
            xmlns = (
                'xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" '
                'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
                'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
                'xmlns:ccts="urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"'
            )
            Signedinfo = Signedinfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )
        data_xml_SignatureValue = self._generate_SignatureValue(Signedinfo)
        SignatureValue = etree.fromstring(data_xml_signature)
        SignatureValue = etree.tostring(SignatureValue[1])
        SignatureValue = SignatureValue.decode()
        data_xml_signature = data_xml_signature.replace(
            '-sigvalue"/>',
            '-sigvalue">%s</ds:SignatureValue>' % data_xml_SignatureValue,
            1,
        )
        return data_xml_signature

    def _get_software_identification_code(self):
        company = self.env.company
        return company.software_identification_code

    def _get_software_pin(self):
        company = self.env.company
        return company.software_pin

    def _get_password_environment(self):
        company = self.env.company
        return company.password_environment

    @api.model
    def _get_dian_constants_purchase(self, data_header_doc):
        company = self.env.company
        partner = data_header_doc.partner_id

        dian_constants = {}
        dian_constants["document_repository"] = company.document_repository
        dian_constants["Username"] = self._get_software_identification_code()
        dian_constants["Password"] = hashlib.new("sha256", self._get_password_environment().encode()).hexdigest()
        dian_constants["IdentificationCode"] = "CO"
        dian_constants["SoftwareProviderID"] = company.partner_id.vat_co or ""
        dian_constants["SoftwareProviderSchemeID"] = company.partner_id.vat_vd
        dian_constants["ProviderID"] = partner.vat_co or ""
        dian_constants["SoftwareID"] = self._get_software_identification_code()
        dian_constants["SoftwareSecurityCode"] = self._generate_software_security_code(
            self._get_software_identification_code(),
            self._get_software_pin(),
            data_header_doc.name,
        )
        dian_constants["PINSoftware"] = self._get_software_pin()
        dian_constants["SeedCode"] = company.seed_code
        dian_constants["UBLVersionID"] = "UBL 2.1"
        dian_constants["ProfileID"] = self._get_profile_id(data_header_doc)
        dian_constants["CustomizationID"] = self._get_customization_id(data_header_doc)
        dian_constants["ProfileExecutionID"] = tipo_ambiente["PRODUCCION"] if company.production else tipo_ambiente["PRUEBA"]
        dian_constants["SupplierAdditionalAccountID"] = "1" if partner.is_company else "2"
        dian_constants["SupplierID"] = partner.vat_co or ""
        dian_constants["SupplierSchemeID"] = self.return_number_document_type(partner.l10n_latam_identification_type_id.l10n_co_document_code)
        dian_constants["SupplierPartyName"] = self._replace_character_especial(partner.name)
        dian_constants["SupplierDepartment"] = (
            partner.city_id.state_id.name.title()
            if (partner.city_id and partner.city_id.state_id and partner.city_id.state_id.name)
            else False
        )
        dian_constants["SupplierCityCode"] = (
            partner.city_id.code_dian if (partner.city_id and partner.city_id.code_dian) else False
        )
        dian_constants["SupplierCountrySubentity"] = (
            partner.city_id.state_id.name.title()
            if (partner.city_id and partner.city_id.state_id and partner.city_id.state_id.name)
            else False
        )
        dian_constants["SupplierCityName"] = partner.city_id.name.title() if partner.city_id else partner.city
        dian_constants["SupplierPostal"] = partner.zip
        dian_constants["SupplierPartyPhone"] = partner.phone
        dian_constants["SupplierCountrySubentityCode"] = (
            partner.city_id.code_dian[0:2]
            if (partner.city_id and partner.city_id.code_dian)
            else False
        )
        dian_constants["IndustryClassificationCode"] = partner.ciiu_ids[0].code if partner.ciiu_ids else ""
        dian_constants["SupplierCountryCode"] = partner.country_id.code
        dian_constants["SupplierCountryName"] = partner.country_id.name
        dian_constants["SupplierLine"] = partner.street
        dian_constants["SupplierRegistrationName"] = company.trade_name
        dian_constants["schemeID"] = partner.vat_vd
        dian_constants["SupplierElectronicMail"] = partner.email
        dian_constants["SupplierTaxLevelCode"] = self._get_partner_fiscal_responsability_code(partner.id)
        if not partner.city_id and partner.country_id.code == "CO":
            raise UserError(_("El Cliente / Proveedor {} no tiene ciudad establecida".format(partner.name)))
        dian_constants["Certificate"] = company.digital_certificate
        dian_constants["NitSinDV"] = partner.vat_co
        dian_constants["CertificateKey"] = company.certificate_key
        dian_constants["archivo_pem"] = company.pem
        dian_constants["archivo_certificado"] = company.certificate
        dian_constants["CertDigestDigestValue"] = self._generate_CertDigestDigestValue()
        dian_constants["IssuerName"] = company.issuer_name
        dian_constants["SerialNumber"] = company.serial_number
        dian_constants["TaxSchemeID"] = partner.tribute_id.code
        dian_constants["TaxSchemeName"] = partner.tribute_id.name
        dian_constants["Currency"] = company.currency_id.id
        dian_constants["CurrencyID"] = data_header_doc.company_id.currency_id.name
        dian_constants["SupplierCityNameSubentity"] = partner.city_id.name
        dian_constants["DeliveryAddress"] = (
            partner.partner_shipping_id.street
            if hasattr(partner, "partner_shipping_id")
            else partner.street
        )
        dian_constants["URLQRCode"] = self._get_url_qr_code(company)

        return dian_constants

    @api.model
    def _get_dian_constants_sale(self, data_header_doc):
        company = self.env.company
        partner = self.env.company.partner_id
        dian_constants = {}
        dian_constants["document_repository"] = company.document_repository
        dian_constants["Username"] = self._get_software_identification_code()
        dian_constants["Password"] = hashlib.new("sha256", self._get_password_environment().encode()).hexdigest()
        dian_constants["IdentificationCode"] = partner.country_id.code
        dian_constants["SoftwareProviderID"] = company.partner_id.vat_co or ""
        dian_constants["SoftwareProviderSchemeID"] = company.partner_id.vat_vd
        dian_constants["ProviderID"] = partner.vat_co or ""
        dian_constants["SoftwareID"] = self._get_software_identification_code()
        dian_constants["SoftwareSecurityCode"] = self._generate_software_security_code(
            self._get_software_identification_code(),
            self._get_software_pin(),
            data_header_doc.name,
        )
        dian_constants["PINSoftware"] = self._get_software_pin()
        dian_constants["SeedCode"] = company.seed_code
        dian_constants["UBLVersionID"] = "UBL 2.1"
        dian_constants["ProfileID"] = self._get_profile_id(data_header_doc)
        dian_constants["CustomizationID"] = self._get_customization_id(data_header_doc)
        dian_constants["ProfileExecutionID"] = tipo_ambiente["PRODUCCION"] if company.production else tipo_ambiente["PRUEBA"]
        dian_constants["SupplierAdditionalAccountID"] = "1" if partner.is_company else "2"
        dian_constants["SupplierID"] = partner.vat_co or ""
        dian_constants["SupplierSchemeID"] = self.return_number_document_type(partner.l10n_latam_identification_type_id.l10n_co_document_code if partner.l10n_latam_identification_type_id else "")
        dian_constants["SupplierPartyName"] = self._replace_character_especial(partner.name)
        dian_constants["SupplierDepartment"] = partner.city_id.state_id.name.title() if partner.city_id else False
        dian_constants["SupplierCityCode"] = partner.city_id.code_dian if partner.city_id else False
        dian_constants["SupplierCountrySubentity"] = partner.city_id.state_id.name.title() if partner.city_id else False
        dian_constants["SupplierCityName"] = partner.city_id.name.title() if partner.city_id else partner.city
        dian_constants["SupplierPostal"] = partner.zip
        dian_constants["SupplierPartyPhone"] = partner.phone
        dian_constants["SupplierCountrySubentityCode"] = partner.city_id.code_dian[0:2] if partner.city_id else False
        dian_constants["SupplierCountryCode"] = partner.country_id.code
        dian_constants["SupplierCountryName"] = partner.country_id.name
        dian_constants["SupplierLine"] = partner.street
        dian_constants["IndustryClassificationCode"] = partner.ciiu_ids[0].code if partner.ciiu_ids else ""
        dian_constants["SupplierRegistrationName"] = company.trade_name
        dian_constants["schemeID"] = partner.vat_vd
        dian_constants["SupplierElectronicMail"] = partner.email
        dian_constants["SupplierTaxLevelCode"] = self._get_partner_fiscal_responsability_code(partner.id)
        if not partner.city_id and partner.country_id.code == "CO":
            raise UserError(_("El Cliente / Proveedor {} no tiene ciudad establecida".format(partner.name)))
        dian_constants["Certificate"] = company.digital_certificate
        dian_constants["NitSinDV"] = partner.vat_co
        dian_constants["CertificateKey"] = company.certificate_key
        dian_constants["archivo_pem"] = company.pem
        dian_constants["archivo_certificado"] = company.certificate
        dian_constants["CertDigestDigestValue"] = self._generate_CertDigestDigestValue()
        dian_constants["IssuerName"] = company.issuer_name
        dian_constants["SerialNumber"] = company.serial_number
        dian_constants["TaxSchemeID"] = partner.tribute_id.code
        dian_constants["TaxSchemeName"] = partner.tribute_id.name
        dian_constants["Currency"] = company.currency_id.id
        dian_constants["CurrencyID"] = data_header_doc.company_id.currency_id.name
        dian_constants["SupplierCityNameSubentity"] = partner.city_id.name
        dian_constants["DeliveryAddress"] = (
            partner.partner_shipping_id.street
            if hasattr(partner, "partner_shipping_id")
            else partner.street
        )
        dian_constants["URLQRCode"] = self._get_url_qr_code(company)

        return dian_constants

    @api.model
    def _get_dian_constants(self, data_header_doc):
        if data_header_doc.journal_id.type == "purchase":
            return self._get_dian_constants_purchase(data_header_doc)
        else:
            return self._get_dian_constants_sale(data_header_doc)

    def _get_profile_id(self, data_header_doc):
        if data_header_doc.move_type == "out_invoice" and not data_header_doc.is_debit_note:
            return "DIAN 2.1: Factura Electrónica de Venta"
        elif data_header_doc.is_debit_note:
            return "DIAN 2.1: Nota Débito de Factura Electrónica de Venta"
        elif data_header_doc.move_type == 'out_refund':
            return "DIAN 2.1: Nota Crédito de Factura Electrónica de Venta"
        elif data_header_doc.move_type == 'in_invoice' and data_header_doc.is_debit_note == False:
            return "DIAN 2.1: documento soporte en adquisiciones efectuadas a no obligados a facturar."
        elif data_header_doc.move_type == 'in_invoice' and data_header_doc.is_debit_note or data_header_doc.debit_origin_id:
            raise UserError('Los documentos Soporte No tiene Nota Debito Habilitadas para su emisión a la DIAN, Por Favor Emitir Otro documento Soporte')
        elif data_header_doc.move_type == 'in_refund':
            return "DIAN 2.1: Nota de ajuste al documento soporte en adquisiciones efectuadas a sujetos no obligados a expedir factura o documento equivalente"


    def _get_customization_id(self, data_header_doc):
        if data_header_doc.move_type == "out_refund":
            return "22" if data_header_doc.document_without_reference else "20"
        elif data_header_doc.is_debit_note:
            return "32" if data_header_doc.document_without_reference else "30"
        elif data_header_doc.fe_type == '02':
            return "02"
        elif data_header_doc.move_type in ('in_invoice', 'in_refund'):
            if data_header_doc.partner_id.type_residence == "si":
                return '10'
            elif self.document_id.partner_id.type_residence == "no":
                return '11'
            else:
                raise ValidationError('El proveedor {0} no tiene la informacion de residencia en su formulario'.format(self.document_id.partner_id.name))
        return data_header_doc.fe_operation_type

    def _get_url_qr_code(self, company):
        if company.production:
            return 'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey'
        else:
            return 'https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey'
        
    def return_number_document_type(self, document_type):
        document_type_map = {
            "31": "31",
            "rut": "31",
            "national_citizen_id": "13",
            "civil_registration": "11",
            "id_card": "12",
            "21": "21",
            "foreign_id_card": "22",
            "passport": "41",
            "43": "43",
            'id_document': '',
            'external_id': '50',
            'residence_document': '47',
            'PEP': '47',
            'niup_id': '91',
            'foreign_colombian_card': '21',
            'foreign_resident_card': '22',
            'diplomatic_card': '',
            'PPT': '48',
            'vat': '50',
        }
        return str(document_type_map.get(document_type, "13"))

    def _generate_data_constants_document(self, data_header_doc, dian_constants, document_type, in_contingency_4):
        partner_to_send = self.env.company.partner_id if data_header_doc.journal_id.type == "purchase" else data_header_doc.partner_id
        NitSinDV = dian_constants["NitSinDV"]
        data_constants_document = {}
        data_resolution = self._get_resolution_dian(data_header_doc)

        data_constants_document.update(self._generate_filename_data(data_resolution, NitSinDV, data_header_doc))
        data_constants_document.update(self._generate_resolution_data(data_resolution, data_header_doc,document_type,dian_constants))
        data_constants_document.update(self._generate_invoice_data(data_header_doc, dian_constants, document_type,in_contingency_4,partner_to_send))
        data_constants_document.update(self._generate_partner_data(partner_to_send))
        data_constants_document.update(self._generate_payment_data(data_header_doc))
        data_constants_document.update(self._generate_credit_debit_data(data_header_doc,in_contingency_4))
        data_constants_document.update(self._generate_contingency_data(data_header_doc,in_contingency_4))
        data_constants_document.update(self._generate_identifier_data())

        return data_constants_document

    def _generate_filename_data(self, data_resolution, NitSinDV, data_header_doc):
        return {
            "FileNameXML": self._generate_xml_filename(data_resolution, NitSinDV, data_header_doc.move_type, data_header_doc.debit_origin_id),
            "FileNameZIP": self._generate_zip_filename(data_resolution, NitSinDV, data_header_doc.move_type, data_header_doc.debit_origin_id),
        }

    def _generate_resolution_data(self, data_resolution, data_header_doc,document_type,dian_constants):
        return {
            "InvoiceAuthorization": data_resolution["InvoiceAuthorization"],
            "StartDate": data_resolution["StartDate"],
            "EndDate": data_resolution["EndDate"],
            "Prefix": self._get_prefix(data_resolution, data_header_doc),
            "From": data_resolution["From"],
            "To": data_resolution["To"],
            "InvoiceID": data_resolution["InvoiceID"],
            "ContingencyID": data_resolution["ContingencyID"] if document_type == "contingency" else " ",
            "Nonce": self._generate_nonce(data_resolution["InvoiceID"], dian_constants["SeedCode"]),
            "TechnicalKey": data_resolution["TechnicalKey"],
        }

    def _generate_invoice_data(self, data_header_doc, dian_constants, document_type,in_contingency_4,partner_to_send):
        resultado = data_header_doc.generar_invoice_tax(data_header_doc)
        return {
            "LineExtensionAmount": resultado['line_extension_amount'],
            "TotalTaxInclusiveAmount": resultado['tax_inclusive_amount'],
            "TaxExclusiveAmount": resultado['tax_exclusive_amount'],
            "PayableAmount": resultado['payable_amount'],
            "Notes": resultado['invoice_note'],
            'IssueDate': data_header_doc.fecha_xml.date().isoformat(),
            'IssueTime': data_header_doc.fecha_xml.strftime("%H:%M:%S-05:00"),
            "IssueDateSend": data_header_doc.fecha_xml.date().isoformat(),
            "IssueDateCufe": data_header_doc.fecha_xml.date().isoformat(),
            'rete_fue_cop': resultado['rete_fue_cop'],
            'rete_iva_cop': resultado['rete_iva_cop'],
            'rete_ica_cop': resultado['rete_ica_cop'],
            'tot_iva_cop': resultado['tot_iva_cop'],
            'tot_inc_cop': resultado['tot_inc_cop'],
            'tot_bol_cop': resultado['tot_bol_cop'],
            'imp_otro_cop': resultado['imp_otro_cop'],
            'rounding_adjustment_data': resultado['rounding_adjustment_data'],
            'UUID': resultado['cufe'],
            'ret_total_values':resultado['ret_total_values'],
            'tax_total_values':resultado['tax_total_values'],
            'invoice_lines':resultado['invoice_lines'],
            'data_taxs_xml' : resultado['tax_xml'] + resultado['ret_xml'],
            'data_lines_xml' : resultado['line'],
            'QR_code' : resultado['qr'] ,
            'qr_data' : resultado['qr_code'] ,
            'rounding_charge' : resultado['rounding_charge'] ,
            'rounding_discount' : resultado['rounding_discount'] ,
            "InvoiceTypeCode": self._get_doctype(data_header_doc.move_type, data_header_doc.debit_origin_id, in_contingency_4),
            "CreditNoteTypeCode": self._get_doctype(data_header_doc.move_type, data_header_doc.debit_origin_id, in_contingency_4),
            "DebitNoteTypeCode": self._get_doctype(data_header_doc.move_type, data_header_doc.debit_origin_id, in_contingency_4),
            "LineCountNumeric": self._get_lines_invoice(data_header_doc.id),
            "CustomerTaxSchemeID": partner_to_send.tribute_id.code,
            "CustomerTaxSchemeName": partner_to_send.tribute_id.name,
            "DocumentCurrencyCode": data_header_doc.currency_id.name,
            "CustomerAdditionalAccountID": "1" if partner_to_send.is_company else "2",
            "CalculationRate": self._get_calculation_rate(data_header_doc),
            "DateRate": data_header_doc.invoice_date,
            "CurrencyID": data_header_doc.company_id.currency_id.name,
        }

    def _generate_partner_data(self, partner_to_send):
        return {
            "IDAdquiriente": partner_to_send.vat_co if partner_to_send.vat_co else "",
            "SchemeNameAdquiriente": self.return_number_document_type(partner_to_send.l10n_latam_identification_type_id.l10n_co_document_code if partner_to_send.l10n_latam_identification_type_id else ""),
            "SchemeIDAdquiriente": partner_to_send.vat_vd,
            "SupplierSchemeName": self.return_number_document_type(self.document_id.partner_id.l10n_latam_identification_type_id.l10n_co_document_code if self.document_id.partner_id.l10n_latam_identification_type_id else ""),
            "CustomerID": partner_to_send.vat_co if partner_to_send.vat_co else "",
            "CustomerSchemeID": self.return_number_document_type(partner_to_send.l10n_latam_identification_type_id.l10n_co_document_code if partner_to_send.l10n_latam_identification_type_id else ""),
            "CustomerPartyName": self._replace_character_especial(partner_to_send.name),
            "CustomerPostal": self._replace_character_especial(partner_to_send.zip),
            "CustomerElectronicPhone": self._replace_character_especial(partner_to_send.phone),
            "CustomerDepartment": partner_to_send.state_id.name if partner_to_send.state_id.name else "",
            "CustomerCityCode": partner_to_send.city_id.code_dian if partner_to_send.city_id else False,
            "CustomerCityName": partner_to_send.city_id.name.title() if partner_to_send.city_id else partner_to_send.city,
            "CustomerCountrySubentity": partner_to_send.state_id.name,
            "IndustryClassificationCode" : partner_to_send.ciiu_ids[0].code if partner_to_send.ciiu_ids else "",
            "CustomerCountrySubentityCode": partner_to_send.city_id.code_dian[0:2] if partner_to_send.city_id else False,
            "CustomerCountryCode": partner_to_send.country_id.code,
            "CustomerCountryName": partner_to_send.country_id.name,
            "CustomerAddressLine": partner_to_send.street,
            "CustomerTaxLevelCode": self._get_partner_fiscal_responsability_code(partner_to_send.id),
            "CustomerRegistrationName": self._replace_character_especial(partner_to_send.name),
            "CustomerEmail": partner_to_send.email if partner_to_send.email else "",
            "CustomerLine": partner_to_send.street,
            "CustomerElectronicMail": partner_to_send.email,
            "CustomerschemeID": partner_to_send.vat_vd,
            "Firstname": self._replace_character_especial(partner_to_send.name),
        }

    def _generate_payment_data(self, data_header_doc):
        payment_data = {
            "PaymentMeansID": "1",
            "PaymentDueDate": data_header_doc.invoice_date,
            "PaymentMeansCode": data_header_doc.method_payment_id.code or "1",
        }
        if data_header_doc.payment_format == 'Credito':
            payment_data["PaymentMeansID"] = "2"
            payment_data["PaymentDueDate"] = data_header_doc.invoice_date_due

        if data_header_doc.invoice_payment_term_id.line_ids:
            for line_term_pago in data_header_doc.invoice_payment_term_id.line_ids:
                if line_term_pago.nb_days == 0:
                    payment_data["PaymentMeansID"] = "1"
                    payment_data["PaymentDueDate"] = data_header_doc.invoice_date
                else:
                    payment_data["PaymentMeansID"] = "2"
                    payment_data["PaymentDueDate"] = data_header_doc.invoice_date_due

        return payment_data

    def _generate_credit_debit_data(self, data_header_doc,in_contingency_4):
        credit_debit_data = {
            "credit_note_reason": data_header_doc.reversed_entry_id.narration or data_header_doc.ref,
            "billing_reference_id": data_header_doc.reversed_entry_id.name,
            "ResponseCodeCreditNote": data_header_doc.concepto_credit_note,
            "ResponseCodeDebitNote": data_header_doc.concept_debit_note,
            "DescriptionDebitCreditNote": dict(data_header_doc._fields['concepto_credit_note'].selection).get(data_header_doc.concepto_credit_note),
        }

        if self._get_doctype(data_header_doc.move_type, data_header_doc.debit_origin_id, in_contingency_4) in ("91", "92", "95"):
            invoice_cancel = data_header_doc.reversed_entry_id
            if data_header_doc.debit_origin_id:
                invoice_cancel = data_header_doc.debit_origin_id
            credit_debit_data["InvoiceReferenceDate"] = ''
            if data_header_doc.document_without_reference:
                credit_debit_data["InvoiceReferenceDate"] = data_header_doc.invoice_date

            if invoice_cancel and invoice_cancel.state_dian_document == 'exitoso':
                dian_document_cancel = self.env["dian.document"].search([
                    ("state", "=", "exitoso"),
                    ("document_type", "in", ["f", "c"]),
                    ("id", "=", invoice_cancel.diancode_id.id),
                ])
                if dian_document_cancel:
                    credit_debit_data["InvoiceReferenceID"] = dian_document_cancel.dian_code
                    credit_debit_data["InvoiceReferenceUUID"] = dian_document_cancel.cufe
                    credit_debit_data["InvoiceReferenceDate"] = invoice_cancel.invoice_date

            if (
                self.document_id.document_from_other_system
                and self.document_id.cufe_cuds_other_system
                and self.document_id.date_from_other_system
            ):
                credit_debit_data["InvoiceReferenceID"] = self.document_id.document_from_other_system
                credit_debit_data["InvoiceReferenceUUID"] = self.document_id.cufe_cuds_other_system
                credit_debit_data["InvoiceReferenceDate"] = str(self.document_id.date_from_other_system)

        return credit_debit_data

    def _generate_contingency_data(self, data_header_doc,in_contingency_4):
        contingency_data = {}

        if self._get_doctype(data_header_doc.move_type, data_header_doc.debit_origin_id, in_contingency_4)  == ("03"):
            contingency_data["ContingencyReferenceID"] = data_header_doc.contingency_invoice_number
            contingency_data["ContingencyIssueDate"] = data_header_doc.invoice_date
            contingency_data["ContingencyDocumentTypeCode"] = "FTC"

        return contingency_data

    def _generate_identifier_data(self):
        return {
            "identifier": uuid.uuid4(),
            "identifierkeyinfo": uuid.uuid4(),
        }

    def _get_prefix(self, data_resolution, data_header_doc):
        prefix = data_resolution["Prefix"]
        if data_header_doc.move_type != "out_invoice" and data_header_doc.move_type != "in_invoice":
            prefix = data_resolution["PrefixNC"]
        if data_header_doc.is_debit_note:
            prefix = data_resolution["PrefixND"]
        return prefix

    def _get_calculation_rate(self, data_header_doc):
        if data_header_doc.company_id.currency_id == data_header_doc.currency_id:
            return 1.00
        else:
            calculation_rate = self._get_rate_date(
                data_header_doc.company_id.id,
                data_header_doc.currency_id.id,
                data_header_doc.invoice_date,
            )
            return self._complements_second_decimal_total(calculation_rate)

    def _replace_character_especial(self, text):
        if text:
            for char, replacement in [('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'), ('"', '&quot;'), ("'", '&apos;')]:
                text = text.replace(char, replacement)
        return text

    def _get_partner_fiscal_responsability_code(self, partner_id):
        partner = self.env["res.partner"].browse(partner_id)
        return ";".join(partner.fiscal_responsability_ids.mapped('code'))
    
    @staticmethod
    def _template_attached_document():
        return """
<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ccts="urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent></ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>%(UBLVersionID)s</cbc:UBLVersionID>
    <cbc:CustomizationID>%(CustomizationID)s</cbc:CustomizationID>
    <cbc:ProfileID>%(ProfileID)s</cbc:ProfileID>
    <cbc:ProfileExecutionID>%(ProfileExecutionID)s</cbc:ProfileExecutionID>
    <cbc:ID>%(InvoiceID)s</cbc:ID>
    <cbc:IssueDate>%(IssueDate)s</cbc:IssueDate>
    <cbc:IssueTime>%(IssueTime)s</cbc:IssueTime>
    <cbc:DocumentType>Contenedor de Factura Electrónica</cbc:DocumentType>
    <cbc:ParentDocumentID>%(InvoiceID)s</cbc:ParentDocumentID>
    <cac:SenderParty>
        <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(SupplierTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
        </cac:PartyTaxScheme>
    </cac:SenderParty>
    <cac:ReceiverParty>
        <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(CustomerTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
        </cac:PartyTaxScheme>
    </cac:ReceiverParty>
    <cac:Attachment>
        <cac:ExternalReference>
            <cbc:MimeCode>text/xml</cbc:MimeCode>
            <cbc:EncodingCode>UTF-8</cbc:EncodingCode>
            <cbc:Description><![CDATA[%(document_xml)s]]></cbc:Description>
        </cac:ExternalReference>
    </cac:Attachment>
    <cac:ParentDocumentLineReference>
        <cbc:LineID>1</cbc:LineID>
        <cac:DocumentReference>
            <cbc:ID>%(InvoiceID)s</cbc:ID>
            <cbc:UUID schemeName="CUFE-SHA384">%(UUID)s</cbc:UUID>
            <cbc:IssueDate>%(IssueDate)s</cbc:IssueDate>
            <cbc:DocumentType>ApplicationResponse</cbc:DocumentType>
            <cac:Attachment>
                <cac:ExternalReference>
                    <cbc:MimeCode>text/xml</cbc:MimeCode>
                    <cbc:EncodingCode>UTF-8</cbc:EncodingCode>
                    <cbc:Description><![CDATA[%(ApplicationResponse)s]]></cbc:Description>
                </cac:ExternalReference>
            </cac:Attachment>
            <cac:ResultOfVerification>
                <cbc:ValidatorID>Unidad Especial Dirección de Impuestos y Aduanas Nacionales</cbc:ValidatorID>
                <cbc:ValidationResultCode>%(ValidationResultCode)s</cbc:ValidationResultCode>
                <cbc:ValidationDate>%(ValidationDate)s</cbc:ValidationDate>
                <cbc:ValidationTime>%(ValidationTime)s</cbc:ValidationTime>
            </cac:ResultOfVerification>
        </cac:DocumentReference>
    </cac:ParentDocumentLineReference>
</AttachedDocument>
        """

    def _template_basic_data_fe_xml(self):
        template_basic_data_fe_xml = """
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2    http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
                <sts:DianExtensions>
                    <sts:InvoiceControl>
                        <sts:InvoiceAuthorization>%(InvoiceAuthorization)s</sts:InvoiceAuthorization>
                        <sts:AuthorizationPeriod>
                            <cbc:StartDate>%(StartDate)s</cbc:StartDate>
                            <cbc:EndDate>%(EndDate)s</cbc:EndDate>
                        </sts:AuthorizationPeriod>
                        <sts:AuthorizedInvoices>
                            <sts:Prefix>%(Prefix)s</sts:Prefix>
                            <sts:From>%(From)s</sts:From>
                            <sts:To>%(To)s</sts:To>
                        </sts:AuthorizedInvoices>
                    </sts:InvoiceControl>
                    <sts:InvoiceSource>
                        <cbc:IdentificationCode listAgencyID="6" listAgencyName="United Nations Economic Commission for Europe" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1">%(IdentificationCode)s</cbc:IdentificationCode>
                    </sts:InvoiceSource>
                    <sts:SoftwareProvider>
                        <sts:ProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(SoftwareProviderSchemeID)s" schemeName="31">%(SoftwareProviderID)s</sts:ProviderID>
                        <sts:SoftwareID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareID)s</sts:SoftwareID>
                    </sts:SoftwareProvider>
                    <sts:SoftwareSecurityCode schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareSecurityCode)s</sts:SoftwareSecurityCode>
                    <sts:AuthorizationProvider>
                        <sts:AuthorizationProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="4" schemeName="31">800197268</sts:AuthorizationProviderID>
                    </sts:AuthorizationProvider>
                    <sts:QRCode>URL=%(URLQRCode)s=%(UUID)s</sts:QRCode>
                </sts:DianExtensions>
            </ext:ExtensionContent>
        </ext:UBLExtension>
        <ext:UBLExtension>
            <ext:ExtensionContent></ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
   <cbc:UBLVersionID>%(UBLVersionID)s</cbc:UBLVersionID>
   <cbc:CustomizationID>%(CustomizationID)s</cbc:CustomizationID>
   <cbc:ProfileID>%(ProfileID)s</cbc:ProfileID>
   <cbc:ProfileExecutionID>%(ProfileExecutionID)s</cbc:ProfileExecutionID>
   <cbc:ID>%(InvoiceID)s</cbc:ID>
   <cbc:UUID schemeID="%(ProfileExecutionID)s" schemeName="CUFE-SHA384">%(UUID)s</cbc:UUID>
   <cbc:IssueDate>%(IssueDate)s</cbc:IssueDate>
   <cbc:IssueTime>%(IssueTime)s</cbc:IssueTime>
   <cbc:InvoiceTypeCode>%(InvoiceTypeCode)s</cbc:InvoiceTypeCode>
   <cbc:DocumentCurrencyCode>%(DocumentCurrencyCode)s</cbc:DocumentCurrencyCode>
   <cbc:LineCountNumeric>%(LineCountNumeric)s</cbc:LineCountNumeric>
   <cac:AccountingSupplierParty>
      <cbc:AdditionalAccountID>%(SupplierAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyName>
            <cbc:Name>%(SupplierPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(SupplierTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>

               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cac:CorporateRegistrationScheme>
               <cbc:ID>%(Prefix)s</cbc:ID>
            </cac:CorporateRegistrationScheme>
         </cac:PartyLegalEntity>
         <cac:Contact>
           <cbc:ElectronicMail>%(SupplierElectronicMail)s</cbc:ElectronicMail>
         </cac:Contact>
      </cac:Party>
   </cac:AccountingSupplierParty>
   <cac:AccountingCustomerParty>
      <cbc:AdditionalAccountID>%(CustomerAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyIdentification>
            <cbc:ID schemeName="%(SchemeNameAdquiriente)s" schemeID="%(SchemeIDAdquiriente)s">%(IDAdquiriente)s</cbc:ID>
         </cac:PartyIdentification>
         <cac:PartyName>
            <cbc:Name>%(CustomerPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(CustomerCityCode)s</cbc:ID>
               <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(CustomerLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(CustomerTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(CustomerCityCode)s</cbc:ID>
               <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(CustomerLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
        </cac:PartyLegalEntity>
        <cac:Contact>
           <cbc:ElectronicMail>%(CustomerElectronicMail)s</cbc:ElectronicMail>
        </cac:Contact>
        <cac:Person>
           <cbc:FirstName>%(Firstname)s</cbc:FirstName>
        </cac:Person>
      </cac:Party>
   </cac:AccountingCustomerParty>
   <cac:PaymentMeans>
      <cbc:ID>%(PaymentMeansID)s</cbc:ID>
      <cbc:PaymentMeansCode>%(PaymentMeansCode)s</cbc:PaymentMeansCode>
      <cbc:PaymentDueDate>%(PaymentDueDate)s</cbc:PaymentDueDate>
      <cbc:PaymentID>1234</cbc:PaymentID>
   </cac:PaymentMeans>
   <cac:PaymentExchangeRate>
      <cbc:SourceCurrencyCode>%(CurrencyID)s</cbc:SourceCurrencyCode>
      <cbc:SourceCurrencyBaseRate>1.00</cbc:SourceCurrencyBaseRate>
      <cbc:TargetCurrencyCode>COP</cbc:TargetCurrencyCode>
      <cbc:TargetCurrencyBaseRate>1.00</cbc:TargetCurrencyBaseRate>
      <cbc:CalculationRate>%(CalculationRate)s</cbc:CalculationRate>
      <cbc:Date>%(DateRate)s</cbc:Date>
   </cac:PaymentExchangeRate>%(data_taxs_xml)s
   <cac:LegalMonetaryTotal>
      <cbc:LineExtensionAmount currencyID="%(CurrencyID)s">%(TotalLineExtensionAmount)s</cbc:LineExtensionAmount>
      <cbc:TaxExclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxExclusiveAmount)s</cbc:TaxExclusiveAmount>
      <cbc:TaxInclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxInclusiveAmount)s</cbc:TaxInclusiveAmount>
      <cbc:PayableAmount currencyID="%(CurrencyID)s">%(PayableAmount)s</cbc:PayableAmount>
   </cac:LegalMonetaryTotal>%(data_lines_xml)s
</Invoice>
"""
        return template_basic_data_fe_xml

    def _template_basic_data_fe_exportacion_xml(self):
        template_basic_data_fe_exportacion_xml = """
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2    http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
                <sts:DianExtensions>
                    <sts:InvoiceControl>
                        <sts:InvoiceAuthorization>%(InvoiceAuthorization)s</sts:InvoiceAuthorization>
                        <sts:AuthorizationPeriod>
                            <cbc:StartDate>%(StartDate)s</cbc:StartDate>
                            <cbc:EndDate>%(EndDate)s</cbc:EndDate>
                        </sts:AuthorizationPeriod>
                        <sts:AuthorizedInvoices>
                            <sts:Prefix>%(Prefix)s</sts:Prefix>
                            <sts:From>%(From)s</sts:From>
                            <sts:To>%(To)s</sts:To>
                        </sts:AuthorizedInvoices>
                    </sts:InvoiceControl>
                    <sts:InvoiceSource>
                        <cbc:IdentificationCode listAgencyID="6" listAgencyName="United Nations Economic Commission for Europe" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1">%(IdentificationCode)s</cbc:IdentificationCode>
                    </sts:InvoiceSource>
                    <sts:SoftwareProvider>
                        <sts:ProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(SoftwareProviderSchemeID)s" schemeName="31">%(SoftwareProviderID)s</sts:ProviderID>
                        <sts:SoftwareID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareID)s</sts:SoftwareID>
                    </sts:SoftwareProvider>
                    <sts:SoftwareSecurityCode schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareSecurityCode)s</sts:SoftwareSecurityCode>
                    <sts:AuthorizationProvider>
                        <sts:AuthorizationProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="4" schemeName="31">800197268</sts:AuthorizationProviderID>
                    </sts:AuthorizationProvider>
                    <sts:QRCode>URL=%(URLQRCode)s=%(UUID)s</sts:QRCode>
                </sts:DianExtensions>
            </ext:ExtensionContent>
        </ext:UBLExtension>
        <ext:UBLExtension>
            <ext:ExtensionContent></ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
   <cbc:UBLVersionID>%(UBLVersionID)s</cbc:UBLVersionID>
   <cbc:CustomizationID>%(CustomizationID)s</cbc:CustomizationID>
   <cbc:ProfileID>%(ProfileID)s</cbc:ProfileID>
   <cbc:ProfileExecutionID>%(ProfileExecutionID)s</cbc:ProfileExecutionID>
   <cbc:ID>%(InvoiceID)s</cbc:ID>
   <cbc:UUID schemeID="%(ProfileExecutionID)s" schemeName="CUFE-SHA384">%(UUID)s</cbc:UUID>
   <cbc:IssueDate>%(IssueDate)s</cbc:IssueDate>
   <cbc:IssueTime>%(IssueTime)s</cbc:IssueTime>
   <cbc:InvoiceTypeCode>%(InvoiceTypeCode)s</cbc:InvoiceTypeCode>
   <cbc:DocumentCurrencyCode>%(DocumentCurrencyCode)s</cbc:DocumentCurrencyCode>
   <cbc:LineCountNumeric>%(LineCountNumeric)s</cbc:LineCountNumeric>
   <cac:AccountingSupplierParty>
      <cbc:AdditionalAccountID>%(SupplierAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyName>
            <cbc:Name>%(SupplierPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(SupplierTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cac:CorporateRegistrationScheme>
               <cbc:ID>%(Prefix)s</cbc:ID>
            </cac:CorporateRegistrationScheme>
         </cac:PartyLegalEntity>
         <cac:Contact>
           <cbc:ElectronicMail>%(SupplierElectronicMail)s</cbc:ElectronicMail>
         </cac:Contact>
      </cac:Party>
   </cac:AccountingSupplierParty>
   <cac:AccountingCustomerParty>
      <cbc:AdditionalAccountID>%(CustomerAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyIdentification>
            <cbc:ID schemeName="%(SchemeNameAdquiriente)s" schemeID="%(SchemeIDAdquiriente)s">%(IDAdquiriente)s</cbc:ID>
         </cac:PartyIdentification>
         <cac:PartyName>
            <cbc:Name>%(CustomerPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(CustomerCityCode)s</cbc:ID>
               <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(CustomerLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(CustomerTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(CustomerCityCode)s</cbc:ID>
               <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(CustomerLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
        </cac:PartyLegalEntity>
        <cac:Contact>
           <cbc:ElectronicMail>%(CustomerElectronicMail)s</cbc:ElectronicMail>
        </cac:Contact>
        <cac:Person>
           <cbc:FirstName>%(Firstname)s</cbc:FirstName>
        </cac:Person>
      </cac:Party>
   </cac:AccountingCustomerParty>
   <cac:PaymentMeans>
      <cbc:ID>%(PaymentMeansID)s</cbc:ID>
      <cbc:PaymentMeansCode>%(PaymentMeansCode)s</cbc:PaymentMeansCode>
      <cbc:PaymentDueDate>%(PaymentDueDate)s</cbc:PaymentDueDate>
      <cbc:PaymentID>1234</cbc:PaymentID>
   </cac:PaymentMeans>
   <cac:PaymentExchangeRate>
      <cbc:SourceCurrencyCode>%(CurrencyID)s</cbc:SourceCurrencyCode>
      <cbc:SourceCurrencyBaseRate>1.00</cbc:SourceCurrencyBaseRate>
      <cbc:TargetCurrencyCode>COP</cbc:TargetCurrencyCode>
      <cbc:TargetCurrencyBaseRate>1.00</cbc:TargetCurrencyBaseRate>
      <cbc:CalculationRate>%(CalculationRate)s</cbc:CalculationRate>
      <cbc:Date>%(DateRate)s</cbc:Date>
   </cac:PaymentExchangeRate>%(data_taxs_xml)s
   <cac:LegalMonetaryTotal>
      <cbc:LineExtensionAmount currencyID="%(CurrencyID)s">%(TotalLineExtensionAmount)s</cbc:LineExtensionAmount>
      <cbc:TaxExclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxExclusiveAmount)s</cbc:TaxExclusiveAmount>
      <cbc:TaxInclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxInclusiveAmount)s</cbc:TaxInclusiveAmount>
      <cbc:PayableAmount currencyID="%(CurrencyID)s">%(PayableAmount)s</cbc:PayableAmount>
   </cac:LegalMonetaryTotal>%(data_lines_xml)s
</Invoice>
"""
        return template_basic_data_fe_exportacion_xml

    def _generate_data_fe_document_xml(
        self,
        template_basic_data_fe_xml,
        dc,
        dcd,
        data_taxs_xml,
        data_lines_xml,
        CUFE,
        data_xml_signature,
    ):
        template_basic_data_fe_xml = template_basic_data_fe_xml % {
            "InvoiceAuthorization": dcd["InvoiceAuthorization"],
            "StartDate": dcd["StartDate"],
            "EndDate": dcd["EndDate"],
            "Prefix": dcd["Prefix"],
            "From": dcd["From"],
            "To": dcd["To"],
            "IdentificationCode": dc["IdentificationCode"],
            "ProviderID": dc["ProviderID"],
            "SoftwareProviderID": dc["SoftwareProviderID"],
            "SoftwareProviderSchemeID": dc["SoftwareProviderSchemeID"],
            "SoftwareID": dc["SoftwareID"],
            "SoftwareSecurityCode": dc["SoftwareSecurityCode"],
            "UUID": CUFE,
            "UBLVersionID": dc["UBLVersionID"],
            "CustomizationID": dc["CustomizationID"],
            "ProfileID": dc["ProfileID"],
            "ProfileExecutionID": dc["ProfileExecutionID"],
            "InvoiceID": dcd["InvoiceID"],
            "IssueDate": dcd["IssueDate"],
            "IssueTime": dcd["IssueTime"],
            "InvoiceTypeCode": dcd["InvoiceTypeCode"],
            "DocumentCurrencyCode": dcd["DocumentCurrencyCode"],
            "LineCountNumeric": dcd["LineCountNumeric"],
            "SupplierAdditionalAccountID": dc["SupplierAdditionalAccountID"],
            "SupplierPartyName": dc["SupplierPartyName"],
            "SupplierCityCode": dc["SupplierCityCode"],
            "SupplierCityName": dc["SupplierCityName"],
            "SupplierPostal": dc["SupplierPostal"],
            "SupplierCountrySubentity": dc["SupplierCountrySubentity"],
            "SupplierCountrySubentityCode": dc["SupplierCountrySubentityCode"],
            "SupplierLine": dc["SupplierLine"],
            "SupplierCountryCode": dc["SupplierCountryCode"],
            "SupplierCountryName": dc["SupplierCountryName"],
            "schemeID": dc["schemeID"],
            "SupplierTaxLevelCode": dc["SupplierTaxLevelCode"],
            "TaxSchemeID": dcd["TaxSchemeID"],
            "TaxSchemeName": dcd["TaxSchemeName"],
            "SupplierElectronicMail": dc["SupplierElectronicMail"],
            "CustomerAdditionalAccountID": dcd["CustomerAdditionalAccountID"],
            "CustomerPartyName": dcd["CustomerPartyName"],
            "CustomerschemeID": dcd["CustomerschemeID"],
            "CustomerCityCode": dcd["CustomerCityCode"],
            "CustomerCityName": dcd["CustomerCityName"],
            "CustomerCountrySubentity": dcd["CustomerCountrySubentity"],
            "CustomerCountrySubentityCode": dcd["CustomerCountrySubentityCode"],
            "CustomerLine": dcd["CustomerLine"],
            "CustomerCountryCode": dcd["CustomerCountryCode"],
            "CustomerCountryName": dcd["CustomerCountryName"],
            "CustomerSchemeID": dcd["CustomerSchemeID"],
            "CustomerID": dcd["CustomerID"],
            "CustomerTaxLevelCode": dcd["CustomerTaxLevelCode"],
            "CustomerElectronicMail": dcd["CustomerElectronicMail"],
            "Firstname": dcd["Firstname"],
            "PaymentMeansID": dcd["PaymentMeansID"],
            "PaymentMeansCode": dcd["PaymentMeansCode"],
            "PaymentDueDate": dcd["PaymentDueDate"],
            "data_taxs_xml": data_taxs_xml,
            "TotalLineExtensionAmount": dcd["LineExtensionAmount"],
            "TotalTaxExclusiveAmount": dcd["TaxExclusiveAmount"],
            "TotalTaxInclusiveAmount": dcd["TotalTaxInclusiveAmount"],
            "PayableAmount": dcd["PayableAmount"],
            "data_lines_xml": data_lines_xml,
            "CurrencyID": dcd["CurrencyID"],
            "CalculationRate": dcd["CalculationRate"],
            "DateRate": dcd["DateRate"],
            "SchemeIDAdquiriente": dcd["SchemeIDAdquiriente"],
            "SchemeNameAdquiriente": dcd["SchemeNameAdquiriente"],
            "SupplierSchemeName": dcd["SupplierSchemeName"],
            "IDAdquiriente": dcd["IDAdquiriente"],
            "SupplierCityNameSubentity": dc["SupplierCityNameSubentity"],
            "URLQRCode": dc.get("URLQRCode", ""),
            "DeliveryAddress": dc["DeliveryAddress"],
            "DescriptionDebitCreditNote": dcd["DescriptionDebitCreditNote"],
        }
        return template_basic_data_fe_xml

    def _template_basic_data_contingencia_xml(self):
        template_basic_data_contingencia_xml = """
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2    http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
                <sts:DianExtensions>
                    <sts:InvoiceControl>
                        <sts:InvoiceAuthorization>%(InvoiceAuthorization)s</sts:InvoiceAuthorization>
                        <sts:AuthorizationPeriod>
                            <cbc:StartDate>%(StartDate)s</cbc:StartDate>
                            <cbc:EndDate>%(EndDate)s</cbc:EndDate>
                        </sts:AuthorizationPeriod>
                        <sts:AuthorizedInvoices>
                            <sts:Prefix>%(Prefix)s</sts:Prefix>
                            <sts:From>%(From)s</sts:From>
                            <sts:To>%(To)s</sts:To>
                        </sts:AuthorizedInvoices>
                    </sts:InvoiceControl>
                    <sts:InvoiceSource>
                        <cbc:IdentificationCode listAgencyID="6" listAgencyName="United Nations Economic Commission for Europe" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1">%(IdentificationCode)s</cbc:IdentificationCode>
                    </sts:InvoiceSource>
                    <sts:SoftwareProvider>
                        <sts:ProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(SoftwareProviderSchemeID)s" schemeName="31">%(SoftwareProviderID)s</sts:ProviderID>
                        <sts:SoftwareID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareID)s</sts:SoftwareID>
                    </sts:SoftwareProvider>
                    <sts:SoftwareSecurityCode schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareSecurityCode)s</sts:SoftwareSecurityCode>
                    <sts:AuthorizationProvider>
                        <sts:AuthorizationProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="4" schemeName="31">800197268</sts:AuthorizationProviderID>
                    </sts:AuthorizationProvider>
                    <sts:QRCode>URL=%(URLQRCode)s=%(UUID)s</sts:QRCode>
                </sts:DianExtensions>
            </ext:ExtensionContent>
        </ext:UBLExtension>
        <ext:UBLExtension>
            <ext:ExtensionContent></ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
   <cbc:UBLVersionID>%(UBLVersionID)s</cbc:UBLVersionID>
   <cbc:CustomizationID>%(CustomizationID)s</cbc:CustomizationID>
   <cbc:ProfileID>%(ProfileID)s</cbc:ProfileID>
   <cbc:ProfileExecutionID>%(ProfileExecutionID)s</cbc:ProfileExecutionID>
   <cbc:ID>%(ContingencyID)s</cbc:ID>
   <cbc:UUID schemeID="%(ProfileExecutionID)s" schemeName="CUDE-SHA384">%(UUID)s</cbc:UUID>
   <cbc:IssueDate>%(IssueDate)s</cbc:IssueDate>
   <cbc:IssueTime>%(IssueTime)s</cbc:IssueTime>
   <cbc:InvoiceTypeCode>%(InvoiceTypeCode)s</cbc:InvoiceTypeCode>
   <cbc:DocumentCurrencyCode>%(DocumentCurrencyCode)s</cbc:DocumentCurrencyCode>
   <cbc:LineCountNumeric>%(LineCountNumeric)s</cbc:LineCountNumeric>
   <cac:AdditionalDocumentReference>
      <cbc:ID>%(ContingencyReferenceID)s</cbc:ID>
      <cbc:IssueDate>%(ContingencyIssueDate)s</cbc:IssueDate>
      <cbc:DocumentTypeCode>%(ContingencyDocumentTypeCode)s</cbc:DocumentTypeCode>
   </cac:AdditionalDocumentReference>
   <cac:AccountingSupplierParty>
      <cbc:AdditionalAccountID>%(SupplierAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyName>
            <cbc:Name>%(SupplierPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(SupplierTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cac:CorporateRegistrationScheme>
               <cbc:ID>%(Prefix)s</cbc:ID>
            </cac:CorporateRegistrationScheme>
         </cac:PartyLegalEntity>
         <cac:Contact>
           <cbc:ElectronicMail>%(SupplierElectronicMail)s</cbc:ElectronicMail>
         </cac:Contact>
      </cac:Party>
   </cac:AccountingSupplierParty>
   <cac:AccountingCustomerParty>
      <cbc:AdditionalAccountID>%(CustomerAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyIdentification>
            <cbc:ID schemeName="%(SchemeNameAdquiriente)s" schemeID="%(SchemeIDAdquiriente)s">%(IDAdquiriente)s</cbc:ID>
         </cac:PartyIdentification>
         <cac:PartyName>
            <cbc:Name>%(CustomerPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(CustomerCityCode)s</cbc:ID>
               <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(CustomerLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(CustomerTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(CustomerCityCode)s</cbc:ID>
               <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(CustomerLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
        </cac:PartyLegalEntity>
        <cac:Contact>
           <cbc:ElectronicMail>%(CustomerElectronicMail)s</cbc:ElectronicMail>
        </cac:Contact>
        <cac:Person>
           <cbc:FirstName>%(Firstname)s</cbc:FirstName>
        </cac:Person>
      </cac:Party>
   </cac:AccountingCustomerParty>
   <cac:PaymentMeans>
      <cbc:ID>%(PaymentMeansID)s</cbc:ID>
      <cbc:PaymentMeansCode>%(PaymentMeansCode)s</cbc:PaymentMeansCode>
      <cbc:PaymentDueDate>%(PaymentDueDate)s</cbc:PaymentDueDate>
      <cbc:PaymentID>1234</cbc:PaymentID>
   </cac:PaymentMeans>%(data_taxs_xml)s
   <cac:LegalMonetaryTotal>
      <cbc:LineExtensionAmount currencyID="%(CurrencyID)s">%(TotalLineExtensionAmount)s</cbc:LineExtensionAmount>
      <cbc:TaxExclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxExclusiveAmount)s</cbc:TaxExclusiveAmount>
      <cbc:TaxInclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxInclusiveAmount)s</cbc:TaxInclusiveAmount>
      <cbc:PayableAmount currencyID="%(CurrencyID)s">%(PayableAmount)s</cbc:PayableAmount>
   </cac:LegalMonetaryTotal>%(data_lines_xml)s
</Invoice>
"""
        return template_basic_data_contingencia_xml

    def _generate_data_contingencia_document_xml(
        self,
        template_basic_data_contingencia_xml,
        dc,
        dcd,
        data_taxs_xml,
        data_lines_xml,
        CUFE,
        data_xml_signature,
    ):
        template_basic_data_contingencia_xml = template_basic_data_contingencia_xml % {
            "InvoiceAuthorization": dcd["InvoiceAuthorization"],
            "StartDate": dcd["StartDate"],
            "EndDate": dcd["EndDate"],
            "Prefix": dcd["Prefix"],
            "From": dcd["From"],
            "To": dcd["To"],
            "IdentificationCode": dc["IdentificationCode"],
            "ProviderID": dc["ProviderID"],
            "SoftwareProviderID": dc["SoftwareProviderID"],
            "SoftwareProviderSchemeID": dc["SoftwareProviderSchemeID"],
            "SoftwareID": dc["SoftwareID"],
            "SoftwareSecurityCode": dc["SoftwareSecurityCode"],
            "UUID": CUFE,
            "UBLVersionID": dc["UBLVersionID"],
            "CustomizationID": dc["CustomizationID"],
            "ProfileID": dc["ProfileID"],
            "ProfileExecutionID": dc["ProfileExecutionID"],
            "ContingencyID": dcd["ContingencyID"],
            "IssueDate": dcd["IssueDate"],
            "IssueTime": dcd["IssueTime"],
            "InvoiceTypeCode": dcd["InvoiceTypeCode"],
            "DocumentCurrencyCode": dcd["DocumentCurrencyCode"],
            "LineCountNumeric": dcd["LineCountNumeric"],
            "SupplierAdditionalAccountID": dc["SupplierAdditionalAccountID"],
            "SupplierPartyName": dc["SupplierPartyName"],
            "SupplierCityCode": dc["SupplierCityCode"],
            "SupplierCityName": dc["SupplierCityName"],
            "SupplierCountrySubentity": dc["SupplierCountrySubentity"],
            "SupplierCountrySubentityCode": dc["SupplierCountrySubentityCode"],
            "SupplierLine": dc["SupplierLine"],
            "SupplierCountryCode": dc["SupplierCountryCode"],
            "SupplierCountryName": dc["SupplierCountryName"],
            "schemeID": dc["schemeID"],
            "SupplierTaxLevelCode": dc["SupplierTaxLevelCode"],
            "TaxSchemeID": dcd["TaxSchemeID"],
            "TaxSchemeName": dcd["TaxSchemeName"],
            "SupplierElectronicMail": dc["SupplierElectronicMail"],
            "CustomerAdditionalAccountID": dcd["CustomerAdditionalAccountID"],
            "CustomerPartyName": dcd["CustomerPartyName"],
            "CustomerschemeID": dcd["CustomerschemeID"],
            "CustomerCityCode": dcd["CustomerCityCode"],
            "CustomerCityName": dcd["CustomerCityName"],
            "CustomerCountrySubentity": dcd["CustomerCountrySubentity"],
            "CustomerCountrySubentityCode": dcd["CustomerCountrySubentityCode"],
            "CustomerLine": dcd["CustomerLine"],
            "CustomerCountryCode": dcd["CustomerCountryCode"],
            "CustomerCountryName": dcd["CustomerCountryName"],
            "CustomerSchemeID": dcd["CustomerSchemeID"],
            "CustomerID": dcd["CustomerID"],
            "CustomerTaxLevelCode": dcd["CustomerTaxLevelCode"],
            "CustomerElectronicMail": dcd["CustomerElectronicMail"],
            "Firstname": dcd["Firstname"],
            "PaymentMeansID": dcd["PaymentMeansID"],
            "PaymentMeansCode": dcd["PaymentMeansCode"],
            "PaymentDueDate": dcd["PaymentDueDate"],
            "data_taxs_xml": data_taxs_xml,
            "TotalLineExtensionAmount": dcd["LineExtensionAmount"],
            "TotalTaxExclusiveAmount": dcd["TaxExclusiveAmount"],
            "TotalTaxInclusiveAmount": dcd["TotalTaxInclusiveAmount"],
            "PayableAmount": dcd["PayableAmount"],
            "data_lines_xml": data_lines_xml,
            "ContingencyReferenceID": dcd["ContingencyReferenceID"],
            "ContingencyDocumentTypeCode": dcd["ContingencyDocumentTypeCode"],
            "ContingencyIssueDate": dcd["ContingencyIssueDate"],
            "CurrencyID": dcd["CurrencyID"],
            "SchemeIDAdquiriente": dcd["SchemeIDAdquiriente"],
            "SchemeNameAdquiriente": dcd["SchemeNameAdquiriente"],
            "IDAdquiriente": dcd["IDAdquiriente"],
        }
        return template_basic_data_contingencia_xml

    def _template_basic_data_nc_xml(self):
        template_basic_data_nc_xml = """
<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2    http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-CreditNote-2.1.xsd">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
                <sts:DianExtensions>
                    <sts:InvoiceSource>
                        <cbc:IdentificationCode listAgencyID="6" listAgencyName="United Nations Economic Commission for Europe" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1">%(IdentificationCode)s</cbc:IdentificationCode>
                    </sts:InvoiceSource>
                    <sts:SoftwareProvider>
                        <sts:ProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</sts:ProviderID>
                        <sts:SoftwareID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareID)s</sts:SoftwareID>
                    </sts:SoftwareProvider>
                    <sts:SoftwareSecurityCode schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareSecurityCode)s</sts:SoftwareSecurityCode>
                    <sts:AuthorizationProvider>
                        <sts:AuthorizationProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="4" schemeName="31">800197268</sts:AuthorizationProviderID>
                    </sts:AuthorizationProvider>
                    <sts:QRCode>URL=%(URLQRCode)s=%(UUID)s</sts:QRCode>
                </sts:DianExtensions>
            </ext:ExtensionContent>
        </ext:UBLExtension>
        <ext:UBLExtension>
            <ext:ExtensionContent></ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>

    <cbc:UBLVersionID>%(UBLVersionID)s</cbc:UBLVersionID>
    <cbc:CustomizationID>%(CustomizationID)s</cbc:CustomizationID>
    <cbc:ProfileID>%(ProfileID)s</cbc:ProfileID>
    <cbc:ProfileExecutionID>%(ProfileExecutionID)s</cbc:ProfileExecutionID>
    <cbc:ID>%(InvoiceID)s</cbc:ID>
    <cbc:UUID schemeID="%(ProfileExecutionID)s" schemeName="CUDE-SHA384">%(UUID)s</cbc:UUID>
    <cbc:IssueDate>%(IssueDate)s</cbc:IssueDate>
    <cbc:IssueTime>%(IssueTime)s</cbc:IssueTime>
    <cbc:CreditNoteTypeCode>%(CreditNoteTypeCode)s</cbc:CreditNoteTypeCode>
    <cbc:DocumentCurrencyCode>%(DocumentCurrencyCode)s</cbc:DocumentCurrencyCode>
    <cbc:LineCountNumeric>%(LineCountNumeric)s</cbc:LineCountNumeric>
    <cac:BillingReference>
       <cac:InvoiceDocumentReference>
          <cbc:ID>%(InvoiceReferenceID)s</cbc:ID>
          <cbc:UUID schemeName="CUFE-SHA384">%(InvoiceReferenceUUID)s</cbc:UUID>
          <cbc:IssueDate>%(InvoiceReferenceDate)s</cbc:IssueDate>
       </cac:InvoiceDocumentReference>
    </cac:BillingReference>
    <cac:AccountingSupplierParty>
      <cbc:AdditionalAccountID>%(SupplierAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyName>
            <cbc:Name>%(SupplierPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(SupplierTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cac:CorporateRegistrationScheme>
               <cbc:ID>%(Prefix)s</cbc:ID>
            </cac:CorporateRegistrationScheme>
         </cac:PartyLegalEntity>
         <cac:Contact>
           <cbc:ElectronicMail>%(SupplierElectronicMail)s</cbc:ElectronicMail>
         </cac:Contact>
      </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
       <cbc:AdditionalAccountID>%(CustomerAdditionalAccountID)s</cbc:AdditionalAccountID>
       <cac:Party>
          <cac:PartyIdentification>
             <cbc:ID schemeName="%(SchemeNameAdquiriente)s" schemeID="%(SchemeIDAdquiriente)s">%(IDAdquiriente)s</cbc:ID>
          </cac:PartyIdentification>
          <cac:PartyName>
             <cbc:Name>%(CustomerPartyName)s</cbc:Name>
          </cac:PartyName>
          <cac:PhysicalLocation>
             <cac:Address>
                <cbc:ID>%(CustomerCityCode)s</cbc:ID>
                <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
                <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
                <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
                <cac:AddressLine>
                   <cbc:Line>%(CustomerLine)s</cbc:Line>
                </cac:AddressLine>
                <cac:Country>
                   <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                   <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
                </cac:Country>
             </cac:Address>
          </cac:PhysicalLocation>
          <cac:PartyTaxScheme>
             <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
             <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
             <cbc:TaxLevelCode listName="48">%(CustomerTaxLevelCode)s</cbc:TaxLevelCode>
             <cac:RegistrationAddress>
                <cbc:ID>%(CustomerCityCode)s</cbc:ID>
                <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
                <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
                <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
                <cac:AddressLine>
                   <cbc:Line>%(CustomerLine)s</cbc:Line>
                </cac:AddressLine>
                <cac:Country>
                   <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                   <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
                </cac:Country>
             </cac:RegistrationAddress>
             <cac:TaxScheme>
                <cbc:ID>%(TaxSchemeID)s</cbc:ID>
                <cbc:Name>%(TaxSchemeName)s</cbc:Name>
             </cac:TaxScheme>
          </cac:PartyTaxScheme>
          <cac:PartyLegalEntity>
             <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
             <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
         </cac:PartyLegalEntity>
         <cac:Contact>
            <cbc:ElectronicMail>%(CustomerElectronicMail)s</cbc:ElectronicMail>
         </cac:Contact>
         <cac:Person>
            <cbc:FirstName>%(Firstname)s</cbc:FirstName>
         </cac:Person>
       </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:PaymentMeans>
       <cbc:ID>%(PaymentMeansID)s</cbc:ID>
       <cbc:PaymentMeansCode>%(PaymentMeansCode)s</cbc:PaymentMeansCode>
       <cbc:PaymentDueDate>%(PaymentDueDate)s</cbc:PaymentDueDate>
       <cbc:PaymentID>1234</cbc:PaymentID>
    </cac:PaymentMeans>%(data_taxs_xml)s
    <cac:LegalMonetaryTotal>
       <cbc:LineExtensionAmount currencyID="%(CurrencyID)s">%(TotalLineExtensionAmount)s</cbc:LineExtensionAmount>
       <cbc:TaxExclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxExclusiveAmount)s</cbc:TaxExclusiveAmount>
       <cbc:TaxInclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxInclusiveAmount)s</cbc:TaxInclusiveAmount>
       <cbc:PayableAmount currencyID="%(CurrencyID)s">%(PayableAmount)s</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>%(data_credit_lines_xml)s

</CreditNote>"""
        return template_basic_data_nc_xml

    def _generate_data_nc_document_xml(
        self,
        template_basic_data_nc_xml,
        dc,
        dcd,
        data_credit_lines_xml,
        CUFE,
        data_taxs_xml,
    ):
        template_basic_data_nc_xml = template_basic_data_nc_xml % {
            "InvoiceAuthorization": dcd["InvoiceAuthorization"],
            "StartDate": dcd["StartDate"],
            "EndDate": dcd["EndDate"],
            "Prefix": dcd["Prefix"],
            "From": dcd["From"],
            "To": dcd["To"],
            "IdentificationCode": dc["IdentificationCode"],
            "ProviderID": dc["ProviderID"],
            "SoftwareProviderID": dc["SoftwareProviderID"],
            "SoftwareProviderSchemeID": dc["SoftwareProviderSchemeID"],
            "SoftwareID": dc["SoftwareID"],
            "SoftwareSecurityCode": dc["SoftwareSecurityCode"],
            "PayableAmount": dcd["PayableAmount"],
            "UBLVersionID": dc["UBLVersionID"],
            "ProfileExecutionID": dc["ProfileExecutionID"],
            "ProfileID": dc["ProfileID"],
            "CustomizationID": dc["CustomizationID"],
            "InvoiceID": dcd["InvoiceID"],
            "UUID": CUFE,
            "IssueDate": dcd["IssueDate"],
            "IssueTime": dcd["IssueTime"],
            "CreditNoteTypeCode": dcd["CreditNoteTypeCode"],
            "LineCountNumeric": dcd["LineCountNumeric"],
            "TaxSchemeID": dcd["TaxSchemeID"],
            "TaxSchemeName": dcd["TaxSchemeName"],
            "DocumentCurrencyCode": dcd["DocumentCurrencyCode"],
            "SupplierAdditionalAccountID": dc["SupplierAdditionalAccountID"],
            "SupplierPartyName": dc["SupplierPartyName"],
            "SupplierCountrySubentityCode": dc["SupplierCountrySubentityCode"],
            "SupplierCityName": dc["SupplierCityName"],
            "SupplierCountrySubentity": dc["SupplierCountrySubentity"],
            "SupplierLine": dc["SupplierLine"],
            "SupplierCountryCode": dc["SupplierCountryCode"],
            "SupplierCountryName": dc["SupplierCountryName"],
            "SupplierTaxLevelCode": dc["SupplierTaxLevelCode"],
            "SupplierCityCode": dc["SupplierCityCode"],
            "SupplierElectronicMail": dc["SupplierElectronicMail"],
            "schemeID": dc["schemeID"],
            "CustomerAdditionalAccountID": dcd["CustomerAdditionalAccountID"],
            "CustomerID": dcd["CustomerID"],
            "CustomerSchemeID": dcd["CustomerSchemeID"],
            "CustomerPartyName": dcd["CustomerPartyName"],
            "SupplierSchemeName": dcd["SupplierSchemeName"],
            "CustomerCountrySubentityCode": dcd["CustomerCountrySubentityCode"],
            "CustomerCountrySubentity": dcd["CustomerCountrySubentity"],
            "CustomerCityName": dcd["CustomerCityName"],
            "CustomerLine": dcd["CustomerLine"],
            "CustomerCountryCode": dcd["CustomerCountryCode"],
            "CustomerCountryName": dcd["CustomerCountryName"],
            "CustomerTaxLevelCode": dcd["CustomerTaxLevelCode"],
            "CustomerschemeID": dcd["CustomerschemeID"],
            "CustomerCityCode": dcd["CustomerCityCode"],
            "CustomerElectronicMail": dcd["CustomerElectronicMail"],
            "TotalLineExtensionAmount": dcd["LineExtensionAmount"],
            "TotalTaxExclusiveAmount": dcd["TaxExclusiveAmount"],
            "PaymentMeansID": dcd["PaymentMeansID"],
            "PaymentMeansCode": dcd["PaymentMeansCode"],
            "PaymentDueDate": dcd["PaymentDueDate"],
            "TotalTaxInclusiveAmount": dcd["TotalTaxInclusiveAmount"],
            "Firstname": dcd["Firstname"],
            "InvoiceReferenceID": dcd.get("InvoiceReferenceID", ""),
            "InvoiceReferenceUUID": dcd.get("InvoiceReferenceUUID", ""),
            "InvoiceReferenceDate": dcd["InvoiceReferenceDate"],
            "data_taxs_xml": data_taxs_xml,
            "data_credit_lines_xml": data_credit_lines_xml,
            "CurrencyID": dcd["CurrencyID"],
            "SchemeIDAdquiriente": dcd["SchemeIDAdquiriente"],
            "SchemeNameAdquiriente": dcd["SchemeNameAdquiriente"],
            "IDAdquiriente": dcd["IDAdquiriente"],
            "ResponseCodeCreditNote": dcd["ResponseCodeCreditNote"],
            "DescriptionCreditNote": dcd["DescriptionDebitCreditNote"],
            "SupplierCityNameSubentity": dc["SupplierCityNameSubentity"],
            "DeliveryAddress": dc["DeliveryAddress"],
            "URLQRCode": dc.get("URLQRCode", ""),
            "DiscrepancyResponseID": dc.get("DiscrepancyResponseID", ""),
            "DiscrepancyResponseCode": dc.get("DiscrepancyResponseCode", ""),
            "DiscrepancyResponseDescription": dc.get( "DiscrepancyResponseDescription", "" ),
            "CalculationRate": dcd["CalculationRate"],
            "DateRate": dcd["DateRate"],
        }
        return template_basic_data_nc_xml

    def _template_basic_data_nd_xml(self):
        template_basic_data_nd_xml = """
<DebitNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2    http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-DebitNote-2.1.xsd">
   <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
                <sts:DianExtensions>
                    <sts:InvoiceSource>
                        <cbc:IdentificationCode listAgencyID="6" listAgencyName="United Nations Economic Commission for Europe" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1">%(IdentificationCode)s</cbc:IdentificationCode>
                    </sts:InvoiceSource>
                    <sts:SoftwareProvider>
                        <sts:ProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(SoftwareProviderSchemeID)s" schemeName="31">%(SoftwareProviderID)s</sts:ProviderID>
                        <sts:SoftwareID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareID)s</sts:SoftwareID>
                    </sts:SoftwareProvider>
                    <sts:SoftwareSecurityCode schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">%(SoftwareSecurityCode)s</sts:SoftwareSecurityCode>
                    <sts:AuthorizationProvider>
                        <sts:AuthorizationProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="4" schemeName="31">800197268</sts:AuthorizationProviderID>
                    </sts:AuthorizationProvider>
                    <sts:QRCode>URL=%(URLQRCode)s=%(UUID)s</sts:QRCode>
                </sts:DianExtensions>
            </ext:ExtensionContent>
        </ext:UBLExtension>
        <ext:UBLExtension>
            <ext:ExtensionContent></ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>

    <cbc:UBLVersionID>%(UBLVersionID)s</cbc:UBLVersionID>
    <cbc:CustomizationID>%(CustomizationID)s</cbc:CustomizationID>
    <cbc:ProfileID>%(ProfileID)s</cbc:ProfileID>
    <cbc:ProfileExecutionID>%(ProfileExecutionID)s</cbc:ProfileExecutionID>
    <cbc:ID>%(InvoiceID)s</cbc:ID>
    <cbc:UUID schemeID="%(ProfileExecutionID)s" schemeName="CUDE-SHA384">%(UUID)s</cbc:UUID>
    <cbc:IssueDate>%(IssueDate)s</cbc:IssueDate>
    <cbc:IssueTime>%(IssueTime)s</cbc:IssueTime>
    <cbc:DocumentCurrencyCode>%(DocumentCurrencyCode)s</cbc:DocumentCurrencyCode>
    <cbc:LineCountNumeric>%(LineCountNumeric)s</cbc:LineCountNumeric>
    <cac:BillingReference>
       <cac:InvoiceDocumentReference>
          <cbc:ID>%(InvoiceReferenceID)s</cbc:ID>
          <cbc:UUID schemeName="CUFE-SHA384">%(InvoiceReferenceUUID)s</cbc:UUID>
          <cbc:IssueDate>%(InvoiceReferenceDate)s</cbc:IssueDate>
       </cac:InvoiceDocumentReference>
    </cac:BillingReference>
    <cac:AccountingSupplierParty>
      <cbc:AdditionalAccountID>%(SupplierAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyName>
            <cbc:Name>%(SupplierPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(SupplierTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cac:CorporateRegistrationScheme>
               <cbc:ID>%(Prefix)s</cbc:ID>
            </cac:CorporateRegistrationScheme>
         </cac:PartyLegalEntity>
         <cac:Contact>
           <cbc:ElectronicMail>%(SupplierElectronicMail)s</cbc:ElectronicMail>
         </cac:Contact>
      </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
       <cbc:AdditionalAccountID>%(CustomerAdditionalAccountID)s</cbc:AdditionalAccountID>
       <cac:Party>
          <cac:PartyIdentification>
             <cbc:ID schemeName="%(SchemeNameAdquiriente)s" schemeID="%(SchemeIDAdquiriente)s">%(IDAdquiriente)s</cbc:ID>
          </cac:PartyIdentification>
          <cac:PartyName>
             <cbc:Name>%(CustomerPartyName)s</cbc:Name>
          </cac:PartyName>
          <cac:PhysicalLocation>
             <cac:Address>
                <cbc:ID>%(CustomerCityCode)s</cbc:ID>
                <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
                <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
                <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
                <cac:AddressLine>
                   <cbc:Line>%(CustomerLine)s</cbc:Line>
                </cac:AddressLine>
                <cac:Country>
                   <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                   <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
                </cac:Country>
             </cac:Address>
          </cac:PhysicalLocation>
          <cac:PartyTaxScheme>
             <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
             <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
             <cbc:TaxLevelCode listName="48">%(CustomerTaxLevelCode)s</cbc:TaxLevelCode>
             <cac:RegistrationAddress>
                <cbc:ID>%(CustomerCityCode)s</cbc:ID>
                <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
                <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
                <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
                <cac:AddressLine>
                   <cbc:Line>%(CustomerLine)s</cbc:Line>
                </cac:AddressLine>
                <cac:Country>
                   <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                   <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
                </cac:Country>
             </cac:RegistrationAddress>
             <cac:TaxScheme>
                <cbc:ID>%(TaxSchemeID)s</cbc:ID>
                <cbc:Name>%(TaxSchemeName)s</cbc:Name>
             </cac:TaxScheme>
          </cac:PartyTaxScheme>
          <cac:PartyLegalEntity>
             <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
             <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
         </cac:PartyLegalEntity>
         <cac:Contact>
            <cbc:ElectronicMail>%(CustomerElectronicMail)s</cbc:ElectronicMail>
         </cac:Contact>
         <cac:Person>
            <cbc:FirstName>%(Firstname)s</cbc:FirstName>
         </cac:Person>
       </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:PaymentMeans>
       <cbc:ID>%(PaymentMeansID)s</cbc:ID>
       <cbc:PaymentMeansCode>%(PaymentMeansCode)s</cbc:PaymentMeansCode>
       <cbc:PaymentDueDate>%(PaymentDueDate)s</cbc:PaymentDueDate>
       <cbc:PaymentID>1234</cbc:PaymentID>
    </cac:PaymentMeans>%(data_taxs_xml)s
    <cac:RequestedMonetaryTotal>
       <cbc:LineExtensionAmount currencyID="%(CurrencyID)s">%(TotalLineExtensionAmount)s</cbc:LineExtensionAmount>
       <cbc:TaxExclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxExclusiveAmount)s</cbc:TaxExclusiveAmount>
       <cbc:TaxInclusiveAmount currencyID="%(CurrencyID)s">%(TotalTaxInclusiveAmount)s</cbc:TaxInclusiveAmount>
       <cbc:PayableAmount currencyID="%(CurrencyID)s">%(PayableAmount)s</cbc:PayableAmount>
    </cac:RequestedMonetaryTotal>%(data_debit_lines_xml)s

</DebitNote>"""
        return template_basic_data_nd_xml

    def _generate_data_nd_document_xml(
        self,
        template_basic_data_nc_xml,
        dc,
        dcd,
        data_debit_lines_xml,
        CUFE,
        data_taxs_xml,
    ):
        template_basic_data_nd_xml = template_basic_data_nc_xml % {
            "InvoiceAuthorization": dcd["InvoiceAuthorization"],
            "StartDate": dcd["StartDate"],
            "EndDate": dcd["EndDate"],
            "Prefix": dcd["Prefix"],
            "From": dcd["From"],
            "To": dcd["To"],
            "CustomerElectronicPhone": dcd["CustomerElectronicPhone"],
            "credit_note_reason": dcd["credit_note_reason"],
            "billing_reference_id": dcd["billing_reference_id"],
            "IdentificationCode": dc["IdentificationCode"],
            "ProviderID": dc["ProviderID"],
            "SoftwareProviderID": dc["SoftwareProviderID"],
            "SoftwareProviderSchemeID": dc["SoftwareProviderSchemeID"],
            "SoftwareID": dc["SoftwareID"],
            "SoftwareSecurityCode": dc["SoftwareSecurityCode"],
            "PayableAmount": dcd["PayableAmount"],
            "UBLVersionID": dc["UBLVersionID"],
            "ProfileExecutionID": dc["ProfileExecutionID"],
            "ProfileID": dc["ProfileID"],
            "CustomizationID": dc["CustomizationID"],
            "InvoiceID": dcd["InvoiceID"],
            "UUID": CUFE,
            "IssueDate": dcd["IssueDate"],
            "IssueTime": dcd["IssueTime"],
            "DebitNoteTypeCode": dcd["DebitNoteTypeCode"],
            "LineCountNumeric": dcd["LineCountNumeric"],
            "TaxSchemeID": dc["TaxSchemeID"],
            "TaxSchemeName": dc["TaxSchemeName"],
            "DocumentCurrencyCode": dcd["DocumentCurrencyCode"],
            "SupplierAdditionalAccountID": dc["SupplierAdditionalAccountID"],
            "SupplierPartyName": dc["SupplierPartyName"],
            "SupplierCountrySubentityCode": dc["SupplierCountrySubentityCode"],
            "SupplierCityName": dc["SupplierCityName"],
            "SupplierCountrySubentity": dc["SupplierCountrySubentity"],
            "SupplierLine": dc["SupplierLine"],
            "SupplierCountryCode": dc["SupplierCountryCode"],
            "SupplierCountryName": dc["SupplierCountryName"],
            "SupplierTaxLevelCode": dc["SupplierTaxLevelCode"],
            "SupplierCityCode": dc["SupplierCityCode"],
            "SupplierElectronicMail": dc["SupplierElectronicMail"],
            "SupplierPartyPhone": dc["SupplierPartyPhone"],
            "SupplierPostal": dc["SupplierPostal"],
            "schemeID": dc["schemeID"],
            "CustomerAdditionalAccountID": dcd["CustomerAdditionalAccountID"],
            "CustomerID": dcd["CustomerID"],
            "CustomerSchemeID": dcd["CustomerSchemeID"],
            "CustomerPartyName": dcd["CustomerPartyName"],
            "CustomerCountrySubentityCode": dcd["CustomerCountrySubentityCode"],
            "CustomerCountrySubentity": dcd["CustomerCountrySubentity"],
            "CustomerCityName": dcd["CustomerCityName"],
            "CustomerPostal": dcd["CustomerPostal"],
            "CustomerElectronicPhone": dcd["CustomerElectronicPhone"],
            "CustomerLine": dcd["CustomerLine"],
            "CustomerCountryCode": dcd["CustomerCountryCode"],
            "CustomerCountryName": dcd["CustomerCountryName"],
            "CustomerTaxLevelCode": dcd["CustomerTaxLevelCode"],
            "CustomerschemeID": dcd["CustomerschemeID"],
            "CustomerCityCode": dcd["CustomerCityCode"],
            "CustomerElectronicMail": dcd["CustomerElectronicMail"],
            "TotalLineExtensionAmount": dcd["LineExtensionAmount"],
            "TotalTaxExclusiveAmount": dcd["TaxExclusiveAmount"],
            "PaymentMeansID": dcd["PaymentMeansID"],
            "PaymentMeansCode": dcd["PaymentMeansCode"],
            "PaymentDueDate": dcd["PaymentDueDate"],
            "TotalTaxInclusiveAmount": dcd["TotalTaxInclusiveAmount"],
            "Firstname": dcd["Firstname"],
            "InvoiceReferenceID": dcd.get("InvoiceReferenceID", ""),
            "InvoiceReferenceUUID": dcd.get("InvoiceReferenceUUID", ""),
            "InvoiceReferenceDate": dcd.get("InvoiceReferenceDate", ""),
            "data_taxs_xml": data_taxs_xml,
            "data_debit_lines_xml": data_debit_lines_xml,
            "CurrencyID": dcd["CurrencyID"],
            "SchemeIDAdquiriente": dcd["SchemeIDAdquiriente"],
            "SchemeNameAdquiriente": dcd["SchemeNameAdquiriente"],
            "IDAdquiriente": dcd["IDAdquiriente"],
            "ResponseCode": dcd["ResponseCodeDebitNote"],
            "DescriptionDebitCreditNote": dcd["DescriptionDebitCreditNote"],
            "SupplierCityNameSubentity": dc["SupplierCityNameSubentity"],
            "DeliveryAddress": dc["DeliveryAddress"],
            "URLQRCode": dc.get("URLQRCode", ""),
            "DiscrepancyResponseID": dc.get("DiscrepancyResponseID", ""),
            "DiscrepancyResponseCode": dc.get("DiscrepancyResponseCode", ""),
            "DiscrepancyResponseDescription": dc.get(
                "DiscrepancyResponseDescription", ""
            ),
            "CalculationRate": dcd["CalculationRate"],
            "DateRate": dcd["DateRate"],
        }
        return template_basic_data_nd_xml


    def _template_line_data_information_content_provider_party_xml(self):
        return """
            <cac:InformationContentProviderParty>
                <cac:PowerOfAttorney>
                    <cac:AgentParty>
                        <cac:PartyIdentification>
                            <cbc:ID schemeAgencyID="195" schemeID="3" schemeName="31">%(MandanteNumberIdentification)s</cbc:ID>
                        </cac:PartyIdentification>
                    </cac:AgentParty>
                </cac:PowerOfAttorney>
            </cac:InformationContentProviderParty>
        """





    def _template_signature_data_xml(self):
        template_signature_data_xml = """
                <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Id="xmldsig-%(identifier)s">
                    <ds:SignedInfo>
                        <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
                        <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                        <ds:Reference Id="xmldsig-%(identifier)s-ref0" URI="">
                            <ds:Transforms>
                                <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
                            </ds:Transforms>
                            <ds:DigestMethod  Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                            <ds:DigestValue>%(data_xml_signature_ref_zero)s</ds:DigestValue>
                        </ds:Reference>
                        <ds:Reference URI="#xmldsig-%(identifierkeyinfo)s-keyinfo">
                            <ds:DigestMethod  Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                            <ds:DigestValue>%(data_xml_keyinfo_base)s</ds:DigestValue>
                        </ds:Reference>
                        <ds:Reference Type="http://uri.etsi.org/01903#SignedProperties" URI="#xmldsig-%(identifier)s-signedprops">
                            <ds:DigestMethod  Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                            <ds:DigestValue>%(data_xml_SignedProperties_base)s</ds:DigestValue>
                        </ds:Reference>
                    </ds:SignedInfo>
                    <ds:SignatureValue Id="xmldsig-%(identifier)s-sigvalue">%(SignatureValue)s</ds:SignatureValue>
                    <ds:KeyInfo Id="xmldsig-%(identifierkeyinfo)s-keyinfo">
                        <ds:X509Data>
                            <ds:X509Certificate>%(data_public_certificate_base)s</ds:X509Certificate>
                        </ds:X509Data>
                    </ds:KeyInfo>
                    <ds:Object>
                        <xades:QualifyingProperties xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" Target="#xmldsig-%(identifier)s">
                            <xades:SignedProperties Id="xmldsig-%(identifier)s-signedprops">
                                <xades:SignedSignatureProperties>
                                    <xades:SigningTime>%(data_xml_SigningTime)s</xades:SigningTime>
                                    <xades:SigningCertificate>
                                        <xades:Cert>
                                            <xades:CertDigest>
                                                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                                                <ds:DigestValue>%(CertDigestDigestValue)s</ds:DigestValue>
                                            </xades:CertDigest>
                                            <xades:IssuerSerial>
                                                <ds:X509IssuerName>%(IssuerName)s</ds:X509IssuerName>
                                                <ds:X509SerialNumber>%(SerialNumber)s</ds:X509SerialNumber>
                                            </xades:IssuerSerial>
                                        </xades:Cert>
                                    </xades:SigningCertificate>
                                    <xades:SignaturePolicyIdentifier>
                                        <xades:SignaturePolicyId>
                                            <xades:SigPolicyId>
                                                <xades:Identifier>https://facturaelectronica.dian.gov.co/politicadefirma/v2/politicadefirmav2.pdf</xades:Identifier>
                                                <xades:Description>Politica de firma para facturas electronicas de la Republica de Colombia</xades:Description>
                                            </xades:SigPolicyId>
                                            <xades:SigPolicyHash>
                                                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                                                <ds:DigestValue>%(data_xml_politics)s</ds:DigestValue>
                                            </xades:SigPolicyHash>
                                        </xades:SignaturePolicyId>
                                    </xades:SignaturePolicyIdentifier>
                                    <xades:SignerRole>
                                        <xades:ClaimedRoles>
                                            <xades:ClaimedRole>supplier</xades:ClaimedRole>
                                        </xades:ClaimedRoles>
                                    </xades:SignerRole>
                                </xades:SignedSignatureProperties>
                            </xades:SignedProperties>
                        </xades:QualifyingProperties>
                    </ds:Object>
                </ds:Signature>"""
        return template_signature_data_xml

    def _template_send_data_xml(self):
        template_send_data_xml = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:rep="http://www.dian.gov.co/servicios/facturaelectronica/ReportarFactura">
<soapenv:Header>
<wsse:Security soapenv:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
<wsse:UsernameToken>
<wsse:Username>%(Username)s</wsse:Username>
<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">%(Password)s</wsse:Password>
<wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">%(Nonce)s</wsse:Nonce>
<wsu:Created>%(Created)s</wsu:Created>
</wsse:UsernameToken>
</wsse:Security>
</soapenv:Header>
<soapenv:Body>
<rep:EnvioFacturaElectronicaPeticion>
<rep:NIT>%(NIT)s</rep:NIT>
<rep:InvoiceNumber>%(InvoiceNumber)s</rep:InvoiceNumber>
<rep:IssueDate>%(IssueDate)s</rep:IssueDate>
<rep:Document>%(Document)s</rep:Document>
</rep:EnvioFacturaElectronicaPeticion>
</soapenv:Body>
</soapenv:Envelope>"""
        return template_send_data_xml

    @api.model
    def _generate_signature_ref0(
        self, data_xml_document, document_repository, password
    ):
        template_basic_data_fe_xml = data_xml_document
        template_basic_data_fe_xml = etree.tostring(
            etree.fromstring(template_basic_data_fe_xml),
            method="c14n",
            exclusive=False,
            with_comments=False,
            inclusive_ns_prefixes=None,
        )
        data_xml_sha256 = hashlib.new("sha256", template_basic_data_fe_xml)
        data_xml_digest = data_xml_sha256.digest()
        data_xml_signature_ref_zero = base64.b64encode(data_xml_digest)
        data_xml_signature_ref_zero = data_xml_signature_ref_zero.decode()
        return data_xml_signature_ref_zero

    @api.model
    def _update_signature(
        self,
        template_signature_data_xml,
        data_xml_signature_ref_zero,
        data_public_certificate_base,
        data_xml_keyinfo_base,
        data_xml_politics,
        data_xml_SignedProperties_base,
        data_xml_SigningTime,
        dian_constants,
        data_xml_SignatureValue,
        data_constants_document,
    ):
        data_xml_signature = template_signature_data_xml % {
            "data_xml_signature_ref_zero": data_xml_signature_ref_zero,
            "data_public_certificate_base": data_public_certificate_base,
            "data_xml_keyinfo_base": data_xml_keyinfo_base,
            "data_xml_politics": data_xml_politics,
            "data_xml_SignedProperties_base": data_xml_SignedProperties_base,
            "data_xml_SigningTime": data_xml_SigningTime,
            "CertDigestDigestValue": dian_constants["CertDigestDigestValue"],
            "IssuerName": dian_constants["IssuerName"],
            "SerialNumber": dian_constants["SerialNumber"],
            "SignatureValue": data_xml_SignatureValue,
            "identifier": data_constants_document["identifier"],
            "identifierkeyinfo": data_constants_document["identifierkeyinfo"],
        }
        return data_xml_signature

    
    def _generate_signature_ref1(
        self, data_xml_keyinfo_generate, document_repository, password
    ):
        data_xml_keyinfo_generate = etree.tostring(
            etree.fromstring(data_xml_keyinfo_generate), method="c14n"
        )
        data_xml_keyinfo_sha256 = hashlib.new("sha256", data_xml_keyinfo_generate)
        data_xml_keyinfo_digest = data_xml_keyinfo_sha256.digest()
        data_xml_keyinfo_base = base64.b64encode(data_xml_keyinfo_digest)
        data_xml_keyinfo_base = data_xml_keyinfo_base.decode()
        return data_xml_keyinfo_base

    def _generate_digestvalue_to(self, elementTo):
        # Generar el digestvalue de to
        elementTo = etree.tostring(etree.fromstring(elementTo), method="c14n")
        elementTo_sha256 = hashlib.new("sha256", elementTo)
        elementTo_digest = elementTo_sha256.digest()
        elementTo_base = base64.b64encode(elementTo_digest)
        elementTo_base = elementTo_base.decode()
        return elementTo_base

    
    def _generate_signature_politics(self, document_repository):
        data_xml_politics = "dMoMvtcG5aIzgYo0tIsSQeVJBDnUnfSOfBpxXrmor0Y="
        return data_xml_politics

    
    def _generate_signature_ref2(self, data_xml_SignedProperties_generate):
        # Generar la referencia 2, se obtine desde el elemento SignedProperties que se
        # encuentra en la firma aplicando el algoritmo SHA256 y convirtiendolo a base64.
        data_xml_SignedProperties_c14n = etree.tostring(
            etree.fromstring(data_xml_SignedProperties_generate), method="c14n"
        )
        data_xml_SignedProperties_sha256 = hashlib.new(
            "sha256", data_xml_SignedProperties_c14n
        )
        data_xml_SignedProperties_digest = data_xml_SignedProperties_sha256.digest()
        data_xml_SignedProperties_base = base64.b64encode(
            data_xml_SignedProperties_digest
        )
        data_xml_SignedProperties_base = data_xml_SignedProperties_base.decode()
        return data_xml_SignedProperties_base

    
    def _generate_CertDigestDigestValue(self):
        _, certificate = self.get_key() 

        cert_der = certificate.public_bytes(encoding=serialization.Encoding.DER)
        digest = hashes.Hash(hashes.SHA256())
        digest.update(cert_der)
        cert_digest = digest.finalize()
        CertDigestDigestValue = base64.b64encode(cert_digest).decode()
        return CertDigestDigestValue

    
    def _generate_SignatureValue(self, data_xml_SignedInfo_generate):
        data_xml_SignatureValue_c14n = etree.tostring(
            etree.fromstring(data_xml_SignedInfo_generate),
            method="c14n",
            exclusive=False,
            with_comments=False,
        )
        private_key, _ = self.get_key()
        try:
            # Sign the data
            signature = private_key.sign(
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except Exception as ex:
            raise UserError(_("Failed to sign the document: %s") % tools.ustr(ex))
        SignatureValue = base64.b64encode(signature).decode()
        
        
        public_key = self.get_pem() 
        try:
            public_key.verify(
                signature,
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except Exception:
            raise UserError(_("Signature was not successfully validated"))
        
        return SignatureValue

    @api.model
    def _get_doctype(self, doctype, is_debit_note, in_contingency_4):
        docdian = False
        if doctype == "out_invoice" and not is_debit_note:  # Es una factura
            if (
                not self.contingency_3
                and not self.contingency_4
                and not in_contingency_4
            ):
                docdian = "01"
            elif self.contingency_3 and not in_contingency_4:
                docdian = "03"
            elif self.contingency_4 and not in_contingency_4:
                docdian = "04"
            elif in_contingency_4:
                docdian = "04"
            if self.document_id.fe_type =="02":
                docdian = "02"
        
        if doctype == "out_refund":
            docdian = "91"
        if doctype == "out_invoice" and is_debit_note:
            docdian = "92"
        return docdian

    @api.model
    def _get_lines_invoice(self, invoice_id):
        lines = self.env["account.move.line"].search_count([
                ("move_id", "=", invoice_id),
                ("product_id", "!=", None),
                ("product_id.enable_charges", "!=", True),
                ("display_type", "=", 'product'),
                ("price_subtotal", "!=", 0.00),])
        return lines

    @api.model
    def _get_time(self):
        fmt = "%H:%M:%S"
        now_utc = datetime.now(timezone("UTC"))
        now_time = now_utc.strftime(fmt)
        return now_time

    @api.model
    def _get_time_colombia(self):
        fmt = "%H:%M:%S-05:00"
        now_utc = datetime.now(timezone("UTC"))
        now_time = now_utc.strftime(fmt)
        return now_time

    
    def _generate_signature_signingtime(self):
        fmt = "%Y-%m-%dT%H:%M:%S"
        now_utc = datetime.now(timezone("UTC"))
        now_bogota = now_utc
        data_xml_SigningTime = now_bogota.strftime(fmt) + "-05:00"
        return data_xml_SigningTime

    @api.model
    def _generate_xml_filename(self, data_resolution, NitSinDV, doctype, is_debit_note):
        if doctype == "out_invoice" and not is_debit_note:
            docdian = "fv"
        elif doctype == "out_refund":
            docdian = "nc"
        elif doctype == "out_invoice" and is_debit_note:
            docdian = "nd"

        len_prefix = len(data_resolution["Prefix"])
        len_invoice = len(data_resolution["InvoiceID"])
        dian_code_int = int(data_resolution["InvoiceID"][len_prefix:len_invoice])
        dian_code_hex = self.IntToHex(dian_code_int)
        dian_code_hex.zfill(10)
        # TODO: Revisar el secuenciador segun la norma
        file_name_xml = docdian + NitSinDV.zfill(10) + dian_code_hex.zfill(10) + ".xml"
        return file_name_xml

    def IntToHex(self, dian_code_int):
        dian_code_hex = "%02x" % dian_code_int
        return dian_code_hex

    def _generate_zip_filename(self, data_resolution, NitSinDV, doctype, is_debit_note):
        if doctype == "out_invoice" and not is_debit_note:
            docdian = "fv"
        elif doctype == "out_refund":
            docdian = "nc"
        elif doctype == "out_invoice" and is_debit_note:
            docdian = "nd"
        secuenciador = data_resolution["InvoiceID"]
        dian_code_int = int(re.sub(r"\D", "", secuenciador))
        dian_code_hex = self.IntToHex(dian_code_int)
        dian_code_hex.zfill(10)
        file_name_zip = docdian + NitSinDV.zfill(10) + dian_code_hex.zfill(10) + ".zip"
        return file_name_zip

    def _generate_zip_content(
        self, FileNameXML, FileNameZIP, data_xml_document, document_repository
    ):
        # Almacena archvio XML
        xml_file = document_repository + "/" + FileNameXML
        f = open(xml_file, "w")
        f.write(str(data_xml_document))
        f.close()
        # Comprime archvio XML
        zip_file = document_repository + "/" + FileNameZIP
        zf = zipfile.ZipFile(zip_file, mode="w")
        try:
            zf.write(xml_file, compress_type=compression)
        finally:
            zf.close()
        # Obtiene datos comprimidos
        data_xml = zip_file
        data_xml = open(data_xml, "rb")
        data_xml = data_xml.read()
        contenido_data_xml_b64 = base64.b64encode(data_xml)
        contenido_data_xml_b64 = contenido_data_xml_b64.decode()
        return contenido_data_xml_b64

    @staticmethod
    def _generate_zip_multiple_files(files, zip_file_name):
        """
        @param: files: tuple((file_name, file_data))
        @return: base64 zip file
        """
        with zipfile.ZipFile(f"/tmp/{zip_file_name}", mode="w") as zf:
            for name, data in files:
                zf.writestr(name, data)
        with open(f"/tmp/{zip_file_name}", "rb") as zfile:
            data = zfile.read()
            return base64.b64encode(data)

    @api.model
    def _generate_nonce(self, InvoiceID, seed_code):
        nonce = randint(1, seed_code)
        nonce = base64.b64encode((InvoiceID + str(nonce)).encode())
        nonce = nonce.decode()
        return nonce

    def _generate_software_security_code(
        self, software_identification_code, software_pin, NroDocumento
    ):
        software_security_code = hashlib.sha384(
            (software_identification_code + software_pin + NroDocumento).encode()
        )
        software_security_code = software_security_code.hexdigest()
        return software_security_code

    def _generate_datetime_timestamp(self):
        fmt = "%Y-%m-%dT%H:%M:%S.%f"
        # now_utc = datetime.now(timezone('UTC'))
        now_bogota = datetime.now(timezone("UTC"))
        # now_bogota = now_utc.astimezone(timezone('America/Bogota'))
        Created = now_bogota.strftime(fmt)[:-3] + "Z"
        now_bogota = now_bogota + timedelta(minutes=5)
        Expires = now_bogota.strftime(fmt)[:-3] + "Z"
        timestamp = {"Created": Created, "Expires": Expires}
        return timestamp

    def _generate_datetime_IssueDate(self):
        date_invoice_cufe = {}
        fmtSend = "%Y-%m-%dT%H:%M:%S"
        now_utc = datetime.now(timezone("UTC"))
        now_bogota = now_utc
        # now_bogota = now_utc.astimezone(timezone('America/Bogota'))
        date_invoice_cufe["IssueDateSend"] = now_bogota.strftime(fmtSend)
        fmtCUFE = "%Y-%m-%d"
        date_invoice_cufe["IssueDateCufe"] = now_bogota.strftime(fmtCUFE)
        fmtInvoice = "%Y-%m-%d"
        date_invoice_cufe["IssueDate"] = now_bogota.strftime(fmtInvoice)
        return date_invoice_cufe

    def _complements_second_decimal(self, amount):
        amount_dec = round(((amount - int(amount)) * 100.0), 2)
        amount_int = int(amount_dec)
        if amount_int % 10 == 0:
            amount = str(amount) + "0"
        else:
            amount = str(amount)
        # amount = str(int(amount)) + (str((amount - int(amount)))[1:4])
        return amount

    def count_decimals(self, amount):
        if amount:
            return str(amount)[::-1].find(".")

        return amount

    def truncate(self, amount, decimals):
        if amount:
            return math.floor(amount * 10**decimals) / 10**decimals
        else:
            return "0.00"

    def _complements_second_decimal_total(
        self, amount, allow_more_than_two_decimals=False
    ):
        if amount:
            cant_decimals = self.count_decimals(amount)
            if cant_decimals >= 3:
                if allow_more_than_two_decimals:
                    return self.truncate(amount, 3)
                return str("{:.2f}".format(amount))
            return str("{:.2f}".format(amount))
        else:
            return "0.00"

    def _second_decimal_total(self, amount):
        if amount:
            return str("{:.2f}".format(str(amount)))
        else:
            return 0

    def _template_SendTestSetAsyncsend_xml(self):
        template_SendTestSetAsyncsend_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/SendTestSetAsync</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:SendTestSetAsync>
            <wcf:fileName>%(fileName)s</wcf:fileName>
            <wcf:contentFile>%(contentFile)s</wcf:contentFile>
            <wcf:testSetId>%(testSetId)s</wcf:testSetId>
        </wcf:SendTestSetAsync>
    </soap:Body>
</soap:Envelope>
"""
        return template_SendTestSetAsyncsend_xml

    @api.model
    def _generate_SendTestSetAsync_send_xml(
        self,
        template_send_data_xml,
        fileName,
        contentFile,
        Created,
        testSetId,
        identifier,
        Expires,
        Certificate,
        identifierSecurityToken,
        identifierTo,
    ):
        data_send_xml = template_send_data_xml % {
            "fileName": fileName,
            "contentFile": contentFile,
            "testSetId": testSetId,
            "identifier": identifier,
            "Created": Created,
            "Expires": Expires,
            "Certificate": Certificate,
            "identifierSecurityToken": identifierSecurityToken,
            "identifierTo": identifierTo,
        }
        return data_send_xml

    def _template_SendBillAsyncsend_xml(self):
        template_SendBillAsyncsend_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/SendBillAsync</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:SendBillAsync>
            <wcf:fileName>%(fileName)s</wcf:fileName>
            <wcf:contentFile>%(contentFile)s</wcf:contentFile>
        </wcf:SendBillAsync>
    </soap:Body>
</soap:Envelope>
"""
        return template_SendBillAsyncsend_xml

        # <wcf:testSetId>%(testSetId)s</wcf:testSetId>

    @api.model
    def _generate_SendBillAsync_send_xml(
        self,
        template_send_data_xml,
        fileName,
        contentFile,
        Created,
        testSetId,
        identifier,
        Expires,
        Certificate,
        identifierSecurityToken,
        identifierTo,
    ):
        data_send_xml = template_send_data_xml % {
            "fileName": fileName,
            "contentFile": contentFile,
            "testSetId": testSetId,
            "identifier": identifier,
            "Created": Created,
            "Expires": Expires,
            "Certificate": Certificate,
            "identifierSecurityToken": identifierSecurityToken,
            "identifierTo": identifierTo,
        }
        return data_send_xml

    def _template_GetStatus_xml(self):
        template_GetStatus_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatusZip</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:GetStatusZip>
            <wcf:trackId>%(trackId)s</wcf:trackId>
        </wcf:GetStatusZip>
    </soap:Body>
</soap:Envelope>
"""
        return template_GetStatus_xml

    @api.model
    def _generate_GetStatus_send_xml(
        self,
        template_getstatus_send_data_xml,
        identifier,
        Created,
        Expires,
        Certificate,
        identifierSecurityToken,
        identifierTo,
        trackId,
    ):
        data_getstatus_send_xml = template_getstatus_send_data_xml % {
            "identifier": identifier,
            "Created": Created,
            "Expires": Expires,
            "Certificate": Certificate,
            "identifierSecurityToken": identifierSecurityToken,
            "identifierTo": identifierTo,
            "trackId": trackId,
        }
        return data_getstatus_send_xml

    def _template_GetStatusExist_xml(self):
        template_GetStatus_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatus</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:GetStatus>
            <wcf:trackId>%(trackId)s</wcf:trackId>
        </wcf:GetStatus>
    </soap:Body>
</soap:Envelope>
"""
        return template_GetStatus_xml

    def _template_GetStatusExistTest_xml(self):
        template_GetStatus_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatus</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:GetStatus>
            <wcf:trackId>%(trackId)s</wcf:trackId>
        </wcf:GetStatus>
    </soap:Body>
</soap:Envelope>
"""
        return template_GetStatus_xml


    def _template_SendBillSyncTestsend_xml(self):
        template_SendBillSyncTestsend_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/SendTestSetAsync</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:SendTestSetAsync>
            <wcf:fileName>%(fileName)s</wcf:fileName>
            <wcf:contentFile>%(contentFile)s</wcf:contentFile>
            <wcf:testSetId>%(testSetId)s</wcf:testSetId>
        </wcf:SendTestSetAsync>
    </soap:Body>
</soap:Envelope>
"""
        return template_SendBillSyncTestsend_xml

    @api.model
    def _generate_SendBillSyncTest_send_xml(
        self,
        template_send_data_xml,
        fileName,
        contentFile,
        Created,
        testSetId,
        identifier,
        Expires,
        Certificate,
        identifierSecurityToken,
        identifierTo,
    ):
        data_send_xml = template_send_data_xml % {
            "fileName": fileName,
            "contentFile": contentFile,
            "testSetId": testSetId,
            "identifier": identifier,
            "Created": Created,
            "Expires": Expires,
            "Certificate": Certificate,
            "identifierSecurityToken": identifierSecurityToken,
            "identifierTo": identifierTo,
        }
        return data_send_xml


    def _template_SendBillSyncsend_xml(self):
        template_SendBillSyncsend_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/SendBillSync</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:SendBillSync>
            <wcf:fileName>%(fileName)s</wcf:fileName>
            <wcf:contentFile>%(contentFile)s</wcf:contentFile>
        </wcf:SendBillSync>
    </soap:Body>
</soap:Envelope>
"""
        return template_SendBillSyncsend_xml

        # <wcf:testSetId>%(testSetId)s</wcf:testSetId>

    @api.model
    def _generate_SendBillSync_send_xml(
        self,
        template_send_data_xml,
        fileName,
        contentFile,
        Created,
        testSetId,
        identifier,
        Expires,
        Certificate,
        identifierSecurityToken,
        identifierTo,
    ):
        data_send_xml = template_send_data_xml % {
            "fileName": fileName,
            "contentFile": contentFile,
            "testSetId": testSetId,
            "identifier": identifier,
            "Created": Created,
            "Expires": Expires,
            "Certificate": Certificate,
            "identifierSecurityToken": identifierSecurityToken,
            "identifierTo": identifierTo,
        }
        return data_send_xml

    def _get_datetime(self):
        fmt = "%Y-%m-%d %H:%M:%S"
        date_time_envio = datetime.now(timezone("UTC"))
        date_time_envio = date_time_envio + timedelta(hours=-5)
        date_time_envio = date_time_envio.strftime(fmt)
        return date_time_envio

    def _cron_validate_accept_email_invoice_dian(self):
        date_current = self._get_datetime()
        date_current = datetime.strptime(date_current, "%Y-%m-%d %H:%M:%S")
        rec_dian_documents = (
            self.env["dian.document"]
            .sudo()
            .search([("state", "=", "exitoso"), ("email_response", "=", "pending")])
        )
        for rec_dian_document in rec_dian_documents:
            if rec_dian_document.date_email_send:
                time_difference = date_current - rec_dian_document.date_email_send
                if time_difference.days > 3:
                    rec_dian_document.date_email_acknowledgment = fields.Datetime.now()
                    rec_dian_document.email_response = "accepted"

    def _get_rate_date(self, company_id, currency_id, date_invoice):
        Calculationrate = 0.00
        sql = """
        select max(name) as date
          from res_currency_rate
         where company_id = {}
           and currency_id = {}
           and name <= '{}'
         """.format(
            company_id,
            currency_id,
            date_invoice,
        )

        self.sudo().env.cr.execute(sql)
        resultado = self.sudo().env.cr.dictfetchall()
        if resultado[0]["date"] is not None:
            sql = """
            select rate as rate
              from res_currency_rate
             where company_id = {}
               and currency_id = {}
               and name = '{}'
             """.format(
                company_id,
                currency_id,
                resultado[0]["date"],
            )

            self.sudo().env.cr.execute(sql)
            resultado = self.sudo().env.cr.dictfetchall()
            rate = resultado[0]["rate"]
            Calculationrate = 1.00 / rate
        else:
            raise UserError(
                _(
                    "La divisa utilizada en la factura no tiene tasa de cambio registrada"
                )
            )
        return Calculationrate
