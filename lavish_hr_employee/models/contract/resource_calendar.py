# -*- coding: utf-8 -*-
"""
Extension de resource.calendar - Horarios de trabajo con horas diurnas/nocturnas.
"""
from odoo import models, fields, api, _
from datetime import timedelta

class resource_calendar(models.Model):
    _inherit = 'resource.calendar'

    type_working_schedule = fields.Selection([
        ('employees', 'Empleados'),
        ('tasks', 'Tareas Proyectos'),
        ('other', 'Otro')
    ], string='Tipo Horario')
    consider_holidays = fields.Boolean(string='Tener en Cuenta Festivos')

class resource_calendar_attendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    daytime_hours = fields.Float(string='Horas Diurnas',compute='_get_jornada_hours',store=True)
    night_hours = fields.Float(string='Horas Nocturnas',compute='_get_jornada_hours',store=True)

    @api.depends('hour_from','hour_to')
    def _get_jornada_hours(self):
        for record in self:
            record.night_hours = 0
            record.daytime_hours = 0
