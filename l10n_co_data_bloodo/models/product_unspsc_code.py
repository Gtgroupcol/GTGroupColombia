# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.osv import expression


class ProductCode(models.Model):
    """
    Product and UoM codes defined by UNSPSC
    Used by Mexico, Peru and Colombia localizations
    """
    _name = 'product.unspsc.code'
    _description = "Product and UOM Codes from UNSPSC"

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    applies_to = fields.Selection([('product', 'Product'),
                                   ('uom', 'UoM'), ],
                                  'Applies to',
                                  required=True,
                                  help='Indicate if this code could'
                                  ' be used in products or in UoM',
                                  )
    active = fields.Boolean()

    def _get_complete_name(self):
        result = []
        for prod in self:
            result.append((prod.id, "%s %s" % (prod.code, prod.name or '')))
        return result
    
    @api.depends('name', 'code')
    def _compute_display_name(self):
        for template in self:
            template.display_name = False if not template.name else (
                '{}{}'.format(
                    template.code and '[%s] ' % template.code or '', template.name
                ))
    @api.model
    def _name_search(self, name, args=None, operator='ilike',
                     limit=100, name_get_uid=None,order=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('name', 'ilike', name), ('code', 'ilike', name)]
        return self._search(
            expression.AND([domain, args]),
            limit=limit, order=order,
            access_rights_uid=name_get_uid
        )
