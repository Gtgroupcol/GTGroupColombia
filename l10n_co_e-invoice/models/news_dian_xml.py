# -*- coding: utf-8 -*-
from odoo import _, api, fields, models, tools, Command
from cryptography.hazmat.primitives import hashes, serialization
from pytz import timezone
from odoo.exceptions import UserError,ValidationError
from odoo.tools import float_repr,cleanup_xml_node
from odoo.tools.float_utils import float_round
from collections import defaultdict
import hashlib
from lxml import etree
import xml.etree.ElementTree as ET
import re
from markupsafe import Markup
from base64 import encodebytes, b64encode
import io
import zipfile
from odoo.tools import html_escape
from . import xml_utils
from odoo.exceptions import UserError
from hashlib import sha384
import base64
import logging
import html
from random import randint
import qrcode
from io import BytesIO
_logger = logging.getLogger(__name__)
COUNTRIES_ES = {
    "AF": "Afganistán",
    "AX": "Åland",
    "AL": "Albania",
    "DE": "Alemania",
    "AD": "Andorra",
    "AO": "Angola",
    "AI": "Anguila",
    "AQ": "Antártida",
    "AG": "Antigua y Barbuda",
    "SA": "Arabia Saudita",
    "DZ": "Argelia",
    "AR": "Argentina",
    "AM": "Armenia",
    "AW": "Aruba",
    "AU": "Australia",
    "AT": "Austria",
    "AZ": "Azerbaiyán",
    "BS": "Bahamas",
    "BD": "Bangladés",
    "BB": "Barbados",
    "BH": "Baréin",
    "BE": "Bélgica",
    "BZ": "Belice",
    "BJ": "Benín",
    "BM": "Bermudas",
    "BY": "Bielorrusia",
    "BO": "Bolivia",
    "BQ": "Bonaire, San Eustaquio y Saba",
    "BA": "Bosnia y Herzegovina",
    "BW": "Botsuana",
    "BR": "Brasil",
    "BN": "Brunéi",
    "BG": "Bulgaria",
    "BF": "Burkina Faso",
    "BI": "Burundi",
    "BT": "Bután",
    "CV": "Cabo Verde",
    "KH": "Camboya",
    "CM": "Camerún",
    "CA": "Canadá",
    "QA": "Catar",
    "TD": "Chad",
    "CL": "Chile",
    "CN": "China",
    "CY": "Chipre",
    "CO": "Colombia",
    "KM": "Comoras",
    "KP": "Corea del Norte",
    "KR": "Corea del Sur",
    "CI": "Costa de Marfil",
    "CR": "Costa Rica",
    "HR": "Croacia",
    "CU": "Cuba",
    "CW": "Curazao",
    "DK": "Dinamarca",
    "DM": "Dominica",
    "EC": "Ecuador",
    "EG": "Egipto",
    "SV": "El Salvador",
    "AE": "Emiratos Árabes Unidos",
    "ER": "Eritrea",
    "SK": "Eslovaquia",
    "SI": "Eslovenia",
    "ES": "España",
    "US": "Estados Unidos",
    "EE": "Estonia",
    "ET": "Etiopía",
    "PH": "Filipinas",
    "FI": "Finlandia",
    "FJ": "Fiyi",
    "FR": "Francia",
    "GA": "Gabón",
    "GM": "Gambia",
    "GE": "Georgia",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GD": "Granada",
    "GR": "Grecia",
    "GL": "Groenlandia",
    "GP": "Guadalupe",
    "GU": "Guam",
    "GT": "Guatemala",
    "GF": "Guayana Francesa",
    "GG": "Guernsey",
    "GN": "Guinea",
    "GW": "Guinea-Bisáu",
    "GQ": "Guinea Ecuatorial",
    "GY": "Guyana",
    "HT": "Haití",
    "HN": "Honduras",
    "HK": "Hong Kong",
    "HU": "Hungría",
    "IN": "India",
    "ID": "Indonesia",
    "IQ": "Irak",
    "IR": "Irán",
    "IE": "Irlanda",
    "BV": "Isla Bouvet",
    "IM": "Isla de Man",
    "CX": "Isla de Navidad",
    "IS": "Islandia",
    "KY": "Islas Caimán",
    "CC": "Islas Cocos",
    "CK": "Islas Cook",
    "FO": "Islas Feroe",
    "GS": "Islas Georgias del Sur y Sandwich del Sur",
    "HM": "Islas Heard y McDonald",
    "FK": "Islas Malvinas",
    "MP": "Islas Marianas del Norte",
    "MH": "Islas Marshall",
    "PN": "Islas Pitcairn",
    "SB": "Islas Salomón",
    "TC": "Islas Turcas y Caicos",
    "UM": "Islas ultramarinas de Estados Unidos",
    "VG": "Islas Vírgenes Británicas",
    "VI": "Islas Vírgenes de los Estados Unidos",
    "IL": "Israel",
    "IT": "Italia",
    "JM": "Jamaica",
    "JP": "Japón",
    "JE": "Jersey",
    "JO": "Jordania",
    "KZ": "Kazajistán",
    "KE": "Kenia",
    "KG": "Kirguistán",
    "KI": "Kiribati",
    "XK": "Kosovo",
    "KW": "Kuwait",
    "LA": "Laos",
    "LS": "Lesoto",
    "LV": "Letonia",
    "LB": "Líbano",
    "LR": "Liberia",
    "LY": "Libia",
    "LI": "Liechtenstein",
    "LT": "Lituania",
    "LU": "Luxemburgo",
    "MO": "Macao",
    "MK": "Macedonia",
    "MG": "Madagascar",
    "MY": "Malasia",
    "MW": "Malaui",
    "MV": "Maldivas",
    "ML": "Malí",
    "MT": "Malta",
    "MA": "Marruecos",
    "MQ": "Martinica",
    "MU": "Mauricio",
    "MR": "Mauritania",
    "YT": "Mayotte",
    "MX": "México",
    "FM": "Micronesia",
    "MD": "Moldavia",
    "MC": "Mónaco",
    "MN": "Mongolia",
    "ME": "Montenegro",
    "MS": "Montserrat",
    "MZ": "Mozambique",
    "MM": "Myanmar",
    "NA": "Namibia",
    "NR": "Nauru",
    "NP": "Nepal",
    "NI": "Nicaragua",
    "NE": "Níger",
    "NG": "Nigeria",
    "NU": "Niue",
    "NF": "Norfolk",
    "NO": "Noruega",
    "NC": "Nueva Caledonia",
    "NZ": "Nueva Zelanda",
    "OM": "Omán",
    "NL": "Países Bajos",
    "PK": "Pakistán",
    "PW": "Palaos",
    "PS": "Palestina",
    "PA": "Panamá",
    "PG": "Papúa Nueva Guinea",
    "PY": "Paraguay",
    "PE": "Perú",
    "PF": "Polinesia Francesa",
    "PL": "Polonia",
    "PT": "Portugal",
    "PR": "Puerto Rico",
    "GB": "Reino Unido",
    "EH": "República Árabe Saharaui Democrática",
    "CF": "República Centroafricana",
    "CZ": "República Checa",
    "CG": "República del Congo",
    "CD": "República Democrática del Congo",
    "DO": "República Dominicana",
    "RE": "Reunión",
    "RW": "Ruanda",
    "RO": "Rumania",
    "RU": "Rusia",
    "WS": "Samoa",
    "AS": "Samoa Americana",
    "BL": "San Bartolomé",
    "KN": "San Cristóbal y Nieves",
    "SM": "San Marino",
    "MF": "San Martín",
    "PM": "San Pedro y Miquelón",
    "VC": "San Vicente y las Granadinas",
    "SH": "Santa Elena, Ascensión y Tristán de Acuña",
    "LC": "Santa Lucía",
    "ST": "Santo Tomé y Príncipe",
    "SN": "Senegal",
    "RS": "Serbia",
    "SC": "Seychelles",
    "SL": "Sierra Leona",
    "SG": "Singapur",
    "SX": "Sint Maarten",
    "SY": "Siria",
    "SO": "Somalia",
    "LK": "Sri Lanka",
    "SZ": "Suazilandia",
    "ZA": "Sudáfrica",
    "SD": "Sudán",
    "SS": "Sudán del Sur",
    "SE": "Suecia",
    "CH": "Suiza",
    "SR": "Surinam",
    "SJ": "Svalbard y Jan Mayen",
    "TH": "Tailandia",
    "TW": "Taiwán (República de China)",
    "TZ": "Tanzania",
    "TJ": "Tayikistán",
    "IO": "Territorio Británico del Océano Índico",
    "TF": "Tierras Australes y Antárticas Francesas",
    "TL": "Timor Oriental",
    "TG": "Togo",
    "TK": "Tokelau",
    "TO": "Tonga",
    "TT": "Trinidad y Tobago",
    "TN": "Túnez",
    "TM": "Turkmenistán",
    "TR": "Turquía",
    "TV": "Tuvalu",
    "UA": "Ucrania",
    "UG": "Uganda",
    "UY": "Uruguay",
    "UZ": "Uzbekistán",
    "VU": "Vanuatu",
    "VA": "Vaticano, Ciudad del",
    "VE": "Venezuela",
    "VN": "Vietnam",
    "WF": "Wallis y Futuna",
    "YE": "Yemen",
    "DJ": "Yibuti",
    "ZM": "Zambia",
    "ZW": "Zimbabue",
}

