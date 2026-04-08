from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AdvancePaymentWizard(models.TransientModel):
    _name = 'advance.payment.wizard'
    _description = 'Advance Payment Wizard'

    date = fields.Date(string='Advance Payment Date', required=True, default=fields.Date.context_today)
    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    invoice_id = fields.Many2one('account.move', string='Invoice', required=True)

    @api.constrains('date')
    def _check_date(self):
        for wizard in self:
            if wizard.date < wizard.invoice_id.date:
                raise ValidationError(_("La fecha de pago del anticipo no puede ser anterior a la fecha de contabilización de la factura."))

    @api.model
    def default_get(self, fields):
        res = super(AdvancePaymentWizard, self).default_get(fields)
        if self._context.get('active_model') == 'account.move' and self._context.get('active_id'):
            move = self.env['account.move'].browse(self._context['active_id'])
            res.update({
                'invoice_id': move.id,
                'date': max(fields.Date.context_today(self), move.date),
            })
        return res

    def confirm_advance_payment(self):
        self.ensure_one()
        return self.invoice_id.create_advance_payment(
            self.amount, 
            self.invoice_id.partner_id.id, 
            self._context.get('account_id'), 
            self._context.get('payment_line_id'), 
            self._context.get('invoice_line_id'),
            self.date
        )