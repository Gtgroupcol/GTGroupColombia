# -*- coding: utf-8 -*-
import base64
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, date_utils
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval
import logging
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
class HrPayslipEdi(models.Model):
    _name = 'hr.payslip.edi'
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
    _order = 'date_to desc'

    # ---------------------------------------------------------------------
    # CAMPOS
    # ---------------------------------------------------------------------
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura')
    struct_type_id = fields.Many2one('hr.payroll.structure.type', related='struct_id.type_id')
    wage_type = fields.Selection(related='struct_type_id.wage_type')
    name = fields.Char(string='Referencia', required=True)
    number = fields.Char(string='Numero', default='/', copy=False)
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    date_from = fields.Date(string='Desde', required=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_to = fields.Date(string='A', required=True,
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('verify', 'Espera'),
        ('done', 'Hecho'),
        ('cancel', 'Cancelada'),
    ], string='Estado', index=True, readonly=True, copy=False, default='draft')
    line_ids = fields.One2many('hr.payslip.edi.line', 'slip_id', store=True, string='Líneas de nomina')
    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False, required=True,
        default=lambda self: self.env.company)
    worked_days_line_ids = fields.One2many('hr.payslip.edi.worked_days', 'payslip_id',
        string='Días trabajados', copy=True)
    paid = fields.Boolean(string='Made Payment Order ? ', readonly=True, copy=False)
    note = fields.Text(string='Internal Note')
    contract_id = fields.Many2one('hr.contract', string='Contracto', domain="[('company_id', '=', company_id)]")
    credit_note = fields.Boolean(string='Credit Note', help="Indicates this payslip has a refund of another")
    payslip_run_id = fields.Many2one('hr.payslip.edi.run', string='Batch Name', ondelete='cascade',
        domain="[('company_id', '=', company_id)]")
    sum_worked_hours = fields.Float(compute='_compute_worked_hours', store=True,
        help='Total hours of attendance and time off (paid or not)')
    normal_wage = fields.Integer(compute='_compute_normal_wage', store=True)
    compute_date = fields.Date('Computed On')
    basic_wage = fields.Monetary(compute='_compute_basic_net')
    net_wage = fields.Monetary(compute='_compute_basic_net')
    currency_id = fields.Many2one(related='contract_id.currency_id')
    warning_message = fields.Char(readonly=True)
    validar_cron = fields.Boolean('Validar por Cron')
    is_superuser = fields.Boolean(compute="_compute_is_superuser")
    payslip_ids = fields.One2many('hr.payslip', 'epayslip_bach_id', string='Nominas del mes')
    total_devengos = fields.Float('Total Devengados', default=0.0)
    total_deducciones = fields.Float('Total Deducciones', default=0.0)
    total_paid = fields.Float('Total Comprobante', default=0.0)
    matched_payslips = fields.Boolean('Nóminas Igualadas', compute='_compute_matched_payslips', store=True)

    @api.depends('payslip_ids', 'total_paid')
    def _compute_matched_payslips(self):
        for batch in self:
            total_payslips = sum(batch.payslip_ids.mapped('net_wage'))
            difference = abs(total_payslips - batch.total_paid)
            batch.matched_payslips = difference < 100
    # ---------------------------------------------------------------------
    # MÉTODOS DE ESTADO
    # ---------------------------------------------------------------------
    def action_cancel(self):
        return self.write({'state': 'cancel'})

    def action_draft(self):
        # Limpia tablas auxiliares (si las usas)
        self._cr.execute(''' DELETE FROM hr_payslip_nes_line WHERE slip_id2 = %s''', (self.id,))
        self._cr.execute(''' DELETE FROM hr_payslip_nes_line_ded WHERE slip_id2 = %s''', (self.id,))
        return self.write({'state': 'draft', 'total_devengos': 0.0, 'total_deducciones': 0.0, 'total_paid': 0.0})

    # ---------------------------------------------------------------------
    # CÁLCULOS DE TOTALES
    # ---------------------------------------------------------------------
    def update_total(self):
        """
        Actualiza total_devengos, total_deducciones y total_paid,
        usando la búsqueda directa en hr_payslip_edi_line + devengado_rule_id / deduccion_rule_id.
        """
        DevengadosTotal = self.get_value_etotal('devengados', self)
        self.total_devengos = round(DevengadosTotal, 2)

        DeduccionesTotal = self.get_value_etotal('deducciones', self)
        self.total_deducciones = round(DeduccionesTotal, 2)

        ComprobanteTotal = DevengadosTotal + DeduccionesTotal
        self.total_paid = round(ComprobanteTotal, 2)

    def get_value_etotal(self, tag, edi):
        if tag == 'devengados':
            self._cr.execute('''
                SELECT sum(total)
                  FROM hr_payslip_edi_line l
                  JOIN hr_salary_rule r ON r.id = l.salary_rule_id
                 WHERE r.devengado_rule_id IS NOT NULL
                   AND slip_id = %s
            ''', (edi.id,))
            value_tag = self._cr.fetchone()
            return value_tag[0] if value_tag and value_tag[0] else 0.0

        elif tag == 'deducciones':
            self._cr.execute('''
                SELECT sum(total)
                  FROM hr_payslip_edi_line l
                  JOIN hr_salary_rule r ON r.id = l.salary_rule_id
                 WHERE r.deduccion_rule_id IS NOT NULL
                   AND slip_id = %s
            ''', (edi.id,))
            value_tag = self._cr.fetchone()
            return value_tag[0] if value_tag and value_tag[0] else 0.0

        return 0.0

    # ---------------------------------------------------------------------
    # ONCHANGE DE EMPLEADO
    # ---------------------------------------------------------------------
    @api.onchange('employee_id', 'struct_id', 'contract_id', 'date_from', 'date_to')
    def _onchange_employee(self):
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return

        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        self.company_id = employee.company_id

        if not self.contract_id or self.employee_id != self.contract_id.employee_id:
            contracts = employee._get_contracts(date_from, date_to)
            if not contracts:
                closed_payslips = self.env['hr.payslip'].search([
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ['done', 'paid']),
                    ('date_from', '<=', date_to),
                    ('date_to', '>=', date_from)
                ], order='date_to desc', limit=1)
                if closed_payslips:
                    self.contract_id = closed_payslips.contract_id.id
                    self.struct_id = closed_payslips.struct_id.id
                else:
                    self.contract_id = False
                    self.struct_id = False
                    return
            else:
                if not contracts[0].structure_type_id.default_struct_id:
                    self.contract_id = False
                    self.struct_id = False
                    return
                self.contract_id = contracts[0]
                self.struct_id = contracts[0].structure_type_id.default_struct_id

        lang = employee.sudo().work_contact_id.lang or self.env.user.lang
        context = {'lang': lang}
        payslip_name = self.struct_id.payslip_name or _('Salary Slip')
        del context

        self.name = '%s - %s - %s' % (
            payslip_name,
            self.employee_id.name or '',
            format_date(self.env, self.date_from, date_format="MMMM y", lang_code=lang)
        )

        if date_to > date_utils.end_of(fields.Date.today(), 'month'):
            self.warning_message = _(
                "This payslip can be erroneous! Work entries may not be generated for the period from %(start)s to %(end)s.",
                start=date_utils.add(date_utils.end_of(fields.Date.today(), 'month'), days=1),
                end=date_to,
            )
        else:
            self.warning_message = False

    # ---------------------------------------------------------------------
    # CÁLCULOS DE SALARIO BÁSICO, NETO, ETC.
    # ---------------------------------------------------------------------
    def _get_contract_wage(self):
        self.ensure_one()
        return self.contract_id._get_contract_wage()

    @api.depends('contract_id')
    def _compute_normal_wage(self):
        with_contract = self.filtered('contract_id')
        (self - with_contract).normal_wage = 0
        for payslip in with_contract:
            payslip.normal_wage = payslip._get_contract_wage()

    def _compute_basic_net(self):
        for rec in self:
            BASIC = 0.0
            NET = 0.0
            if rec.payslip_ids.line_ids:
                # Buscar sólo las nóminas con struct_process = 'nomina' o 'contrato'
                for line_id in rec.payslip_ids.filtered(lambda x: x.struct_process in ('nomina','contrato')).line_ids:
                    if line_id.category_id.code == 'BASIC':
                        BASIC += abs(line_id.total)
                    elif line_id.category_id.code == 'NET':
                        NET += abs(line_id.total)
            rec.basic_wage = BASIC
            rec.net_wage = NET

    @api.depends('worked_days_line_ids.number_of_hours', 'worked_days_line_ids.is_paid')
    def _compute_worked_hours(self):
        for payslip in self:
            payslip.sum_worked_hours = sum(line.number_of_hours for line in payslip.worked_days_line_ids)

    def _compute_is_superuser(self):
        self.update({'is_superuser': self.env.user._is_superuser() and self.user_has_groups("base.group_no_one")})
    
    @api.model_create_multi
    def create(self, vals_list):
        new_list = []
        for vals in vals_list:
            if vals.get("number", "/") == "/" and not vals.get("credit_note"):
                new_vals = dict(vals, number=self.env["ir.sequence"].next_by_code("bach.epayslip"))
            else:
                new_vals = dict(vals, number=self.env["ir.sequence"].next_by_code("bachepayslipnote"))
            new_list.append(new_vals)
        return super().create(new_list)

    def action_generated_number(self):
        for epayslip in self:
            if not epayslip.credit_note and epayslip.number == "/":
                number = self.env['ir.sequence'].next_by_code('bach.epayslip')
            else:
                number = self.env['ir.sequence'].next_by_code('bachepayslipnote')
            return epayslip.write({'number': number})

    # ---------------------------------------------------------------------
    # FLUJO PRINCIPAL: update_data -> get_payslip_period -> get_epayslip_line
    # ---------------------------------------------------------------------
    def update_data(self):
        """
        Método principal que:
         - get_payslip_period -> rellena payslip_ids
         - get_epayslip_line -> (este llamará a update_tabla)
         - update_total -> recalcula totales
        """
        for epayslip in self:
            epayslip.get_payslip_period()
            epayslip.get_epayslip_line(epayslip)
            epayslip.update_total()

    def get_payslip_period(self):
        """
        Asocia a self (hr.payslip.edi) las hr.payslip en estado done/paid
        del empleado y dentro del rango de fecha.
        """
        self.payslip_ids = [(5, 0, 0)]
        query = """
            SELECT id 
            FROM hr_payslip 
            WHERE employee_id = %s 
            AND state IN ('done', 'paid')
            AND date_from BETWEEN %s AND %s
            AND date_to BETWEEN %s AND %s
        """
        self.env.cr.execute(query, (
            self.employee_id.id, 
            self.date_from, self.date_to,
            self.date_from, self.date_to
        ))
        payslip_records = self.env.cr.fetchall()
        if payslip_records:
            self.payslip_ids = [(4, record[0]) for record in payslip_records]
            self.update_edi()
        return

    def update_edi(self):
        """
        Actualiza el campo epayslip_bach_id de las hr.payslip con self.id
        """
        if self.payslip_ids:
            for rec in self.payslip_ids:
                rec.write({'epayslip_bach_id': self.id})

    def get_epayslip_line(self, epayslip):
        """
        Llama a update_tabla para crear las lines (hr.payslip.edi.line).
        """
        self.update_tabla(epayslip)
        self.env.cr.commit()

    # ---------------------------------------------------------------------
    # update_tabla (SIN AGRUPAR)
    # ---------------------------------------------------------------------
    def update_tabla(self,epayslip):
        """
        Optimized version that handles all operations in SQL:
        1) Cleans existing EDI data (worked days + lines)
        2) Inserts merged records directly via SQL
        3) Handles all grouping and calculations in SQL
        """
        self.ensure_one()
        if not epayslip.payslip_ids:
            return False

        # Calculate period days once
        period_days = 0
        if epayslip.date_from and epayslip.date_to and epayslip.date_from <= epayslip.date_to:
            period_days = (epayslip.date_to - epayslip.date_from).days + 1

        if epayslip.contract_id and epayslip.contract_id.date_end:
            if epayslip.contract_id.date_end < epayslip.date_to:
                diff = (epayslip.contract_id.date_end - epayslip.date_from).days + 1
                period_days = min(period_days, max(0, diff))

        # Delete existing data
        epayslip._delete_existing_edi_data()

        # Insert worked days and lines
        epayslip._create_worked_days_using_commands(period_days)
        epayslip._create_payslip_lines_using_commands()

        return True

    def _delete_existing_edi_data(self):
        """Delete existing EDI data"""
        self.write({
            'worked_days_line_ids': [Command.clear()],
            'line_ids': [Command.clear()]
        })

    def _get_grouped_worked_days_data(self):
        """Get grouped worked days data using SQL"""
        self.env.cr.execute("""
            SELECT id FROM hr_payslip 
            WHERE id IN %s 
            AND struct_process IN ('nomina', 'contrato')
        """, (tuple(self.payslip_ids.ids),))
        
        payslip_ids = [r[0] for r in self.env.cr.fetchall()]
        if not payslip_ids:
            return []

        query = """
            SELECT 
                w.work_entry_type_id,
                wet.code as work_entry_code,
                SUM(w.number_of_days) as total_days,
                SUM(w.number_of_hours) as total_hours,
                SUM(w.amount) as total_amount,
                array_agg(w.id) as worked_day_ids,
                wet.name as work_entry_name
            FROM hr_payslip_worked_days w
            JOIN hr_work_entry_type wet ON wet.id = w.work_entry_type_id
            WHERE w.payslip_id = ANY(%s)
            GROUP BY 
                w.work_entry_type_id,
                wet.code,
                wet.name
        """
        self.env.cr.execute(query, (payslip_ids,))
        return self.env.cr.dictfetchall()

    def _create_worked_days_using_commands(self, period_days):
        """Create worked days records using commands for better performance"""
        grouped_data = self._get_grouped_worked_days_data()
        
        worked_days_commands = []
        for data in grouped_data:
            # Calculate number of days based on conditions
            number_of_days = data['total_days']
            if data['work_entry_code'] == 'WORK100':
                number_of_days = min(number_of_days, 30, period_days)

            worked_days_commands.append(Command.create({
                'name': data['work_entry_name'],
                'work_entry_type_id': data['work_entry_type_id'],
                'number_of_days': number_of_days,
                'number_of_hours': data['total_hours'],
                'amount': data['total_amount'],
            }))

        if worked_days_commands:
            self.write({
                'worked_days_line_ids': worked_days_commands
            })

    def _get_grouped_line_data(self):
        """Get grouped payslip line data using SQL"""
        if not self.payslip_ids:
            return []

        query = """
            SELECT 
                l.salary_rule_id,
                r.category_id,
                cat.code as category_code,
                l.name as rule_name,
                l.code as code,
                l.leave_id as last_leave_id,
                bool_and(l.quantity = 1) as all_qty_one,
                sum(l.total) as total_sum,
                sum(l.quantity) as total_qty,
                array_agg(l.id ORDER BY l.id DESC) as line_ids,
                max(l.id) as last_line_id,
                max(l.employee_id) as employee_id,
                max(l.contract_id) as contract_id,
                max(l.sequence) as max_sequence,
                bool_or(l.leave_id IS NOT NULL) as has_leave,
                MIN(l.initial_accrual_date) as initial_date,
                max(l.final_accrual_date) as final_date
            FROM hr_payslip_line l
            JOIN hr_salary_rule r ON r.id = l.salary_rule_id
            LEFT JOIN hr_salary_rule_category cat ON cat.id = r.category_id
            WHERE (r.devengado_rule_id IS NOT NULL 
                   OR r.deduccion_rule_id IS NOT NULL)
                AND l.slip_id IN %s
            GROUP BY 
                l.leave_id,
                l.salary_rule_id,
                l.code,
                r.category_id,
                cat.code,
                l.name
        """
        self.env.cr.execute(query, (tuple(self.payslip_ids.ids),))
        return self.env.cr.dictfetchall()

    def _create_payslip_lines_using_commands(self):
        """Create payslip lines using commands for better performance"""
        grouped_data = self._get_grouped_line_data()
        
        line_commands = []
        for data in grouped_data:
            # Calculate quantity based on conditions
            if data['all_qty_one']:
                quantity = 1
            elif data['category_code'] == 'PRESTACIONES_SOCIALES':
                quantity = data['total_qty']  # Ya tenemos la cantidad del último registro en total_qty
            else:
                quantity = data['total_qty']
            amount = data['total_sum'] / quantity if quantity else 0
            if data['category_code'] in ('LICENCIA_NO_REMUNERADA','INAS_INJU','GROSS'):
                amount = 0
   

            line_commands.append(Command.create({
                'salary_rule_id': data['salary_rule_id'],
                'code': data['code'],
                'name': data['rule_name'],
                'category_id': data['category_id'],
                'sequence': data['max_sequence'],
                'quantity': quantity,
                'amount': round(amount, 2),
                'employee_id': data['employee_id'],
                'contract_id': data['contract_id'],
                'leave_id': data['last_leave_id'],
                'initial_accrual_date': data['initial_date'],
                'final_accrual_date': data['final_date'],
            }))

        if line_commands:
            self.write({
                'line_ids': line_commands
            })