tipo_ambiente = {
    "PRODUCCION": "1",
    "PRUEBA": "2",
}

class DianDocument(models.Model):
    _inherit = "dian.document"
    message_json = fields.Json()
    message = fields.Html(compute="_compute_message")
    invoice_id = fields.Many2one(comodel_name='ir.attachment', string="XML Factura")
    response_id = fields.Many2one(comodel_name='ir.attachment', string="Respuesta DIAN")
    attachment_id = fields.Many2one(comodel_name='ir.attachment', string="Attached DIAN")
 
    
    @api.depends('message_json')
    def _compute_message(self):
        for doc in self:
            if not doc.message_json or not isinstance(doc.message_json, dict):
                doc.message = "No hay información de mensaje disponible"
                continue

            msg = html_escape(doc.message_json.get('status', ""))
            
            if doc.message_json.get('errors'):
                errors = doc.message_json['errors']
                if isinstance(errors, list):
                    error_list = Markup().join(
                        Markup("<li>%s</li>") % html_escape(error) for error in errors
                    )
                    msg += Markup("<ul>{errors}</ul>").format(errors=error_list)
                elif isinstance(errors, str):
                    msg += Markup("<ul><li>%s</li></ul>") % html_escape(errors)
                else:
                    msg += Markup("<ul><li>Error desconocido</li></ul>")

            doc.message = msg

    @api.model
    def _parse_errors(self, root):
        """ Returns a list containing the errors/warnings from a DIAN response """
        return [node.text for node in root.findall(".//{*}ErrorMessage/{*}string")]

    @api.model
    def _build_message(self, root):
        msg = {'status': False, 'errors': []}
        fault = root.find('.//{*}Fault/{*}Reason/{*}Text')
        if fault is not None and fault.text:
            msg['status'] = fault.text + " (Esto podría deberse al uso de certificados incorrectos.)"
        status = root.find('.//{*}StatusDescription')
        if status is not None and status.text:
            msg['status'] = status.text
        msg['errors'] = self._parse_errors(root)
        return msg

    def _action_get__xml(self,name=False,cufe=False):
        """ Fetch the status of a document sent to 'SendTestSetAsync' using the 'GetStatusZip' webservice. """
        self.ensure_one()
        if not cufe:
            cufe = self.cufe
            name = f'DIAN_invoice_.xml'
        response = xml_utils._build_and_send_request(
            self,
            payload={
                'track_id': cufe,
                'soap_body_template': "l10n_co_e-invoice.get_xml",
            },
            service="GetXmlByDocumentKey",
            company=self.document_id.company_id,
        )
        
        if response['status_code'] == 200:
            root = etree.fromstring(response['response'])
            self.message_json = self._build_message(root)
            namespaces = {
                's': 'http://www.w3.org/2003/05/soap-envelope',
                'b': 'http://schemas.datacontract.org/2004/07/EventResponse'
            }
            code = root.xpath('//s:Body//b:Code/text()', namespaces=namespaces)
            message = root.xpath('//s:Body//b:Message/text()', namespaces=namespaces)
            xml_bytes_base64 = root.xpath('//s:Body//b:XmlBytesBase64/text()', namespaces=namespaces)
            if xml_bytes_base64:
                base64_content = xml_bytes_base64[0]   
                decoded_content = base64.b64decode(base64_content)
                attachment_vals = {
                    'name': name,
                    'type': 'binary',
                    'datas': base64.b64encode(decoded_content),
                    'res_model': self._name,
                    'res_id': self.id,
                }
                attachment = self.env['ir.attachment'].create(attachment_vals)
                self.write({'invoice_id': attachment.id, 'xml_document': decoded_content, })
        elif response['status_code']:
            raise UserError(_("El servidor de la DIAN arrojó error (Codigo %s)", response['status_code']))
        else:
            raise UserError(_("El servidor DIAN no respondió."))

    def _get_qr_co(self):
        """
        """
        self.ensure_one()
        root = etree.fromstring(self.invoice_id.raw)
        nsmap = {k: v for k, v in root.nsmap.items() if k}  # empty namespace prefix is not supported for XPaths
        supplier_company_id = root.findtext('./cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID', namespaces=nsmap)
        customer_company_id = root.findtext('./cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID', namespaces=nsmap)
        line_extension_amount = root.findtext('./cac:LegalMonetaryTotal/cbc:LineExtensionAmount', namespaces=nsmap)
        tax_amount_01 = sum(float(x) for x in root.xpath('./cac:TaxTotal[.//cbc:ID/text()="01"]/cbc:TaxAmount/text()', namespaces=nsmap))
        payable_amount = root.findtext('./cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces=nsmap)
        identifier = root.findtext('./cbc:UUID', namespaces=nsmap)
        qr_code = root.findtext('./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sts:DianExtensions/sts:QRCode', namespaces=nsmap)
        vals = {
            'NumDS': root.findtext('./cbc:ID', namespaces=nsmap),
            'FecFD': root.findtext('./cbc:IssueDate', namespaces=nsmap),
            'HorDS': root.findtext('./cbc:IssueTime', namespaces=nsmap),
        }
        if self.move_type in ('in_invoice', 'in_refund'):
            vals.update({
                'NumSNO': supplier_company_id,
                'DocABS': customer_company_id,
                'ValDS': line_extension_amount,
                'ValIva': tax_amount_01,
                'ValTolDS': payable_amount,
                'CUDS': identifier,
                'QRCode': qr_code,
            })
        else:
            vals.update({
                'NitFac': supplier_company_id,
                'DocAdq': customer_company_id,
                'ValFac': line_extension_amount,
                'ValIva': tax_amount_01,
                'ValOtroIm': sum(float(x) for x in root.xpath('./cac:TaxTotal[.//cbc:ID/text()!="01"]/cbc:TaxAmount/text()', namespaces=nsmap)),
                'ValTolFac': payable_amount,
                'CUFE': identifier,
                'QRCode': qr_code,
            })
        qr_code_text = "\n".join(f"{k}: {v}" for k, v in vals.items())
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_code_text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Convertir la imagen a base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_image = base64.b64encode(buffered.getvalue()).decode()

        return qr_code_text, qr_code_image

    def generate_and_save_qr_code(self):
        for record in self:
            qr_code_text, qr_code_image = record._l10n_co_dian_get_invoice_report_qr_code_value()
            record.write({
                'QR_code': qr_code_image,
                'qr_data': qr_code_text,
            })

    def format_float(self, amount, precision_digits):
        if amount is None:
            return None
        return float_repr(float_round(amount, precision_digits), precision_digits)
    
class Invoice(models.Model):
    _inherit = "account.move"
  


    def _get_profile_id(self, data_header_doc):
        if data_header_doc.move_type == "out_invoice" and not data_header_doc.is_debit_note:
            return "DIAN 2.1: Factura Electrónica de Venta"
        elif data_header_doc.is_debit_note:
            return "DIAN 2.1: Nota Débito de Factura Electrónica de Venta"
        elif self.move_type == 'out_refund':
            return "DIAN 2.1: Nota Crédito de Factura Electrónica de Venta"
        elif self.move_type == 'in_invoice' and self.is_debit_note == False:
            return "DIAN 2.1: documento soporte en adquisiciones efectuadas a no obligados a facturar."
        elif self.move_type == 'in_invoice' and self.is_debit_note or self.debit_origin_id:
            raise UserError('Los documentos Soporte No tiene Nota Debito Habilitadas para su emisión a la DIAN, Por Favor Emitir Otro documento Soporte')
        elif self.move_type == 'in_refund':
            return "DIAN 2.1: Nota de ajuste al documento soporte en adquisiciones efectuadas a sujetos no obligados a expedir factura o documento equivalente"

    def _get_customization_id(self, data_header_doc):
        if data_header_doc.move_type == "out_refund":
            return "22" if data_header_doc.document_without_reference else "20"
        elif data_header_doc.is_debit_note:
            return "32" if data_header_doc.document_without_reference else "30"
        elif data_header_doc.move_type in ('in_invoice', 'in_refund'):
            if data_header_doc.partner_id.type_residence == "si":
                return '10'
            elif self.partner_id.type_residence == "no":
                return '11'
            else:
                return '10' if data_header_doc.partner_id.country_code == 'CO' else '11'
        return data_header_doc.fe_operation_type
    
    def _get_invoice_payment_exchange_rate_vals(self, invoice):
        if invoice.currency_id.name != "COP":
            rate = invoice.amount_total_signed / (invoice.amount_total or 1)
            return {
                'source_currency_code': "COP",
                'source_currency_base_rate': self.format_float(rate, 6),  # 6 decimals are allowed
                'target_currency_code': invoice.currency_id.name,
                'target_currency_base_rate': "1.00",
                'calculation_rate': self.format_float(rate, 6),  # 6 decimals are allowed
                'date': invoice.invoice_date,
            }
        return {}

    def _get_invoice_payment_means_vals_list(self, invoice):
        # OVERRIDE account.edi.xml.ubl_20
        return [{
            'id': '1' if invoice.payment_format != 'Credito' else '2',
            'payment_means_code': invoice.method_payment_id.code,
            'payment_due_date': invoice.invoice_date_due,
            'payment_id_vals': [invoice.payment_reference or invoice.name],
        }]

    def _generate_software_security_code(self, software_identification_code, software_pin, NroDocumento):
        software_security_code = hashlib.sha384(
            (software_identification_code + software_pin + NroDocumento).encode()
        )
        software_security_code = software_security_code.hexdigest()
        return software_security_code

    def _get_url_qr_code(self, company):
        if company.production:
            return 'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey'
        else:
            return 'https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey'
        

    @api.model
    def _get_dian_constants(self, data_header_doc):
        
        def format_domestic_phone_number(phone):
            phone = (phone or '').replace(' ', '')
            if len(phone) <= 10:
                return phone
            phone = re.sub(r'^(\+57|0057)', '', phone)
            return phone[:10]
    
        def _dian_get_identifier_vals(invoice, invoice_vals):
            def format_float(amount, precision_digits=invoice_vals['currency_dp']):
                return self.format_float(amount, precision_digits)
            if invoice.move_type == 'out_invoice' and not invoice.is_debit_note:
                key =  invoice_vals['TechnicalKey']
            else:
                key = invoice.company_id.software_pin
            tax_computed_values = {tax: value['total'] for tax, value in invoice_vals['tax_total_values'].items()}
            vals = {
                'invoice_id': invoice_vals['InvoiceID'],
                'issue_date': invoice_vals['issue_date'],
                'issue_time': invoice_vals['issue_time'], 
                'line_extension_amount': invoice_vals['TotalLineExtensionAmount'],
                'tax_code_01': '01',
                'ValImp1': format_float(tax_computed_values.get('01', 0)),
                'tax_code_04': '04',
                'ValImp2': format_float(tax_computed_values.get('04', 0)),
                'tax_code_03': '03',
                'ValImp3': format_float(tax_computed_values.get('03', 0)),
                'ValTotFac': invoice_vals['PayableAmount'],
                'supplier_company_id': invoice_vals['SupplierID'],
                'customer_company_id': invoice_vals['IDAdquiriente'],
                'key': key or 'missing_key',
                'profile_execution_id':['ProfileExecutionID'],
            }
            if invoice.move_type == 'in_invoice':
                [vals.pop(k) for k in ('tax_code_04', 'ValImp2', 'tax_code_03', 'ValImp3')]
            return {k: str(v) for k, v in vals.items()} 
        data_resolution = self._get_resolution_dian(data_header_doc)
        company = data_header_doc.company_id
        is_purchase = data_header_doc.journal_id.type == "purchase"
        partner = data_header_doc.partner_id if is_purchase else company.partner_id
        customer = data_header_doc.partner_id if not is_purchase else company.partner_id
        reversed_move = data_header_doc.reversed_entry_id
        original_invoice = data_header_doc.debit_origin_id
        resultado = data_header_doc.generar_invoice_tax()
        dian_constants = defaultdict(str)
        dian_constants.update({
            "InvoiceID":data_header_doc.name,
            'ret_total_values':resultado['ret_total_values'],
            'tax_total_values':resultado['tax_total_values'],
            'invoice_lines':resultado['invoice_lines'],
            "TotalLineExtensionAmount": resultado['line_extension_amount'],
            "TotalTaxInclusiveAmount": resultado['tax_inclusive_amount'],
            "TotalTaxExclusiveAmount": resultado['tax_exclusive_amount'],
            "PayableAmount": resultado['payable_amount'],
            "Notes": resultado['invoice_note'],
            #NAME
            "FileNameXML": self._generate_xml_filename_new(data_resolution, company.partner_id.vat_co, data_header_doc.move_type, data_header_doc.debit_origin_id,data_header_doc.sequence_number),
            "FileNameZIP": self._generate_zip_filename_new(data_resolution, company.partner_id.vat_co,  data_header_doc.move_type, data_header_doc.debit_origin_id,data_header_doc.sequence_number),
            #RESOLUCION
            "InvoiceAuthorization": data_resolution["InvoiceAuthorization"],
            "StartDate": data_resolution["StartDate"],
            "EndDate": data_resolution["EndDate"],
            "Prefix": self._get_prefix(data_resolution, data_header_doc),
            "From": data_resolution["From"],
            "To": data_resolution["To"],
            "Nonce": self._generate_nonce(data_resolution["InvoiceID"], company.seed_code),
            "TechnicalKey": data_resolution["TechnicalKey"],
            "InvoiceTypeCode": self._get_doctype(data_header_doc.move_type, data_header_doc.debit_origin_id, False),
            "CreditNoteTypeCode": self._get_doctype(data_header_doc.move_type, data_header_doc.debit_origin_id, False),
            "DebitNoteTypeCode": self._get_doctype(data_header_doc.move_type, data_header_doc.debit_origin_id, False),
            #payment
            'PaymentMeansID': '1' if data_header_doc.payment_format != 'Credito' else '2',
            'PaymentMeansCode': data_header_doc.method_payment_id.code or "ZZ",
            'PaymentDueDate': data_header_doc.invoice_date_due,
            'payment_id_vals': [data_header_doc.payment_reference or data_header_doc.name],
            'currency_dp': self._get_currency_decimal_places(company.currency_id),
            #company
            "document_repository": company.document_repository,
            "Username": company.software_identification_code,
            "Password": hashlib.new("sha256", company.password_environment.encode()).hexdigest(),
            "IdentificationCode": "CO",
            "SoftwareProviderID": company.partner_id.vat_co or "",
            "SoftwareProviderSchemeID": company.partner_id.vat_vd,
            "ProviderID": partner.vat_co or "",
            "SoftwareID": company.software_identification_code,
            'SoftwareSecurityCode': self._generate_software_security_code(
                company.software_identification_code,
                company.software_pin,
                data_header_doc.name,
            ),
            "source_currency_name": company.currency_id.name,
            "PINSoftware": company.software_pin,
            "SeedCode": company.seed_code,
            "UBLVersionID": "UBL 2.1",
            "ProfileID": self._get_profile_id(data_header_doc),
            "CustomizationID": self._get_customization_id(data_header_doc),
            "ProfileExecutionID": tipo_ambiente["PRODUCCION"] if company.production else tipo_ambiente["PRUEBA"],
            "LineCountNumeric": self._get_lines_invoice(data_header_doc.id),
            "sequence_number": data_header_doc.sequence_number,
            "sequence_prefix": data_header_doc.sequence_prefix,
            #Supplier DIAN DATA
            "SupplierAdditionalAccountID": "1" if partner.is_company else "2",
            "SupplierID": partner.vat_co or "",
            "SupplierSchemeID": self._get_document_type_code(partner.l10n_co_document_code),
            "SupplierPartyName": self._replace_character_especial(partner.name),
            "SupplierDepartment": partner.city_id.state_id.name.title() if partner.city_id else "",
            "SupplierCityCode": partner.city_id.code_dian if partner.city_id else "",
            "SupplierCountrySubentity": partner.city_id.state_id.name.title() if partner.city_id else "",
            "SupplierCityName": partner.city_id.name.title() if partner.city_id else partner.city,
            "SupplierPostal": partner.zip,
            "SupplierPartyPhone": format_domestic_phone_number(partner.phone),
            "SupplierCountrySubentityCode": partner.city_id.code_dian[:2] if partner.city_id else "",
            "IndustryClassificationCode": partner.ciiu_ids[0].code if partner.ciiu_ids else "",
            "SupplierCountryCode": partner.country_id.code,
            "SupplierCountryName": COUNTRIES_ES[partner.country_id.code],
            "SupplierLine": partner.street,
            "SupplierRegistrationName": company.trade_name or company.name,
            "schemeID": partner.vat_vd,
            "SupplierElectronicMail": partner.email,
            "SupplierTaxLevelCode": self._get_partner_fiscal_responsability_code(partner.id),
            "Certificate": company.digital_certificate,
            "NitSinDV": partner.vat_co,
            "CertificateKey": company.certificate_key,
            "archivo_pem": company.pem,
            "archivo_certificado": company.certificate,
            "CertDigestDigestValue": data_header_doc.diancode_id._generate_CertDigestDigestValue(),
            "IssuerName": company.issuer_name,
            "SerialNumber": company.serial_number,
            "TaxSchemeID": partner.tribute_id.code,
            "TaxSchemeName": partner.tribute_id.name,
            "Currency": company.currency_id.id,
            "CurrencyID": data_header_doc.currency_id.name,
            "SupplierCityNameSubentity": partner.city_id.name.title() if partner.city_id else partner.city,
            "DeliveryAddress": getattr(partner, "partner_shipping_id", partner).street,
            "URLQRCode": self._get_url_qr_code(company),
            'issue_date': data_header_doc.fecha_xml.date().isoformat(),
            'issue_time': data_header_doc.fecha_xml.strftime("%H:%M:%S-05:00"),
            # Cliente Campos
            "CustomerTaxSchemeID": customer.tribute_id.code,
            "CustomerTaxSchemeName": customer.tribute_id.name,
            "CustomerAdditionalAccountID": "1" if customer.is_company else "2",
            "IDAdquiriente": customer.vat_co or "",
            "SchemeNameAdquiriente": str(self._get_document_type_code(customer.l10n_co_document_code)),
            "SchemeIDAdquiriente": customer.vat_vd,
            "CustomerID": customer.vat_co or "",
            "CustomerSchemeID": str(self._get_document_type_code(customer.l10n_co_document_code)),
            "CustomerPartyName": self._replace_character_especial(customer.name),
            "CustomerPostal": self._replace_character_especial(customer.zip),
            "CustomerElectronicPhone": format_domestic_phone_number(customer.phone),
            "CustomerDepartment": customer.state_id.name if customer.state_id else "",
            "CustomerCityCode": customer.city_id.code_dian if customer.city_id else "",
            "CustomerCityName": customer.city_id.name.title() if customer.city_id else customer.city,
            "CustomerCountrySubentity": customer.state_id.name if customer.state_id else "",
            "CustomerCountrySubentityCode": customer.city_id.code_dian[:2] if customer.city_id else "",
            "CustomerCountryCode": customer.country_id.code,
            "CustomerCountryName": COUNTRIES_ES[customer.country_id.code], #customer.country_id.name,
            "CustomerAddressLine": customer.street,
            "CustomerTaxLevelCode": self._get_partner_fiscal_responsability_code(customer.id),
            "CustomerRegistrationName": self._replace_character_especial(customer.name),
            "CustomerEmail": customer.email or "",
            "CustomerLine": customer.street,
            "CustomerElectronicMail": customer.email,
            "Firstname": self._replace_character_especial(customer.name),
            "document_id": self,
            #currency
            "CalculationRate": self._get_calculation_rate(data_header_doc),
            "DateRate": data_header_doc.invoice_date,
            "CurrencyID": data_header_doc.currency_id.name,
         })
        if reversed_move:
            dian_constants.update({
                'reverse_reference_id': reversed_move.name,
                'reverse_response_code': data_header_doc.concepto_credit_note,
                'reverse_description': dict(data_header_doc._fields['concepto_credit_note'].selection).get(data_header_doc.concepto_credit_note),
                'billing_reference_vals_id': reversed_move.name,
                'billing_reference_vals_uuid': reversed_move.cufe,
                'billing_reference_vals_uuid_attrs': {"schemeName": "CUFE-SHA384"},
                'billing_reference_vals_issue_date': reversed_move.invoice_date.isoformat(),
            })
        if original_invoice:
            dian_constants.update({
                'discrepancy_reference_id': original_invoice.name,
                'discrepancy_response_code': data_header_doc.concept_debit_note,
                'discrepancy_description': dict(data_header_doc._fields['concept_debit_note'].selection).get(data_header_doc.concept_debit_note),
                'discrepancy_id': original_invoice.name,
                'discrepancy_uuid': original_invoice.cufe,
                'discrepancy_uuid_attrs': {"schemeName": "CUFE-SHA384"},
                'discrepancy_issue_date': original_invoice.invoice_date.isoformat(),
            })
        if not partner.city_id and partner.country_id.code == "CO":
            raise UserError(_("El Cliente / Proveedor {} no tiene ciudad establecida".format(partner.name)))
        identifier_vals = _dian_get_identifier_vals(data_header_doc, dian_constants)
        cufe_cude_cuds_vals = "".join(str(v) for v in identifier_vals.values() if v is not None)
        dian_constants.update({
            'UUID' : sha384(cufe_cude_cuds_vals.encode()).hexdigest(),  #
            'note_vals': cufe_cude_cuds_vals})
        return dian_constants
    
    def format_float(self, amount, precision_digits):
        if amount is None:
            return None
        return float_repr(float_round(amount, precision_digits), precision_digits)
    
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
            elif self.fe_type == "02":
                docdian = "02"
        if doctype == "out_refund":
            docdian = "91"
        if doctype == "out_invoice" and is_debit_note:
            docdian = "92"
        return docdian

    def _get_currency_decimal_places(self, currency_id):
        return currency_id.decimal_places
    
    def send_dian_document_new(self):
        for rec in self:
            rec.diancode_id.unlink()
            document_dian = rec.diancode_id
            if not document_dian and rec.state == "posted":
                if rec.move_type in ("out_invoice", "in_invoice") and not rec.is_debit_note:
                    document_dian = self.env["dian.document"].sudo().create({"document_id": rec.id, "document_type": "f"})
                elif rec.move_type in ("out_refund", "in_refund"):
                    document_dian = self.env["dian.document"].sudo().create({"document_id": rec.id, "document_type": "c"})
                elif rec.move_type in ("out_invoice", "in_invoice") and rec.debit_origin_id:
                    document_dian = self.env["dian.document"].sudo().create({"document_id": rec.id, "document_type": "d"})
            rec.diancode_id = document_dian.id
            document_type = document_dian.document_type
            document_dian.send_pending_dian(document_dian, document_type,rec)
        return True
 
    def _dian_get_operation_mode(self, invoice):
        """Looks for the desired operation mode record based on the mode type"""
        mode = 'invoice' if invoice.is_sale_document() else 'bill'
        if mode == 'invoice':
            return "DIAN 2.1: Electronic Invoices"
        else:
            return "DIAN 2.1: Support Documents"
        
    def _dian_get_qr_code_url(self, invoice, identifier):
        """ Returns the value used to fill the sts:DianExtensions/sts:QRCode node """
        if not invoice.company_id.production:
            url = 'https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey='
        else:
            url = 'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey='
        return url + identifier



    def _dian_sign_xml(self, xml, invoice):
        errors = []
        root = etree.fromstring(xml)
        company = invoice.company_id
        certificate_file = company.certificate_file
        certificate_password = company.certificate_key
        if not certificate_file:
            raise ValidationError("No se encontró un archivo de certificado para esta compañía")
        p12_data = base64.b64decode(certificate_file)
        private_key, main_cert, additional_certs = xml_utils._extract_from_p12(p12_data, certificate_password)
        if not main_cert:
            raise ValidationError("No se pudo extraer el certificado del archivo P12")
        # x509_certificates = [{
        #     'x509_issuer_description': main_cert.issuer.rfc4514_string(),
        #     'x509_serial_number': main_cert.serial_number,
        # }]
        all_certs = [main_cert] + additional_certs
        operation_mode = self._dian_get_operation_mode(invoice)
        x509_certificates = []
        for cert in all_certs:
            x509_certificates.append({
                'x509_issuer_description': company.issuer_name,
                'x509_serial_number': cert.serial_number,
            })
        sts_namespace = ("http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" 
                         if invoice.is_debit_note or invoice.move_type == 'out_refund' 
                         else "dian:gov:co:facturaelectronica:Structures-2-1")
        uuid = root.findtext('./cbc:UUID', namespaces=root.nsmap)
        qr_code_val = self._dian_get_qr_code_url(invoice, uuid if uuid is not None else self.cufe)
        data_resolution = self._get_resolution_dian(invoice)
        signature_vals = {
            'record': invoice,
            "InvoiceAuthorization": data_resolution["InvoiceAuthorization"],
            "StartDate": data_resolution["StartDate"],
            "EndDate": data_resolution["EndDate"],
            "Prefix": self._get_prefix(data_resolution, invoice),
            "From": data_resolution["From"],
            "To": data_resolution["To"],
            "Nonce": self._generate_nonce(data_resolution["InvoiceID"], company.seed_code),
            "TechnicalKey": data_resolution["TechnicalKey"],
            'sts_namespace': sts_namespace,
            'provider_check_digit': company.partner_id.vat_vd,
            'provider_id': company.partner_id.vat_co,
            'software_id': company.software_identification_code,
            'software_security_code': self._generate_software_security_code(
                company.software_identification_code,
                company.software_pin,
                invoice.name,
            ),
            'qr_code_val': qr_code_val, 
            'document_id': "xmldsig-" + str(xml_utils._uuid1()),
            'key_info_id': "xmldsig-" + str(xml_utils._uuid1()) + "-keyinfo",
            'x509_certificate': encodebytes(main_cert.public_bytes(encoding=serialization.Encoding.DER)).decode(),
            'x509_certificates': x509_certificates,
            'signature_value': 'to be filled later',
            'signing_time': fields.datetime.now(tz=timezone('America/Bogota')).isoformat(timespec='milliseconds'),
            'sigcertif_digest': b64encode(main_cert.fingerprint(hashes.SHA256())).decode(),
            'claimed_role': "supplier",
        }
        extensions = self.env['ir.qweb']._render('l10n_co_e-invoice.ubl_extension_dian', signature_vals)
        extensions = cleanup_xml_node(extensions, remove_blank_nodes=False)
        root.insert(0, extensions)
        xml_utils._remove_tail_and_text_in_hierarchy(root)
        # Hash and sign
        xml_utils._reference_digests(extensions.find(".//ds:SignedInfo", {'ds': 'http://www.w3.org/2000/09/xmldsig#'}))
        xml_utils._fill_signature(extensions.find(".//ds:Signature", {'ds': 'http://www.w3.org/2000/09/xmldsig#'}), private_key)
        return etree.tostring(root, encoding='UTF-8'), errors

    @api.model
    def _send_to_dian(self, xml, move,dian_constants):
        """ Send an xml to DIAN.
        If the Certification Process is activated, use the dedicated 'SendTestSetAsync' (asynchronous) webservice,
        otherwise, use the 'SendBillSync' (synchronous) webservice.

        :return: a l10n_co_dian.document
        """
        # Zip the xml
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
            for att in [{'name': dian_constants['FileNameXML'], 'content': xml}]:
                zipfile_obj.writestr(att['name'], att['content'])
        zipped_content = buffer.getvalue()

        if not move.company_id.production:
            document_vals = self._send_test_set_async(zipped_content, move,dian_constants['FileNameZIP'])
        else:
            document_vals = self._send_bill_sync(zipped_content, move,dian_constants['FileNameZIP'])
        move.diancode_id.write(document_vals)

    @api.model
    def _send_test_set_async(self, zipped_content, move,name):
        """ Send the document to the 'SendTestSetAsync' (asynchronous) webservice.
        NB: later, need to fetch the result by calling the 'GetStatusZip' webservice.
        """
        operation_mode = self.env['account.edi.xml.ubl_dian']._dian_get_operation_mode(move)
        response = xml_utils._build_and_send_request(
            self,
            payload={
                'file_name': name,
                'content_file': b64encode(zipped_content).decode(),
                'test_set_id': operation_mode.dian_testing_id,
                'soap_body_template': "l10n_co_e-invoice.send_test_set_async",
            },
            service="SendTestSetAsync",
            company=move.company_id,
        )
        if not response['response']:
            return {
                'state': 'error',
                'message_json': {'status': _("The DIAN server did not respond.")},
            }
        root = etree.fromstring(response['response'])
        if response['status_code'] != 200:
            return {
                'state': 'error',
                'message_json': self._build_message(root),
            }
        zip_key = root.findtext('.//{*}ZipKey')
        if zip_key:
            return {
                'state': 'por_validar',
                'message_json': {'status': _("Invoice is being processed by the DIAN.")},
                'zip_key': zip_key,
            }
        return {
            'state': 'error',
            'message_json': {'errors': [node.text for node in root.findall('.//{*}ProcessedMessage')]},
        }

    @api.model
    def _send_bill_sync(self, zipped_content, move,name):
        """ Send the document to the 'SendBillSync' (synchronous) webservice. """
        response = xml_utils._build_and_send_request(
            self,
            payload={
                'file_name': name,
                'content_file': b64encode(zipped_content).decode(),
                'soap_body_template': "l10n_co_e-invoice.send_bill_sync",
            },
            service="SendBillSync",
            company=move.company_id,
        )
        if not response['response']:
            return {
                'state': 'error',
                'message_json': {'status': _("The DIAN server did not respond.")},
            }
        root = etree.fromstring(response['response'])
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
            attachment_vals = {
                'name': file_name,
                'type': 'binary',
                'datas': base64.b64encode(decoded_content),
                'res_model': move.diancode_id._name,
                'res_id': move.diancode_id.id,
            }
            attachment = self.env['ir.attachment'].create(attachment_vals)
            move.diancode_id.write({'response_id': attachment.id})

        if response['status_code'] != 200:
            return {
                'state': 'error',
                'message_json': self._build_message(root),
            }
        elif root.findtext('.//{*}IsValid') != 'true':
            is_previously_processed = False
            error_descriptions = []
            for error in error_message:
                error_text = error.text
                error_descriptions.append(error_text)
                if 'Regla: 90' in error_text and 'Documento procesado anteriormente' in error_text:
                    is_previously_processed = True
                    move.diancode_id.write({'cufe': document_key, 'state': 'exitoso'})
            if is_previously_processed:
                self._action_get__xml(file_name,document_key)
                return{'cufe': document_key, 'state': 'exitoso','message_json': self._build_message(root)}
        return {
            'state': 'exitoso' if root.findtext('.//{*}IsValid') == 'true' else 'error',
            'message_json': self._build_message(root),
        }
        
        
        
    @api.model
    def _generate_xml_filename_new(self, data_resolution, NitSinDV, doctype, is_debit_note, number):
        if doctype == "out_invoice" and not is_debit_note:
            docdian = "fv"
        elif doctype == "out_refund":
            docdian = "nc"
        elif doctype == "out_invoice" and is_debit_note:
            docdian = "nd"
        dian_code_hex = self.IntToHex(number)
        dian_code_hex.zfill(10)
        # TODO: Revisar el secuenciador segun la norma
        file_name_xml = docdian + NitSinDV.zfill(10) + dian_code_hex.zfill(10) + ".xml"
        return file_name_xml

    def IntToHex(self, dian_code_int):
        dian_code_hex = "%02x" % dian_code_int
        return dian_code_hex

    @api.model
    def _generate_zip_filename_new(self, data_resolution, NitSinDV, doctype, is_debit_note, number):
        if doctype == "out_invoice" and not is_debit_note:
            docdian = "fv"
        elif doctype == "out_refund":
            docdian = "nc"
        elif doctype == "out_invoice" and is_debit_note:
            docdian = "nd"
        dian_code_hex = self.IntToHex(number)
        dian_code_hex.zfill(10)
        file_name_zip = docdian + NitSinDV.zfill(10) + dian_code_hex.zfill(10) + ".zip"
        return file_name_zip

    def action_get_attached_invoices(self):
        for doc in self:
            doc._get_attached_invoices()

    def _get_attached_invoices(self):
        # Obtener los datos de los adjuntos
        invoice_attachment = self.invoice_id
        response_attachment = self.response_id
        # Procesar el XML de la factura
        invoice_xml_escaped = base64.b64decode(invoice_attachment.datas).decode('UTF-8')
        invoice_xml = html.unescape(invoice_xml_escaped)
        invoice_root = etree.fromstring(invoice_xml.encode('UTF-8'))
        
        # Procesar el XML de la respuesta
        response_xml_escaped = base64.b64decode(response_attachment.datas).decode('UTF-8')
        response_xml = html.unescape(response_xml_escaped)
        response_root = etree.fromstring(response_xml.encode('UTF-8'))
    
        # Definir namespaces
        namespaces = {
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
            'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'
        }
        # Función auxiliar para extraer texto de un xpath
        def xpath_text(root, xpath):
            elements = root.xpath(xpath, namespaces=namespaces)
            return elements[0].text if elements else ''
        document_xml_string = etree.tostring(invoice_root, encoding='UTF-8', pretty_print=True)
        response_xml_string = etree.tostring(response_root, encoding='UTF-8', pretty_print=True)
        insert_cdata = f'<![CDATA[<?xml version="1.0" encoding="UTF-8"?>{document_xml_string}]]>'
        insert_response_cdata = f'<![CDATA[<?xml version="1.0" encoding="UTF-8"?>{response_xml_string}]]>'
        # Extraer datos de la factura
        invoice_data = {
            'UBLVersionID': xpath_text(invoice_root, '//cbc:UBLVersionID'),
            'CustomizationID': xpath_text(invoice_root, '//cbc:CustomizationID'),
            'ProfileID': xpath_text(invoice_root, '//cbc:ProfileID'),
            'ProfileExecutionID': xpath_text(invoice_root, '//cbc:ProfileExecutionID'),
            'InvoiceID': xpath_text(invoice_root, '//cbc:ID'),
            'IssueDate': xpath_text(invoice_root, '//cbc:IssueDate'),
            'IssueTime': xpath_text(invoice_root, '//cbc:IssueTime'),
            'SupplierPartyName': xpath_text(invoice_root, '//cac:AccountingSupplierParty//cbc:RegistrationName'),
            'schemeID': invoice_root.xpath('//cac:AccountingSupplierParty//cbc:CompanyID/@schemeID', namespaces=namespaces)[0] if invoice_root.xpath('//cac:AccountingSupplierParty//cbc:CompanyID/@schemeID', namespaces=namespaces) else '',
            'ProviderID': xpath_text(invoice_root, '//cac:AccountingSupplierParty//cbc:CompanyID'),
            'SoftwareProviderID': xpath_text(invoice_root, '//sts:SoftwareProvider/sts:ProviderID'),
            'SoftwareProviderSchemeID': invoice_root.xpath('//sts:SoftwareProvider/sts:ProviderID/@schemeID', namespaces=namespaces)[0] if invoice_root.xpath('//sts:SoftwareProvider/sts:ProviderID/@schemeID', namespaces=namespaces) else '',
            'SupplierTaxLevelCode': xpath_text(invoice_root, '//cac:AccountingSupplierParty//cbc:TaxLevelCode'),
            'TaxSchemeID': xpath_text(invoice_root, '//cac:AccountingSupplierParty//cac:PartyTaxScheme/cac:TaxScheme/cbc:ID'),
            'TaxSchemeName': xpath_text(invoice_root, '//cac:AccountingSupplierParty//cac:PartyTaxScheme/cac:TaxScheme/cbc:Name'),
            'CustomerPartyName': xpath_text(invoice_root, '//cac:AccountingCustomerParty//cbc:RegistrationName'),
            'CustomerschemeID': invoice_root.xpath('//cac:AccountingCustomerParty//cbc:CompanyID/@schemeID', namespaces=namespaces)[0] if invoice_root.xpath('//cac:AccountingCustomerParty//cbc:CompanyID/@schemeID', namespaces=namespaces) else '',
            'CustomerID': xpath_text(invoice_root, '//cac:AccountingCustomerParty//cbc:CompanyID'),
            'CustomerTaxLevelCode': xpath_text(invoice_root, '//cac:AccountingCustomerParty//cbc:TaxLevelCode'),
            'insert_cdata': insert_cdata,
            'insert_response_cdata': insert_response_cdata,
        }
        
        # Extraer datos de la respuesta
        response_data = {
            'ValidationResultCode': xpath_text(response_root, '//cac:DocumentResponse/cac:Response/cbc:ResponseCode'),
            'ValidationDate': xpath_text(response_root, '//cbc:IssueDate'),
            'ValidationTime': xpath_text(response_root, '//cbc:IssueTime'),
            "InvoiceTypeCode": "99",
        }
        
        # Extraer CUFE
        cufe = xpath_text(invoice_root, '//cbc:UUID')
        
        # Preparar datos para la plantilla
        data_xml_document = {
            **invoice_data,
            **response_data,
            'UUID': cufe,

        }
        xml_file_name = (
                "ad%s" % (self.xml_file_name[6:] if self.xml_file_name else "000000.xml")
            )
        # Renderizar la plantilla
        xml_string = self.env['ir.qweb']._render('l10n_co_e-invoice.attached_document_template', data_xml_document)
        xml_string.replace('&lt;', '<').replace('&gt;', '>')
        # Parsea el XML
        parser = etree.XMLParser(remove_blank_text=True)
        xml_root = etree.fromstring(xml_string, parser)
        # Limpia y formatea el XML
        for elem in xml_root.iter():
            if elem.text is not None:
                elem.text = elem.text.strip()
            if elem.tail is not None:
                elem.tail = elem.tail.strip()
        
        formatted_xml = etree.tostring(xml_root, pretty_print=True, encoding='UTF-8')
        firmado, errors = self._dian_sign_xml(formatted_xml, self)
        resultado_final =  etree.fromstring(firmado, parser)
        for elem in resultado_final.iter():
            if elem.text is not None:
                elem.text = elem.text.strip()
            if elem.tail is not None:
                elem.tail = elem.tail.strip()

        resultado_final = etree.tostring(resultado_final, pretty_print=True, encoding='UTF-8')
        attachment = self.env['ir.attachment'].create({
            'raw': resultado_final,
            'name': xml_file_name,
            'res_id': self.id,
            'res_model': self._name,
        })
        self.diancode_id.attachment_id = attachment
        return True


    def action_get_status(self):
        for doc in self:
            doc._action_get_status()
    
    def _action_get_status(self):
        """ Fetch the status of a document sent to 'SendTestSetAsync' using the 'GetStatus' webservice. """
        self.ensure_one()
        response = xml_utils._build_and_send_request(
            self,
            payload={
                'track_id': self.cufe,
                'soap_body_template': "l10n_co_e-invoice.get_status",
            },
            service="GetStatus",
            company=self.company_id,
        )
        if response['status_code'] == 200:
            root = etree.fromstring(response['response'])
            self.message_json = self._build_message(root)
            if root.findtext('.//{*}IsValid') == 'true':
                self.state = 'exitoso'
            elif not root.findtext('.//{*}StatusCode'):
                self.state = 'por_validar'
            else:
                self.state = 'error'
        elif response['status_code']:
            raise UserError(_("The DIAN server returned an error (code %s)", response['status_code']))
        else:
            raise UserError(_("The DIAN server did not respond."))
        
    def action_get_status_zip(self):
        for doc in self:
            doc._get_status_zip()
    
    def _get_status_zip(self):
        """ Fetch the status of a document sent to 'SendTestSetAsync' using the 'GetStatusZip' webservice. """
        self.ensure_one()
        response = xml_utils._build_and_send_request(
            self,
            payload={
                'track_id': self.cufe,
                'soap_body_template': "l10n_co_e-invoice.get_status_zip",
            },
            service="GetStatusZip",
            company=self.company_id,
        )
        if response['status_code'] == 200:
            root = etree.fromstring(response['response'])
            self.message_json = self._build_message(root)
            if root.findtext('.//{*}IsValid') == 'true':
                self.state = 'exitoso'
            elif not root.findtext('.//{*}StatusCode'):
                self.state = 'por_validar'
            else:
                self.state = 'error'
        elif response['status_code']:
            raise UserError(_("The DIAN server returned an error (code %s)", response['status_code']))
        else:
            raise UserError(_("The DIAN server did not respond."))

    def action_get__xml(self):
        for doc in self:
            doc._action_get__xml()
    
    def _action_get__xml(self,name=False,cufe=False):
        """ Fetch the status of a document sent to 'SendTestSetAsync' using the 'GetStatusZip' webservice. """
        self.ensure_one()
        if not cufe:
            cufe = self.cufe
            name = f'DIAN_invoice_.xml'
        response = xml_utils._build_and_send_request(
            self,
            payload={
                'track_id': cufe,
                'soap_body_template': "l10n_co_e-invoice.get_xml",
            },
            service="GetXmlByDocumentKey",
            company=self.company_id,
        )
        
        if response['status_code'] == 200:
            root = etree.fromstring(response['response'])
            self.message_json = self._build_message(root)
            namespaces = {
                's': 'http://www.w3.org/2003/05/soap-envelope',
                'b': 'http://schemas.datacontract.org/2004/07/EventResponse'
            }
            code = root.xpath('//s:Body//b:Code/text()', namespaces=namespaces)
            message = root.xpath('//s:Body//b:Message/text()', namespaces=namespaces)
            xml_bytes_base64 = root.xpath('//s:Body//b:XmlBytesBase64/text()', namespaces=namespaces)
            if xml_bytes_base64:
                base64_content = xml_bytes_base64[0]
                decoded_content = base64.b64decode(base64_content)
                attachment_vals = {
                    'name': name,
                    'type': 'binary',
                    'datas': base64.b64encode(decoded_content),
                    'res_model': self._name,
                    'res_id': self.id,
                }
                attachment = self.env['ir.attachment'].create(attachment_vals)
                self.diancode_id.write({'invoice_id': attachment.id})
        elif response['status_code']:
            raise UserError(_("The DIAN server returned an error (code %s)", response['status_code']))
        else:
            raise UserError(_("The DIAN server did not respond."))

    @api.model
    def _parse_errors(self, root):
        """ Returns a list containing the errors/warnings from a DIAN response """
        return [node.text for node in root.findall(".//{*}ErrorMessage/{*}string")]

    @api.model
    def _build_message(self, root):
        msg = {'status': False, 'errors': []}
        fault = root.find('.//{*}Fault/{*}Reason/{*}Text')
        if fault is not None and fault.text:
            msg['status'] = fault.text + " (This might be caused by using incorrect certificates)"
        status = root.find('.//{*}StatusDescription')
        if status is not None and status.text:
            msg['status'] = status.text
        msg['errors'] = self._parse_errors(root)
        return msg


    def _get_document_type_code(self, document_type):
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


    @api.model
    def _get_resolution_dian(self, data_header_doc):
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
                nd_sequence = self.env["ir.sequence"].search(
                    [("code", "=", "nota_debito.sequence")],limit=1
                )
                dict_resolution_dian["PrefixND"] = nd_sequence.prefix

        else:
            raise UserError(
                _("El número de resolución DIAN asociada a la factura no existe")
            )
        return dict_resolution_dian

    @api.model
    def _generate_nonce(self, InvoiceID, seed_code):
        nonce = randint(1, seed_code)
        nonce = base64.b64encode((InvoiceID + str(nonce)).encode())
        nonce = nonce.decode()
        return nonce


    def _get_prefix(self, data_resolution, data_header_doc):
        prefix = data_resolution["Prefix"]
        if data_header_doc.move_type != "out_invoice" and data_header_doc.move_type != "in_invoice":
            prefix = data_resolution["PrefixNC"]
        if data_header_doc.is_debit_note:
            prefix = data_resolution["PrefixND"]
        return prefix


    @api.model
    def _get_lines_invoice(self, invoice_id):
        lines = self.env["account.move.line"].search_count([
                ("move_id", "=", invoice_id),
                ("product_id", "!=", None),
                ("display_type", "=", 'product'),
                ("price_subtotal", "!=", 0.00),])
        return lines


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
    
    def _complements_second_decimal_total(self, amount, allow_more_than_two_decimals=False):
        if amount:
            cant_decimals = self.count_decimals(amount)
            if cant_decimals >= 3:
                if allow_more_than_two_decimals:
                    return self.truncate(amount, 3)
                return str("{:.2f}".format(amount))
            return str("{:.2f}".format(amount))
        else:
            return "0.00"

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


    def _replace_character_especial(self, text):
        if text:
            for char, replacement in [('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'), ('"', '&quot;'), ("'", '&apos;')]:
                text = text.replace(char, replacement)
        return text

    def _get_partner_fiscal_responsability_code(self, partner_id):
        partner = self.env["res.partner"].browse(partner_id)
        return ";".join(partner.fiscal_responsability_ids.mapped('code'))