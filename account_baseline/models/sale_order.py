# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    check_user_edit_line = fields.Boolean(
         compute="compute_check_user_edit_line"
    )

    def compute_check_user_edit_line(self):
        for record in self:
            company = record.company_id
            if company.restriction_line_price:
                record.check_user_edit_line = False
                ids_group_user = self.env.user.groups_id.ids
                id_group_edit_price = self.env.ref("account_baseline.group_line_price_edit").id
                for line in record.order_line:
                    line.check_user_edit_line = False
                if id_group_edit_price in ids_group_user:
                    record.check_user_edit_line = True
                    for line in record.order_line:
                        line.check_user_edit_line = True
            else:
                record.check_user_edit_line = True
                for line in record.order_line:
                        line.check_user_edit_line = True


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    check_user_edit_line = fields.Boolean()
