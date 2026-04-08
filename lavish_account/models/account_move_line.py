
from odoo import models, fields, api, _

class account_move_line(models.Model):
    _inherit = 'account.move.line'
	
    tax_id = fields.Many2many(related='tax_ids', string="Impuestos")
    type_doc_partner = fields.Char(string='NIT Asociado', store=True, readonly=True, related='partner_id.vat')
    required_analytic_account = fields.Boolean(related='account_id.required_analytic_account', string="Obliga cuenta analítica")
    required_partner = fields.Boolean(related='account_id.required_partner', string="Obliga tercero")
    #Niveles cuenta analitica    
    accounting_class = fields.Char(string='Clase', store=True, readonly=True, related='account_id.accounting_class')
    tax_base_amount = fields.Monetary(string="Base Amount", store=True, readonly=False,  currency_field='company_currency_id')
    #parent_type = fields.Char(string="Tipo movimiento")
    supplier_invoice_number = fields.Char(related='move_id.supplier_invoice_number',string='Nº de factura del proveedor')
    required_analytic_account = fields.Boolean(related='account_id.required_analytic_account', string="Obliga cuenta analítica")
    required_partner = fields.Boolean(related='account_id.required_partner', string="Obliga tercero")
    #Niveles cuenta analitica    
    account_group_id = fields.Many2one(related='account_id.group_id', string='Grupo Cuenta', store=True, readonly=True)