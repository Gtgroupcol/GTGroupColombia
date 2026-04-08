# Part of Odoo. See LICENSE file for full copyright and licensing details.
import pprint
import logging

#from werkzeug import urls

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
#from odoo.addons.payment_paypal.const import PAYMENT_STATUS_MAPPING


_logger = logging.getLogger(__name__)

import requests
import json


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'
    #checkout_code_onvopay = fields.Char(
    #    string='Checkout OnvoPay Id',
    #    help='Checkout OnvoPay Id, useful to identify transaction.'
    #)

    def send_payment_wompicol(self):



        dx = self.provider_id.wompicol_form_generate_values(dict(
            reference=self.reference,
            currency=self.currency_id,
            amount=self.amount,
        ))
        request_url = self.provider_id._get_wompicol_urls()
        dx['api_url'] = request_url

        #raise ValidationError(str(dx))




        return  dx



    def _get_specific_rendering_values(self, processing_values):

        _logger.exception('Onvopay : _get_specific_rendering_values')
        """ Function to fetch the values of the payment gateway"""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'wompicol':
            return res
        return self.send_payment_wompicol()

    def _wompicol_get_data_manually(self, id, environment):
        _logger.info("method: _wompicol_get_data_manually")
        """When the client has returned and the payment transaction hasn't been
        updated, check manually and update the transaction"""
        # Check first if this transaciont has been updated already
        if id:
            tx = self.env[
                'payment.transaction'
            ].search([('provider_reference', '=', id)])
            if len(tx):
                _logger.info("Wompicol: Not getting data manually, transaction already updated.")
                return

        api_url = self.provider_id._get_wompicol_api_url(environment)
        request_url = f"{api_url}/transactions/{id}"
        wompi_data = requests.get(request_url, timeout=60)
        # If request succesful
        if wompi_data.status_code == 200:
            wompi_data = wompi_data.json()
            _logger.info("Wompicol: Sucesfully called api for id: %s it returned data: %s"
                         % (id, pprint.pformat(wompi_data)))
            # pprint.pformat(post))
            # Data needed to validate is just on 'data'
            # Format it how it expects it
            wompi_data["data"] = {"transaction": wompi_data["data"]}
            # Fix the reference code, only what's previous to _ is what we want
            # ref = wompi_data['data']['transaction']['reference']
            # if '_' in ref:
            #    wompi_data['data']['transaction']['reference'] = ref.split('_')[0]
            # This avoid confirming the event, since the data is being
            # asked from the server. Instead of listening.
            wompi_data["noconfirm"] = True
            # If the transaction is a test.
            if environment == 'test':
                wompi_data["test"] = True
            _logger.info("Wompicol: creating transaction manually, by calling the api for acquirer reference %s" % id)
            '''
            tx = self.env[
                'payment.transaction'
            ].search([('acquirer_reference', '=', ref)])
            if not len(tx):
                _logger.info("not transaction")
                return
            '''

            transaction = self.env['payment.transaction'].sudo()._get_tx_from_notification_data('wompicol', wompi_data)
            transaction._process_notification_data(wompi_data)
            # transaction = self.env['payment.transaction'].sudo().form_feedback(wompi_data, 'wompicol')

            '''
            _logger.info('transaction')
            _logger.info(transaction)

            if len(transaction):
                tx_ids_list = set(request.session.get("__payment_tx_ids__", [])) | set(transaction.ids)
                request.session["__payment_tx_ids__"] = list(tx_ids_list)
                _logger.info('request.session')
                _logger.info(request.session)
                _logger.info(tx_ids_list)
            '''
            return transaction

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of `payment` to find the transaction based on Mercado Pago data.

        :param str provider_code: The code of the provider that handled the transaction.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction if found.
        :rtype: recordset of `payment.transaction`
        :raise ValidationError: If inconsistent data were received.
        :raise ValidationError: If the data match no transaction.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'wompicol' or len(tx) == 1:
            return tx

        reference = notification_data['data']['transaction']['reference']
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'wompicol')])

        _logger.info("REFERENCIA ENCONTRADA : %s" % (str(tx)))

        if not tx:
            raise ValidationError(
                "wompicol: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        _logger.info('SI LLEGO')
        if self.provider_code != 'wompicol':
            return

        # Make sure this method is run agains only one record
        self.ensure_one()

        _logger.info('SI LLEGO2')

        # Simplify data access
        tx_data = notification_data.get('data').get('transaction')
        status = tx_data.get('status')

        # Check if the data received matches what's in wompi servers
        # Do not do it if running and odoo test, or if the data was
        # queried, not received.
        if not notification_data.get('noconfirm', False):
            self._wompicol_confirm_event(notification_data)

        res = {
            'acquirer_reference': tx_data.get('id'),  # Wompi internal id
            'state_message': f"Wompicol states the transactions as {status}"
        }

        # If came from the test endpoint
        if notification_data.get('test'):
            res["state_message"] = 'TEST TRANSACTION: ' + res["state_message"]

        _logger.info("STATUS : %s"% (status))

        if status == 'APPROVED':
            _logger.info('Validated WompiCol payment for tx %s: setting as done' % self.reference)


            orders = self.sale_order_ids
            self._set_done()
            if self.state == 'done':
                if len(orders) == 1:
                    if orders.state == 'draft':
                        orders.action_confirm()

        elif status == 'PENDING':
            _logger.info('Received notification for WompiCol payment %s: setting as pending' % (self.reference))
            self._set_pending(state_message=notification_data.get('pending_reason'))
            # res.update(state='pending')
            # self._set_transaction_pending()
            # return self.write(res)
        elif status in ['VOIDED', 'DECLINED', 'ERROR']:
            _logger.info('Received notification for WompiCol payment %s: setting as Cancel' % (self.reference))
            self._set_canceled()
            # res.update(state='cancel')
            # self._set_transaction_cancel()
            # return self.write(res)
        else:
            error = 'Received unrecognized status for WompiCol payment %s: %s, setting as error' % (
                self.reference, status)
            _logger.info(error)
            self._set_canceled(state_message=error)
            # res.update(state='cancel', state_message=error)
            # self._set_transaction_cancel()
            # return self.write(res)
        """ Override of `payment` to process the transaction based on Mercado Pago data.

                Note: self.ensure_one() from `_process_notification_data`

                :param dict notification_data: The notification data sent by the provider.
                :return: None
                :raise ValidationError: If inconsistent data were received.
        """

