# -*- coding: utf-8 -*-

from odoo import models, fields, api

ACCOUNT_DOMAIN = "['&', ('deprecated', '=', False), ('account_type', 'not in', ('asset_receivable','liability_payable','asset_cash','liability_credit_card','off_balance'))]"


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    property_account_refund_id = fields.Many2one(
        comodel_name='account.account',
        company_dependent=True,
        string='Refund Account',
        domain=ACCOUNT_DOMAIN,
        help='Keep this field empty to use the default value from the product category.'
    )

    height = fields.Float()
    length = fields.Float()
    width = fields.Float()

    @api.onchange('height', 'length', 'width')
    def compute_volume_product(self):
        for record in self:
            record.volume = record.height*record.length*record.width

    def _get_product_accounts(self):
        accounts = super(ProductTemplate, self)._get_product_accounts()
        accounts.update({'refund': self.property_account_refund_id or self.categ_id.property_account_refund_categ_id})
        if self.env.context.get('default_expense'):
            accounts.update(
                {'expense': self.env.context.get('default_expense')}
            )
        return accounts

class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _get_tax_included_unit_price(self, company, currency, document_date, document_type, is_refund_document=False,
                                     product_uom=None, product_currency=None, product_price_unit=None,
                                     product_taxes=None, fiscal_position=None):
        """ Helper to get the price unit from different models.
            This is needed to compute the same unit price in different models (sale order, account move, etc.) with same parameters.
        """

        product = self

        assert document_type

        if product_uom is None:
            product_uom = product.uom_id
        if not product_currency:
            if document_type == 'sale':
                product_currency = product.currency_id
            elif document_type == 'purchase':
                product_currency = company.currency_id
        if product_price_unit is None:
            if document_type == 'sale':
                product_price_unit = product.with_company(company).lst_price
            elif document_type == 'purchase':
                product_price_unit = product.with_company(company).standard_price
            else:
                return 0.0
        if product_taxes is None:
            if document_type == 'sale':
                product_taxes = product.taxes_id.filtered(lambda x: x.company_id == company)
            elif document_type == 'purchase':
                product_taxes = product.supplier_taxes_id.filtered(lambda x: x.company_id == company)
        # Apply unit of measure.
        if product_uom and product.uom_id != product_uom:
            product_price_unit = product.uom_id._compute_price(product_price_unit, product_uom)
        # Apply fiscal position.
        if product_taxes and fiscal_position:
            product_taxes_after_fp = fiscal_position.map_tax(product_taxes)
            flattened_taxes_after_fp = product_taxes_after_fp._origin.flatten_taxes_hierarchy()
            flattened_taxes_before_fp = product_taxes._origin.flatten_taxes_hierarchy()
            taxes_before_included = all(tax.price_include for tax in flattened_taxes_before_fp)

            if set(product_taxes.ids) != set(product_taxes_after_fp.ids) and taxes_before_included:
                taxes_res = flattened_taxes_before_fp.compute_all(
                    product_price_unit,
                    quantity=1.0,
                    currency=currency,
                    product=product,
                    is_refund=is_refund_document,
                )
                product_price_unit = taxes_res['total_excluded']
                if any(tax.price_include for tax in flattened_taxes_after_fp):
                    taxes_res = flattened_taxes_after_fp.compute_all(
                        product_price_unit,
                        quantity=1.0,
                        currency=currency,
                        product=product,
                        is_refund=is_refund_document,
                        handle_price_include=False,
                    )
                    for tax_res in taxes_res['taxes']:
                        tax = self.env['account.tax'].browse(tax_res['id'])
                        if tax.price_include:
                            product_price_unit += tax_res['amount']

        manual_currency_rate_active = self._context.get('manual_currency_rate_active')
        manual_currency_rate = self._context.get('manual_currency_rate')

        if currency != product_currency:
            if manual_currency_rate_active:
                product_price_unit = product_price_unit * manual_currency_rate
            else:
                product_price_unit = product_currency._convert(product_price_unit, currency, company, document_date)

        return product_price_unit
