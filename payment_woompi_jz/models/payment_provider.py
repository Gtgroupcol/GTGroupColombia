# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, fields, models

from odoo.addons.payment_paypal import const
import math


import uuid

import requests
import pprint
import time
import random

from hashlib import md5
from werkzeug import urls
from odoo.http import request
from odoo import api, fields, models, _, http
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare
from odoo.addons.payment.controllers.portal import PaymentPortal


_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'


    code = fields.Selection(
        selection_add=[('wompicol', "Wompicol")], ondelete={'wompicol': 'set default'}
    )



    wompicol_private_key = fields.Char(
        string="Wompi Colombia Private API Key",
        groups='base.group_user'
    )
    wompicol_public_key = fields.Char(
        string="Wompi Colombia Public API Key",
        groups='base.group_user'
    )



    wompicol_test_private_key = fields.Char(
        string="Wompi Colombia Test Private API Key",
        groups='base.group_user'
    )
    wompicol_test_public_key = fields.Char(
        string="Wompi Colombia Test Public API Key",
        groups='base.group_user'
    )

    wompicol_integrity_key = fields.Char(
        string="Wompi Colombia Integrity API Key",
        groups='base.group_user'
    )

    wompicol_test_integrity_key = fields.Char(
        string="Wompi Colombia Integrity API Key",
        groups='base.group_user'
    )

    wompicol_event_url = fields.Char(
        string="Wompi Colombia URL de Eventos",
        groups='base.group_user',
        readonly=True,
        store=False,
        compute='_wompicol_event_url'
    )
    wompicol_test_event_url = fields.Char(
        string="Wompi Colombia URL Test de Eventos",
        groups='base.group_user',
        readonly=True,
        store=False,
        compute='_wompicol_event_url'
    )

    def _wompicol_event_url(self):
        """Set the urls to config in the wompi console"""
        prod_url = ''
        test_url = ''
        if self.code == 'wompicol':
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            prod_url = f"{base_url}/payment/wompicol/response"
            test_url = f"{base_url}/payment/wompicol_test/response"

        self.wompicol_event_url = prod_url
        self.wompicol_test_event_url = test_url

    def wompicol_form_generate_values(self, values):
        # The base url
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if not base_url:
            raise ValidationError('No se ha definido una url base para e-commerce')
        # Get the payment transaction
        tx = self.env['payment.transaction'].search([('reference', '=', values.get('reference'))])

        if values['currency'].name != 'COP':
            error_msg = (_('WompiCol: Only accepts COP as the currency, received') % (values['currency'].name))
            raise ValidationError(error_msg)

        # wompiref = f"{tx.reference}_{int(random.random() * 1000)}"
        wompiref = tx.reference

        p_key = self._get_keys()[1]

        ammount = math.ceil(values['amount']) * 100

        moneda = 'COP'

        wompicol_tx_values = dict(
            values,
            publickey=p_key,
            currency=moneda,
            # Wompi wants cents (*100) and has to end on 00.
            amountcents=ammount,
            referenceCode=wompiref,
            redirectUrl=urls.url_join(base_url, '/payment/wompicol/client_return'),
        )

        import hashlib

        # Función para generar SHA-256
        def generar_sha256(texto):
            # Crear un objeto hash SHA-256
            sha256 = hashlib.sha256()
            # Actualizar el objeto hash con el texto en formato de bytes
            sha256.update(texto.encode('utf-8'))
            # Devolver el hash en formato hexadecimal
            return sha256.hexdigest()

        # Ejemplo de uso

        texto = f"{wompiref}{ammount}{moneda}{self._get_keys()[2]}"

        hash_resultado = generar_sha256(texto)

        #raise ValidationError(str([texto,hash_resultado]))

        wompicol_tx_values.update({
            'signature': hash_resultado
        })

        return wompicol_tx_values

    def _get_wompicol_urls(self):
        """ Wompi Colombia URLs this method should be called to
        get the url to GET the form"""
        return "https://checkout.wompi.co/p/"

    def _get_keys(self, environment=None):
        """Wompi keys change wether is prod or test
        returns a tuple with (pub, prod) dending on
        environment return the appropiate key."""
        if not environment:
            environment = 'prod' if self.state == 'enabled' else 'test'

        if environment == 'prod':
            prv = self.wompicol_private_key
            pub = self.wompicol_public_key
            return (prv, pub,self.wompicol_integrity_key)
        else:
            test_prv = self.wompicol_test_private_key
            test_pub = self.wompicol_test_public_key
            return (test_prv, test_pub,self.wompicol_test_integrity_key)

    def _get_wompicol_api_url(self, environment=None):
        """This method should be called to get the api
        url to query depending on the environment."""
        if not environment:
            environment = 'prod' if self.state == 'enabled' else 'test'

        if environment == 'prod':
            return 'https://production.wompi.co/v1'
        else:
            return 'https://sandbox.wompi.co/v1'