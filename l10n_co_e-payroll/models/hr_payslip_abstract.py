import io
import logging
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from collections import defaultdict
from odoo import _, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.fields import first
from pytz import timezone
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, pkcs12
from cryptography.x509 import oid
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
from odoo import _, tools
from odoo.exceptions import UserError, ValidationError
from cryptography.hazmat.primitives import serialization, hashes
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
import base64
import hashlib
from lxml import etree
import base64
from lxml import etree
from io import BytesIO
_logger = logging.getLogger(__name__)

try:
    from lxml import etree
except ImportError:
    _logger.warning(
        "Cannot import  etree *************************************")

try:
    import pyqrcode
except ImportError:
    _logger.warning(
        "Cannot import pyqrcode library ***************************")

try:
    import png
except ImportError:
    _logger.warning(
        "Cannot import png library ********************************")

try:
    import hashlib
except ImportError:
    _logger.warning(
        "Cannot import hashlib library ****************************")

try:
    import base64
except ImportError:
    _logger.warning(
        "Cannot import base64 library *****************************")

try:
    import textwrap
except ImportError:
    _logger.warning(
        "no se ha cargado textwrap ********************************")

try:
    import gzip
except ImportError:
    _logger.warning("no se ha cargado gzip ***********************")

try:
    import zlib

    compression = zipfile.ZIP_DEFLATED
except ImportError:
    compression = zipfile.ZIP_STORED

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    import OpenSSL
    from OpenSSL import crypto

    type_ = crypto.FILETYPE_PEM
except ImportError:
    _logger.warning("Cannot import OpenSSL library")

try:
    import requests
except ImportError:
    _logger.warning("no se ha cargado requests")

try:
    import xmltodict
except ImportError:
    _logger.warning("Cannot import xmltodict library")

try:
    import uuid
except ImportError:
    _logger.warning("Cannot import uuid library")

try:
    import re
except ImportError:
    _logger.warning("Cannot import re library")

tipo_ambiente = {
    "PRODUCCION": "1",
    "PRUEBA": "2",
}
XML_STRUCTURE = {
        'devengados': [
            'Basico', 'Transporte', 'HEDs', 'HENs', 'HRNs', 'HEDDFs', 'HRDDFs',
            'HENDFs', 'HRNDFs', 'Vacaciones', 'Primas', 'Cesantias', 'Incapacidades',
            'Licencias', 'Bonificaciones', 'Auxilios', 'HuelgasLegales',
            'OtrosConceptos', 'Compensaciones', 'BonoEPCTVs', 'Comisiones',
            'PagosTerceros', 'Anticipos', 'Dotacion', 'ApoyoSost', 'Teletrabajo',
            'BonifRetiro', 'Indemnizacion', 'Reintegro'
        ],
        'deducciones': [
            'Salud', 'FondoPension', 'FondoSP', 'Sindicatos', 'Sanciones',
            'Libranzas', 'PagosTerceros', 'Anticipos', 'OtrasDeducciones',
            'PensionVoluntaria', 'RetencionFuente', 'AFC', 'Cooperativa',
            'EmbargoFiscal', 'PlanComplementarios', 'Educacion', 'Reintegro', 'Deuda'
        ]
    }
server_url = {
    "TEST": "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc?wsdl",
    "PRODUCCION": "https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl",
}

XML_TEMPLATE_NOMINA_INDIVIDUAL = "l10n_co_e-payroll.nomina_electronica_individual"
XML_TEMPLATE_SIGNATURE = "l10n_co_e-payroll.nomina_electronica_signature"


