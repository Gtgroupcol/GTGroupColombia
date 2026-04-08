# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _has_to_be_paid(self):

        #raise ValueError('oka')
        return False