# -*- coding: utf-8 -*-
"""
Modelo hr.contract.deductions.rtf - Deducciones para retencion en la fuente.
"""
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..payroll.hr_payslip_constants import TOPES_DEDUCCIONES_RTF

class hr_contract_deductions_rtf(models.Model):
    _name = 'hr.contract.deductions.rtf'
    _description = 'Deducciones para Retención en la Fuente'

    input_id = fields.Many2one('hr.salary.rule', 'Regla', required=True,
                               help='Regla salarial', domain="[('type_concepts','=','tributaria')]")
    date_start = fields.Date('Fecha Inicial')
    date_end = fields.Date('Fecha Final')
    number_months = fields.Integer('N° Meses')
    value_total = fields.Float('Valor Total Certificado')
    value_monthly = fields.Float('Valor Mensualizado')
    contract_id = fields.Many2one('hr.contract', 'Contrato', required=True,
                                  ondelete='cascade', index=True, auto_join=True)

    # ─────────────────────────────────────────────────────────────────────────
    # CAMPOS NORMATIVOS - Límites según Estatuto Tributario
    # ─────────────────────────────────────────────────────────────────────────
    limite_uvt_mensual = fields.Float('Limite UVT Mensual', compute='_compute_limites_normativos', store=True)
    limite_uvt_anual = fields.Float('Limite UVT Anual', compute='_compute_limites_normativos', store=True)
    limite_pesos_mensual = fields.Float('Limite $ Mensual', compute='_compute_limite_pesos')
    limite_pesos_anual = fields.Float('Limite $ Anual', compute='_compute_limite_pesos')
    base_legal = fields.Char('Base Legal', compute='_compute_limites_normativos', store=True)
    valor_acumulado_anio = fields.Float('Valor Acumulado Anio', compute='_compute_valor_acumulado')
    porcentaje_usado = fields.Float('% Usado del Limite', compute='_compute_valor_acumulado')

    # ─────────────────────────────────────────────────────────────────────────
    # RELACION CON REPORTES DE RETENCION
    # ─────────────────────────────────────────────────────────────────────────
    retencion_reporte_ids = fields.Many2many(
        'lavish.retencion.reporte',
        string='Reportes de Retencion',
        compute='_compute_retencion_reportes',
        help='Reportes de retencion donde se ha aplicado esta deduccion'
    )
    aplicaciones_count = fields.Integer(
        'Aplicaciones',
        compute='_compute_retencion_reportes',
        help='Numero de reportes de retencion relacionados'
    )
    last_reporte_date = fields.Date(
        'Ultima Aplicacion',
        compute='_compute_retencion_reportes',
        help='Fecha del ultimo reporte de retencion'
    )

    def _compute_retencion_reportes(self):
        """Obtiene los reportes de retencion relacionados con esta deduccion."""
        RetencionReporte = self.env['lavish.retencion.reporte']
        for record in self:
            if not record.contract_id or not record.contract_id.employee_id:
                record.retencion_reporte_ids = False
                record.aplicaciones_count = 0
                record.last_reporte_date = False
                continue

            reportes = RetencionReporte.search([
                ('employee_id', '=', record.contract_id.employee_id.id),
            ], order='date desc')

            record.retencion_reporte_ids = reportes
            record.aplicaciones_count = len(reportes)
            if reportes:
                record.last_reporte_date = reportes[0].date
            else:
                record.last_reporte_date = False

    def action_view_retencion_reportes_related(self):
        """Abre vista de reportes de retencion relacionados."""
        self.ensure_one()
        return {
            'name': _('Reportes de Retencion'),
            'type': 'ir.actions.act_window',
            'res_model': 'lavish.retencion.reporte',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.retencion_reporte_ids.ids)],
            'context': {'create': False},
        }

    @api.depends('input_id', 'input_id.code')
    def _compute_limites_normativos(self):
        """Calcula los límites normativos según el tipo de deducción."""
        for record in self:
            codigo = record.input_id.code if record.input_id else False
            if codigo and codigo in TOPES_DEDUCCIONES_RTF:
                topes = TOPES_DEDUCCIONES_RTF[codigo]
                record.limite_uvt_mensual = topes.get('uvt_mensual', 0)
                record.limite_uvt_anual = topes.get('uvt_anual', 0)
                record.base_legal = topes.get('base_legal', '')
            else:
                record.limite_uvt_mensual = 0
                record.limite_uvt_anual = 0
                record.base_legal = ''

    @api.depends('limite_uvt_mensual', 'limite_uvt_anual')
    def _compute_limite_pesos(self):
        """Convierte los límites UVT a pesos según el valor del UVT vigente."""
        for record in self:
            # Obtener UVT del año actual
            year = fields.Date.today().year
            company_id = (
                record.contract_id.company_id.id
                if record.contract_id and record.contract_id.company_id
                else self.env.company.id
            )
            annual_params = self.env['hr.annual.parameters'].get_for_year(
                year,
                company_id=company_id,
                raise_if_not_found=False,
            )
            uvt = annual_params.value_uvt if annual_params else 0

            record.limite_pesos_mensual = record.limite_uvt_mensual * uvt
            record.limite_pesos_anual = record.limite_uvt_anual * uvt

    @api.depends('contract_id', 'input_id', 'value_monthly')
    def _compute_valor_acumulado(self):
        """Calcula el valor acumulado de la deducción en el año fiscal actual.

        Usa exclusivamente lavish.retencion.reporte como fuente de datos.
        """
        RetencionReporte = self.env['lavish.retencion.reporte']

        for record in self:
            if not record.contract_id or not record.input_id:
                record.valor_acumulado_anio = 0
                record.porcentaje_usado = 0
                continue

            employee = record.contract_id.employee_id
            if not employee:
                record.valor_acumulado_anio = 0
                record.porcentaje_usado = 0
                continue

            year = fields.Date.today().year

            # Buscar reportes de retencion del año actual para este empleado
            reportes = RetencionReporte.search([
                ('employee_id', '=', employee.id),
                ('year', '=', year),
            ])

            if reportes:
                # Obtener el campo correspondiente segun el codigo de la regla
                codigo = (record.input_id.code or '').upper()
                campo_retencion = record._get_campo_retencion(codigo)

                if campo_retencion:
                    # Sumar valores del campo correspondiente en todos los reportes del año
                    total_acumulado = sum(
                        getattr(r, campo_retencion, 0) or 0 for r in reportes
                    )
                    record.valor_acumulado_anio = abs(total_acumulado)
                else:
                    # Si no hay mapeo, usar valor mensual × meses con reportes
                    record.valor_acumulado_anio = record.value_monthly * len(reportes)
            else:
                # Si no hay reportes, calcular basado en valor mensual × meses transcurridos
                mes_actual = fields.Date.today().month
                record.valor_acumulado_anio = record.value_monthly * mes_actual

            # Calcular porcentaje usado del límite anual
            if record.limite_pesos_anual > 0:
                record.porcentaje_usado = (record.valor_acumulado_anio / record.limite_pesos_anual) * 100
            else:
                record.porcentaje_usado = 0

    def _get_campo_retencion(self, codigo):
        """Obtiene el nombre del campo en lavish.retencion.reporte segun el codigo."""
        for prefijo, campo in self.CAMPO_RETENCION_MAP.items():
            if prefijo in codigo:
                return campo
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # VALIDACIONES
    # ─────────────────────────────────────────────────────────────────────────
    @api.onchange('value_total')
    def _onchange_value_total(self):
        for record in self:
            if record.value_total > 0:
                if not record.date_start:
                    raise UserError(_('No se ha especificado la fecha inicial.'))
                if not record.date_end:
                    raise UserError(_('No se ha especificado la fecha final'))

                nSecondDif = (record.date_end - record.date_start).total_seconds()
                nMinutesDif = round(nSecondDif/60,0)
                nHoursDif = round(nMinutesDif/60,0)
                nDaysDif = round(nHoursDif/24,0)
                nMonthsDif = round(nDaysDif/30,0)

                if nMonthsDif != 0:
                    if record.number_months > 0:
                        self.value_monthly = record.value_total / record.number_months
                    else:
                        self.value_monthly = record.value_total / 12
                else:
                    raise UserError(_('La fecha inicial es mayor que la fecha final, por favor verificar.'))

    @api.onchange('value_monthly')
    def _onchange_value_monthly(self):
        for record in self:
            if record.value_monthly > 0:
                if not record.date_start:
                    raise UserError(_('No se ha especificado la fecha inicial.'))
                if not record.date_end:
                    raise UserError(_('No se ha especificado la fecha final'))

                nSecondDif = (record.date_end - record.date_start).total_seconds()
                nMinutesDif = round(nSecondDif/60,0)
                nHoursDif = round(nMinutesDif/60,0)
                nDaysDif = round(nHoursDif/24,0)
                nMonthsDif = round(nDaysDif/30,0)

                if nMonthsDif != 0:
                    if record.number_months > 0:
                        self.value_total = record.value_monthly * record.number_months
                    else:
                        self.value_total = record.value_monthly * 12
                else:
                    raise UserError(_('La fecha inicial es mayor que la fecha final, por favor verificar.'))

    @api.onchange('value_monthly', 'limite_pesos_mensual')
    def _onchange_validar_limite(self):
        """Valida que el valor mensual no exceda el límite normativo."""
        for record in self:
            if record.value_monthly > 0 and record.limite_pesos_mensual > 0:
                if record.value_monthly > record.limite_pesos_mensual:
                    return {
                        'warning': {
                            'title': 'Advertencia - Límite Excedido',
                            'message': f'El valor mensual (${record.value_monthly:,.0f}) excede el límite '
                                      f'normativo de {record.limite_uvt_mensual} UVT (${record.limite_pesos_mensual:,.0f}). '
                                      f'Base Legal: {record.base_legal}'
                        }
                    }

    _sql_constraints = [('change_deductionsrtf_uniq', 'unique(input_id, contract_id)',
                        'Ya existe esta deducción para este contrato, por favor verificar.')]

    # ─────────────────────────────────────────────────────────────────────────
    # SINCRONIZACION CON REPORTE DE RETENCION
    # ─────────────────────────────────────────────────────────────────────────
    retencion_reporte_count = fields.Integer(
        'Reportes Retencion',
        default=0,
        help='Cantidad de reportes de retencion relacionados'
    )
    valor_promedio_aplicado = fields.Float(
        'Valor Promedio Aplicado',
        default=0,
        help='Valor promedio aplicado en los ultimos 3 meses segun reporte de retencion'
    )
    diferencia_configurado_aplicado = fields.Float(
        'Diferencia Config vs Aplicado',
        default=0,
        help='Diferencia entre el valor mensualizado configurado y el valor promedio aplicado'
    )
    ultima_sincronizacion = fields.Datetime(
        'Ultima Sincronizacion',
        help='Fecha de la ultima sincronizacion con reportes de retencion'
    )

    # Mapeo de codigos de regla a campos en lavish.retencion.reporte
    # Incluye codigos exactos y prefijos para mayor flexibilidad
    CAMPO_RETENCION_MAP = {
        # Vivienda - codigo exacto y variantes
        'INTVIV': 'ded_vivienda',
        'VIVIENDA': 'ded_vivienda',
        'DED_VIV': 'ded_vivienda',
        'INT_VIV': 'ded_vivienda',
        # Dependientes
        'DEPENDIENTES': 'ded_dependientes',
        'DED_DEP': 'ded_dependientes',
        # Medicina prepagada - codigo exacto y variantes
        'MEDPRE': 'ded_salud',
        'SALUD_PREP': 'ded_salud',
        'DED_SALUD': 'ded_salud',
        'MED_PREP': 'ded_salud',
        # AVP/AFC
        'AVP': 'valor_avp_afc',
        'AFC': 'valor_avp_afc',
        'AVP_AFC': 'valor_avp_afc',
    }

    def action_actualizar_desde_reportes(self):
        """Actualiza los campos desde los reportes de retencion."""
        RetencionReporte = self.env['lavish.retencion.reporte']

        for record in self:
            if not record.contract_id or not record.input_id:
                continue

            employee = record.contract_id.employee_id
            if not employee:
                continue

            # Buscar reportes de retencion del empleado (ultimos 6 meses)
            fecha_limite = fields.Date.today() - relativedelta(months=6)
            reportes = RetencionReporte.search([
                ('employee_id', '=', employee.id),
                ('date', '>=', fecha_limite)
            ], order='date desc', limit=12)

            # Calcular valor promedio aplicado basado en el tipo de deduccion
            codigo = (record.input_id.code or '').upper()
            campo_retencion = None

            for prefijo, campo in self.CAMPO_RETENCION_MAP.items():
                if prefijo in codigo:
                    campo_retencion = campo
                    break

            promedio = 0
            if campo_retencion and reportes:
                # Tomar los ultimos 3 registros para calcular promedio
                ultimos_3 = reportes[:3]
                valores = [getattr(r, campo_retencion, 0) or 0 for r in ultimos_3]
                promedio = sum(valores) / len(valores) if valores else 0

            record.write({
                'retencion_reporte_count': len(reportes),
                'valor_promedio_aplicado': promedio,
                'diferencia_configurado_aplicado': record.value_monthly - promedio,
                'ultima_sincronizacion': fields.Datetime.now(),
            })

        return True

    @api.model
    def actualizar_todos_desde_reportes(self):
        """Actualiza todos los registros desde reportes de retencion. Para cron."""
        deducciones = self.search([])
        deducciones.action_actualizar_desde_reportes()
        return {
            'registros_actualizados': len(deducciones)
        }

    def action_view_retencion_reportes(self):
        """Abre vista de reportes de retencion relacionados."""
        self.ensure_one()
        employee = self.contract_id.employee_id
        if not employee:
            raise UserError(_('El contrato no tiene empleado asignado.'))

        return {
            'name': _('Reportes de Retencion'),
            'type': 'ir.actions.act_window',
            'res_model': 'lavish.retencion.reporte',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', employee.id)],
            'context': {'create': False},
        }

    def action_sync_from_retencion_reporte(self):
        """Sincroniza el valor mensualizado desde el reporte de retencion."""
        # Primero actualizar desde reportes
        self.action_actualizar_desde_reportes()

        actualizados = 0
        for record in self:
            if record.valor_promedio_aplicado > 0:
                record.value_monthly = record.valor_promedio_aplicado
                record.diferencia_configurado_aplicado = 0  # Ya estan sincronizados
                # Recalcular valor total si hay meses definidos
                if record.number_months > 0:
                    record.value_total = record.value_monthly * record.number_months
                actualizados += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronizacion Completada'),
                'message': _('Se actualizaron %(count)s deducciones desde el reporte de retencion.') % {
                    'count': actualizados
                },
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def sync_all_from_retencion_reporte(self, contract_ids=None):
        """
        Sincroniza todas las deducciones RTF desde los reportes de retencion.
        Puede ejecutarse como cron o manualmente.

        Args:
            contract_ids: Lista de IDs de contratos a sincronizar. Si es None, sincroniza todos.
        """
        domain = []
        if contract_ids:
            domain.append(('contract_id', 'in', contract_ids))

        deducciones = self.search(domain)

        # Primero actualizar campos desde reportes
        deducciones.action_actualizar_desde_reportes()

        actualizadas = 0
        for deduccion in deducciones:
            if deduccion.valor_promedio_aplicado > 0:
                diferencia = abs(deduccion.diferencia_configurado_aplicado)
                # Solo actualizar si hay diferencia significativa (> 1%)
                if diferencia > (deduccion.value_monthly * 0.01) or deduccion.value_monthly == 0:
                    deduccion.value_monthly = deduccion.valor_promedio_aplicado
                    deduccion.diferencia_configurado_aplicado = 0
                    if deduccion.number_months > 0:
                        deduccion.value_total = deduccion.value_monthly * deduccion.number_months
                    actualizadas += 1

        return {
            'deducciones_procesadas': len(deducciones),
            'deducciones_actualizadas': actualizadas
        }

    @api.model
    def set_deduction_value(self, contract_id, code, value_monthly, value_total=0):
        """
        Establece el valor de una deduccion RTF.
        Util para cargar valores desde scripts o integraciones.

        Args:
            contract_id: ID del contrato
            code: Codigo de la regla salarial (INTVIV, MEDPRE, etc.)
            value_monthly: Valor mensual
            value_total: Valor total anual (opcional)

        Returns:
            dict con resultado de la operacion
        """
        # Buscar regla salarial por codigo
        rule = self.env['hr.salary.rule'].search([('code', '=', code)], limit=1)
        if not rule:
            return {'success': False, 'error': f'Regla salarial con codigo {code} no encontrada'}

        # Buscar deduccion existente
        deduccion = self.search([
            ('contract_id', '=', contract_id),
            ('input_id', '=', rule.id)
        ], limit=1)

        if deduccion:
            # Actualizar existente
            deduccion.write({
                'value_monthly': value_monthly,
                'value_total': value_total or (value_monthly * 12),
            })
            return {'success': True, 'action': 'updated', 'id': deduccion.id}
        else:
            # Crear nueva
            nueva = self.create({
                'contract_id': contract_id,
                'input_id': rule.id,
                'value_monthly': value_monthly,
                'value_total': value_total or (value_monthly * 12),
                'number_months': 12,
            })
            return {'success': True, 'action': 'created', 'id': nueva.id}

    @api.model
    def bulk_set_deduction_values(self, values_list):
        """
        Establece valores de deducciones en lote.

        Args:
            values_list: Lista de diccionarios con:
                - contract_id: ID del contrato
                - code: Codigo de regla (INTVIV, MEDPRE)
                - value_monthly: Valor mensual

        Returns:
            dict con resumen de la operacion
        """
        resultados = {
            'total': len(values_list),
            'created': 0,
            'updated': 0,
            'errors': []
        }

        for item in values_list:
            contract_id = item.get('contract_id')
            code = item.get('code')
            value_monthly = item.get('value_monthly', 0)
            value_total = item.get('value_total', 0)

            if not contract_id or not code:
                resultados['errors'].append(f'Datos incompletos: {item}')
                continue

            result = self.set_deduction_value(contract_id, code, value_monthly, value_total)

            if result.get('success'):
                if result.get('action') == 'created':
                    resultados['created'] += 1
                else:
                    resultados['updated'] += 1
            else:
                resultados['errors'].append(result.get('error', 'Error desconocido'))

        return resultados
