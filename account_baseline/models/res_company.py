# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import RedirectWarning


class ResCompany(models.Model):
    _inherit = 'res.company'

    fiscalyear_lock_except = fields.Boolean(
        'Lock Date Exception',
        help='Allows block dates when there are draft seats.'
    )
    restriction_line_price = fields.Boolean(
        'Restrict product line price edition.',
        help='Gives access to groups to be able to '
        'edit the price of the lines of an order. '
    )
    manage_partner_in_invoice_lines_out = fields.Boolean(
        'Manage partner in sales invoice lines',
        help='Allows to change the partner from the sales invoice lines and '
        'these will be assigned to the account income and '
        'the partner in the header will be assigned to the '
        'account receivable.'
    )
    manage_partner_in_invoice_lines_in = fields.Boolean(
        'Manage partner in supplier invoice lines',
        help='Allows to change the partner from the supplier invoice lines and '
        'these will be assigned to the account expense and '
        'the partner in the header will be assigned to the '
        'account payable.'
    )

    def _validate_fiscalyear_lock(self, values):
        if values.get('fiscalyear_lock_date'):

            draft_entries = self.env['account.move'].search([
                ('company_id', 'in', self.ids),
                ('state', '=', 'draft'),
                ('date', '<=', values['fiscalyear_lock_date'])])
            if draft_entries and not self.env.company.fiscalyear_lock_except:
                error_msg = _(
                    'There are still unposted entries in the period you '
                    'want to lock. You should either post or delete them.'
                )
                action_error = {
                    'view_mode': 'tree',
                    'name': 'Unposted Entries',
                    'res_model': 'account.move',
                    'type': 'ir.actions.act_window',
                    'domain': [('id', 'in', draft_entries.ids)],
                    'search_view_id': [
                        self.env.ref('account.view_account_move_filter').id,
                        'search'
                    ],
                    'views': [
                        [self.env.ref('account.view_move_tree').id, 'list'],
                        [self.env.ref('account.view_move_form').id, 'form']
                    ],
                }
                raise RedirectWarning(
                    error_msg, action_error, _('Show unposted entries'))

            unreconciled_statement_lines = self.env[
                'account.bank.statement.line'
            ].search([
                ('company_id', 'in', self.ids),
                ('is_reconciled', '=', False),
                ('date', '<=', values['fiscalyear_lock_date']),
                ('move_id.state', 'in', ('draft', 'posted')),
            ])
            if unreconciled_statement_lines:
                error_msg = _(
                    'There are still unreconciled bank statement lines in '
                    'the period you want to lock.'
                    'You should either reconcile or delete them.'
                )
                action_error = {
                    'type': 'ir.actions.client',
                    'tag': 'bank_statement_reconciliation_view',
                    'context': {
                        'statement_line_ids': unreconciled_statement_lines.ids,
                        'company_ids': self.ids
                    },
                }
                raise RedirectWarning(error_msg, action_error, _(
                    'Show Unreconciled Bank Statement Line'))
