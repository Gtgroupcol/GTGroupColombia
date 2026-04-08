from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError

from datetime import datetime

#MOVIMIENTO CONTABLE ENCABEZADO

class account_move(models.Model):
    _inherit = 'account.move'

    supplier_invoice_number = fields.Char(string='Nº de factura del proveedor',help="La referencia de esta factura proporcionada por el proveedor.", copy=False)
    accounting_closing_id = fields.Many2one('annual.accounting.closing', string='Cierre contable anual', ondelete='cascade')




class lavish_confirm_wizard(models.TransientModel):
    _name = 'lavish.confirm.wizard'
    _description = 'Confirmación de procesos lavish'

    yes_no = fields.Char(default='Desea continuar?')

    def yes(self):
        return True


class lavish_confirm_wizard(models.TransientModel):
    _inherit = 'lavish.confirm.wizard'

    accounting_closing_id = fields.Many2one('annual.accounting.closing', string='Cierre contable anual', ondelete='cascade')

    def yes(self):
        if self.accounting_closing_id:
            obj_move = self.env['account.move'].search([('accounting_closing_id', '=', self.accounting_closing_id.id)])
            obj_move.unlink()
            self.accounting_closing_id.generate_accounting_closing()
        obj_confirm = super(lavish_confirm_wizard, self).yes()
        return obj_confirm

class annual_accounting_closing(models.Model):
    _name = 'annual.accounting.closing'
    _description = 'Cierre contable anual'

    name = fields.Char('Nombre')
    balance = fields.Float('Saldo', readonly=True)
    closing_year = fields.Integer('Año de cierre', size=4)
    counter_contab = fields.Integer(compute='compute_counter_contab', string='Movimientos')
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True, required=True, default=lambda self: self.env.company)
    journal_id = fields.Many2one('account.journal', string='Diario destino', company_dependent=True, required=True)
    counterparty_account = fields.Many2one('account.account', string='Cuenta contrapartida')
    filter_account_ids = fields.Many2many('account.group', string="Cuentas a cerrar")
    partner_id = fields.Many2one('res.partner', 'Tercero de cierre', default=lambda self: self.env.company.partner_id.id)
    closing_by_partner = fields.Boolean('Cerrar por tercero')

    def compute_counter_contab(self):
        count = self.env['account.move'].search_count([('accounting_closing_id', '=', self.id)])
        self.counter_contab = count

    def call_up_closing_wizard(self):
        yes_no = ''
        no_delete = False

        if self.counter_contab > 0:
            obj_contab = self.env['account.move'].search([('accounting_closing_id', '=', self.id)])
            for rows in obj_contab:
                if rows.state != 'draft':
                    no_delete = True
                    break
            if no_delete:
                return {'messages': [{'record': False, 'type': 'warning',
                                      'message': 'Ya hay documentos publicados. No es posible continuar!', }]}
            else:
                yes_no = "El movimiento contable actual para el cierre será borrado para crear uno nuevo. Desea continuar?"

            return {
                'name': 'Deseas continuar?',
                'type': 'ir.actions.act_window',
                'res_model': 'zue.confirm.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_accounting_closing_id': self.id,
                            'default_yes_no': yes_no}
            }
        else:
            self.generate_accounting_closing()

    def return_action_to_open(self):
        res = {
            'name': 'Movimientos',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'target': 'current',
            'domain': "[('accounting_closing_id','in',[" + str(self._ids[0]) + "])]"
        }
        return res

    def generate_accounting_closing(self):
        year = str(self.closing_year)
        start_date = '01/01/' + year
        end_date = '31/12/' + year
        row_count = 0
        accounts = ''

        if self.closing_by_partner:
            if not self.partner_id:
                raise ValidationError(_("No se ha especificado el tercero de cierre. Por favor verifique!"))
            if not self.filter_account_ids:
                raise ValidationError(_("No se han especificado las cuentas de cierre. Por favor verifique!"))
        else:
            if not self.counterparty_account:
                raise ValidationError(_("No se han especificado la cuenta de contrapartida. Por favor verifique!"))

        for account in self.filter_account_ids:
            row_count += 1
            if row_count == 1:
                if row_count == len(self.filter_account_ids):
                    accounts = '(' + account.code_prefix_start + '%)'
                else:
                    accounts = '(' + account.code_prefix_start + '%|'
            elif row_count == len(self.filter_account_ids):
                accounts += account.code_prefix_start + '%)'
            else:
                accounts += account.code_prefix_start + '%|'

        d_start_date = datetime.strptime(start_date, '%d/%m/%Y')
        d_end_date = datetime.strptime(end_date, '%d/%m/%Y')

        query = '''
                select aml.account_id, aml.partner_id, sum(aml.debit-aml.credit) as saldo
                from account_move am 
                inner join account_move_line aml on am.id = aml.move_id 
                inner join account_account aa on aml.account_id = aa.id and code similar to '%s' 
                where am."date" between '%s' and '%s' and am.company_id = %s and am.state = 'posted'
                group by aml.account_id, aml.partner_id
                ''' % (accounts, str(d_start_date), str(d_end_date), self.company_id.id)

        self.env.cr.execute(query)
        result_query = self.env.cr.fetchall()

        if not result_query:
            raise ValidationError(_("No se encontraron movimientos para el año especificado. Por favor verifique!"))

        line_ids = []
        move_dict = {
            'company_id': self.env.company.id,
            'ref': 'Cierre contable año: ' + year,
            'journal_id': self.journal_id.id,
            'date': d_end_date,
            'accounting_closing_id': self.id
        }

        total = 0
        for result in result_query:
            account_id = result[0]
            partner_id = result[1]
            balance = result[2]

            debit = 0
            credit = 0
            total += balance

            if balance > 0:
                credit = abs(balance)
            elif balance < 0:
                debit = abs(balance)
            else:
                continue

            line = {
                'name': 'Cierre contable año: ' + year,
                'partner_id': partner_id,
                'account_id': account_id,
                'journal_id': self.journal_id.id,
                'date': d_end_date,
                'debit': debit,
                'credit': credit,
            }
            line_ids.append(line)

            if self.closing_by_partner:
                line = {
                    'name': 'Cierre contable año: ' + year,
                    'partner_id': self.partner_id.id,
                    'account_id': account_id,
                    'journal_id': self.journal_id.id,
                    'date': d_end_date,
                    'debit': credit,
                    'credit': debit,
                }
                line_ids.append(line)
        debit = 0
        credit = 0
        if total > 0:
            debit = abs(total)
        elif total < 0:
            credit = abs(total)

        if not self.closing_by_partner:
            line = {
                'name': 'Cierre contable año: ' + year,
                'partner_id': self.env.company.partner_id.id,
                'account_id': self.counterparty_account.id,
                'journal_id': self.journal_id.id,
                'date': d_end_date,
                'debit': debit,
                'credit': credit
            }
            line_ids.append(line)

        move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
        move = self.env['account.move'].create(move_dict)
        self.balance = total

        return True