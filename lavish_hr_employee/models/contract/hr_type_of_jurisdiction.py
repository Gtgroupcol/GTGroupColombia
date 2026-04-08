# -*- coding: utf-8 -*-
"""
Modelo hr.type.of.jurisdiction - Tipo de Fuero.
"""
from odoo import models, fields

class hr_type_of_jurisdiction(models.Model):
    _name = 'hr.type.of.jurisdiction'
    _description = 'Tipo de Fuero'

    name = fields.Char('Tipo de Fuero')

    _sql_constraints = [('type_of_jurisdiction_uniq', 'unique(name)',
                         'Ya existe este tipo de fuero, por favor verificar.')]

#Histórico de contratación