# -*- coding: utf-8 -*-

import hashlib
from os import path
from uuid import uuid4
from base64 import b64encode, b64decode
#from StringIO import StringIO
from io import StringIO ## for Python 3
from io import BytesIO
from datetime import datetime, date, timedelta
from OpenSSL import crypto
import xmlsig
from lxml import etree
#from xades import XAdESContext, template
#from xades.policy import GenericPolicyId
from pytz import timezone
from jinja2 import Environment, FileSystemLoader
from odoo import _, tools
from odoo.exceptions import ValidationError
#from mock import patch
#from unidecode import unidecode
#from qrcode import QRCode, constants
from cryptography.hazmat.primitives.serialization import pkcs12
from base64 import b64decode

import logging
_logger = logging.getLogger(__name__)

def get_xml_soap_with_signature(
        xml_soap_without_signature,
        Id,
        certificate_file,
        certificate_key):
    wsse = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
    wsu = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
    X509v3 = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_soap_without_signature, parser=parser)
    signature_id = "{}".format(Id)
    signature = xmlsig.template.create(
        xmlsig.constants.TransformExclC14N,
        xmlsig.constants.TransformRsaSha256,#solo me ha funcionado con esta
        "SIG-" + signature_id)
    ref = xmlsig.template.add_reference(
        signature,
        xmlsig.constants.TransformSha256,
        uri="#id-" + signature_id)
    xmlsig.template.add_transform(
        ref,
        xmlsig.constants.TransformExclC14N)
    ki = xmlsig.template.ensure_key_info(
        signature,
        name="KI-" + signature_id)
    ctx = xmlsig.SignatureContext()
    ctx.load_pkcs12(get_pkcs12(certificate_file, certificate_key))

    for element in root.iter("{%s}Security" % wsse):
        element.append(signature)

    ki_str = etree.SubElement(
        ki,
        "{%s}SecurityTokenReference" % wsse)
    ki_str.attrib["{%s}Id" % wsu] = "STR-" + signature_id
    ki_str_reference = etree.SubElement(
        ki_str,
        "{%s}Reference" % wsse)
    ki_str_reference.attrib['URI'] = "#X509-" + signature_id
    ki_str_reference.attrib['ValueType'] = X509v3
    ctx.sign(signature)
    ctx.verify(signature)

    return root

def get_xml_soap_values(certificate_file, certificate_key):
    Created = datetime.now().replace(tzinfo=timezone('UTC'))
    Created = Created.astimezone(timezone('UTC'))
    Expires = (Created + timedelta(seconds=60000)).strftime('%Y-%m-%dT%H:%M:%S.001Z')
    Created = Created.strftime('%Y-%m-%dT%H:%M:%S.001Z')
    #https://github.com/mit-dig/idm/blob/master/idm_query_functions.py#L151
    pkcs12 = get_pkcs12(certificate_file, certificate_key)
    cert = pkcs12.get_certificate()
    der = b64encode(crypto.dump_certificate(
        crypto.FILETYPE_ASN1,
        cert)).decode("utf-8", "ignore")

    return {
        'Created': Created,
        'Expires': Expires,
        'Id': uuid4(),
        'BinarySecurityToken': der}

def get_template_xml(values, template_name):
    base_path = path.dirname(path.dirname(__file__))
    env = Environment(loader=FileSystemLoader(path.join(
        base_path,
        'templates')))
    template_xml = env.get_template('{}.xml'.format(template_name))
    xml = template_xml.render(values)

    return xml.replace('&', '&amp;').replace('&amp;amp;', '&amp;')


def get_pkcs12(certificate_file, certificate_key):
    password = certificate_key
    try:
        archivo_key = b64decode(certificate_file)
        return crypto.load_pkcs12(archivo_key, password.encode())
    except Exception as ex:
        raise ValidationError(tools.ustr(ex))

# def get_pkcs12(certificate_file, certificate_key):
#     try:
#         # Decode the certificate file and key
#         cert_file_bytes = b64decode(certificate_file)
#         cert_key_bytes = certificate_key.encode()  # Assuming certificate_key is a string

#         # Load the PKCS12 certificate
#         private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
#             cert_file_bytes, cert_key_bytes
#         )

#         # Return the relevant objects
#         return private_key, certificate, additional_certificates

#     except Exception as e:
#         raise ValidationError(_("The certificate password or certificate file is not"
#                                 " valid.\nException: %s") % e)
