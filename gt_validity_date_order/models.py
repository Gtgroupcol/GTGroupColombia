from odoo import api, fields, models , _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    #
    @api.onchange('date_order')
    def change_date_order_p(self):
        for record in self:
            date = record.date_order
            if date:
                record.validity_date = (date + timedelta(days=15)).date()
