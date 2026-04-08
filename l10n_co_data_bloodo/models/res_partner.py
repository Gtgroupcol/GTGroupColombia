# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    dian_representation_type_id = fields.Many2one(
        'dian.type_code',
        'Representation Type',
        domain=[('type', '=', 'representation')]
    )
    dian_establishment_type_id = fields.Many2one(
        'dian.type_code',
        'Establishment Type',
        domain=[('type', '=', 'establishment')]
    )
    dian_obligation_type_ids = fields.Many2many(
        'dian.type_code',
        'partner_dian_obligation_types',
        'partner_id',
        'type_id',
        'Obligations and Responsibilities',
        domain=[('type', '=', 'obligation'),
                ('is_required_dian', '=', True)]
    )
    dian_customs_type_ids = fields.Many2many(
        'dian.type_code',
        'partner_dian_customs_types',
        'partner_id', 'type_id',
        'Customs User',
        domain=[('type', '=', 'customs')]
    )
    dian_fiscal_regimen = fields.Selection(
        [('48', 'Responsable del Impuesto sobre las ventas - IVA'),
         ('49', 'No responsables del IVA'), 
         ('No aplica', 'No aplica')],
        'Tax Regime',
        default='No aplica'
    )
    dian_tax_scheme_id = fields.Many2one(
        'dian.tax.type',
        'Tax Responsibility',
        ondelete='set null'
    )
    dian_commercial_name = fields.Char('Commercial Name')

    # # vat_dv = fields.Char('DV', default='')
    l10n_co_verification_code = fields.Char(
        'CD',
        compute='_compute_verification_code',
        help='Redundancy check to verify the vat number '
        'has been typed in correctly.'
    )
    edi_email = fields.Char('Correo DIAN', help='Email for e-Invoicing.')
    name1 = fields.Char('First name')
    name2 = fields.Char('Second name')
    lastname1 = fields.Char('Last name')
    lastname2 = fields.Char('Second last name')

    @api.onchange('name1','name2','lastname1','lastname2')
    def _onchange_full_name(self):
      if self.company_type == 'person':
          name = (self.name1) if self.name1 else ''
          name = (name + ' ' +self.name2) if self.name2 else name
          name = (name + ' ' +self.lastname1) if self.lastname1 else name
          name = (name + ' ' +self.lastname2) if self.lastname2 else name
          self.name = name

    @api.depends('vat', 'l10n_latam_identification_type_id')
    def _compute_verification_code(self):
        multiplication_factors = [71, 67, 59, 53,
                                  47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]

        for partner in self:
            if partner.l10n_latam_identification_type_id.dian_code \
                    == '31':
                if partner.vat and \
                        partner.country_id == self.env.ref('base.co') and \
                        len(partner.vat) <= len(multiplication_factors):
                    number = 0
                    padded_vat = partner.vat

                    while len(padded_vat) < len(multiplication_factors):
                        padded_vat = '0' + padded_vat

                    # if there is a single non-integer in vat
                    # the verification code should be False
                    try:
                        for index, vat_number in enumerate(padded_vat):
                            number += int(vat_number) * \
                                multiplication_factors[index]

                        number %= 11

                        if number < 2:
                            partner.l10n_co_verification_code = number
                        else:
                            partner.l10n_co_verification_code = 11 - number
                    except ValueError:
                        partner.l10n_co_verification_code = False
                else:
                    partner.l10n_co_verification_code = False
            else:
                partner.l10n_co_verification_code = False

    def _get_vat_without_verification_code(self):
        self.ensure_one()
        # last digit is the verification code
        # last digit is the verification code, but it could have a - before
        if self.l10n_latam_identification_type_id.l10n_co_document_code \
                != 'rut' or self.vat == '222222222222':
            return self.vat
        elif self.vat and '-' in self.vat:
            return self.vat.split('-')[0]
        return self.vat[:-1] if self.vat else ''

    def _get_vat_verification_code(self):
        self.ensure_one()
        if self.l10n_latam_identification_type_id.l10n_co_document_code \
                != 'rut':
            return ''
        elif self.vat and '-' in self.vat:
            return self.vat.split('-')[1]
        return self.vat[-1] if self.vat else ''

    def _get_fiscal_values(self):
        return self.dian_obligation_type_ids | \
            self.dian_customs_type_ids

    # @api.multi
    def check_vat_co(self, vat):
        return True

    @api.constrains('vat', 'country_id')
    def check_vat(self):
        if self.sudo().env.ref('base.module_base_vat').state == 'installed':
            self = self.filtered(
                lambda partner: partner.country_id != self.env.ref('base.co'))
            return super(ResPartner, self).check_vat()
        else:
            return True