class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    epayslip_bach_id = fields.Many2one('hr.payslip.edi', string='Nominas del mes')

class HrPayslipLine(models.Model):
    _name = 'hr.payslip.edi.line'
    _description = 'Payslip Line'
    _order = 'contract_id, sequence, code'

    name = fields.Char(required=True)
    note = fields.Text(string='Description')
    sequence = fields.Integer(required=True, index=True, default=5,
                              help='Use to arrange calculation sequence')
    code = fields.Char(required=True,
                       help="The code of salary rules can be used as reference in computation of other rules. "
                       "In that case, it is case sensitive.")
    slip_id = fields.Many2one('hr.payslip.edi', string='Pay Slip', required=True, ondelete='cascade')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Rule', required=True)
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    rate = fields.Float(string='Rate (%)', digits='Payroll Rate', default=100.0)
    amount = fields.Float(digits='Payroll')
    quantity = fields.Float(digits='Payroll', default=1.0)
    total = fields.Float(compute='_compute_total', string='Total', digits='Payroll', store=True)
    struct_id = fields.Many2one(related='salary_rule_id.struct_id', readonly=True, store=True)
    initial_accrual_date = fields.Date('C. Inicio')
    final_accrual_date = fields.Date('C. Fin')
    amount_select = fields.Selection(related='salary_rule_id.amount_select', readonly=True)
    amount_fix = fields.Float(related='salary_rule_id.amount_fix', readonly=True)
    amount_percentage = fields.Float(related='salary_rule_id.amount_percentage', readonly=True)
    appears_on_payslip = fields.Boolean(related='salary_rule_id.appears_on_payslip', readonly=True)
    category_id = fields.Many2one(related='salary_rule_id.category_id', readonly=True, store=True)
    partner_id = fields.Many2one(related='salary_rule_id.partner_id', readonly=True, store=True)
    leave_id = fields.Many2one('hr.leave', 'Ausencia')
    date_from = fields.Date(string='From', related="slip_id.date_from", store=True)
    date_to = fields.Date(string='To', related="slip_id.date_to", store=True)
    company_id = fields.Many2one(related='slip_id.company_id')

    @api.depends('quantity', 'amount', 'rate')
    def _compute_total(self):
        for line in self:
            line.total = float(line.quantity) * line.amount * line.rate / 100
    days_qty = fields.Integer('Dias Calculados')
    calculated_percentage = fields.Float('% Calculado')
    #sequence_rule = fields.Integer(related="salary_rule_id.sequence_rule")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if 'employee_id' not in values or 'contract_id' not in values:
                payslip = self.env['hr.payslip.edi'].browse(values.get('slip_id'))
                values['employee_id'] = values.get('employee_id') or payslip.employee_id.id
                values['contract_id'] = values.get('contract_id') or payslip.contract_id and payslip.contract_id.id
                if not values['contract_id']:
                    raise UserError(_('You must set a contract to create a payslip line.'))
        return super(HrPayslipLine, self).create(vals_list)


