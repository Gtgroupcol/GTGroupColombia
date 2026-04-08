import re
from odoo import models, fields, api, _, _lt
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date

from odoo.tools import float_is_zero
from datetime import datetime
from dateutil.relativedelta import relativedelta
#PLAN CONTABLE - PUC
class lavish_reconciling_items_encab(models.Model):
    _name = 'lavish.reconciling.items.encab'
    _description = 'Encabezado partidas conciliatorias'

class AccountGroup(models.Model):
    _inherit = "account.group"

    code_cgn = fields.Char(string='Codigo CGN')
    name = fields.Char(required=True, translate=False)
class account_account(models.Model):
    _name = 'account.account'
    _inherit = ['account.account','mail.thread', 'mail.activity.mixin']

    required_analytic_account = fields.Boolean('Obliga cuenta analítica', tracking=True)
    required_partner = fields.Boolean('Obliga tercero', tracking=True)
    accounting_class = fields.Char('Clase', tracking=True)
    code = fields.Char(tracking=True)
    user_type_id = fields.Many2one(tracking=True)
    tax_ids = fields.Many2many(tracking=True)
    group_id = fields.Many2one(tracking=True)
    company_id = fields.Many2one(tracking=True)
    account_distribution = fields.Boolean(tracking=True)
    exclude_balance_test = fields.Boolean('Permitir filtro de excluir en balance de prueba', tracking=True)
    available_fields = fields.Selection([
                              ('amount', 'Valor Pesos'),
                              ('amount_no_dedu','PAGO O ABONO EN CUENTA NO DEDUCIBLE'),
                              ('iva_mayor','IVA MAYOR VALOR DEL COSTO O GASTO DEDUCIBLE'),
                              ('iva_no_dedu','IVA MAYOR VALOR DEL COSTO O GASTO NO DEDUCIBLE'),
                              ('iva_no_dedu','IVA MAYOR VALOR DEL COSTO O GASTO NO DEDUCIBLE'),
                              ('rete','RETENCIÓN EN LA FUENTE PRACTICADA RENTA CRÉDITO'),
                              ('rete_asu','RETENCIÓN EN LA FUENTE ASUMIDA RENTA'),
                              ('rete_iva','RETENCIÓN EN LA FUENTE PRACTICA IVA REGIMÉN COMÚN'),
                              ('rete_iva_no_dom','RETENCIÓN EN LA FUENTE PRACTICA IVA NO DOMICILIADOS	Parámetro'),
                              ('dev_ing','DEVOLUCIONES. REBAJAS Y DESCUENTOS'),
                              ('tax', 'Base Impuestos'),
                              ], 'Campos Seleccionados Exogena')
    not_disaggregate_partner_balance_test = fields.Boolean('No desagregar por tercero en balance de prueba', tracking=True)
    code_cgn = fields.Char(string='Codigo CGN')
    account_value = fields.Selection([ 
        ('1', 'Corriente'),
        ('2', 'No corriente')], string="Valor de cuenta")    