class HrPaySlipAbstrct(models.AbstractModel):
    _name = "hr.payslip.abstract"
    _description = "Model Abstract for hr payslip"

    payroll_period = fields.Many2one(
        "hr.payroll.period", string="Periodo de Nomina")
    xml_response_dian = fields.Text(
        string="Contenido XML de la respuesta DIAN", readonly=True, copy=False
    )
    xml_send_query_dian = fields.Text(
        string="Contenido XML de envío de consulta de documento DIAN",
        readonly=True,
        copy=False,
    )
    name_xml = fields.Char("Name XML")
    name_zip = fields.Char("Name ZIP")
    response_message_dian = fields.Text(
        string="Respuesta DIAN", readonly=True, copy=False
    )
    ZipKey = fields.Char(
        string="Identificador del docuemnto enviado", readonly=True, copy=False
    )
    state_dian = fields.Selection(
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
        copy=False,
    )
    resend = fields.Boolean(string="Autorizar reenvio?",
                            default=False, copy=False)
    previous_cune = fields.Char(string="Previous CUNE", copy=False)
    current_cune = fields.Char(string="CUNE", readonly=1, copy=False)
    type_note = fields.Selection(
        [("1", "Reemplazar"), ("2", "Eliminar")], string="Tipo de Nota", copy=False
    )
    contract_id = fields.Many2one(
        "hr.contract",
        required=True,
        string="Contract",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    payment_date = fields.Date(
        string="Fecha de Pago", default=fields.Date.today())
    xml_sended = fields.Char(string="XML ENVIADO", copy=False)

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
        data_xml_SigningTime = self._generate_signature_signingtime()
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
        if data_constants_document.get("InvoiceTypeCode", False) == "102":  # Factura
            xmlns = (
                'xmlns="dian:gov:co:facturaelectronica:NominaIndividual" '
                'xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            )
            KeyInfo = KeyInfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )

        if data_constants_document.get("InvoiceTypeCode", False) == "103":  # Factura
            xmlns = (
                'xmlns="dian:gov:co:facturaelectronica:NominaIndividualDeAjuste" '
                'xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
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
        if data_constants_document["InvoiceTypeCode"] in ("102"):
            xmlns = (
                'xmlns="dian:gov:co:facturaelectronica:NominaIndividual" '
                'xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            )
            SignedProperties = SignedProperties.replace(
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"',
                "%s" % xmlns,
            )

        if data_constants_document.get("InvoiceTypeCode", False) == "103":  # Factura
            xmlns = (
                'xmlns="dian:gov:co:facturaelectronica:NominaIndividualDeAjuste" '
                'xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            )
            SignedProperties = SignedProperties.replace(
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"',
                "%s" % xmlns,
            )

        data_xml_SignedProperties_base = self._generate_signature_ref2(
            SignedProperties)
        data_xml_signature = data_xml_signature.replace(
            "<ds:DigestValue/>",
            "<ds:DigestValue>%s</ds:DigestValue>" % data_xml_SignedProperties_base,
            1,
        )
        #    Actualiza Signeinfo
        Signedinfo = etree.fromstring(data_xml_signature)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = Signedinfo.decode()
        if data_constants_document["InvoiceTypeCode"] in ("102"):
            xmlns = (
                'xmlns="dian:gov:co:facturaelectronica:NominaIndividual" '
                'xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            )
            Signedinfo = Signedinfo.replace(
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', "%s" % xmlns
            )

        if data_constants_document.get("InvoiceTypeCode", False) == "103":  # Factura
            xmlns = (
                'xmlns="dian:gov:co:facturaelectronica:NominaIndividualDeAjuste" '
                'xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
                'xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" '
                'xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
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

    def request_validating_dian(self):
        dian_constants = self._get_dian_constants()
        if os.path.isfile(dian_constants["document_repository"] + "/" + self.name_xml):
            os.remove(
                dian_constants["document_repository"] + "/" + self.name_xml)
        if os.path.isfile(
            "{}/{}".format(dian_constants["document_repository"],
                           self.name_zip)
        ):
            os.remove(
                dian_constants["document_repository"] + "/" + self.name_zip)
        trackId = self.ZipKey
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
            'xmlns:wcf="http://wcf.dian.colombia" '
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
            server_url["PRODUCCION"]
            if self.company_id.production_payroll
            else server_url["TEST"]
        )
        try:
            response = requests.post(
                URL_WEBService_DIAN, data=data_xml_send, headers=headers
            )
        except Exception:
            raise ValidationError(
                _(
                    "No existe comunicación con la DIAN para el servicio de recepción de Facturas Electrónicas."
                    " Por favor, revise su red o el acceso a internet."
                )
            )
        #   Respuesta de petición
        if response.status_code != 200:  # Respuesta de envío no exitosa
            if response.status_code == 500:
                raise ValidationError(
                    _("Error 500 = Error de servidor interno."))
            elif response.status_code == 503:
                raise ValidationError(_("Error 503 = Servicio no disponible."))
            elif response.status_code == 507:
                raise ValidationError(_("Error 507 = Espacio insuficiente."))
            elif response.status_code == 508:
                raise ValidationError(_("Error 508 = Ciclo detectado."))
            else:
                raise ValidationError(
                    _("Se ha producido un error de comunicación con la DIAN.")
                )
        response_dict = xmltodict.parse(response.content)
        if (
            response_dict["s:Envelope"]["s:Body"]["GetStatusZipResponse"][
                "GetStatusZipResult"
            ]["b:DianResponse"]["b:StatusCode"]
            == "00"
        ):
            self.response_message_dian += (
                "- Respuesta consulta estado del documento: Procesado correctamente \n"
            )
            self.write({"state_dian": "exitoso", "resend": False, 'state': 'done'})
            # self.send_email_from_template(str(self.xml_sended))
        else:
            if (
                response_dict["s:Envelope"]["s:Body"]["GetStatusZipResponse"][
                    "GetStatusZipResult"
                ]["b:DianResponse"]["b:StatusCode"]
                == "90"
            ):
                self.response_message_dian += (
                    "- Respuesta consulta estado del documento: TrackId no encontrado"
                )
                self.write({"state_dian": "por_validar", "resend": False})
            elif (
                response_dict["s:Envelope"]["s:Body"]["GetStatusZipResponse"][
                    "GetStatusZipResult"
                ]["b:DianResponse"]["b:StatusCode"]
                == "99"
            ):
                self.response_message_dian += (
                    "- Respuesta consulta estado del documento: "
                    "Validaciones contiene errores en campos mandatorios"
                )
                self.write({"state_dian": "rechazado", "resend": True})
            elif (
                response_dict["s:Envelope"]["s:Body"]["GetStatusZipResponse"][
                    "GetStatusZipResult"
                ]["b:DianResponse"]["b:StatusCode"]
                == "66"
            ):
                self.response_message_dian += (
                    "- Respuesta consulta estado del documento: NSU no encontrado"
                )
                self.write({"state_dian": "por_validar", "resend": False})
            self.xml_response_dian = response.content
            self.xml_send_query_dian = data_xml_send
        return True

    def test_xml(self):
        dian_constants = self._get_dian_constants()
        template_basic_data_nomina_individual_xml = self._template_nomina_individual(
            dian_constants
        )
        if self.credit_note:
            template_basic_data_nomina_individual_xml = self._template_nomina_individual_ajuste(
                dian_constants
            )

        raise UserError(template_basic_data_nomina_individual_xml)

    def get_name_pdf(self):
        name = """nomina_electronica_{}""".format(self._get_employee().name)
        if self.credit_note:
            name = """nomina_electronica_ajuste_{}""".format(
                self._get_employee().name)
        return name

    def send_pending_dian(self):
        dic_result_verify_status = self.exist_dian(self.ZipKey)
        if not dic_result_verify_status["result_verify_status"]:
            dian_constants = self._get_dian_constants()
            data_constants_document = self._generate_data_constants_document(
                dian_constants
            )
            template_basic_data_nomina_individual_xml = self._template_nomina_individual(
                dian_constants
            )
            if self.credit_note:
                template_basic_data_nomina_individual_xml = self._template_nomina_individual_ajuste(
                    dian_constants
                )

            parser = etree.XMLParser(remove_blank_text=True)
            template_basic_data_nomina_individual_xml = (
                '<?xml version="1.0"?>' + template_basic_data_nomina_individual_xml
            )
            template_basic_data_nomina_individual_xml = etree.tostring(
                etree.XML(template_basic_data_nomina_individual_xml,
                          parser=parser)
            )
            template_basic_data_nomina_individual_xml = (
                template_basic_data_nomina_individual_xml.decode()
            )
            data_xml_document = template_basic_data_nomina_individual_xml

            data_xml_document = data_xml_document.replace(
                "<ext:ExtensionContent/>",
                "<ext:ExtensionContent></ext:ExtensionContent>",
            )

            template_signature_data_xml = self._template_signature_data_xml()
            data_xml_signature = self._generate_signature(
                data_xml_document,
                template_signature_data_xml,
                dian_constants,
                data_constants_document,
            )
            data_xml_signature = etree.tostring(
                etree.XML(data_xml_signature, parser=parser)
            )
            data_xml_signature = data_xml_signature.decode()

            data_xml_document = data_xml_document.replace(
                "<ext:ExtensionContent></ext:ExtensionContent>",
                "<ext:ExtensionContent>%s</ext:ExtensionContent>" % data_xml_signature,
            )
            data_xml_document = (
                '<?xml version="1.0" encoding="UTF-8"?>' + data_xml_document
            )

            Document = self._generate_zip_content(
                data_constants_document["FileNameXML"],
                data_constants_document["FileNameZIP"],
                data_xml_document,
                dian_constants["document_repository"],
            )
            fileName = data_constants_document["FileNameZIP"][:-4]
            # Fecha y hora de la petición y expiración del envío del documento
            timestamp = self._generate_datetime_timestamp()
            Created = timestamp["Created"]
            Expires = timestamp["Expires"]
            # Id de pruebas
            testSetId = self.company_id.identificador_set_pruebas_payroll
            identifierSecurityToken = uuid.uuid4()
            identifierTo = uuid.uuid4()

            if self.company_id.production_payroll:
                template_SendBillSyncsend_xml = self._template_SendBillSyncsend_xml()
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

            parser = etree.XMLParser(remove_blank_text=True)
            data_xml_send = etree.tostring(
                etree.XML(data_xml_send, parser=parser))
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
                'xmlns:wsa="http://www.w3.org/2005/08/addressing" xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
                'xmlns:wcf="http://wcf.dian.colombia">',
                '<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
                'xmlns:soap="http://www.w3.org/2003/05/soap-envelope"'
                ' xmlns:wcf="http://wcf.dian.colombia" '
                'xmlns:wsa="http://www.w3.org/2005/08/addressing">',
            )
            SignatureValue = self._generate_SignatureValue_GetStatus(
                Signedinfo)
            data_xml_send = data_xml_send.replace(
                "<ds:SignatureValue/>",
                "<ds:SignatureValue>%s</ds:SignatureValue>" % SignatureValue,
            )

            URL_WEBService_DIAN = (
                server_url["PRODUCCION"]
                if self.company_id.production_payroll
                else server_url["TEST"]
            )

            try:
                headers = {"content-type": "application/soap+xml"}
                response = requests.post(
                    URL_WEBService_DIAN, data=data_xml_send, headers=headers
                )

            except Exception:
                raise ValidationError(
                    _(
                        "No existe comunicación con la DIAN para el servicio de recepción de Facturas Electrónicas. "
                        "Por favor, revise su red o el acceso a internet."
                    )
                )

            if response.status_code != 200:  # Respuesta de envío no exitosa
                pass
                # TODO: Revisar
            else:
                # Procesa respuesta DIAN
                response_dict = xmltodict.parse(response.content)
                dict_mensaje = {}
                if self.company_id.production_payroll:
                    dict_result_verify_status = self.exist_dian(self.ZipKey)
                    if dict_result_verify_status["result_verify_status"]:
                        return
                    self.response_message_dian = " "
                    if (
                        response_dict["s:Envelope"]["s:Body"]["SendNominaSyncResponse"][
                            "SendNominaSyncResult"
                        ]["b:StatusCode"]
                        == "00"
                    ):
                        self.response_message_dian = (
                            response_dict["s:Envelope"]["s:Body"][
                                "SendNominaSyncResponse"
                            ]["SendNominaSyncResult"]["b:StatusCode"]
                            + " "
                        )
                        self.response_message_dian += (
                            response_dict["s:Envelope"]["s:Body"][
                                "SendNominaSyncResponse"
                            ]["SendNominaSyncResult"]["b:StatusDescription"]
                            + "\n"
                        )
                        self.response_message_dian += response_dict["s:Envelope"][
                            "s:Body"
                        ]["SendNominaSyncResponse"]["SendNominaSyncResult"][
                            "b:StatusMessage"
                        ]
                        if (
                            "ha sido autorizada"
                            in response_dict["s:Envelope"]["s:Body"][
                                "SendNominaSyncResponse"
                            ]["SendNominaSyncResult"]["b:StatusMessage"]
                        ):
                            self.response_message_dian = response_dict["s:Envelope"][
                                "s:Body"
                            ]["SendNominaSyncResponse"]["SendNominaSyncResult"][
                                "b:StatusMessage"
                            ]
                        self.ZipKey = response_dict["s:Envelope"]["s:Body"][
                            "SendNominaSyncResponse"
                        ]["SendNominaSyncResult"]["b:XmlDocumentKey"]
                        self.xml_response_dian = response.content
                        self.xml_send_query_dian = data_xml_send
                        # ENVIA EL CORREO
                        self.write({"state_dian": "exitoso", "resend": False,'state': 'done'})
                        #self.send_email_from_template(str(data_xml_send))
                    else:
                        self.response_message_dian = (
                            response_dict["s:Envelope"]["s:Body"][
                                "SendNominaSyncResponse"
                            ]["SendNominaSyncResult"]["b:StatusCode"]
                            + " "
                        )
                        self.response_message_dian += (
                            response_dict["s:Envelope"]["s:Body"][
                                "SendNominaSyncResponse"
                            ]["SendNominaSyncResult"]["b:StatusDescription"]
                            + "\n"
                        )
                        self.response_message_dian += response_dict["s:Envelope"][
                            "s:Body"
                        ]["SendNominaSyncResponse"]["SendNominaSyncResult"][
                            "b:StatusMessage"
                        ]
                        self.ZipKey = response_dict["s:Envelope"]["s:Body"][
                            "SendNominaSyncResponse"
                        ]["SendNominaSyncResult"]["b:XmlDocumentKey"]
                        self.xml_response_dian = response.content
                        self.xml_send_query_dian = data_xml_send
                        self.write({"state_dian": "rechazado", "resend": True})
                else:  # Ambiente de pruebas
                    dict_mensaje = response_dict["s:Envelope"]["s:Body"][
                        "SendTestSetAsyncResponse"
                    ]["SendTestSetAsyncResult"]["b:ErrorMessageList"]

                    if "@i:nil" in dict_mensaje:
                        if (
                            response_dict["s:Envelope"]["s:Body"][
                                "SendTestSetAsyncResponse"
                            ]["SendTestSetAsyncResult"]["b:ErrorMessageList"]["@i:nil"]
                            == "true"
                        ):
                            self.response_message_dian = "- Respuesta envío: Documento enviado con éxito. Falta validar su estado \n"
                            self.ZipKey = response_dict["s:Envelope"]["s:Body"][
                                "SendTestSetAsyncResponse"
                            ]["SendTestSetAsyncResult"]["b:ZipKey"]

                            self.state_dian = "por_validar"
                            self.xml_sended = data_xml_document
                        else:
                            self.response_message_dian = "- Respuesta envío: Documento enviado con éxito, pero la DIAN detectó errores \n"
                            self.ZipKey = response_dict["s:Envelope"]["s:Body"][
                                "SendTestSetAsyncResponse"
                            ]["SendTestSetAsyncResult"]["b:ZipKey"]

                            self.state_dian = "por_notificar"
                    elif "i:nil" in dict_mensaje:
                        if (
                            response_dict["s:Envelope"]["s:Body"][
                                "SendTestSetAsyncResponse"
                            ]["SendTestSetAsyncResult"]["b:ErrorMessageList"]["i:nil"]
                            == "true"
                        ):
                            self.response_message_dian = "- Respuesta envío: Documento enviado con éxito. Falta validar su estado \n"
                            self.ZipKey = response_dict["s:Envelope"]["s:Body"][
                                "SendTestSetAsyncResponse"
                            ]["SendTestSetAsyncResult"]["b:ZipKey"]
                            self.state_dian = "por_validar"

                        else:
                            self.response_message_dian = "- Respuesta envío: Documento enviado con éxito, pero la DIAN detectó errores \n"
                            self.ZipKey = response_dict["s:Envelope"]["s:Body"][
                                "SendTestSetAsyncResponse"
                            ]["SendTestSetAsyncResult"]["b:ZipKey"]
                            self.state_dian = "por_notificar"
                    else:
                        raise ValidationError(
                            _("Mensaje de respuesta cambió en su estructura xml")
                        )

    def validate(self):
        if self.state_dian in ("rechazado", "por_notificar"):
            self.send_pending_dian()

        if self.state_dian == "por_validar":
            self.request_validating_dian()

    def get_pem(self):
        company = self.env.company
        try:
            archivo_pem = base64.b64decode(company.pem_file_payroll)
            return x509.load_pem_x509_certificate(archivo_pem)
        except Exception as ex:
            raise UserError(tools.ustr(ex))
    def _generate_SignatureValue_GetStatus(self, data_xml_SignedInfo_generate):
        data_xml_SignatureValue_c14n = etree.tostring(
            etree.fromstring(data_xml_SignedInfo_generate), method="c14n"
        )

        key = self.get_key()
        
        try:
            signature = key.sign(
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(), 
                hashes.SHA256() 
            )
        except Exception as ex:
            raise UserError(tools.ustr(ex))
        SignatureValue = base64.b64encode(signature).decode()
        pem = self.get_pem()
        try:
            pem.public_key().verify(
                signature,
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except InvalidSignature:
            raise ValidationError(
                _("Firma para el GestStatus no fue validada exitosamente")
            )
        return SignatureValue

    def zip(self, src, dst):
        zf = zipfile.ZipFile("%s.zip" % (dst), "w", zipfile.ZIP_DEFLATED)
        abs_src = os.path.abspath(src)
        for dirname, subdirs, files in os.walk(src):
            for filename in files:
                if subdirs:
                    _logger.info("subdirs {}".format(subdirs))
                absname = os.path.abspath(os.path.join(dirname, filename))
                arcname = absname[len(abs_src) + 1:]
                zf.write(absname, arcname)
        zf.close()

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
            zf.write(xml_file, FileNameXML, compress_type=compression)
        finally:
            zf.close()
        # Obtiene datos comprimidos
        data_xml = zip_file
        data_xml = open(data_xml, "rb")
        data_xml = data_xml.read()
        contenido_data_xml_b64 = base64.b64encode(data_xml)
        contenido_data_xml_b64 = contenido_data_xml_b64.decode()
        return contenido_data_xml_b64

    def _generate_xml_filename(self):
        # TODO: Generar valor correcto
        # pagina 96 nie para : Documento Soporte de Pago de Nómina Electrónica hay otro para el ajuste
        if not self.name_xml:
            sequece = (
                self.env["ir.sequence"].next_by_code(
                    "hr.payslip.sequence_documents_xml"
                )
                or "00000001"
            )
            dian_code_int = int(sequece)
            dian_code_hex = self.IntToHex(dian_code_int)
            dian_code_hex.zfill(10)
            if self._get_tipo_xml() == "102":
                name = "nie{}{}{}.xml".format(
                    self._get_emisor().vat_co,
                    self.date_to.strftime("%y"),
                    dian_code_hex.zfill(10),
                )
            else:
                name = "niae{}{}{}.xml".format(
                    self._get_emisor().vat_co,
                    self.date_to.strftime("%y"),
                    dian_code_hex.zfill(10),
                )
            self.name_xml = name
        return self.name_xml

    def IntToHex(self, dian_code_int):
        dian_code_hex = "%02x" % dian_code_int
        return dian_code_hex

    def add_attachment(self, xml_element, name):
        buf = io.StringIO()
        buf.write(xml_element)
        document = base64.b64encode(buf.getvalue().encode())
        buf.close()
        ctx = self.env.context.copy()
        ctx.pop("default_type", False)
        values = {
            "name": "{}.xml".format(name),
            "store_fname": "{}.xml".format(name),
            "datas": document,
            "res_model": self._name,
            "res_id": self.id,
            "type": "binary",
        }
        attach = self.env["ir.attachment"].with_context(ctx).create(values)
        return attach

    def hook_mail_template(self):
        return ""

    def _get_name_xml_for_email(self):
        name = """Nomina_Electronica_Empleado_{}""".format(
            self._get_employee().name)
        if self.credit_note:
            name = """Nomina_Ajuste_Empleado_{}""".format(
                self._get_employee().name)
        return name

    def send_email_from_template(self, xml_element):
        # We warn ~ once by hour ~ instead of every 10 min if the interval unit is more than 'hours'.
        mail = self.hook_mail_template()
        for payslip in self:
            tmpl = self.env.ref(mail, False)
            ctx = payslip.env.context.copy()
            attachments = payslip.add_attachment(
                xml_element, self._get_name_xml_for_email()
            )
            email_values = {"attachment_ids": [(4, int(attachments.id)), ]}
            tmpl.with_context(ctx).send_mail(  # noqa
                payslip.id, force_send=True, email_values=email_values
            )
        return {
            "name": "Correo",
            "type": "ir.actions.act_window",
            "res_model": "message.wizard",
            "view_mode": "form",
            "view_type": "form",
            "target": "new",
            "context": {"default_message": "Correo Enviado exitosamente"},
        }

    def _generate_zip_filename(self):
        # TODO: Generar valor correcto
        sequece = (
            self.env["ir.sequence"].next_by_code(
                "hr.payslip.sequence_documents_zip")
            or "00000001"
        )
        dian_code_int = int(sequece)
        dian_code_hex = self.IntToHex(dian_code_int)
        name = "z{}{}{}.zip".format(
            self._get_emisor().vat_co, self.date_to.strftime("%y"), dian_code_hex.zfill(10)
        )
        file_name_zip = name
        return file_name_zip

    def _generate_software_security_code(
        self, software_identification_code, software_pin, NroDocumento
    ):
        software_security_code = hashlib.sha384(
            (software_identification_code + software_pin + NroDocumento).encode()
        )
        software_security_code = software_security_code.hexdigest()
        return software_security_code

    def _generate_CertDigestDigestValue(self):
        key = self.get_key()
        certificate = hashlib.sha256(
            crypto.dump_certificate(
                crypto.FILETYPE_ASN1, key.get_certificate())
        )
        CertDigestDigestValue = base64.b64encode(certificate.digest())
        CertDigestDigestValue = CertDigestDigestValue.decode()
        return CertDigestDigestValue

    def _generate_digestvalue_to(self, elementTo):
        # Generar el digestvalue de to
        elementTo = etree.tostring(etree.fromstring(elementTo), method="c14n")
        elementTo_sha256 = hashlib.new("sha256", elementTo)
        elementTo_digest = elementTo_sha256.digest()
        elementTo_base = base64.b64encode(elementTo_digest)
        elementTo_base = elementTo_base.decode()
        return elementTo_base

    def _get_sequence(self):
        for rec in self:
            if not rec.credit_note:
                sequence = self.env["ir.sequence"].sudo().search(
                    [("code", "=", "bach.epayslip")])
            else:
                sequence = self.env["ir.sequence"].sudo().search(
                    [("code", "=", "bachepayslipnote")])
        return sequence

    def _get_number(self):
        if not self.number:
            raise UserError(_("Se debe de configurar la referencia"))
        return self.number

    def _get_consecutivo(self):
        sequence = self._get_sequence()
        return self.number.replace(sequence.prefix, "") if self.number else ""

    def _get_generation_date(self):
        now_utc = datetime.now(timezone("UTC"))
        now_bogota = now_utc
        issue_date = now_bogota.strftime("%Y-%m-%d")
        return issue_date

    def _get_time_colombia(self):
        fmt = "%H:%M:%S-05:00"
        now_utc = datetime.now(timezone("UTC"))
        now_time = now_utc.strftime(fmt)
        return now_time

    def _get_emisor(self):
        if not self.company_id.partner_id.vat_co:
            raise UserError(_("El NIT del emisor del documento es requerido"))
        if (
            not self.company_id.partner_id.dv
            and type(self.company_id.partner_id.dv) == "boolean"
        ):
            raise UserError(
                _("Falta configurar el DV en el empleado - RES.PARTNER.DV"))
        return self.company_id.partner_id

    def _get_employee_object(self):
        if not self.employee_id:
            raise UserError(_("Por favor defina el empleado"))
        if not self.employee_id.tipo_coti_id:
            raise UserError(
                _("Por Favor defina el tipo de trabajador del empleado"))
        if not self.employee_id.subtipo_coti_id:
            raise UserError(
                _("Por favor defina el sub tipo de trabajador del empleado")
            )
        # if not self.employee_id.work_contact_id.bank_ids:
        #     raise UserError(
        #         _("Por favor defina el tipo de la cuenta bancaria del empleado")
        #     )
        return self.employee_id

    def _get_employee(self):
        if not self.employee_id.work_contact_id:
            raise UserError(_("Por favor defina el tercero del empleado"))
        if not self.employee_id.work_contact_id.vat_co:
            raise UserError(
                _("El numero de identificacion del empleado es requerido"))
        if not self.employee_id.work_contact_id.state_id:
            raise UserError(
                _("Se debe registrar la provincia o estado del empleado"))
        if not self.employee_id.work_contact_id.city_id:
            raise UserError(_(f"Se debe registrar la ciudad del empleado {self.employee_id.name}"))
        if not self.employee_id.work_contact_id.country_id.code:
            raise UserError(
                _("Se debe registrar el codigo del pais del empleado"))
        return self.employee_id.work_contact_id

    def _get_contract(self):
        if not self.contract_id:
            raise UserError(_("Por favor define al contrato del empleado"))
        if not self.contract_id.way_pay_id:
            raise UserError(_("Por favor definir la forma de pago"))
        if not self.contract_id.payment_method_id:
            raise UserError(_("Por favor definir el metodo de pago"))
        return self.contract_id

    def _get_total_devengados(self):
        total_devengado = sum(
            line.total for line in self.line_ids if line.salary_rule_id.devengado_rule_id)
        if not total_devengado:
            raise UserError(
                _("Se debe de tener configurado el devengado total en la nomina"))
        return "{:.2f}".format(abs(total_devengado))

    def _get_total_deducciones(self):
        deducciones_total = sum(
            line.total for line in self.line_ids if line.salary_rule_id.deduccion_rule_id) or 0.0
        return "{:.2f}".format(abs(deducciones_total))

    def _get_total_pagado(self):
        total_devengado = sum(
            line.total for line in self.line_ids if line.salary_rule_id.devengado_rule_id)
        deducciones_total = sum(
            line.total for line in self.line_ids if line.salary_rule_id.deduccion_rule_id) or 0.0
        return "{:.2f}".format(abs(deducciones_total + total_devengado))

    def _get_tipo_xml(self):
        return "103" if self.credit_note else "102"

    def _get_tipo_ambiente(self):
        return "1" if self.company_id.production_payroll else "2"

    def _get_cune(self, dian_constants):
        res = f"""{self._get_number() + dian_constants.get('FechaGen') + dian_constants.get('HoraGen') + self._get_total_devengados() +
                   self._get_total_deducciones() + self._get_total_pagado() + self._get_emisor().vat_co + self._get_employee().vat_co +
                   self._get_tipo_xml() + self.company_id.software_pin_payroll + self._get_tipo_ambiente()}"""
        cune = hashlib.sha384((res).encode())
        cune = cune.hexdigest()
        return cune

    def _get_dian_constants(self):
        company = self.env.company
        sequence = self._get_sequence()
        consecutivo = self._get_consecutivo()
        number = self._get_number()

        dian_constants = {}
        dian_constants["document_repository"] = company.document_repository_payroll
        dian_constants["Username"] = company.software_identification_code_payroll
        dian_constants["Password"] = hashlib.new(
            "sha256", company.password_environment_payroll.encode()
        ).hexdigest()
        dian_constants["SoftwareID"] = company.software_identification_code_payroll
        dian_constants["SoftwareSecurityCode"] = self._generate_software_security_code(
            company.software_identification_code_payroll,
            company.software_pin_payroll,
            number,
        )
        dian_constants["Number"] = number
        dian_constants["Prefix"] = sequence.prefix
        dian_constants["Consecutivo"] = consecutivo
        dian_constants["PINSoftware"] = company.software_pin_payroll
        dian_constants["SeedCode"] = company.seed_code_payroll

        dian_constants["ProfileExecutionID"] = (
            tipo_ambiente["PRODUCCION"]
            if company.production_payroll
            else tipo_ambiente["PRUEBA"]
        )
        dian_constants["CertificateKey"] = company.certificate_key_payroll
        dian_constants["archivo_certificado"] = company.certificate_file_payroll
        dian_constants["CertDigestDigestValue"] = self._generate_CertDigestDigestValue()
        dian_constants["IssuerName"] = self._get_emisor().name
        dian_constants["SerialNumber"] = company.serial_number_payroll
        dian_constants["Certificate"] = company.digital_certificate_payroll
        dian_constants["CertificateKey"] = company.certificate_key_payroll

        dian_constants["HoraGen"] = self._get_time_colombia()
        dian_constants["FechaGen"] = self._get_generation_date()

        return dian_constants

    def get_key(self):
        company = self.env.company
        password = company.certificate_key_payroll
        try:
            archivo_key = base64.b64decode(company.certificate_file_payroll)
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                archivo_key, 
                password.encode('utf-8')
            )
            return private_key, certificate
        except Exception as ex:
            raise UserError(tools.ustr(ex))

    def _generate_data_constants_document(self, dian_constants):
        data_constants_document = {}

        identifier = uuid.uuid4()
        data_constants_document["identifier"] = identifier
        identifierkeyinfo = uuid.uuid4()
        data_constants_document["identifierkeyinfo"] = identifierkeyinfo
        data_constants_document["InvoiceTypeCode"] = self._get_tipo_xml()
        data_constants_document["FileNameXML"] = self._generate_xml_filename()
        data_constants_document["FileNameZIP"] = self._generate_zip_filename()

        return data_constants_document

    def _generate_data_constant_document(self):
        data_constants_document = {}
        identifier = uuid.uuid4()
        data_constants_document["identifier"] = "xmldsig" + identifier + "ref0"

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

    def _generate_signature_ref0(
        self, data_xml_document, document_repository, password
    ):
        # 1er paso. Generar la referencia 0 que consiste en obtener keyvalue desde todo el xml del
        #           documento electronico aplicando el algoritmo SHA256 y convirtiendolo a base64
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

    def _generate_signature_ref1(
        self, data_xml_keyinfo_generate, document_repository, password
    ):
        # Generar la referencia 1 que consiste en obtener keyvalue desde el keyinfo contenido
        # en el documento electrónico aplicando el algoritmo SHA256 y convirtiendolo a base64
        data_xml_keyinfo_generate = etree.tostring(
            etree.fromstring(data_xml_keyinfo_generate), method="c14n"
        )
        data_xml_keyinfo_sha256 = hashlib.new(
            "sha256", data_xml_keyinfo_generate)
        data_xml_keyinfo_digest = data_xml_keyinfo_sha256.digest()
        data_xml_keyinfo_base = base64.b64encode(data_xml_keyinfo_digest)
        data_xml_keyinfo_base = data_xml_keyinfo_base.decode()
        return data_xml_keyinfo_base

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

    def _generate_SignatureValue(self, data_xml_SignedInfo_generate):
        data_xml_SignatureValue_c14n = etree.tostring(
            etree.fromstring(data_xml_SignedInfo_generate),
            method="c14n",
            exclusive=False,
            with_comments=False,
        )
        key = self.get_key()
        try:
            signature = crypto.sign(
                key.get_privatekey(), data_xml_SignatureValue_c14n, "sha256"
            )
        except Exception as ex:
            raise UserError(tools.ustr(ex))
        SignatureValue = base64.b64encode(signature)
        SignatureValue = SignatureValue.decode()
        pem = self.get_pem()
        try:
            crypto.verify(pem, signature,
                          data_xml_SignatureValue_c14n, "sha256")
        except Exception:
            raise ValidationError(_("Firma no fué validada exitosamente"))
        # serial = key.get_certificate().get_serial_number()
        return SignatureValue

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

    # @api.multi
    def _generate_signature_politics(self, document_repository):
        data_xml_politics = "dMoMvtcG5aIzgYo0tIsSQeVJBDnUnfSOfBpxXrmor0Y="
        return data_xml_politics

    def _generate_signature_signingtime(self):
        fmt = "%Y-%m-%dT%H:%M:%S"
        now_utc = datetime.now(timezone("UTC"))
        now_bogota = now_utc
        data_xml_SigningTime = now_bogota.strftime(fmt) + "-05:00"
        return data_xml_SigningTime

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

    def _get_company_id(self):
        if not self.env.company.country_id.code:
            raise UserError(
                _("Se debe configurar el codigo del pais en la compañia"))
        if not self.env.company.partner_id.city_id:
            raise UserError(_("Se debe configurar la ciudad de la compañia"))
        if not self.env.company.partner_id.state_id.code_dian:
            raise UserError(
                _("Se debe configurar el codigo Dian de la provincia de la compañia")
            )
        return self.env.company

    def _get_notes(self):
        if not self.note:
            return "sin notas"
        return self.note

    def return_number_document_type(self, document_type):
        number_document_type = 13

        if document_type:
            if document_type == "31" or document_type == "rut":
                number_document_type = 31
            if document_type == "national_citizen_id":
                number_document_type = 13
            if document_type == "civil_registration":
                number_document_type = 11
            if document_type == "id_card":
                number_document_type = 12
            if document_type == "21":
                number_document_type = 21
            if document_type == "foreign_id_card":
                number_document_type = 22
            if document_type == "passport":
                number_document_type = 41
            if document_type == "43":
                number_document_type = 43
        else:
            raise UserError(_("Debe de ingresar el tipo de documento"))
        return str(number_document_type)

    def _integral(self, contract_type):
        contract = ''
        if contract_type == 'integral':
            contract = 'true'
        else:
            contract = 'false'
        return str(contract)

    def type_contract_e(self, contract_type):
        contract = ''
        if contract_type:
            if contract_type == "fijo" or contract_type == "fijo_parcial" or contract_type == "temporal":
                contract = 1
            if contract_type == "indefinido":
                contract = 2
            if contract_type == "obra":
                contract = 3
            if contract_type == "aprendizaje":
                contract = 4
            if contract_type == "practicas":
                contract = 5
        else:
            raise UserError(_("Debe de ingresar el tipo de Contrato"))
        return str(contract)



    def template_generate_devengados_deducciones(self):
        self.ensure_one()
        
        # Crear nodos principales
        devengados = ET.Element('Devengados')
        deducciones = ET.Element('Deducciones')

        # Procesar secciones
        self._process_basic_info(devengados)
        self._process_extras(devengados)
        self._process_all_concepts(devengados)
        self._process_deducciones(deducciones)

        root_devengado_str = ET.tostring(devengados).decode()
        root_deduccion_str = ET.tostring(deducciones).decode()
        return root_devengado_str + root_deduccion_str
    
    def _get_days_amount(self, lst_codes):
        """Obtiene la cantidad de días para los códigos dados"""
        days = 0
        for entries in self.worked_days_line_ids:
            days += entries.number_of_days if entries.work_entry_type_id.code in lst_codes else 0
        return int(days)

    def _process_basic_info(self, devengados):
        """Procesa información básica: básico y transporte"""
        # Básico
        dias = self._get_days_amount('WORK100')
        ET.SubElement(devengados, 'Basico', 
            DiasTrabajados=str(dias),
            SueldoTrabajado=self._format_value(self._get_line_value('BASIC')))

        # Transporte
        transporte_lines = {
            'auxilio': self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.code == 'TRANS_BASIC'),
            'viatico_s': self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.code == 'TRANS_VIAT_S'),
            'viatico_ns': self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.code == 'TRANS_VIAT_NS')
        }

        # Calcular valores
        valores_transporte = {
            'AuxilioTransporte': sum(transporte_lines['auxilio'].mapped('total')) if transporte_lines['auxilio'] else 0.0,
            'ViaticoManuAlojS': sum(transporte_lines['viatico_s'].mapped('total')) if transporte_lines['viatico_s'] else 0.0,
            'ViaticoManuAlojNS': sum(transporte_lines['viatico_ns'].mapped('total')) if transporte_lines['viatico_ns'] else 0.0
        }
        attrs = {}
        # Crear nodo de transporte
        if valores_transporte['AuxilioTransporte']:
            attrs = {'AuxilioTransporte': self._format_value(valores_transporte['AuxilioTransporte'])}
        
        # Agregar viáticos solo si hay valores
        if valores_transporte['ViaticoManuAlojS'] or valores_transporte['ViaticoManuAlojNS']:
            attrs.update({
                'ViaticoManuAlojS': self._format_value(valores_transporte['ViaticoManuAlojS']),
                'ViaticoManuAlojNS': self._format_value(valores_transporte['ViaticoManuAlojNS'])
            })
        if valores_transporte['AuxilioTransporte'] or valores_transporte['ViaticoManuAlojS'] or valores_transporte['ViaticoManuAlojNS']:    
            ET.SubElement(devengados, 'Transporte', **attrs)

    def _process_extras(self, devengados):
        """Procesa todas las horas extras"""
        extras_info = {
            'HED': {'parent': 'HEDs', 'rate': '25.00'},
            'HEN': {'parent': 'HENs', 'rate': '75.00'},
            'HRN': {'parent': 'HRNs', 'rate': '35.00'},
            'HEDDF': {'parent': 'HEDDFs', 'rate': '100.00'},
            'HRDDF': {'parent': 'HRDDFs', 'rate': '75.00'},
            'HENDF': {'parent': 'HENDFs', 'rate': '150.00'},
            'HRNDF': {'parent': 'HRNDFs', 'rate': '110.00'},
        }

        for code, info in extras_info.items():
            extra_lines = self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.code == code)
            
            if extra_lines:
                parent = ET.SubElement(devengados, info['parent'])
                for line in extra_lines:
                    ET.SubElement(parent, code,
                        HoraInicio=self._format_datetime(line.date_from or self.date_from),
                        HoraFin=self._format_datetime(line.date_to or self.date_to),
                        Cantidad=str(int(line.quantity)),
                        Porcentaje=info['rate'],
                        Pago=self._format_value(line.total))

    def _add_vacations(self, devengados):
        """Agrega las vacaciones en el orden correcto"""

        vac_lines = self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.code == 'VAC_COM')
        comp_lines = self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.code == 'VAC_COMP')

        if vac_lines or comp_lines:        
            parent = ET.SubElement(devengados, 'Vacaciones')
            for line in vac_lines:
                ET.SubElement(parent, 'VacacionesComunes',
                    FechaInicio=self._format_date(line.initial_accrual_date),
                    FechaFin=self._format_date(line.final_accrual_date),
                    Cantidad=str(int(line.quantity or 0)),
                    Pago=self._format_value(line.total))
            
            for line in comp_lines:
                ET.SubElement(parent, 'VacacionesCompensadas',
                    Cantidad=str(int(line.quantity or 0)),
                    Pago=self._format_value(line.total))


    def _add_ausencias(self, parent):
        """Agrega nodos de incapacidades y licencias"""
        # Incapacidades
        incap_lines = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code in ('INCAP_COM','INCAP_PROF','INCAP_LAB'))
        
        if incap_lines:
            inc = ET.SubElement(parent, 'Incapacidades')
            for line in incap_lines:
                ET.SubElement(inc, 'Incapacidad',
                    FechaInicio=self._format_date(line.initial_accrual_date),
                    FechaFin=self._format_date(line.final_accrual_date),
                    Cantidad=str(int(line.quantity or 0)),
                    Tipo=line.salary_rule_id.devengado_rule_id.incapacity_type or "1",
                    Pago=self._format_value(line.total))

        # Licencias
        lic_codes = [('LIC_MP', 'LicenciaMP'), ('LIC_R', 'LicenciaR'), ('LIC_NR', 'LicenciaNR')]
        has_licencias = False
        
        for code, tag in lic_codes:
            lines = self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.code == code)
            if lines:
                if not has_licencias:
                    lic = ET.SubElement(parent, 'Licencias')
                    has_licencias = True
                for line in lines:
                    attrs = {
                        'FechaInicio': self._format_date(line.initial_accrual_date),
                        'FechaFin': self._format_date(line.final_accrual_date),
                        'Cantidad': str(int(line.quantity or 0))
                    }
                    if code != 'LIC_NR':
                        attrs['Pago'] = self._format_value(line.total)
                    ET.SubElement(lic, tag, **attrs)
    
    def _add_prima_cesantias(self, parent):
        """Agrega nodos de prima y cesantías"""
        prima_s = self._get_line_value('PRIMA_S')
        prima_ns = self._get_line_value('PRIMA_NS')
        if prima_s or prima_ns:
            ET.SubElement(parent, 'Primas',
                Cantidad=str(int(self._get_line_value_qty('PRIMA_S'))),
                Pago=self._format_value(prima_s),
                PagoNS=self._format_value(prima_ns))

        cesantias = self._get_line_value('CES')
        intereses = self._get_line_value('INT_CES')
        if cesantias or intereses:
            ET.SubElement(parent, 'Cesantias',
                Pago=self._format_value(cesantias),
                Porcentaje='12.00',
                PagoIntereses=self._format_value(intereses))

    
    def _process_all_concepts(self, devengados):
        """Procesa todos los conceptos de devengados"""
        # Vacaciones

        self._add_vacations(devengados)

        # Primas y Cesantías
        self._add_prima_cesantias(devengados)

        # Ausencias
        self._add_ausencias(devengados)

        # Otros conceptos grupales
        groups = [
            ('Bonificaciones', 'Bonificacion'),
            ('Auxilios', 'Auxilio'),
            ('HuelgasLegales', 'HuelgaLegal'),
            ('OtrosConceptos', 'OtroConcepto'),
            ('Compensaciones', 'Compensacion'),
            ('BonoEPCTVs', 'BonoEPCTV'),
            ('Comisiones', 'Comision'),
            ('PagosTerceros', 'PagoTercero'),
            ('Anticipos', 'Anticipo')
        ]

        for parent_tag, child_tag in groups:
            self._add_concept_group(devengados, parent_tag, child_tag)

        # Conceptos simples
        simple_concepts = [
            'Dotacion', 'ApoyoSost', 'Teletrabajo', 
            'BonifRetiro', 'Indemnizacion', 'Reintegro'
        ]

        for concept in simple_concepts:
            value = self._get_line_value_tag(concept)
            if value:
                ET.SubElement(devengados, concept).text = self._format_value(value)

    def _add_concept_group(self, parent, parent_tag, child_tag):
        """
        Agrega grupos de conceptos según su tipo específico.
        """
        group_node = ET.SubElement(parent, parent_tag)

        # Mapeo de códigos por tipo de concepto
        code_mappings = {
            'Bonificacion': {
                'salarial': 'BONUS_S',
                'no_salarial': 'BONUS_NS',
                'attrs': {'S': 'BonificacionS', 'NS': 'BonificacionNS'}
            },
            'Auxilio': {
                'salarial': 'AID_S',
                'no_salarial': 'AID_NS',
                'attrs': {'S': 'AuxilioS', 'NS': 'AuxilioNS'}
            },
            'HuelgaLegal': {
                'code': 'LEGAL_STRIKE'
            },
            'OtroConcepto': {
                'salarial': 'OTHER_S',
                'no_salarial': 'OTHER_NS',
                'attrs': {'S': 'ConceptoS', 'NS': 'ConceptoNS'}
            },
            'Compensacion': {
                'ordinaria': 'COMP_O',
                'extraordinaria': 'COMP_E',
                'attrs': {'O': 'CompensacionO', 'E': 'CompensacionE'}
            },
            'BonoEPCTV': {
                'salarial': 'EPCTV_S',
                'no_salarial': 'EPCTV_NS',
                'alim_salarial': 'EPCTV_ALIM_S',
                'alim_no_salarial': 'EPCTV_ALIM_NS'
            },
            'Comision': {
                'code': 'COM'
            },
            'PagoTercero': {
                'code': 'THIRD_PAY'
            }
        }

        concept_info = code_mappings.get(child_tag)
        if not concept_info:
            return

        if child_tag in ['Bonificacion', 'Auxilio', 'OtroConcepto']:
            self._process_salarial_concept(group_node, child_tag, concept_info)
        elif child_tag == 'HuelgaLegal':
            self._process_huelga_legal(group_node, concept_info)
        elif child_tag == 'Compensacion':
            self._process_compensacion(group_node, concept_info)
        elif child_tag == 'BonoEPCTV':
            self._process_bono_epctv(group_node, concept_info)
        else:
            self._process_simple_concept(group_node, child_tag, concept_info)

    def _process_salarial_concept(self, group_node, child_tag, concept_info):
        """
        Procesa conceptos con componente salarial y no salarial.
        Solo crea nodos cuando hay valores y requiere componente salarial para incluir no salarial.
        """
        lines_s = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['salarial'])
        lines_ns = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['no_salarial'])

        # No crear nada si no hay líneas
        if not (lines_s or lines_ns):
            return

        attrs = concept_info['attrs']
        # Procesar todas las líneas en un solo bucle
        for line in lines_s:
            attrs_dict = {
                attrs['S']: self._format_value(line.total),
                attrs['NS']: "0.00"
            }
            if child_tag == 'OtroConcepto':
                attrs_dict['DescripcionConcepto'] = str(line.name)
            ET.SubElement(group_node, child_tag, **attrs_dict)

            # Si hay línea salarial, buscar la no salarial correspondiente
            for line_ns in lines_ns:
                attrs_dict = {
                    attrs['S']: "0.00",
                    attrs['NS']: self._format_value(line_ns.total)
                }
                if child_tag == 'OtroConcepto':
                    attrs_dict['DescripcionConcepto'] = str(line_ns.name)
                ET.SubElement(group_node, child_tag, **attrs_dict)

        # Si no hay líneas salariales pero sí no salariales, solo procesar no salariales
        if not lines_s and lines_ns:
            for line_ns in lines_ns:
                attrs_dict = {
                    attrs['NS']: self._format_value(line_ns.total)
                }
                if child_tag == 'OtroConcepto':
                    attrs_dict['DescripcionConcepto'] = str(line_ns.name)
                ET.SubElement(group_node, child_tag, **attrs_dict)
                
    def _process_huelga_legal(self, group_node, concept_info):
        """Procesa conceptos de huelga legal"""
        lines = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['code'])
        
        if lines:
            for line in lines:
                ET.SubElement(group_node, 'HuelgaLegal',
                    FechaInicio=self._format_date(line.initial_accrual_date),
                    FechaFin=self._format_date(line.final_accrual_date),
                    Cantidad=str(int(line.quantity or 0)))
        # else:
        #     ET.SubElement(group_node, 'HuelgaLegal',
        #         FechaInicio="9999-12-31",
        #         FechaFin="9999-12-31",
        #         Cantidad="0")

    def _process_compensacion(self, group_node, concept_info):
        """Procesa conceptos de compensación"""
        lines_o = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['ordinaria'])
        lines_e = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['extraordinaria'])
        
        if lines_o or lines_e:
            ET.SubElement(group_node, 'Compensacion',
                CompensacionO=self._format_value(sum(lines_o.mapped('total'))),
                CompensacionE=self._format_value(sum(lines_e.mapped('total'))))
        # else:
        #     ET.SubElement(group_node, 'Compensacion',
        #         CompensacionO="0.00",
        #         CompensacionE="0.00")

    def _process_bono_epctv(self, group_node, concept_info):
        """
        Procesa conceptos de bono EPCTV.
        """
        # Filtrar líneas por tipo
        lines_s = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['salarial']
        )
        lines_ns = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['no_salarial']
        )
        lines_as = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['alim_salarial']
        )
        lines_ans = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['alim_no_salarial']
        )

        total_s = sum(lines_s.mapped('total'))
        total_ns = sum(lines_ns.mapped('total'))
        total_as = sum(lines_as.mapped('total'))
        total_ans = sum(lines_ans.mapped('total'))

        if total_s or total_ns or total_as or total_ans:
            values = {}
            if total_s:
                values['PagoS'] = self._format_value(total_s)
            if total_ns:
                values['PagoNS'] = self._format_value(total_ns)
            if total_as:
                values['PagoAlimentacionS'] = self._format_value(total_as)
            if total_ans:
                values['PagoAlimentacionNS'] = self._format_value(total_ans)
            
            ET.SubElement(group_node, 'BonoEPCTV', values)

    def _process_simple_concept(self, group_node, child_tag, concept_info):
        """Procesa conceptos simples (Comision, PagoTercero)"""
        lines = self.line_ids.filtered(
            lambda l: l.salary_rule_id.devengado_rule_id.code == concept_info['code'])
        
        if lines:
            for line in lines:
                child = ET.SubElement(group_node, child_tag)
                child.text = self._format_value(line.total)
        # else:
        #     child = ET.SubElement(group_node, child_tag)
        #     child.text = "0.00"


    def _process_deducciones(self, deducciones):
        """Procesa todas las deducciones"""
        # Salud y Pensión
        ET.SubElement(deducciones, 'Salud',
            Porcentaje='4.00',
            Deduccion=self._format_value(self._get_line_value('SALUD')))
            
        ET.SubElement(deducciones, 'FondoPension',
            Porcentaje='4.00',
            Deduccion=self._format_value(self._get_line_value('PENSION')))

        # Obtener las líneas de Solidaridad y Subsistencia
        solidaridad_line = self.line_ids.filtered(lambda l: l.salary_rule_id.deduccion_rule_id.code == 'FSP_SOL')
        subsistencia_line = self.line_ids.filtered(lambda l: l.salary_rule_id.deduccion_rule_id.code == 'FSP_SUB')

        # Crear el nodo con los valores correspondientes
        ET.SubElement(deducciones, 'FondoSP',
            Porcentaje=self._format_value(self._get_porc_fsp(solidaridad_line.salary_rule_id.code)),
            DeduccionSP=self._format_value(sum(solidaridad_line.mapped('total'))),
            PorcentajeSub=self._format_value(self._get_porc_fsp(subsistencia_line.salary_rule_id.code)),
            DeduccionSub=self._format_value(sum(subsistencia_line.mapped('total'))))

        # Grupos con múltiples líneas
        groups = [
            ('Sindicatos', 'Sindicato'),
            ('Sanciones', 'Sancion'),
            ('Libranzas', 'Libranza'),
            ('PagosTerceros', 'PagoTercero'),
            ('Anticipos', 'Anticipo'),
            ('OtrasDeducciones', 'OtraDeduccion')
        ]

        for parent_tag, child_tag in groups:
            self._add_deduction_group(deducciones, parent_tag, child_tag)

        # Conceptos simples
        simple_deductions = [
            'PensionVoluntaria', 'RetencionFuente', 'AFC',
            'Cooperativa', 'EmbargoFiscal', 'PlanComplementarios',
            'Educacion', 'Reintegro', 'Deuda'
        ]

        for deduction in simple_deductions:
            value = self._get_line_value_tag(deduction)
            if value:
                ET.SubElement(deducciones, deduction).text = self._format_value(value)

    def _get_line_value_tag(self, code):
        """Obtiene el valor de una línea por código"""
        line = self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.xml_tag == code or l.salary_rule_id.deduccion_rule_id.xml_tag == code)
        return sum(line.mapped('total')) if line else 0.0



    def _add_deduction_group(self, parent, parent_tag, child_tag):
        """Agrega grupos de deducciones en el orden correcto"""
        
        # Mapeo de códigos de deducciones en orden
        deduction_mappings = {
            'Sindicato': {
                'code': 'SIND',
                'attrs': {'Porcentaje': 'rate', 'Deduccion': 'total'}
            },
            'Sancion': {
                'pub_code': 'SANC_PUB',
                'priv_code': 'SANC_PRIV',
                'attrs': {'SancionPublic': 'pub_total', 'SancionPriv': 'priv_total'}
            },
            'Libranza': {
                'code': 'LIB',
                'attrs': {'Descripcion': 'name', 'Deduccion': 'total'}
            },
            'PagoTercero': {
                'code': 'THIRD_PAY',
                'is_text_node': True
            },
            'Anticipo': {
                'code': 'ADVANCE',
                'is_text_node': True
            },
            'OtraDeduccion': {
                'code': 'OTHER_DED',
                'is_text_node': True
            }
        }

        group_node = ET.SubElement(parent, parent_tag)
        concept_info = deduction_mappings.get(child_tag)
        
        if not concept_info:
            return

        if child_tag == 'Sancion':
            self._process_sancion(group_node, concept_info)
        elif concept_info.get('is_text_node'):
            self._process_text_node(group_node, child_tag, concept_info)
        else:
            self._process_attribute_node(group_node, child_tag, concept_info)

    def _process_sancion(self, group_node, concept_info):
        """Procesa nodos de sanción"""
        lines_pub = self.line_ids.filtered(
            lambda l: l.salary_rule_id.deduccion_rule_id.code == concept_info['pub_code'])
        lines_priv = self.line_ids.filtered(
            lambda l: l.salary_rule_id.deduccion_rule_id.code == concept_info['priv_code'])
        
        if lines_pub or lines_priv:
            ET.SubElement(group_node, 'Sancion',
                SancionPublic=self._format_value(sum(lines_pub.mapped('total'))),
                SancionPriv=self._format_value(sum(lines_priv.mapped('total'))))
        # else:
        #     ET.SubElement(group_node, 'Sancion',
        #         SancionPublic="0.00",
        #         SancionPriv="0.00")

    def _process_text_node(self, group_node, child_tag, concept_info):
        """Procesa nodos con valor de texto"""
        lines = self.line_ids.filtered(
            lambda l: l.salary_rule_id.deduccion_rule_id.code == concept_info['code'])
        
        if lines:
            for line in lines:
                child = ET.SubElement(group_node, child_tag)
                child.text = self._format_value(line.total)
        # else:
        #     child = ET.SubElement(group_node, child_tag)
        #     child.text = "0.00"

    def _process_attribute_node(self, group_node, child_tag, concept_info):
        """Procesa nodos con atributos"""
        lines = self.line_ids.filtered(
            lambda l: l.salary_rule_id.deduccion_rule_id.code == concept_info['code'])
        
        if lines:
            for line in lines:
                attrs = {}
                for xml_attr, field in concept_info['attrs'].items():
                    if field == 'name':
                        attrs[xml_attr] = line.name or ""
                    elif field == 'rate':
                        attrs[xml_attr] = self._format_value(line.rate)
                    else:
                        attrs[xml_attr] = self._format_value(line.total)
                ET.SubElement(group_node, child_tag, **attrs)
        # else:
        #     attrs = {attr: "0.00" for attr in concept_info['attrs'].keys()}
        #     if 'Descripcion' in attrs:
        #         attrs['Descripcion'] = ""
        #     ET.SubElement(group_node, child_tag, **attrs)
                
    def _format_value(self, value):
        """Formatea valores numéricos"""
        return "{:.2f}".format(abs(value) if value else 0.0)


    def _format_amount(self, amount):
        """Formatea montos con dos decimales"""
        return "{:.2f}".format(abs(amount or 0.0))

    def _format_date(self, date):
        """Formatea fechas"""
        return date.strftime('%Y-%m-%d') if date else '9999-12-31'

    def _format_datetime(self, date):
        """Formatea fecha y hora"""
        if not date:
            return '9999-12-31T00:00:00'
        dt = datetime.combine(date, datetime.min.time())
        return dt.astimezone(timezone('America/Bogota')).strftime("%Y-%m-%dT%H:%M:%S")
    def _get_line_value(self, code):
        """Obtiene el valor de una línea por código"""
        line = self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.code == code or l.salary_rule_id.deduccion_rule_id.code == code)
        return sum(line.mapped('total')) if line else 0.0

    def _get_line_value_qty(self, code):
        """Obtiene el valor de una línea por código"""
        line = self.line_ids.filtered(lambda l: l.salary_rule_id.devengado_rule_id.code == code or l.salary_rule_id.deduccion_rule_id.code == code)
        return sum(line.mapped('quantity')) if line else 0.0
    
    def _get_url_qr(self):
        tipo_ambiente = self._get_tipo_ambiente()
        if tipo_ambiente == "1":
            return "https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey="
        else:
            return (
                "https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey="
            )
    def get_bank_information(self,r_bank=0,r_type=0,r_account=0):
        for bank in self.employee_id.work_contact_id.bank_ids:
            if bank.is_main:
                if r_bank != 0:
                    return bank.bank_id.name
                if r_type != 0:
                    return bank.type_account
                if r_account != 0:
                    return bank.acc_number
    def get_subtipo_trabajador(self):
        try:
            employee = self._get_employee_object()
            if employee and employee.subtipo_coti_id and employee.subtipo_coti_id.code:
                code = employee.subtipo_coti_id.code
                if code in ('4', '5', '6'):
                    return '02'
                return code 
            else:
                return '01'
        except Exception as e:
            _logger.error(f"Error getting SubTipoTrabajador: {e}")
            return '01' 
        
    def _template_nomina_individual(self, dian_constants):
        cune = self._get_cune(dian_constants)
        url_qr = self._get_url_qr()
        if not self.payment_date:
            raise UserError(_("Debe configurar la fecha de pago"))


        # if not self.payroll_period:
        #     raise UserError(_("Debe configurar el periodo de la nomina"))
        # if not self.worked_days_line_ids.filtered(lambda x: x.code in ["WORK100", "COMPENSATORIO", "WORK110", "EGA", "LICENCIA_REMUNERADA", "VACDISFRUTADAS"]):
        #     raise UserError(
        #         _("Debes ingresar el numero de dias trabajado con el codifo WORK100")
        #     )
        nomina_payroll = "5"
        number_days = abs((self.contract_id.date_start - self.date_to).days)
        self.current_cune = cune
    # Verificar si el método de pago es en efectivo
        metodo_pago_efectivo = False  # Asumimos que el método de pago no es en efectivo
        if self._get_contract().payment_method_id.code == "10":
            metodo_pago_efectivo = True
        pago_xml = ""
        if metodo_pago_efectivo:
            pago_xml = f"""<Pago Forma="{self._get_contract().way_pay_id.code}" Metodo="{self._get_contract().payment_method_id.code}"/>"""
        else:
            pago_xml = f"""<Pago Forma="{self._get_contract().way_pay_id.code}" Metodo="{self._get_contract().payment_method_id.code}"
                Banco="{self.get_bank_information(r_bank=1)}"
                TipoCuenta="{self.get_bank_information(r_type=1)}"
                NumeroCuenta="{self.get_bank_information(r_account=1)}" />"""
        xml = f"""<NominaIndividual xmlns="dian:gov:co:facturaelectronica:NominaIndividual"
        xmlns:xs="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
        xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
        xmlns:xades="http://uri.etsi.org/01903/v1.3.2#"
        xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        SchemaLocation="" xsi:schemaLocation="dian:gov:co:facturaelectronica:NominaIndividual NominaIndividualElectronicaXSD.xsd">
                <ext:UBLExtensions>
                    <ext:UBLExtension>
                        <ext:ExtensionContent></ext:ExtensionContent>
                    </ext:UBLExtension>
                </ext:UBLExtensions>
          <Novedad CUNENov="A">false</Novedad>
          <Periodo FechaIngreso="{str(self._get_contract().date_start)}" FechaLiquidacionInicio="{str(self.date_from)}"
          FechaLiquidacionFin="{str(self.date_to)}" TiempoLaborado="{number_days}"
          FechaGen="{dian_constants.get('FechaGen')}" />
          <NumeroSecuenciaXML CodigoTrabajador="{self._get_employee().vat_co}" Prefijo="{dian_constants.get('Prefix')}"
          Consecutivo="{dian_constants.get('Consecutivo')}" Numero="{dian_constants.get('Number')}" />
          <LugarGeneracionXML Pais="{str(self._get_company_id().partner_id.country_id.code) or ''}"
          DepartamentoEstado="{str(self._get_company_id().partner_id.state_id.code_dian)}"
          MunicipioCiudad="{str(self._get_company_id().partner_id.city_id.code)}" Idioma="es" />
          <ProveedorXML RazonSocial="{self._get_emisor().name}" 
            NIT="{self._get_emisor().vat_co}" 
            DV="{self._get_emisor().dv}" 
            SoftwareID="{dian_constants.get('SoftwareID')}" 
            SoftwareSC="{dian_constants.get('SoftwareSecurityCode')}" />
          <CodigoQR>{url_qr}{cune}</CodigoQR>
          <InformacionGeneral Version="V1.0: Documento Soporte de Pago de Nómina Electrónica"
            Ambiente="{self._get_tipo_ambiente()}" 
            TipoXML="{self._get_tipo_xml()}" 
            CUNE="{cune}"
            EncripCUNE="CUNE-SHA384" FechaGen="{dian_constants.get('FechaGen')}"
            HoraGen="{dian_constants.get('HoraGen')}" PeriodoNomina="{nomina_payroll}"
            TipoMoneda="COP" TRM="0" />
          <Notas>{str(self._get_notes())}</Notas>
          <Empleador RazonSocial="{self._get_emisor().name}" 
            NIT="{self._get_emisor().vat_co}"
            DV="{str(self._get_emisor().dv)}" 
            Pais="{str(self._get_emisor().country_id.code)}"
            DepartamentoEstado="{str(self._get_emisor().state_id.code_dian)}"
            MunicipioCiudad="{str(self._get_company_id().partner_id.city_id.code)}"
            Direccion="{str(self._get_emisor().street)}" />
          <Trabajador TipoTrabajador="{self._get_employee_object().tipo_coti_id.code}"
          SubTipoTrabajador="{self.get_subtipo_trabajador()}" 
            AltoRiesgoPension="false"
            TipoDocumento="{self.return_number_document_type(self._get_employee().l10n_latam_identification_type_id.l10n_co_document_code)}"
            NumeroDocumento="{self._get_employee().vat_co}" 
            PrimerApellido="{self._get_employee().first_lastname}"
            SegundoApellido="{self._get_employee().second_lastname}" 
            PrimerNombre="{self._get_employee().firs_name}"
            OtrosNombres="{self._get_employee().second_name}" 
            LugarTrabajoPais="{self._get_employee().country_id.code}"
            LugarTrabajoDepartamentoEstado="{self._get_employee().state_id.code_dian}"
            LugarTrabajoMunicipioCiudad="{self._get_employee().city_id.code}"
            LugarTrabajoDireccion="{self._get_employee().street}" 
            SalarioIntegral="{self._integral(self._get_employee_object().contract_id.modality_salary)}"
            TipoContrato="{self.type_contract_e(self._get_employee_object().contract_id.contract_type)}"
            Sueldo="{'{:.2f}'.format(self._get_employee_object().contract_id.wage)}" 
            CodigoTrabajador="{self._get_employee().vat_co}" />
            {pago_xml}
          <FechasPagos>
            <FechaPago>{self.payment_date}</FechaPago>
          </FechasPagos>
          {self.template_generate_devengados_deducciones()}
          <DevengadosTotal>{self._get_total_devengados()}</DevengadosTotal>
          <DeduccionesTotal>{self._get_total_deducciones()}</DeduccionesTotal>
          <ComprobanteTotal>{self._get_total_pagado()}</ComprobanteTotal>
        </NominaIndividual>"""
        return xml

    def get_values_for_previous_xml(self, xml_sended):
        xml = xmltodict.parse(xml_sended)
        return {
            "Prefix": xml["NominaIndividual"]["NumeroSecuenciaXML"]["@Prefijo"],
            "consecutivo": xml["NominaIndividual"]["NumeroSecuenciaXML"][
                "@Consecutivo"
            ],
            "numero": xml["NominaIndividual"]["NumeroSecuenciaXML"]["@Numero"],
            "pais": xml["NominaIndividual"]["LugarGeneracionXML"]["@Pais"],
            "departamento": xml["NominaIndividual"]["LugarGeneracionXML"][
                "@DepartamentoEstado"
            ],
            "idioma": xml["NominaIndividual"]["LugarGeneracionXML"]["@Idioma"],
            "municipio": xml["NominaIndividual"]["LugarGeneracionXML"][
                "@MunicipioCiudad"
            ],
            "softwareid": xml["NominaIndividual"]["ProveedorXML"]["@SoftwareID"],
            "softwaresc": xml["NominaIndividual"]["ProveedorXML"]["@SoftwareSC"],
            "codeqr": xml["NominaIndividual"]["CodigoQR"],
            "cune": xml["NominaIndividual"]["InformacionGeneral"]["@CUNE"],
            "fechagen": xml["NominaIndividual"]["InformacionGeneral"]["@FechaGen"],
            "horagen": xml["NominaIndividual"]["InformacionGeneral"]["@HoraGen"],
            "NitNIAE": xml["NominaIndividual"]["Empleador"]["@NIT"],
            "TipoXML": xml["NominaIndividual"]["InformacionGeneral"]["@TipoXML"],
            "TipAmb": xml["NominaIndividual"]["InformacionGeneral"]["@Ambiente"],
        }

    def _get_cune_ajuste(self, values):
        res = f"""{values['numNIAE'] + values['FecNIAE'] + values.get('HorNIAE') + '0.00' +
                   '0.00' + '0.00' + values['NitNIAE'] + '0' +
                   values['TipoXML'] + self.company_id.software_pin_payroll + self._get_tipo_ambiente()}"""
        _logger.info(res)
        cune = hashlib.sha384(res.encode())
        cune = cune.hexdigest()
        return cune

    def get_code_nomina_individual_ajuste(
        self, code, cune, dian_constants, number_days, nomina_payroll, payslip_id
    ):
        values = self.get_values_for_previous_xml(payslip_id.xml_sended)
        url_qr = self._get_url_qr()
        if code == 1:
            xml = f"""
<Reemplazar>
<ReemplazandoPredecesor NumeroPred="{payslip_id.number}" CUNEPred="{payslip_id.current_cune}" FechaGenPred="{payslip_id.payment_date}"/>
<Periodo FechaIngreso="{str(self._get_contract().date_start)}" FechaLiquidacionInicio="{str(self.date_from)}"
FechaLiquidacionFin="{str(self.date_to)}" TiempoLaborado="{number_days}"
FechaGen="{dian_constants.get('FechaGen')}" />
<NumeroSecuenciaXML CodigoTrabajador="{self._get_employee().vat_co}" Prefijo="{dian_constants.get('Prefix')}"
Consecutivo="{dian_constants.get('Consecutivo')}" Numero="{dian_constants.get('Number')}" />
<LugarGeneracionXML Pais="{str(self._get_company_id().partner_id.country_id.code) or ''}"
DepartamentoEstado="{str(self._get_company_id().partner_id.state_id.code_dian)}"
MunicipioCiudad="{str(self._get_company_id().partner_id.city_id.code)}" Idioma="es" />
<ProveedorXML NIT="{self._get_emisor().vat_co}" RazonSocial="{self._get_emisor().name}"
DV="{self._get_emisor().dv}" SoftwareID="{dian_constants.get('SoftwareID')}"
SoftwareSC="{dian_constants.get('SoftwareSecurityCode')}" />
<CodigoQR>{url_qr}{cune}</CodigoQR>
<InformacionGeneral Version="V1.0: Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica"
Ambiente="{self._get_tipo_ambiente()}" TipoXML="{self._get_tipo_xml()}" CUNE="{cune}"
EncripCUNE="CUNE-SHA384" FechaGen="{dian_constants.get('FechaGen')}"
HoraGen="{dian_constants.get('HoraGen')}" PeriodoNomina="{nomina_payroll}" TipoMoneda="COP" TRM="0" />
<Notas>{str(self._get_notes())}</Notas>
<Empleador RazonSocial="{self._get_emisor().name}" NIT="{self._get_emisor().vat_co}" DV="{str(self._get_emisor().dv)}"
Pais="{str(self._get_emisor().country_id.code)}" DepartamentoEstado="{str(self._get_emisor().state_id.code_dian)}"
MunicipioCiudad="{str(self._get_company_id().partner_id.city_id.code)}" Direccion="{str(self._get_emisor().street)}" />
<Trabajador TipoTrabajador="{self._get_employee_object().tipo_coti_id.code}"
SubTipoTrabajador="{self._get_employee_object().subtipo_coti_id.code}"
AltoRiesgoPension="false" TipoDocumento="{self.return_number_document_type(self._get_employee().l10n_latam_identification_type_id.l10n_co_document_code)}"
NumeroDocumento="{self._get_employee().vat_co}" PrimerApellido="{self._get_employee().first_lastname}"
SegundoApellido="{self._get_employee().second_lastname}" PrimerNombre="{self._get_employee().firs_name}"
OtrosNombres="{self._get_employee().second_name}" LugarTrabajoPais="{self._get_employee().country_id.code}"
LugarTrabajoDepartamentoEstado="{self._get_employee().state_id.code_dian}"
LugarTrabajoMunicipioCiudad="{self._get_employee().city_id.code}" LugarTrabajoDireccion="{self._get_employee().street}"
SalarioIntegral="{self._integral(self._get_employee_object().contract_id.modality_salary)}" TipoContrato="{self.type_contract_e(self._get_employee_object().contract_id.contract_type)}"
Sueldo="{self._get_employee_object().contract_id.wage}" CodigoTrabajador="{self._get_employee().vat_co}" />
<Pago Forma="{self._get_contract().way_pay_id.code}" Metodo="{self._get_contract().payment_method_id.code}"
Banco="{self._get_employee_object().bank_account_id.bank_id.name}"
TipoCuenta="{self._get_employee_object().bank_account_id.acc_type}"
NumeroCuenta="{self._get_employee_object().bank_account_id.acc_number}" />
<FechasPagos>
<FechaPago>{self.payment_date}</FechaPago>
</FechasPagos>
{self.template_generate_devengados_deducciones()}
<DevengadosTotal>{self._get_total_devengados()}</DevengadosTotal>
<DeduccionesTotal>{self._get_total_deducciones()}</DeduccionesTotal>
<ComprobanteTotal>{self._get_total_pagado()}</ComprobanteTotal>
</Reemplazar>
            """
        else:
            dic = {
                "numNIAE": dian_constants.get("Number"),
                "FecNIAE": dian_constants.get("FechaGen"),
                "HorNIAE": dian_constants.get("HoraGen"),
                "NitNIAE": self._get_emisor().vat_co,
                "TipoXML": self._get_tipo_xml(),
                "TipAmb:": self._get_tipo_ambiente(),
            }
            cune = self._get_cune_ajuste(dic)
            xml = f"""
<Eliminar>
<EliminandoPredecesor NumeroPred="{payslip_id.number}" CUNEPred="{payslip_id.current_cune}"
FechaGenPred="{payslip_id.payment_date}"/>
<NumeroSecuenciaXML Prefijo="{dian_constants.get('Prefix')}" Consecutivo="{dian_constants.get('Consecutivo')}"
Numero="{dian_constants.get('Number')}"/>
<LugarGeneracionXML Pais="{values.get('pais')}" DepartamentoEstado="{values.get('departamento')}"
MunicipioCiudad="{values.get('municipio')}" Idioma="{values.get('idioma')}"/>
<ProveedorXML RazonSocial="{payslip_id._get_emisor().name}" PrimerApellido="{payslip_id._get_emisor().first_lastname}"
SegundoApellido="{payslip_id._get_emisor().second_lastname}" PrimerNombre="{payslip_id._get_emisor().firs_name}"
OtrosNombres="{payslip_id._get_emisor().second_name}" NIT="{payslip_id._get_emisor().vat_co}"
DV="{payslip_id._get_emisor().dv}" SoftwareID="{dian_constants.get('SoftwareID')}"
SoftwareSC="{dian_constants.get('SoftwareSecurityCode')}"/>
<CodigoQR>{url_qr}{cune}</CodigoQR>
<InformacionGeneral Version="V1.0: Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica"
Ambiente="{self._get_tipo_ambiente()}" TipoXML="{self._get_tipo_xml()}" CUNE="{cune}"
EncripCUNE="CUNE-SHA384" FechaGen="{dian_constants.get('FechaGen')}"
HoraGen="{dian_constants.get('HoraGen')}"/>
<Notas>{payslip_id.note}</Notas>
<Empleador RazonSocial="{payslip_id._get_emisor().name}" PrimerApellido="{payslip_id._get_emisor().first_lastname}"
SegundoApellido="{payslip_id._get_emisor().second_lastname}" PrimerNombre="{payslip_id._get_emisor().firs_name}"
OtrosNombres="{payslip_id._get_emisor().second_name}" NIT="{payslip_id._get_emisor().vat_co}"
DV="{payslip_id._get_emisor().dv}" Pais="{payslip_id._get_emisor().country_id.code}"
DepartamentoEstado="{str(payslip_id._get_emisor().state_id.code_dian)}"
MunicipioCiudad="{str(payslip_id._get_company_id().partner_id.city_id.code)}"
Direccion="{str(payslip_id._get_emisor().street)}"/>
</Eliminar>
            """
        return xml

    def _template_nomina_individual_ajuste(self, dian_constants):
        cune = self._get_cune(dian_constants)
        if not self.payment_date:
            raise UserError(_("Debe configurar la fecha de pago"))
        # if not self.payroll_period:
        #     raise UserError(_("Debe configurar el periodo de la nomina"))
        if not self.worked_days_line_ids.filtered(lambda x: x.code == "WORK100"):
            raise UserError(
                _("Debes ingresar el numer de dias trabajado con el codifo WORK100")
            )
        if not self.previous_cune:
            raise UserError(
                _("Debes ingresar el identificador Cune de la nomina a afectar")
            )
        nomina_payroll = "5"
        # min(30,sum(x.number_of_days for x in self.worked_days_line_ids.filtered(lambda x: x.code in ["WORK100", "COMPENSATORIO", "WORK110", "EGA", "LICENCIA_REMUNERADA", "VACDISFRUTADAS"])))
        number_days = abs((self.contract_id.date_start - self.date_to).days)
        current_model = self._name 
    
        if current_model == "hr.payslip":
            model_to_search = self.env["hr.payslip"]
        elif current_model == "hr.payslip.edi":
            model_to_search = self.env["hr.payslip.edi"]
        else:
            raise UserError(_("No se puede determinar el modelo para realizar la búsqueda."))
        previous_payslip = model_to_search.search(
            [("current_cune", "=", self.previous_cune)], limit=1
        )
        if not previous_payslip:
            raise UserError(_("No se encontró ninguna nomina asociada"))

        xml = f"""
        <NominaIndividualDeAjuste xmlns="dian:gov:co:facturaelectronica:NominaIndividualDeAjuste"
        xmlns:xs="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
        xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
        xmlns:xades="http://uri.etsi.org/01903/v1.3.2#"
        xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        SchemaLocation=""
        xsi:schemaLocation="dian:gov:co:facturaelectronica:NominaIndividualDeAjuste NominaIndividualDeAjusteElectronicaXSD.xsd">
                <ext:UBLExtensions>
                    <ext:UBLExtension>
                        <ext:ExtensionContent></ext:ExtensionContent>
                    </ext:UBLExtension>
                </ext:UBLExtensions>
          <TipoNota>{self.type_note}</TipoNota>
          {self.get_code_nomina_individual_ajuste(int(self.type_note), cune, dian_constants, number_days, nomina_payroll
                                                  , previous_payslip)}
        </NominaIndividualDeAjuste>"""
        return xml

    def _template_signature_data_xml(self):
        return """
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
<xades:Description>Politica de firma para nominas electronicas de la Republica de Colombia</xades:Description>
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

    def _template_GetStatus_xml(self):
        template_GetStatus_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
<soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
<wsu:Timestamp wsu:Id="TS-%(identifier)s">
<wsu:Created>%(Created)s</wsu:Created>
<wsu:Expires>%(Expires)s</wsu:Expires>
</wsu:Timestamp>
<wsse:BinarySecurityToken
EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"
ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
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
<wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s"
ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
</wsse:SecurityTokenReference>
</ds:KeyInfo>
</ds:Signature>
</wsse:Security>
<wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatusZip</wsa:Action>
<wsa:To wsu:Id="ID-%(identifierTo)s"
xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc
</wsa:To>
</soap:Header>
<soap:Body>
<wcf:GetStatusZip>
<wcf:trackId>%(trackId)s</wcf:trackId>
</wcf:GetStatusZip>
</soap:Body>
</soap:Envelope>
"""
        return template_GetStatus_xml

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

    def exist_dian(self, document_id):
        dic_result_verify_status = {}
        dian_constants = self._get_dian_constants()
        trackId = self.ZipKey
        identifier = uuid.uuid4()
        identifierTo = uuid.uuid4()
        identifierSecurityToken = uuid.uuid4()
        timestamp = self._generate_datetime_timestamp()
        Created = timestamp["Created"]
        Expires = timestamp["Expires"]

        if self.company_id.production_payroll:
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
            server_url["PRODUCCION"]
            if self.company_id.production_payroll
            else server_url["TEST"]
        )
        try:
            response = requests.post(
                URL_WEBService_DIAN, data=data_xml_send, headers=headers
            )
        except Exception:
            raise ValidationError(
                _(
                    "No existe comunicación con la DIAN para el servicio de recepción de Facturas Electrónicas. Por favor, revise su red o el acceso a internet."
                )
            )
        #   Respuesta de petición
        if response.status_code != 200:  # Respuesta de envío no exitosa
            if response.status_code == 500:
                raise ValidationError(
                    _("Error 500 = Error de servidor interno."))
            elif response.status_code == 503:
                raise ValidationError(_("Error 503 = Servicio no disponible."))
            elif response.status_code == 507:
                raise ValidationError(_("Error 507 = Espacio insuficiente."))
            elif response.status_code == 508:
                raise ValidationError(_("Error 508 = Ciclo detectado."))
            else:
                raise ValidationError(
                    _("Se ha producido un error de comunicación con la DIAN.")
                )
        response_dict = xmltodict.parse(response.content)

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

    def _template_GetStatusExistTest_xml(self):
        template_GetStatus_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
<soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
<wsu:Timestamp wsu:Id="TS-%(identifier)s">
<wsu:Created>%(Created)s</wsu:Created>
<wsu:Expires>%(Expires)s</wsu:Expires>
</wsu:Timestamp>
<wsse:BinarySecurityToken
EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"
ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
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
<wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s"
ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
</wsse:SecurityTokenReference>
</ds:KeyInfo>
</ds:Signature>
</wsse:Security>
<wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatus</wsa:Action>
<wsa:To wsu:Id="ID-%(identifierTo)s"
xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc
</wsa:To>
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
<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
<wsu:Timestamp wsu:Id="TS-%(identifier)s">
<wsu:Created>%(Created)s</wsu:Created>
<wsu:Expires>%(Expires)s</wsu:Expires>
</wsu:Timestamp>
<wsse:BinarySecurityToken
EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"
ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
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
<wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s"
ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
</wsse:SecurityTokenReference>
</ds:KeyInfo>
</ds:Signature>
</wsse:Security>
<wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/SendTestSetAsync</wsa:Action>
<wsa:To wsu:Id="ID-%(identifierTo)s"
xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc
</wsa:To>
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

    def _template_SendBillSyncsend_xml(self):
        template_SendBillSyncsend_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
<soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
<wsu:Timestamp wsu:Id="TS-%(identifier)s">
<wsu:Created>%(Created)s</wsu:Created>
<wsu:Expires>%(Expires)s</wsu:Expires>
</wsu:Timestamp>
<wsse:BinarySecurityToken
EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"
ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
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
<wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s"
ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
</wsse:SecurityTokenReference>
</ds:KeyInfo>
</ds:Signature>
</wsse:Security>
<wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/SendNominaSync</wsa:Action>
<wsa:To wsu:Id="ID-%(identifierTo)s"
xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
https://vpfe.dian.gov.co/WcfDianCustomerServices.svc
</wsa:To>
</soap:Header>
<soap:Body>
<wcf:SendNominaSync>
<wcf:fileName>%(fileName)s</wcf:fileName>
<wcf:contentFile>%(contentFile)s</wcf:contentFile>
</wcf:SendNominaSync>
</soap:Body>
</soap:Envelope>
        """
        return template_SendBillSyncsend_xml

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

    def _template_GetStatusExist_xml(self):
        template_GetStatus_xml = """
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
        <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
        xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
        <wsu:Timestamp wsu:Id="TS-%(identifier)s">
        <wsu:Created>%(Created)s</wsu:Created>
        <wsu:Expires>%(Expires)s</wsu:Expires>
        </wsu:Timestamp>
        <wsse:BinarySecurityToken
        EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"
        ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
        wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
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
        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s"
        ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
        </wsse:SecurityTokenReference>
        </ds:KeyInfo>
        </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatus</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s"
        xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
        https://vpfe.dian.gov.co/WcfDianCustomerServices.svc
        </wsa:To>
        </soap:Header>
        <soap:Body>
        <wcf:GetStatus>
        <wcf:trackId>%(trackId)s</wcf:trackId>
        </wcf:GetStatus>
        </soap:Body>
        </soap:Envelope>
        """
        return template_GetStatus_xml

##
# Posicion Temporal Para validar que firme correctamente
##
    def get_pem(self):
        company = self.env.company
        try:
            archivo_pem = base64.b64decode(company.pem_file_payroll)
            return x509.load_pem_x509_certificate(archivo_pem, default_backend())
        except Exception as ex:
            raise UserError(tools.ustr(ex))

    def _generate_SignatureValue_GetStatus(self, data_xml_SignedInfo_generate):
        data_xml_SignatureValue_c14n = etree.tostring(
            etree.fromstring(data_xml_SignedInfo_generate), method="c14n"
        )
        
        key, _, _ = self.get_key()
        try:
            signature = key.sign(
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except Exception as ex:
            raise UserError(tools.ustr(ex))
        
        SignatureValue = base64.b64encode(signature).decode()
        pem = self.get_pem()
        try:
            pem.public_key().verify(
                signature,
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except InvalidSignature:
            raise ValidationError(
                _("Firma para el GestStatus no fue validada exitosamente")
            )
        return SignatureValue

    def _generate_CertDigestDigestValue(self):
        pem = self.get_pem()
        cert_digest = hashlib.sha256(pem.public_bytes(serialization.Encoding.DER))
        CertDigestDigestValue = base64.b64encode(cert_digest.digest()).decode()
        return CertDigestDigestValue

    def get_key(self):
        company = self.env.company
        password = company.certificate_key_payroll
        try:
            archivo_key = base64.b64decode(company.certificate_file_payroll)
            key, cert, additional_certs = load_key_and_certificates(archivo_key, password.encode(), backend=default_backend())
            return key, cert, additional_certs
        except Exception as ex:
            raise UserError(tools.ustr(ex))

    def _generate_SignatureValue(self, data_xml_SignedInfo_generate):
        data_xml_SignatureValue_c14n = etree.tostring(
            etree.fromstring(data_xml_SignedInfo_generate),
            method="c14n",
            exclusive=False,
            with_comments=False,
        )
        
        key, _, _ = self.get_key()
        try:
            signature = key.sign(
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except Exception as ex:
            raise UserError(tools.ustr(ex))
        
        SignatureValue = base64.b64encode(signature).decode()
        pem = self.get_pem()
        try:
            pem.public_key().verify(
                signature,
                data_xml_SignatureValue_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except InvalidSignature:
            raise ValidationError(_("Firma no fue validada exitosamente"))
        
        return SignatureValue


class HrPayslipNESLine(models.Model):
    _name = 'hr.payslip.nes.line'
    _description = 'Línea de Devengos Nómina Electrónica'
    _order = 'sequence, id'  # Cambiado para respetar el orden del XML

    name = fields.Char(string='Nombre', required=True)
    name_2 = fields.Char(string='Nombre secundario')
    sequence = fields.Integer(string='Secuencia', required=True, default=5)
    code = fields.Char(string='Código', required=True)
    code_2 = fields.Char(string='Código secundario')
    slip_id2 = fields.Many2one('hr.payslip.edi', string='Nómina', ondelete='cascade')
    slip_id = fields.Many2one('hr.payslip', string='Nómina', ondelete='cascade')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Regla', required=True)
    salary_rule_id_2 = fields.Many2one('hr.salary.rule', string='Regla secundaria')
    contract_id = fields.Many2one('hr.contract', string='Contrato', required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    
    # Campos para valores y cantidades
    quantity = fields.Float(string='Cantidad', digits='Payroll', default=1.0)
    amount = fields.Float(string='Importe', digits='Payroll')
    rate = fields.Float(string='Porcentaje (%)', digits='Payroll Rate', default=0.0)
    total = fields.Float(string='Total', digits='Payroll', store=True)
    
    # Campos para valores secundarios
    quantity_2 = fields.Float(string='Cantidad secundaria', digits='Payroll', default=1.0)
    amount_2 = fields.Float(string='Importe secundario', digits='Payroll')
    rate_2 = fields.Float(string='Porcentaje secundario (%)', digits='Payroll Rate', default=0.0)
    total_2 = fields.Float(string='Total secundario', digits='Payroll', store=True)
    
    # Campos para fechas y ausencias
    departure_date = fields.Date('Fecha inicio')
    return_date = fields.Date('Fecha fin')
    leave_id = fields.Many2one('hr.leave', 'Ausencia')
    
    # Campos de control
    devengado_rule_id = fields.Many2one(related='salary_rule_id.devengado_rule_id', string='Electronico', required=True)
    xml_tag = fields.Char(related='devengado_rule_id.xml_tag', string='Etiqueta XML', store=True)
    xml_parent_tag = fields.Char(related='devengado_rule_id.parent_id.xml_tag', string='Etiqueta Padre XML', store=True)
    category_id = fields.Many2one(related='salary_rule_id.category_id', string='Categoría', store=True)
    is_overtime = fields.Boolean(related='devengado_rule_id.has_times', string='Es Hora Extra', store=True)

class HrPayslipNESLineDed(models.Model):
    _name = 'hr.payslip.nes.line.ded'
    _description = 'Línea de Deducciones Nómina Electrónica'
    _order = 'sequence, id'  # Cambiado para respetar el orden del XML

    name = fields.Char(string='Nombre', required=True)
    name_2 = fields.Char(string='Nombre secundario')
    sequence = fields.Integer(string='Secuencia', required=True, default=5)
    code = fields.Char(string='Código', required=True)
    code_2 = fields.Char(string='Código secundario')
    slip_id2 = fields.Many2one('hr.payslip.edi', string='Nómina', ondelete='cascade')
    slip_id = fields.Many2one('hr.payslip', string='Nómina', ondelete='cascade')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Regla', required=True)
    salary_rule_id_2 = fields.Many2one('hr.salary.rule', string='Regla secundaria')
    contract_id = fields.Many2one('hr.contract', string='Contrato', required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    
    # Campos para valores y cantidades
    quantity = fields.Float(string='Cantidad', digits='Payroll', default=1.0)
    amount = fields.Float(string='Importe', digits='Payroll')
    rate = fields.Float(string='Porcentaje (%)', digits='Payroll Rate', default=0.0)
    total = fields.Float(string='Total', digits='Payroll', store=True)
    
    # Campos para valores secundarios
    quantity_2 = fields.Float(string='Cantidad secundaria', digits='Payroll', default=1.0)
    amount_2 = fields.Float(string='Importe secundario', digits='Payroll')
    rate_2 = fields.Float(string='Porcentaje secundario (%)', digits='Payroll Rate', default=0.0)
    total_2 = fields.Float(string='Total secundario', digits='Payroll', store=True)
    
    # Campos para fechas y ausencias
    departure_date = fields.Date('Fecha inicio')
    return_date = fields.Date('Fecha fin')
    leave_id = fields.Many2one('hr.leave', 'Ausencia')
    
    # Campos de control
    deduccion_rule_id = fields.Many2one(related='salary_rule_id.deduccion_rule_id', string='Electronico', required=True)
    xml_tag = fields.Char(related='deduccion_rule_id.xml_tag', string='Etiqueta XML', store=True)
    xml_parent_tag = fields.Char(related='deduccion_rule_id.parent_id.xml_tag', string='Etiqueta Padre XML', store=True)
    category_id = fields.Many2one(related='salary_rule_id.category_id', string='Categoría', store=True)
    is_overtime = fields.Boolean(related='deduccion_rule_id.has_times', string='Es Hora Extra', store=True)