from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from collections import defaultdict
import base64
import io
import xlsxwriter
import math
import logging
from odoo.osv import expression
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)

#Código fiscal
class fiscal_accounting_code_details(models.Model):
    _name = 'fiscal.accounting.code.details'
    _description = 'Código Fiscal - Cuentas'

    fiscal_accounting_id = fields.Many2one('fiscal.accounting.code',string='Código fiscal', required=True)
    account_id = fields.Many2one('account.account',string='Cuenta', required=True)
    move_type = fields.Selection([('debit', 'Débito'),
                                     ('credit', 'Crédito'),
                                     ('net', 'Neto')], string='Tipo de movimiento', required=True)

    _sql_constraints = [('fiscal_account_id_uniq', 'unique(fiscal_accounting_id,account_id)',
                         'Ya existe la cuenta en este código fiscal, por favor verficar.')]

class fiscal_accounting_code(models.Model):
    _name = 'fiscal.accounting.code.line'
    _description = 'Código Fiscal'

    account_ids = fields.Many2many('account.account',string='Cuentas')
    fiscal_code = fields.Many2one('fiscal.accounting.code', string='Codigo Asociada')
    excluded_documents_ids = fields.Many2many('account.journal', string="Documentos Excluidos")
    porcentaje = fields.Float(string='Porcentaje',default="100.0")
    available_fields = fields.Selection([
                            ('amount_1001', 'Pago o abono en cuenta deducible'),
                            ('amount_1003', 'Retención que le practicaron'),
                            ('amount_1005', 'Impuesto Descontable'),
                            ('amount_1006', 'Impuesto generado'),
                            ('amount_1007', 'Ingresos brutos recibidos'),
                            ('amount_1008', 'Saldo cuentas por cobrar al 31-12'),
                            ('amount_1009', 'Saldo cuentas por pagar al 31-12'),
                            ('amount_1009', 'Saldo cuentas por pagar al 31-12'),
                            ('amount_1010', 'Valor patrimonial acciones o aportes al 31-12'),
                            ('amount_ind', 'Valor al 31-12'),
                            ('amount', 'Valor o Balance'),
                            ('inc','Impuesto al consumo'),
                            ('amount_no_dedu','Pago o abono en cuenta NO deducible'),
                            ('iva_mayor','IVA mayor valor del costo o gasto, deducible'),
                            ('iva_no_dedu','IVA mayor valor del costo o gasto no deducible'),
                            ('rete','Retención en la fuente practicada Renta'),
                            ('rete_asu','Retención en la fuente asumida Renta'),
                            ('rete_iva','Retención en la fuente practicada IVA a responsables del IVA'),
                            ('rete_iva_no_dom','Retención en la fuente practicada IVA a no residentes o no domiciliados'),
                            ('dev_ing','Devoluciones, rebajas y descuentos'),
                            ('dev_iva_sale','IVA resultante por devoluciones en ventas anuladas. rescindidas o resueltas'),
                            ('dev_iva_purchase','IVA recuperado en devoluciones en compras anuladas. rescindidas o resueltas'),
                            ('operator', 'Operador'),
                            ('rate_part', 'Porcentaje de participación'),
                            ('rate_part_dec', 'Porcentaje de participación (posición decimal)'),
                            ('tax_1003', 'Valor acumulado del pago o abono sujeto a Retención en la fuente'),
                            ('unit_rate', 'Tarifa Aplicada'),
                            ('amount_payroll_1','Pagos por Salarios'),
                            ('amount_payroll_2','Pagos por emolumentos eclesiásticos'),
                            ('amount_payroll_3','Pagos realizados con bonos electrónicos o de papel de servicio, cheques, tarjetas, vales, etc.'),
                            ('amount_payroll_4','Valor del exceso de los pagos por alimentación mayores a 41 UVT, art. 387-1 E.T.'),
                            ('amount_payroll_5','Pagos por honorarios'),
                            ('amount_payroll_6','Pagos por servicios'),
                            ('amount_payroll_7','Pagos por comisiones'),
                            ('amount_payroll_8','Pagos por prestaciones sociales'),
                            ('amount_payroll_9','Pagos por viáticos'),
                            ('amount_payroll_10','Pagos por gastos de representación'),
                            ('amount_payroll_11','Pagos por compensaciones trabajo asociado cooperativo'),
                            ('amount_payroll_12','Valor apoyos económicos no reembolsables o condonados, entregados por el Estado o financiados con recursos públicos, para financiar programas educativos.'),
                            ('amount_payroll_13','Otros pagos'),
                            ('amount_payroll_14','Cesantías e intereses de cesantías efectivamente pagadas al empleado'),
                            ('amount_payroll_15','Cesantías consignadas al fondo de cesantías'),
                            ('amount_payroll_16','Auxilio de cesantías reconocido a trabajadores del régimen tradicional del Código Sustantivo del Trabajo, Capítulo VII, Título VIII Parte Primera'),
                            ('amount_payroll_17','Pensiones de Jubilación, vejez o invalidez'),
                            ('amount_payroll_18','Total ingresos brutos por rentas de trabajo y pensión'),
                            ('amount_payroll_19','Aportes obligatorios por salud a cargo del trabajador'),
                            ('amount_payroll_20','Aportes obligatorios a fondos de pensiones y solidaridad pensional a cargo del trabajador'),
                            ('amount_payroll_21','Aportes voluntarios al régimen de ahorro individual con solidaridad - RAIS'),
                            ('amount_payroll_22','Aportes voluntarios a fondos de pensiones voluntarias'),
                            ('amount_payroll_23','Aportes a cuentas AFC'),
                            ('amount_payroll_24','Aportes a cuentas AVC'),
                            ('amount_payroll_25','Valor de las retenciones en la fuente por pagos de rentas de trabajo o pensiones'),
                            ('amount_payroll_26','Impuesto sobre las ventas – IVA, mayor valor del costo o gasto'),
                            ('amount_payroll_27','Retención en la fuente a título de impuesto sobre las ventas – IVA.'),
                            ('amount_payroll_28','Pagos por alimentación hasta 41 UVT'),
                            ('amount_payroll_29','Valor ingreso laboral promedio de los últimos seis meses.'),
                                ], 'Campos Seleccionados Exogena', required=True)

