from odoo import Command, models, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _prepare_duplicate_line(self):
        """
        Prepare a dictionary of values to be used during the duplication of a line.
        This dictionary will help specify additional parameters that should be copied, which are not copied by default.
        """
        self.ensure_one()
        return {'move_id': self.move_id.id,
                'sale_line_ids': [Command.link(sale_line_id) for sale_line_id in self.sale_line_ids.ids],
                }

    def duplicate_line(self):
        """
        Allow duplicating a line while retaining the link to the original sale order lines.
        This feature enables invoicing quantities of a sold product at different prices by splitting the line.
        """
        self.ensure_one()
        if self.move_id.state != 'cancel' and self.move_id.move_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
            self.copy(self._prepare_duplicate_line())
        else:
            raise UserError(_("You can only duplicate lines for customer or vendor invoices/credit notes that are in the 'draft' state."))