class HrPayslipWorkedDays(models.Model):
    _name = 'hr.payslip.edi.worked_days'
    _description = 'Payslip Worked Days'
    _order = 'payslip_id, sequence'

    name = fields.Char(related='work_entry_type_id.name', string='Description', readonly=True)
    payslip_id = fields.Many2one('hr.payslip.edi', string='Pay Slip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(string='Code', related='work_entry_type_id.code')
    work_entry_type_id = fields.Many2one('hr.work.entry.type', string='Type', required=True, help="The code that can be used in the salary rules")
    number_of_days = fields.Float(string='Number of Days')
    number_of_hours = fields.Float(string='Number of Hours')
    is_paid = fields.Boolean(compute='_compute_is_paid', store=True)
    amount = fields.Monetary(string='Amount', compute='_compute_amount', store=True)
    contract_id = fields.Many2one(related='payslip_id.contract_id', string='Contract',
        help="The contract for which apply this worked days")
    currency_id = fields.Many2one('res.currency', related='payslip_id.currency_id')

    @api.depends('work_entry_type_id', 'payslip_id', 'payslip_id.struct_id')
    def _compute_is_paid(self):
        unpaid = {struct.id: struct.unpaid_work_entry_type_ids.ids for struct in self.mapped('payslip_id.struct_id')}
        for worked_days in self:
            worked_days.is_paid = worked_days.work_entry_type_id.id not in unpaid[worked_days.payslip_id.struct_id.id] if worked_days.payslip_id.struct_id.id in unpaid else False

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'payslip_id.normal_wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        for worked_days in self:
            if not worked_days.contract_id:
                worked_days.amount = 0
                continue
            if worked_days.payslip_id.wage_type == "hourly":
                worked_days.amount = worked_days.payslip_id.contract_id.hourly_wage * worked_days.number_of_hours if worked_days.is_paid else 0
            else:
                worked_days.amount = worked_days.payslip_id.normal_wage * worked_days.number_of_hours / (worked_days.payslip_id.sum_worked_hours or 1) if worked_days.is_paid else 0

class HrPayslipRunEdi(models.Model):
    _name = 'hr.payslip.edi.run'
    _description = 'Payslip Batches'
    _order = 'date_end desc'

    name = fields.Char(required=True)
    slip_ids = fields.One2many('hr.payslip.edi', 'payslip_run_id', string='Nomina')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Verify'),
        ('close', 'Done'),
    ], string='Estados', index=True, readonly=True, copy=False, default='draft')
    date_start = fields.Date(string='Fecha Inicio', required=True, default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_end = fields.Date(string='Fecha Fin', required=True,
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    credit_note = fields.Boolean(string='Credit Note',
        help="If its checked, indicates that all payslips generated from here are refund payslips.")
    payslip_count = fields.Integer(compute='_compute_payslip_count')
    company_id = fields.Many2one('res.company', string='Company', readonly=True, required=True,      default=lambda self: self.env.company)
    error_log_ids = fields.One2many('hr.payslip.error.log', 'payslip_run_id', string='Logs de Error')
    error_count = fields.Integer(compute='_compute_error_count', string='Cantidad de Errores')
    has_errors = fields.Boolean(compute='_compute_error_count', store=True)

    @api.depends('error_log_ids')
    def _compute_error_count(self):
        for run in self:
            errors = run.error_log_ids.filtered(lambda l: l.state == 'error')
            run.error_count = len(errors)
            run.has_errors = bool(errors)



    def action_retry_errors(self):
        """Reintenta procesar todas las nóminas con error"""
        self.ensure_one()
        error_logs = self.error_log_ids.filtered(lambda l: l.state == 'error')
        for log in error_logs:
            log.action_retry()

    def action_view_errors(self):
        """Abre la vista de logs de error"""
        self.ensure_one()
        return {
            'name': _('Logs de Error'),
            'view_mode': 'tree,form',
            'res_model': 'hr.payslip.error.log',
            'domain': [('payslip_run_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_payslip_run_id': self.id}
        }
    
    def _compute_payslip_count(self):
        for payslip_run in self:
            payslip_run.payslip_count = len(payslip_run.slip_ids)

    def action_draft(self):
        return self.write({'state': 'draft'})

    def action_close(self):
        if self._are_payslips_ready():
            self.write({'state' : 'close'})

    def action_validate(self):
        for rec in self:
            rec.mapped('slip_ids').filtered(lambda slip: slip.state != 'cancel').update_data()

    def compute_sheet(self):
        for rec in self.slip_ids.filtered(lambda slip: slip.state != 'done' and slip.state_dian != 'exitoso'):
            rec.compute_sheet_nes()
    def action_confirm(self):
        for index, rec in enumerate(self, 1):
            if not any(rec.mapped('slip_ids').filtered(lambda slip: slip.net_wage != 0)):
                raise UserError(_('Compute Hoja antes de confirmar'))
            else:
                for slip in rec.mapped('slip_ids').filtered(lambda slip: slip.state_dian != 'exitoso'):
                    try:
                        slip.validate()
                        self.env.cr.commit()
                    except Exception as e:
                        self.env.cr.rollback()
                        # Crear log de error
                        self.env['hr.payslip.error.log'].create({
                            'payslip_run_id': rec.id,
                            'payslip_id': slip.id,
                            'error_message': str(e)
                        })
                        _logger.error(f'Error al validar nómina {slip.name}: {str(e)}')
                        continue
            rec.write({'state': 'close'})

    def restart_full_payroll_batch(self):
        for payslip in self.slip_ids:
            payslip.write({'state':'verify'})
            payslip.action_cancel()
            payslip.unlink()
        return self.write({'state': 'draft'})


    def action_open_payslips(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip.edi",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [['id', 'in', self.slip_ids.ids]],
            "name": "Payslips",
        }

    def unlink(self):
        if any(self.filtered(lambda payslip_run: payslip_run.state not in ('draft'))):
            raise UserError(_('You cannot delete a payslip batch which is not draft!'))
        if any(self.mapped('slip_ids').filtered(lambda payslip: payslip.state not in ('draft','cancel'))):
            raise UserError(_('You cannot delete a payslip which is not draft or cancelled!'))
        return super(HrPayslipRunEdi, self).unlink()

    def _are_payslips_ready(self):
        return all(slip.state in ['done', 'cancel'] for slip in self.mapped('slip_ids'))
    
class HrPayslipErrorLog(models.Model):
    _name = 'hr.payslip.error.log'
    _description = 'Log de errores de nómina'
    _order = 'create_date desc'

    payslip_run_id = fields.Many2one('hr.payslip.edi.run', string='Lote de Nómina')
    payslip_id = fields.Many2one('hr.payslip.edi', string='Nómina')
    error_message = fields.Text('Mensaje de Error')
    state = fields.Selection([
        ('error', 'Error'),
        ('resolved', 'Resuelto')
    ], default='error', string='Estado')
    create_date = fields.Datetime('Fecha Error')
    resolved_date = fields.Datetime('Fecha Resolución')

    def action_retry(self):
        self.ensure_one()
        if self.payslip_id:
            try:
                self.payslip_id.validate()
                self.write({
                    'state': 'resolved',
                    'resolved_date': fields.Datetime.now()
                })
            except Exception as e:
                self.write({
                    'error_message': str(e),
                    'create_date': fields.Datetime.now()
                })



class EPayslipLine(models.Model):
    _name = 'epayslip.line'
    _description = 'EPayslip Line'

    # salary_rule_id = fields.Many2one('hr.salary.rule', string='Salary rule')
    # electronictag_id = fields.Many2one('hr.electronictag.structure', string='Electronic Tags')
    # value = fields.Float(string="Valor", default=0.00) # Agregar tipo de moneda
    # epayslip_bach_id = fields.Many2one('epayslip.bach', string='Epayslip bach', ondelete="cascade")
    # employee_id = fields.Many2one('hr.employee', string='HR employee')
    # bach_run_id = fields.Many2one('epayslip.bach.run', string='Bach Run')
    # name = fields.Char(string='name')