class fiscal_accounting_code(models.Model):
    _name = 'fiscal.accounting.code'
    _description = 'Código Fiscal'
    _rec_name = 'code_description'

    company_id = fields.Many2one('res.company', string='Compañía', readonly=True, required=True,
                                 default=lambda self: self.env.company)
    concept_dian = fields.Char(string="Código Fiscal", required=True)
    code_description = fields.Char(string="Descripción del Código", required=True)
    format_id = fields.Many2one('format.encab', string='Formato')
    account_type = fields.Selection([('movement', 'Movimiento del periodo'),
                              ('balance', 'Saldo a la Fecha'),
                              ], 'Tipo de cuenta')
    move_type = fields.Selection([('debit', 'Débito'),
                                  ('credit', 'Crédito'),
                                  ('net', 'Neto')], string='Tipo de movimiento', default='net',required=True)
    retention_associated = fields.Many2one('fiscal.accounting.code', string='Retención Asociada')
    required_retention_associated = fields.Boolean('Aplica para todos los conceptos del formato asociado', tracking=True)
    accounting_details_ids = fields.Many2many('account.account',string='Cuentas')
    concept = fields.Char(string="Concepto")
    account_code = fields.Char(string="Código de cuenta")
    excluded_documents_ids = fields.Many2many('account.journal', string="Documentos Excluidos")
    #fiscal_group_id = fields.Many2one('fiscal.accounting.group',string="Grupo Fiscal")
    line_ids = fields.One2many('fiscal.accounting.code.line','fiscal_code', string="Documentos Excluidos")
    _sql_constraints = [('fiscal_code_uniq', 'unique(company_id,concept_dian,id)',
                         'El concepto DIAN digitado ya esta registrado para esta compañía, por favor verificar.')]
    def name_get(self):
        result = []
        for account in self:
            name = account.concept_dian + ' ' + account.code_description
            result.append((account.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            if operator in ('=', '!='):
                domain = ['|', ('concept_dian', '=', name.split(' ')[0]), ('code_description', operator, name)]
            else:
                domain = ['|', ('concept_dian', '=ilike', name.split(' ')[0] + '%'), ('code_description', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
#Grupo Fiscal
class fiscal_accounting_group(models.Model):
    _name = 'fiscal.accounting.group'
    _description = 'Grupo Fiscal'
    _rec_name = 'group_description'

    company_id = fields.Many2one('res.company', string='Compañía', readonly=True, required=True,
                                 default=lambda self: self.env.company)
    fiscal_group = fields.Char(string="Grupo Fiscal", required=True)
    group_description = fields.Char(string="Descripción del Grupo", required=True)
    operator = fields.Selection([('>', 'Mayor que'),
                              ('<', 'Menor que'),
                              ('=', 'Igual que'),
                              ('!=', 'Distinto de'),
                              ('<=','Menor o igual que'),
                              ('>=', 'Mayor o igual que'),
                              ], 'Operador')
    amount = fields.Float(string="Monto")
    tax_type = fields.Selection([('dian', "DIAN Art 631"),
                              ('treasury', "Distrital"),
                              ], "Tipo de impuesto")
    concept_dian_ids = fields.Many2many('fiscal.accounting.code', string="Códigos Fiscales")
    excluded_thirdparty_ids = fields.Many2many('res.partner', string="Tercero Excluido")
    partner_minor_amounts = fields.Many2one('res.partner', string="Tercero Cuantías menores")

    _sql_constraints = [('fiscal_group_uniq', 'unique(company_id,fiscal_group)',
                         'El grupo fiscal digitado ya esta registrado para esta compañía, por favor verificar.')]


class format_encab(models.Model):
    _name = 'format.encab'
    _description = 'Formato de Código Fiscal Encabezado'

    format_id = fields.Char(string="Código Formato", required=True)
    description = fields.Char(string="Descripción del formato", required=True)
    details_ids = fields.One2many('format.detail','format_id',string = 'Campos Disponibles', ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True, required=True,default=lambda self: self.env.company)
    format_associated_id = fields.Many2one('format.encab', string='Formato Asociado')
    fields_associated_code_fiscal_ids = fields.One2many('fiscal.accounting.code','format_id', string='Conceptos Asociados')

    _sql_constraints = [('format_encab_uniq', 'unique(format_id,company_id,id)',
                         'El formato fiscal digitado ya esta registrado para esta compañía, por favor verificar.')]

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, "{} - {}".format(record.format_id,record.description)))
        return result
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            if operator in ('=', '!='):
                domain = ['|', ('format_id', '=', name.split(' ')[0]), ('description', operator, name)]
            else:
                domain = ['|', ('format_id', '=ilike', name.split(' ')[0] + '%'), ('description', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
class format_detail(models.Model):
    _name = 'format.detail'
    _description = 'Formato de Código Fiscal Detalle'

    format_id = fields.Many2one('format.encab',string='Código Formato', required=True, ondelete='cascade')
    sequence = fields.Integer(string="Secuencia", required=True)
    name = fields.Char('Nombre del campo XLS')
    information_fields_id = fields.Many2one('ir.model.fields', string="Información",domain="[('model_id.model', 'in', ['hr.employee','res.partner','res.company','res.city','hr.contract','res.country','res.country.state'])]")
    information_fields_relation = fields.Char(related='information_fields_id.relation', string='Relación del objeto',store=True)
    related_field_id = fields.Many2one('ir.model.fields', string='Campo Relación',domain="[('model_id.model', '=', information_fields_relation)]")
    available_fields = fields.Selection([
                            ('info', 'Info Generica'),
                            ('fiscal_accounting_id', 'Concepto Fiscal'),
                            ('concept_dian',  'Concepto DIAN'),
                            ('format',  'Formato Archivo'),
                            ('document_type', 'Tipo Documento Tercero'),
                            ('vat', 'Número Documento Tercero'),
                            ('first_name', 'Primer Nombre'),
                            ('second_name', 'Segundo Nombre'),
                            ('first_lastname', 'Primer Apellido'),
                            ('second_lastname', 'Segundo Apellido'),
                            ('commercial_company_name', 'Razón Social'),
                            ('digit_verification', 'Dígito de Verificación'),
                            ('email', 'Email'),
                            ('street', 'Dirección'),
                            ('state_id', 'Código Departamento'),
                            ('city', 'Código Ciudad'),
                            ('amount_1001', 'Pago o abono en cuenta deducible'),
                            ('amount_1003', 'Retención que le practicaron'),
                            ('amount_1005', 'Impuesto Descontable'),
                            ('amount_1006', 'Impuesto generado'),
                            ('amount_1007', 'Ingresos brutos recibidos'),
                            ('amount_1008', 'Saldo cuentas por cobrar al 31-12'),
                            ('amount_1009', 'Saldo cuentas por pagar al 31-12'),
                            ('amount_1009', 'Saldo cuentas por pagar al 31-12'),
                            ('amount_1010', 'Valor patrimonial acciones o aportes al 31-12'),
                            ('amount_ind', 'Valor al 31-12'),
                            ('amount', 'Valor o Balance'),
                            ('inc','Impuesto al consumo'),
                            ('amount_no_dedu','Pago o abono en cuenta NO deducible'),
                            ('iva_mayor','IVA mayor valor del costo o gasto, deducible'),
                            ('iva_no_dedu','IVA mayor valor del costo o gasto no deducible'),
                            ('rete','Retención en la fuente practicada Renta'),
                            ('rete_asu','Retención en la fuente asumida Renta'),
                            ('rete_iva','Retención en la fuente practicada IVA a responsables del IVA'),
                            ('rete_iva_no_dom','Retención en la fuente practicada IVA a no residentes o no domiciliados'),
                            ('dev_ing','Devoluciones, rebajas y descuentos'),
                            ('dev_iva_sale','IVA resultante por devoluciones en ventas anuladas. rescindidas o resueltas'),
                            ('dev_iva_purchase','IVA recuperado en devoluciones en compras anuladas. rescindidas o resueltas'),
                            ('operator', 'Operador'),
                            ('rate_part', 'Porcentaje de participación'),
                            ('rate_part_dec', 'Porcentaje de participación (posición decimal)'),
                            ('tax_1003', 'Valor acumulado del pago o abono sujeto a Retención en la fuente'),
                            ('code_dian', 'Código País DIAN'),
                            ('phone', 'Teléfono Tercero'),
                            ('unit_rate', 'Tarifa Aplicada'),
                            ('amount_payroll_1','Pagos por Salarios'),
                            ('amount_payroll_2','Pagos por emolumentos eclesiásticos'),
                            ('amount_payroll_3','Pagos realizados con bonos electrónicos o de papel de servicio, cheques, tarjetas, vales, etc.'),
                            ('amount_payroll_4','Valor del exceso de los pagos por alimentación mayores a 41 UVT, art. 387-1 E.T.'),
                            ('amount_payroll_5','Pagos por honorarios'),
                            ('amount_payroll_6','Pagos por servicios'),
                            ('amount_payroll_7','Pagos por comisiones'),
                            ('amount_payroll_8','Pagos por prestaciones sociales'),
                            ('amount_payroll_9','Pagos por viáticos'),
                            ('amount_payroll_10','Pagos por gastos de representación'),
                            ('amount_payroll_11','Pagos por compensaciones trabajo asociado cooperativo'),
                            ('amount_payroll_12','Valor apoyos económicos no reembolsables o condonados, entregados por el Estado o financiados con recursos públicos, para financiar programas educativos.'),
                            ('amount_payroll_13','Otros pagos'),
                            ('amount_payroll_14','Cesantías e intereses de cesantías efectivamente pagadas al empleado'),
                            ('amount_payroll_15','Cesantías consignadas al fondo de cesantías'),
                            ('amount_payroll_16','Auxilio de cesantías reconocido a trabajadores del régimen tradicional del Código Sustantivo del Trabajo, Capítulo VII, Título VIII Parte Primera'),
                            ('amount_payroll_17','Pensiones de Jubilación, vejez o invalidez'),
                            ('amount_payroll_18','Total ingresos brutos por rentas de trabajo y pensión'),
                            ('amount_payroll_19','Aportes obligatorios por salud a cargo del trabajador'),
                            ('amount_payroll_20','Aportes obligatorios a fondos de pensiones y solidaridad pensional a cargo del trabajador'),
                            ('amount_payroll_21','Aportes voluntarios al régimen de ahorro individual con solidaridad - RAIS'),
                            ('amount_payroll_22','Aportes voluntarios a fondos de pensiones voluntarias'),
                            ('amount_payroll_23','Aportes a cuentas AFC'),
                            ('amount_payroll_24','Aportes a cuentas AVC'),
                            ('amount_payroll_25','Valor de las retenciones en la fuente por pagos de rentas de trabajo o pensiones'),
                            ('amount_payroll_26','Impuesto sobre las ventas – IVA, mayor valor del costo o gasto'),
                            ('amount_payroll_27','Retención en la fuente a título de impuesto sobre las ventas – IVA.'),
                            ('amount_payroll_28','Pagos por alimentación hasta 41 UVT'),
                            ('amount_payroll_29','Valor ingreso laboral promedio de los últimos seis meses.'),
                              ], 'Campos Seleccionados')
    @api.onchange('available_fields')
    def _onchange_available_fields(self):
        if self.available_fields:
            field_name = self.available_fields
            field_value = getattr(self, field_name, False)
            if field_value:
                self.name = str(field_value)
            else:
                self.name = ''

class generate_media_magnetic(models.TransientModel):
    _name = 'generate.media.magnetic'
    _description = 'Generar Medios Magneticos'

    company_id = fields.Many2one('res.company',string='Compañia', readonly=True,required=True, default=lambda self: self.env.company)
    type_media_magnetic = fields.Selection([('dian', 'Generar Artículo 631'),
                                            ('distrital', 'Generar Impuesto Distrital')],'Tipo de medio magnético', default='dian')
    year =  fields.Integer(string="Año", required=True)
    formatos = fields.Many2many('format.encab', string='Formatos')
    excel_file = fields.Binary('Excel file')
    excel_file_name = fields.Char('Excel name')

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, "Generar Medios Magnético {}".format(record.type_media_magnetic.upper())))
        return result

    def right(s, amount):
        return s[-amount:]

    def get_partners_accounts_info(self, cta_cod):
        current_year_query = """
            SELECT
                aa.code AS code_cuenta,
                aml.account_id AS cuenta,
                COALESCE(aml.partner_id, -1) AS id_partner,
                SUM(CASE WHEN aml.debit > 0 THEN 1 ELSE -1 END * aml.tax_base_amount) AS base,
                SUM(aml.debit) AS debito,
                SUM(aml.credit) AS credito,
                SUM(aml.balance) AS balance,
                COALESCE(ac.amount, 
                    CASE
                        WHEN SUM(aml.tax_base_amount) = 0 THEN 0
                        ELSE ROUND(ABS(SUM(aml.balance) / SUM(aml.tax_base_amount)), 5)
                    END,
                    0
                ) AS tarifa
            FROM
                account_move_line aml
                INNER JOIN account_account aa ON aa.id = aml.account_id
                INNER JOIN account_move am ON am.id = aml.move_id
                LEFT JOIN account_tax ac ON ac.id = aml.tax_line_id
            WHERE
                aa.code IN %s
                AND am.state = 'posted'
                AND EXTRACT(YEAR FROM aml.date) = %s
                AND aml.company_id = %s
            GROUP BY
                aa.code,
                aml.account_id,
                COALESCE(aml.partner_id, -1),
                ac.amount;
        """
    
        previous_years_query = """
            SELECT
                aa.code AS code_cuenta,
                aml.account_id AS cuenta,
                COALESCE(aml.partner_id, -1) AS id_partner,
                SUM(CASE WHEN aml.debit > 0 THEN 1 ELSE -1 END * aml.tax_base_amount) AS base,
                SUM(aml.debit) AS debito,
                SUM(aml.credit) AS credito,
                SUM(aml.balance) AS balance,
                COALESCE(ac.amount, 
                    CASE
                        WHEN SUM(aml.tax_base_amount) = 0 THEN 0
                        ELSE ROUND(ABS(SUM(aml.balance) / SUM(aml.tax_base_amount)), 5)
                    END,
                    0
                ) AS tarifa
            FROM
                account_move_line aml
                INNER JOIN account_account aa ON aa.id = aml.account_id
                INNER JOIN account_move am ON am.id = aml.move_id
                LEFT JOIN account_tax ac ON ac.id = aml.tax_line_id
            WHERE
                aa.code IN %s
                AND am.state = 'posted'
                AND EXTRACT(YEAR FROM aml.date) <= %s
                AND aml.company_id = %s
            GROUP BY
                aa.code,
                aml.account_id,
                COALESCE(aml.partner_id, -1),
                ac.amount;
        """
    
        try:
            params = (tuple(cta_cod), self.year, self.env.company.id)
            self.env.cr.execute(current_year_query, params)
            current_year_data = self.env.cr.dictfetchall()
    
            params = (tuple(cta_cod), self.year, self.env.company.id)
            self.env.cr.execute(previous_years_query, params)
            previous_years_data = self.env.cr.dictfetchall()
    
            current_year_moves = []
            previous_years_moves = []
    
            for move in current_year_data:
                current_year_moves.append({
                    'code_cuenta': move['code_cuenta'],
                    'id_partner': move['id_partner'],
                    'tax_base_amount': str(move['base'] or 0).split('.')[0],
                    'debit': str(move['debito'] or 0).split('.')[0],
                    'credit': str(move['credito'] or 0).split('.')[0],
                    'balance': str(move['balance'] or 0).split('.')[0],
                    'saldo': str(move['balance'] or 0).split('.')[0],
                    'saldo_legado': '0',
                    'tarifa': str(abs(move['tarifa'] or 0) * 1000)[:4]
                })
    
            for move in previous_years_data:
                previous_years_moves.append({
                    'code_cuenta': move['code_cuenta'],
                    'id_partner': move['id_partner'],
                    'tax_base_amount': str(move['base'] or 0).split('.')[0],
                    'debit': str(move['debito'] or 0).split('.')[0],
                    'credit': str(move['credito'] or 0).split('.')[0],
                    'balance': str(move['balance'] or 0).split('.')[0],
                    'saldo': str(move['balance'] or 0).split('.')[0],
                    'saldo_legado': '0',
                    'tarifa': str(abs(move['tarifa'] or 0) * 1000)[:4]
                })
    
            current_year_all_data = {}
            previous_years_all_data = {}
    
            for move in current_year_moves:
                code_cuenta = move['code_cuenta']
                id_partner = move['id_partner']
                
                if code_cuenta not in current_year_all_data:
                    current_year_all_data[code_cuenta] = {}
                
                if id_partner not in current_year_all_data[code_cuenta]:
                    current_year_all_data[code_cuenta][id_partner] = {
                        'tax_base_amount': 0,
                        'debit': 0,
                        'credit': 0,
                        'balance': 0,
                        'saldo': 0,
                        'saldo_legado': 0,
                        'tarifa': 0
                    }
                
                current_year_all_data[code_cuenta][id_partner]['tax_base_amount'] += int(move['tax_base_amount'] or 0)
                current_year_all_data[code_cuenta][id_partner]['debit'] += int(move['debit'] or 0)
                current_year_all_data[code_cuenta][id_partner]['credit'] += int(move['credit'] or 0)
                current_year_all_data[code_cuenta][id_partner]['balance'] += int(move['balance'] or 0)
                current_year_all_data[code_cuenta][id_partner]['saldo'] += int(move['saldo'] or 0)
                current_year_all_data[code_cuenta][id_partner]['tarifa'] = move['tarifa']
    
            for move in previous_years_moves:
                code_cuenta = move['code_cuenta']
                id_partner = move['id_partner']
                
                if code_cuenta not in previous_years_all_data:
                    previous_years_all_data[code_cuenta] = {}
                
                if id_partner not in previous_years_all_data[code_cuenta]:
                    previous_years_all_data[code_cuenta][id_partner] = {
                        'tax_base_amount': 0,
                        'debit': 0,
                        'credit': 0,
                        'balance': 0,
                        'saldo': 0,
                        'saldo_legado': 0,
                        'tarifa': 0
                    }
                
                previous_years_all_data[code_cuenta][id_partner]['tax_base_amount'] += int(move['tax_base_amount'] or 0)
                previous_years_all_data[code_cuenta][id_partner]['debit'] += int(move['debit'] or 0)
                previous_years_all_data[code_cuenta][id_partner]['credit'] += int(move['credit'] or 0)
                previous_years_all_data[code_cuenta][id_partner]['balance'] += int(move['balance'] or 0)
                previous_years_all_data[code_cuenta][id_partner]['saldo'] += int(move['saldo'] or 0)
                previous_years_all_data[code_cuenta][id_partner]['tarifa'] = move['tarifa']
    
            current_year_all_moves = []
            for code_cuenta, partners in current_year_all_data.items():
                for id_partner, move_data in partners.items():
                    current_year_all_moves.append({
                        'code_cuenta': code_cuenta,
                        'id_partner': id_partner,
                        'tax_base_amount': str(move_data['tax_base_amount']),
                        'debit': str(move_data['debit']),
                        'credit': str(move_data['credit']),
                        'balance': str(move_data['balance']),
                        'saldo': str(move_data['saldo']),
                        'saldo_legado': str(move_data['saldo_legado']),
                        'tarifa': move_data['tarifa']
                    })
    
            previous_years_all_moves = []
            for code_cuenta, partners in previous_years_all_data.items():
                for id_partner, move_data in partners.items():
                    previous_years_all_moves.append({
                        'code_cuenta': code_cuenta,
                        'id_partner': id_partner,
                        'tax_base_amount': str(move_data['tax_base_amount']),
                        'debit': str(move_data['debit']),
                        'credit': str(move_data['credit']),
                        'balance': str(move_data['balance']),
                        'saldo': str(move_data['saldo']),
                        'saldo_legado': str(move_data['saldo_legado']),
                        'tarifa': move_data['tarifa']
                    })
    
            return current_year_moves, previous_years_moves, current_year_all_moves, previous_years_all_moves
    
        except Exception as e:
            raise ValidationError("Problemas consultando la base de datos: " + str(e))
    def _get_saldo_legado(self, acc):
        sql = """                
                select 
                    aa.code as code_cuenta,
                    aml.account_id as cuenta, 
                    aml.partner_id as id_partner, 
                    sum(aml.balance) as balance 
                    from account_move_line aml
                    inner join account_account aa on aa.id = aml.account_id 
                    inner join account_move am on am.id = aml.move_id
                    where aa.code = %s
                    and am.state = 'posted'
                    and extract(year from aml.date)<%s
                    and aml.company_id=%s
                    group by aml.account_id, aml.partner_id, aa.code;
                """
        try:
            self.env.cr.execute(sql, [acc, self.year, self.env.company.id])
            result = self.env.cr.fetchall()
            return [{'partner_id': item[2], 'saldo': item[3]} for item in result]

        except Exception as e:
            raise ValidationError("La actualización del informe no puede realizarse: " + str(e))
        return False

    # - Obtain legacy balance last year of version selected
    # - return a dictionary with account and legacy balance
    def get_saldos_legados_by_accounts(self, acc_ids):
        saldos = []
        for acc in acc_ids:
            saldos.append({
                'acc': acc,
                'saldos': self._get_saldo_legado(acc)
            })
        return saldos


    def generate_media_magnetic_dian(self):
        # Variables excel
        filename = f'MedioMagnetico_{self.year}.xlsx'
        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {'in_memory': True})
        # Variables proceso
        date_start = datetime(self.year, 1, 1).date()
        date_end = datetime(self.year, 12, 31).date()
        minor_amounts = 0
        account_moves_ids = []
        data = defaultdict(list)
        accounts = defaultdict(dict)
        merged_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
        # Traer todos los formatos
        obj_formats = self.formatos or self.env['format.encab'].search([])
    
        for i, format in enumerate(obj_formats, start=1):
            for rec in format.fields_associated_code_fiscal_ids.line_ids:
                if rec:
                    for account_id in rec.account_ids:
                        data['concepts'].append({
                            'id_aux': i,
                            'concept_id': format.fields_associated_code_fiscal_ids.id,
                            'concept_code': format.fields_associated_code_fiscal_ids.concept_dian,
                            'account_type': format.fields_associated_code_fiscal_ids.account_type,
                            'move_type': format.fields_associated_code_fiscal_ids.move_type,
                            'account_id': account_id.id,
                            'account_code': account_id.code,
                            'fields_data': rec.available_fields,
                        })
    
        account_codes = sorted(set(concept['account_code'] for concept in data['concepts']))
        if not account_codes:
            raise ValidationError("No se encuentran registros de movimientos contables asociadas a las cuentas relacionadas")
    
        current_year_moves, previous_years_moves, current_year_all_moves, previous_years_all_moves = self.get_partners_accounts_info(account_codes)
    
        for move in current_year_moves + previous_years_moves:
                account_code = move['code_cuenta']
                partner_id = move['id_partner']
                for concept in data['concepts']:
                    if concept['account_code'] == account_code:
                        concept['partner_ids'][partner_id]['tax_base_amount'] += int(move['tax_base_amount'] or 0)
                        concept['partner_ids'][partner_id]['debit'] += int(move['debit'] or 0)
                        concept['partner_ids'][partner_id]['credit'] += int(move['credit'] or 0)
                        concept['partner_ids'][partner_id]['balance'] += int(move['balance'] or 0)
                        concept['partner_ids'][partner_id]['saldo'] += int(move['saldo'] or 0)
                        concept['partner_ids'][partner_id]['saldo_legado'] += int(move['saldo_legado'] or 0)
                        concept['partner_ids'][partner_id]['tarifa'] = move['tarifa']
        
                for concept in data['concepts']:
                    account_code = concept['account_code']
                    merged_data[account_code]['account_id'] = concept['account_id']
                    merged_data[account_code]['fields_data'] = concept['fields_data']
                    merged_data[account_code]['partner_ids'] = concept['partner_ids']
                    merged_data[account_code]['saldo_legado'] = 0
        
        _logger.error(f"----> no hace nada de momento TT_TT {merged_data}")
        return True
        for format in obj_formats:
            obj_account_fiscal = self.env['fiscal.accounting.code'].search([('format_id','=',format.id)])
            lst_Mvto = []
            lst_partner_minor = []
            for fiscal in obj_account_fiscal:
                obj_group_fiscal = self.env['fiscal.accounting.group'].search([('concept_dian_ids', 'in', fiscal.ids)],limit=1)
                partner_ids = [] 
                dict_partner_minor = {}
                dict_partner_minor_associated = {}                                                           
                format_fields = fiscal.format_id.details_ids
                if fiscal.line_ids:
                    if fiscal.account_type == "movement":
                        partner_ids = self.env['account.move.line'].search([('date', '>=', date_start),
                                                                            ('date', '<=', date_end),
                                                                            ('move_id.state','=','posted'),
                                                                            ('move_id.accounting_closing_id','=',False),
                                                                            ('journal_id','not in', fiscal.line_ids.excluded_documents_ids.ids),
                                                                            ('account_id', 'in', fiscal.line_ids.account_ids.ids)]).mapped('partner_id').ids
                    else:
                        partner_ids = self.env['account.move.line'].search([('date', '<=', date_end),
                                                                            ('move_id.state','=','posted'),
                                                                            ('move_id.accounting_closing_id','=',False),
                                                                            ('journal_id','not in', fiscal.line_ids.excluded_documents_ids.ids),
                                                                            ('account_id', 'in', fiscal.line_ids.account_ids.ids)]).mapped('partner_id').ids 
                        
                obj_partner_ids = self.env['res.partner'].search([('id','in',partner_ids)])
                for partner in obj_partner_ids:
                    amount = 0
                    dev_ing = 0
                    tax_base_amount = 0
                    amount_no_dedu = 0
                    iva_mayor = 0
                    rete = 0
                    rete_asu = 0
                    rete_iva = 0
                    iva_no_dedu = 0
                    rete_iva_no_dom =0
                    for rec in fiscal.line_ids:
                        if fiscal.account_type == "movement":
                            moves = self.env['account.move.line'].search([('date', '>=', date_start),
                                                                    ('date', '<=', date_end),
                                                                    ('parent_state','=','posted'),
                                                                    ('journal_id','not in', rec.excluded_documents_ids.ids),
                                                                    ('move_id.accounting_closing_id','=',False),
                                                                    ('account_id', 'in', rec.account_ids.ids),
                                                                    ('partner_id', '=', partner.id)])
                        else:
                            moves = self.env['account.move.line'].search([('date', '<=', date_end),
                                                                    ('parent_state','=','posted'),
                                                                    ('journal_id','not in', rec.excluded_documents_ids.ids),
                                                                    ('move_id.accounting_closing_id','=',False),
                                                                    ('account_id', 'in', rec.account_ids.ids),
                                                                    ('partner_id', '=', partner.id)])
                        account_moves_ids = account_moves_ids + moves.ids
                        if rec.available_fields == 'amount':
                            if fiscal.move_type == 'debit':
                                amount += (sum(map(lambda x: x.debit, moves))*(rec.porcentaje/100))
                            elif fiscal.move_type == 'credit':
                                amount += sum(map(lambda x: x.credit, moves))*(rec.porcentaje/100)
                            else:
                                amount += sum(map(lambda x: x.balance, moves))*(rec.porcentaje/100)
                        elif rec.available_fields == 'dev_ing':
                            if fiscal.move_type == 'debit':
                                dev_ing += sum(map(lambda x: x.debit, moves))*(rec.porcentaje/100)
                            elif fiscal.move_type == 'credit':
                                dev_ing += sum(map(lambda x: x.credit, moves))*(rec.porcentaje/100)
                            else:
                                dev_ing += sum(map(lambda x:x.balance, moves))*(rec.porcentaje/100)
                        elif rec.available_fields == 'amount_no_dedu':
                            if fiscal.move_type == 'debit':
                                amount_no_dedu += sum(map(lambda x: x.debit, moves))*(rec.porcentaje/100)
                            elif fiscal.move_type == 'credit':
                                amount_no_dedu += sum(map(lambda x: x.credit, moves))*(rec.porcentaje/100)
                            else:
                                amount_no_dedu += sum(map(lambda x:x.balance, moves))*(rec.porcentaje/100)
                        elif rec.available_fields == 'iva_mayor':
                            if fiscal.move_type == 'debit':
                                iva_mayor += sum(map(lambda x: x.debit, moves))*(rec.porcentaje/100)
                            elif fiscal.move_type == 'credit':
                                iva_mayor += sum(map(lambda x: x.credit, moves))*(rec.porcentaje/100)
                            else:
                                iva_mayor += sum(map(lambda x:x.balance, moves))*(rec.porcentaje/100)
                        elif rec.available_fields == 'rete':
                            if fiscal.move_type == 'debit':
                                rete += sum(map(lambda x: x.debit, moves))*(rec.porcentaje/100)
                            elif fiscal.move_type == 'credit':
                                rete += sum(map(lambda x: x.credit, moves))*(rec.porcentaje/100)
                            else:
                                rete += sum(map(lambda x:x.balance, moves))*(rec.porcentaje/100)
                        elif rec.available_fields == 'rete_asu':
                            if fiscal.move_type == 'debit':
                                rete_asu += sum(map(lambda x: x.debit, moves))*(rec.porcentaje/100)
                            elif fiscal.move_type == 'credit':
                                rete_asu += sum(map(lambda x: x.credit, moves))*(rec.porcentaje/100)
                            else:
                                rete_asu += sum(map(lambda x:x.balance, moves))*(rec.porcentaje/100)
                        elif rec.available_fields == 'rete_iva':
                            if fiscal.move_type == 'debit':
                                rete_iva += sum(map(lambda x: x.debit, moves))*(rec.porcentaje/100)
                            elif fiscal.move_type == 'credit':
                                rete_iva += sum(map(lambda x: x.credit, moves))*(rec.porcentaje/100)
                            else:
                                rete_iva += sum(map(lambda x:x.balance, moves))*(rec.porcentaje/100)
                        elif rec.available_fields == 'iva_no_dedu':
                            if fiscal.move_type == 'debit':
                                iva_no_dedu += sum(map(lambda x: x.debit, moves))*(rec.porcentaje/100)
                            elif fiscal.move_type == 'credit':
                                iva_no_dedu += sum(map(lambda x: x.credit, moves))*(rec.porcentaje/100)
                            else:
                                iva_no_dedu += sum(map(lambda x:x.balance, moves))*(rec.porcentaje/100)
                        elif rec.available_fields == 'rete_iva_no_dom':
                            if fiscal.move_type == 'debit':
                                rete_iva_no_dom += sum(map(lambda x: x.debit, moves))*(rec.porcentaje/100)
                            elif fiscal.move_type == 'credit':
                                rete_iva_no_dom += sum(map(lambda x: x.credit, moves))*(rec.porcentaje/100)
                            else:
                                rete_iva_no_dom += sum(map(lambda x:x.balance, moves))*(rec.porcentaje/100)
                        tax_base_amount += sum(map(lambda x:x.tax_base_amount, moves))
                    
                    if len(obj_group_fiscal) > 0:
                        ldict = {'amount':amount,'validation_minor':False}
                        code_python = f'validation_minor = True if amount {obj_group_fiscal.operator} {obj_group_fiscal.amount}  else False'
                        exec(code_python,ldict)
                        validation_minor = ldict.get('validation_minor')
                    else:
                        validation_minor = False
                    
                    if validation_minor == False and (abs(tax_base_amount) + abs(dev_ing) + abs(amount) != 0.0):
                        #Armamos el dict con la información
                        #dict_documents = dict(self.env['res.partner']._fields['vat_type'].selection)
                        #document_type = dict_documents.get(partner.vat_type) if partner.vat_type else ''
                        razon_social = ''
                        if partner.company_type == 'company':
                            razon_social = partner.name
                        else: 
                            razon_social = ''
                        city_fix = ''
                        if partner.city_id:
                            city_fix = partner.city_id.code_dian
                        else:
                            city_fix = 'Falta la Ciudad'
                        info = {'fiscal_accounting_id': fiscal.concept or fiscal.concept_dian,
                                'concept_dian': fiscal.code_description,
                                'format':fiscal.format_id.format_id,
                                'x_document_type': partner.document_type or 'Falta Tipo de Documento',
                                'vat': partner.vat_co or 'No Tiene Nit',
                                'x_first_name': partner.firs_name or '',
                                'x_second_name': partner.second_name if partner.second_name else '',
                                'x_first_lastname': partner.first_lastname or '',
                                'x_second_lastname': partner.second_lastname or '',
                                'commercial_company_name': razon_social,# partner.name,
                                'x_digit_verification': partner.vat_vd or '',
                                'street': partner.street or 'Falta Direccion',
                                'state_id': partner.state_id.code_dian or '',
                                'x_city': city_fix, #partner.cities.city_code[3:] if partner.cities.city_code else '',
                                'amount': round(amount, 0),
                                'dev_ing' : round(dev_ing, 0),
                                'tax_base_amount' : round(tax_base_amount, 0),
                                'amount_no_dedu' : round(amount_no_dedu, 0),
                                'iva_mayor' : round(iva_mayor, 0),
                                'rete' : round(rete, 0),
                                'rete_asu' : round(rete_asu, 0),
                                'rete_iva' : round(rete_iva, 0),
                                'iva_no_dedu' : round(iva_no_dedu, 0),
                                'rete_iva_no_dom' : round(rete_iva_no_dom, 0),
                                'operator':obj_group_fiscal.operator,
                                'tax': tax_base_amount,
                                'x_code_dian': partner.country_id.code_dian or '',
                                'phone': partner.phone or partner.mobile,
                                'unit_rate': 0,
                                'email': partner.email,
                                'higher_value_iva': 0,
                            }
                        #Formatos asociados
                        info_associated = {}
                        obj_account_fiscal_associated = self.env['fiscal.accounting.code'].search([('format_id', '=', format.format_associated_id.id)])
                        for fiscal_associated in obj_account_fiscal_associated:
                            if (fiscal_associated.required_retention_associated == False):
                                obj_retention_associated = self.env['fiscal.accounting.code'].search([('id','in',fiscal_associated.ids),('retention_associated','=',fiscal.id)])
                            else:
                                obj_retention_associated = self.env['fiscal.accounting.code'].search([('id', 'in', fiscal_associated.ids)])
                            moves_associated = self.env['account.move.line'].search(
                                [('date', '>=', date_start), ('date', '<=', date_end),('move_id.state','=','posted'),
                                ('move_id.accounting_closing_id','=',False),('account_id', 'in', obj_retention_associated.accounting_details_ids.ids), ('partner_id', '=', partner.id)])
                            amount_associated = abs(sum([i.balance for i in moves_associated]))
                            name_associated = fiscal_associated.code_description.replace(' ','_')
                            info_associated[name_associated] = amount_associated
                        #Guardado final
                        media_magnetic = {}
                        for field in sorted(format_fields, key=lambda x: x.sequence):
                            if field.available_fields in info:
                                media_magnetic[field.available_fields] = info.get(field.available_fields)
                        lst_Mvto.append({**media_magnetic, **info_associated})
                    else:
                        #Armamos el dict con la información
                        dict_partner_minor['fiscal_info'] = fiscal
                        dict_partner_minor['group_fiscal'] = obj_group_fiscal
                        dict_partner_minor['amount'] = dict_partner_minor.get('amount',0) + amount
                        dict_partner_minor['amount_no_dedu'] = dict_partner_minor.get('amount_no_dedu', 0) + amount_no_dedu
                        dict_partner_minor['iva_mayor'] = dict_partner_minor.get('iva_mayor', 0) + iva_mayor
                        dict_partner_minor['rete'] = dict_partner_minor.get('rete', 0) + rete
                        dict_partner_minor['rete_asu'] = dict_partner_minor.get('rete_asu', 0) + rete_asu
                        dict_partner_minor['rete_iva'] = dict_partner_minor.get('rete_iva', 0) + rete_iva
                        dict_partner_minor['iva_no_dedu'] = dict_partner_minor.get('iva_no_dedu', 0) + iva_no_dedu
                        dict_partner_minor['rete_iva_no_dom'] = dict_partner_minor.get('rete_iva_no_dom', 0) + rete_iva_no_dom
                        dict_partner_minor['tax'] = dict_partner_minor.get('tax', 0) + tax_base_amount
                        
                        #Formatos asociados
                        obj_account_fiscal_associated = self.env['fiscal.accounting.code'].search([('format_id', '=', format.format_associated_id.id)])
                        for fiscal_associated in obj_account_fiscal_associated:
                            if (fiscal_associated.required_retention_associated == False):
                                obj_retention_associated = self.env['fiscal.accounting.code'].search([('id','in',fiscal_associated.ids),('retention_associated','=',fiscal.id)])
                            else:
                                obj_retention_associated = self.env['fiscal.accounting.code'].search([('id', 'in', fiscal_associated.ids)])
                            moves_associated = self.env['account.move.line'].search(
                                [('date', '>=', date_start), ('date', '<=', date_end),('move_id.state','=','posted'),
                                ('move_id.accounting_closing_id','=',False),('account_id', 'in', obj_retention_associated.accounting_details_ids.ids), ('partner_id', '=', partner.id)])
                            amount_associated = abs(sum([i.balance for i in moves_associated]))
                            name_associated = fiscal_associated.code_description.replace(' ','_')
                            dict_partner_minor_associated[name_associated] = dict_partner_minor_associated.get(name_associated, 0) + amount_associated

                if len(dict_partner_minor) > 0:
                    #dict_documents = dict(self.env['res.partner']._fields['vat_type'].selection)
                    #document_type = dict_documents.get(
                    #    dict_partner_minor.get('group_fiscal').partner_minor_amounts.vat_type) if dict_partner_minor.get('group_fiscal').partner_minor_amounts.vat_type else ''
                    info = {'fiscal_accounting_id': dict_partner_minor.get('fiscal_info').concept or dict_partner_minor.get('fiscal_info').concept_dian,
                            'concept_dian': dict_partner_minor.get('fiscal_info').code_description,
                            'format': dict_partner_minor.get('fiscal_info').format_id.format_id,
                            'x_document_type':  dict_partner_minor.get('group_fiscal').partner_minor_amounts.document_type,
                            'vat': dict_partner_minor.get('group_fiscal').partner_minor_amounts.vat_co,
                            'x_first_name': dict_partner_minor.get('group_fiscal').partner_minor_amounts.firs_name or '',
                            'x_second_name': dict_partner_minor.get('group_fiscal').partner_minor_amounts.second_name or '',
                            'x_first_lastname': dict_partner_minor.get('group_fiscal').partner_minor_amounts.first_lastname or '',
                            'x_second_lastname': dict_partner_minor.get('group_fiscal').partner_minor_amounts.second_lastname or '' ,
                            'commercial_company_name': dict_partner_minor.get('group_fiscal').partner_minor_amounts.name,
                            'x_digit_verification': dict_partner_minor.get('group_fiscal').partner_minor_amounts.vat_vd or '',
                            'street': dict_partner_minor.get('group_fiscal').partner_minor_amounts.street,
                            'state_id': dict_partner_minor.get('group_fiscal').partner_minor_amounts.state_id.code_dian,
                            'x_city': dict_partner_minor.get('group_fiscal').partner_minor_amounts.city_id.code_dian,
                            'amount': abs(dict_partner_minor.get('amount',0)),
                            'dev_ing': abs(dict_partner_minor.get('dev_ing',0)),
                            'amount_no_dedu': abs(dict_partner_minor.get('amount_no_dedu',0)),
                            'iva_mayor': abs(dict_partner_minor.get('iva_mayor',0)),
                            'rete': abs(dict_partner_minor.get('rete',0)),
                            'rete_asu': abs(dict_partner_minor.get('rete_asu',0)),
                            'iva_no_dedu': abs(dict_partner_minor.get('iva_no_dedu',0)),
                            'rete_iva_no_dom': abs(dict_partner_minor.get('rete_iva_no_dom',0)),
                            'rete_iva': abs(dict_partner_minor.get('rete_iva',0)),
                            'operator': dict_partner_minor.get('group_fiscal').operator,
                            'tax': dict_partner_minor.get('tax',0),
                            'x_code_dian': '169', #dict_partner_minor.get('group_fiscal').partner_minor_amounts.country_id.code,
                            'phone': dict_partner_minor.get('group_fiscal').partner_minor_amounts.phone or dict_partner_minor.get('group_fiscal').partner_minor_amounts.mobile,
                            'unit_rate': 0,
                            'email': dict_partner_minor.get('group_fiscal').partner_minor_amounts.email,
                            'higher_value_iva': 0,
                            }
                    #Guardado final
                    media_magnetic = {}
                    for field in sorted(format_fields, key=lambda x: x.sequence):
                        if field.available_fields in info:
                            media_magnetic[field.available_fields] = info.get(field.available_fields)
                    lst_Mvto.append({**media_magnetic, **dict_partner_minor_associated})
                    lst_partner_minor.append({**dict_partner_minor, **dict_partner_minor_associated})
            #Generar hoja de excel
            sheet = book.add_worksheet(format.format_id)
            if len(lst_Mvto) == 0:
                continue
            columns = []
            for field in lst_Mvto[0].keys():
                field_name = dict(self.env['format.detail']._fields['available_fields'].selection).get(field,field.replace('_',' '))
                columns.append(field_name)
            # Agregar columnas
            aument_columns = 0
            for column in columns:
                sheet.write(0, aument_columns, column)
                aument_columns = aument_columns + 1
            # Agregar valores
            aument_columns = 0
            aument_rows = 1
            for info in lst_Mvto:
                for row in info.values():
                    width = len(str(row)) + 10
                    sheet.write(aument_rows, aument_columns, row)
                    # Ajustar tamaño columna
                    sheet.set_column(aument_columns, aument_columns, width)
                    aument_columns = aument_columns + 1
                aument_rows = aument_rows + 1
                aument_columns = 0

            # Convertir en tabla
            array_header_table = []
            for i in columns:
                dict_h = {'header': i}
                array_header_table.append(dict_h)
            sheet.add_table(0, 0, aument_rows-1, len(columns)-1, {'style': 'Table Style Medium 2', 'columns': array_header_table})

        # Generar hoja de excel resumen
        sheet_resumen = book.add_worksheet("Resumen")
        columns = ['Documento','Fecha','Referencia','Débito','Crédito','Balance','Número Documento','Nombre','Cuenta','Descripción Cuenta','Cuenta Analítíca']
        # Agregar columnas
        aument_columns = 0
        for column in columns:
            sheet_resumen.write(0, aument_columns, column)
            aument_columns = aument_columns + 1
        #Agrefar info
        date_format = book.add_format({'num_format': 'dd/mm/yyyy'})
        info_moves = self.env['account.move.line'].search([('id', 'in', account_moves_ids)])
        aument_rows_resumen = 1
        for move in info_moves:
            sheet_resumen.write(aument_rows_resumen, 0, move.move_name)
            sheet_resumen.set_column(0, 0, len(str(move.move_name))+13)
            sheet_resumen.write_datetime(aument_rows_resumen, 1, move.date, date_format)
            sheet_resumen.set_column(1, 1, len(str(move.date)) + 10)
            sheet_resumen.write(aument_rows_resumen, 2, move.ref)
            sheet_resumen.set_column(2, 2, len(str(move.ref)) + 10)
            sheet_resumen.write(aument_rows_resumen, 3, move.debit)
            sheet_resumen.set_column(3, 3, len(str(move.debit)) + 10)
            sheet_resumen.write(aument_rows_resumen, 4, move.credit)
            sheet_resumen.set_column(4, 4, len(str(move.credit)) + 15)
            sheet_resumen.write(aument_rows_resumen, 5, move.balance)
            sheet_resumen.set_column(5, 5, len(str(move.balance)) + 10)
            sheet_resumen.write(aument_rows_resumen, 6, move.partner_id.vat)
            sheet_resumen.set_column(6, 6, len(str(move.partner_id.vat)) + 13)
            sheet_resumen.write(aument_rows_resumen, 7, move.partner_id.name)
            sheet_resumen.set_column(7, 7, len(str(move.partner_id.name)) + 13)
            sheet_resumen.write(aument_rows_resumen, 8, move.account_id.code)
            sheet_resumen.set_column(8, 8, len(str(move.account_id.code)) + 13)
            sheet_resumen.write(aument_rows_resumen, 9, move.account_id.name)
            sheet_resumen.set_column(9, 9, len(str(move.account_id.name)) + 15)
            sheet_resumen.write(aument_rows_resumen, 10, move.name)
            sheet_resumen.set_column(10, 10, len(str(move.name)) + 15)
            aument_rows_resumen = aument_rows_resumen + 1

        # Convertir en tabla
        array_header_table_resumen = []
        for i in columns:
            dict_h = {'header': i}
            array_header_table_resumen.append(dict_h)
        sheet_resumen.add_table(0, 0, aument_rows_resumen - 1, len(columns) - 1,
                        {'style': 'Table Style Medium 2', 'columns': array_header_table_resumen})

        book.close()
        self.write({
            'excel_file': base64.b64encode(stream.getvalue()).decode('utf-8'),
            'excel_file_name': filename,
        })

        action = {
            'name': 'Export Medio magnetico información exogena',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=generate.media.magnetic&id=" + str(
                self.id) + "&filename_field=excel_file_name&field=excel_file&download=true&filename=" + self.excel_file_name,
            'target': 'self',
        }
        return action

    def generate_media_magnetic_distrital(self):
        date_start = str(self.year) +'-01-01'
        date_end = str(self.year) +'-12-31'
        lst_Mvto = []

    def generate_media_magnetic(self):
        if self.type_media_magnetic == 'dian':
            return self.generate_media_magnetic_dian()
        if self.type_media_magnetic == 'distrital':
            return self.generate_media_magnetic_distrital()

