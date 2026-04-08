# -*- coding: utf-8 -*-
"""
Servicio de Consultas Consolidadas por Período
==============================================

Este servicio centraliza todas las consultas repetitivas a hr.payslip y hr.payslip.line
en consultas SQL únicas y optimizadas usando service_sql builders.

Tipos de consulta:
- IBD (Ingreso Base de Cotización)
- RETENCIONES (Retención en la fuente)
- PRESTACIONES (Prestaciones sociales)
- AUXILIO TRANSPORTE (Tope y Pagado)

Cada tipo usa su builder especializado que construye los WHERE dinámicamente.
"""

from odoo import models, api
from odoo.exceptions import ValidationError

from .service_sql import (
    IBDQueryBuilder,
    RetencionesQueryBuilder,
    PrestacionesQueryBuilder,
    AuxilioTransporteQueryBuilder,
    LeavePeriodQueryBuilder,
    VALID_PAYSLIP_STATES,
    VALID_LEAVE_STATES,
)
from odoo.addons.lavish_hr_employee.models.reglas.config_reglas import get_prestacion_base_field


class PeriodPayslipQueryService(models.AbstractModel):
    """
    Servicio centralizado para consultas de nómina agrupadas por período.

    Usa builders de service_sql para construir queries dinámicamente.
    """
    _name = 'period.payslip.query.service'
    _description = 'Servicio de consultas consolidadas por período'

    # =========================================================================
    # BUILDERS MAP
    # =========================================================================

    CALCULATION_BUILDERS = {
        'ibd': IBDQueryBuilder,
        'retenciones': RetencionesQueryBuilder,
        'prestaciones': PrestacionesQueryBuilder,
    }

    # =========================================================================
    # CONSULTAS DE NOMINA
    # =========================================================================

    def get_period_payslip_data(
        self,
        contract_id,
        date_from,
        date_to,
        calculation_type,
        exclude_payslip_id=None,
        states=('done', 'paid'),
        tipo_prestacion=None,
        contexto_base='liquidacion',
        exclude_codes=None,
        include_categories=None,
        excluded_categories=None,
    ):
        """
        Consulta SQL para datos de NÓMINA por período usando builders.

        Args:
            contract_id: ID del contrato
            date_from: Fecha inicio del período
            date_to: Fecha fin del período
            calculation_type: 'ibd', 'retenciones', 'prestaciones'
            exclude_payslip_id: ID de nómina a excluir
            states: Estados de nómina a incluir
            tipo_prestacion: Para prestaciones: 'prima', 'cesantias', 'vacaciones', 'all'
            contexto_base: Para prestaciones: 'provision' o 'liquidacion'
            exclude_codes: Para retenciones: códigos a excluir
            include_categories: Para retenciones: categorías a incluir
            excluded_categories: Para prestaciones: categorías a excluir

        Returns:
            dict con total, totals_by_type, tree, by_period, etc.
        """
        # Normalizar estados
        states = self._normalize_states(states)

        # Obtener builder segun tipo
        builder = self._create_payslip_builder(calculation_type)

        # Configurar builder base
        builder.for_contract(contract_id)
        builder.in_period(date_from, date_to)
        builder.with_states(states)
        builder.with_leave_info()

        if exclude_payslip_id:
            builder.exclude_payslip(exclude_payslip_id)

        # Configurar parametros especificos segun tipo
        self._configure_payslip_builder(
            builder, calculation_type,
            tipo_prestacion=tipo_prestacion,
            contexto_base=contexto_base,
            exclude_codes=exclude_codes,
            include_categories=include_categories,
            excluded_categories=excluded_categories,
        )

        # Construir y ejecutar
        query, params = builder.build()
        self._cr.execute(query, params)
        rows = self._cr.dictfetchall()

        return self._process_payslip_results(rows, calculation_type)

    def _create_payslip_builder(self, calculation_type):
        """Crea el builder apropiado para el tipo de calculo."""
        builder_class = self.CALCULATION_BUILDERS.get(calculation_type)
        if not builder_class:
            raise ValueError(f"Tipo de calculo no soportado: {calculation_type}")
        return builder_class()

    def _configure_payslip_builder(
        self, builder, calculation_type,
        tipo_prestacion=None,
        contexto_base='liquidacion',
        exclude_codes=None,
        include_categories=None,
        excluded_categories=None,
    ):
        """Configura parametros especificos del builder."""
        if calculation_type == 'retenciones':
            if include_categories:
                builder.include_categories(include_categories)
            if exclude_codes:
                builder.exclude_codes(exclude_codes)
        elif calculation_type == 'prestaciones':
            if tipo_prestacion:
                builder.tipo_prestacion(tipo_prestacion)
            if hasattr(builder, 'contexto_base'):
                builder.contexto_base(contexto_base)
            if excluded_categories:
                builder.exclude_categories(excluded_categories)

    # =========================================================================
    # CONSULTAS DE AUSENCIAS
    # =========================================================================

    def get_period_leave_data(
        self,
        contract_id,
        date_from,
        date_to,
        calculation_type,
        leave_states=None,
    ):
        """
        Consulta SQL para datos de AUSENCIAS por período usando builder.

        Args:
            contract_id: ID del contrato
            date_from: Fecha inicio del período
            date_to: Fecha fin del período
            calculation_type: 'ibd', 'retenciones', 'prestaciones'
            leave_states: Estados de ausencia a incluir

        Returns:
            dict con total, totals_by_type, tree, by_period, etc.
        """
        # Normalizar estados
        if leave_states is None:
            leave_states = ('paid', 'validate', 'validated')
        elif isinstance(leave_states, list):
            leave_states = tuple(leave_states)
        elif isinstance(leave_states, str):
            leave_states = (leave_states,)

        # Crear y configurar builder
        builder = LeavePeriodQueryBuilder()
        builder.for_contract(contract_id)
        builder.in_period(date_from, date_to)
        builder.with_leave_states(leave_states)
        builder.for_calculation_type(calculation_type)

        # Construir y ejecutar
        query, params = builder.build()
        self._cr.execute(query, params)
        rows = self._cr.dictfetchall()

        return self._process_leave_results(rows, calculation_type)

    # =========================================================================
    # CONSULTAS DE AUXILIO DE TRANSPORTE
    # =========================================================================

    def get_devengos_tope_auxilio(
        self,
        contract_id,
        date_from,
        date_to,
        exclude_payslip_id=None,
        states=('done', 'paid'),
        solo_marcadas=False,
    ):
        """
        Obtiene devengos para el tope de auxilio de transporte usando builder.

        Args:
            contract_id: ID del contrato
            date_from: Fecha inicio del periodo
            date_to: Fecha fin del periodo
            exclude_payslip_id: ID de nomina a excluir
            states: Estados de nomina
            solo_marcadas: Solo reglas marcadas con base_auxtransporte_tope=True

        Returns:
            dict con total, tree, by_period
        """
        states = self._normalize_states(states)

        # Crear y configurar builder
        builder = AuxilioTransporteQueryBuilder()
        builder.for_contract(contract_id)
        builder.in_period(date_from, date_to)
        builder.with_states(states)
        builder.mode_tope(solo_marcadas=solo_marcadas)

        if exclude_payslip_id:
            builder.exclude_payslip(exclude_payslip_id)

        # Construir y ejecutar
        query, params = builder.build()
        self._cr.execute(query, params)
        rows = self._cr.dictfetchall()

        return self._process_auxilio_tope_results(rows)

    def get_auxilio_transporte_pagado(
        self,
        contract_id,
        date_from,
        date_to,
        exclude_payslip_id=None,
        states=('done', 'paid'),
    ):
        """
        Obtiene valores de auxilio de transporte pagados usando builder.

        Args:
            contract_id: ID del contrato
            date_from: Fecha inicio del periodo
            date_to: Fecha fin del periodo
            exclude_payslip_id: ID de nomina a excluir
            states: Estados de nomina

        Returns:
            dict con total_auxilio, total_basic, total_dias_auxilio, etc.
        """
        states = self._normalize_states(states)

        # Crear y configurar builder
        builder = AuxilioTransporteQueryBuilder()
        builder.for_contract(contract_id)
        builder.in_period(date_from, date_to)
        builder.with_states(states)
        builder.mode_pagado()

        if exclude_payslip_id:
            builder.exclude_payslip(exclude_payslip_id)

        # Construir y ejecutar
        query, params = builder.build()
        self._cr.execute(query, params)
        rows = self._cr.dictfetchall()

        return self._process_auxilio_pagado_results(rows)

    # =========================================================================
    # CONSULTAS COMBINADAS
    # =========================================================================

    def get_period_data_combined(
        self,
        contract_id,
        date_from,
        date_to,
        calculation_type,
        exclude_payslip_id=None,
        states=('done', 'paid'),
        leave_states=None,
        tipo_prestacion=None,
        exclude_codes=None,
        include_categories=None,
        excluded_categories=None,
    ):
        """Obtiene datos combinados de nómina Y ausencias."""
        payslip_data = self.get_period_payslip_data(
            contract_id=contract_id,
            date_from=date_from,
            date_to=date_to,
            calculation_type=calculation_type,
            exclude_payslip_id=exclude_payslip_id,
            states=states,
            tipo_prestacion=tipo_prestacion,
            exclude_codes=exclude_codes,
            include_categories=include_categories,
            excluded_categories=excluded_categories,
        )

        leave_data = self.get_period_leave_data(
            contract_id=contract_id,
            date_from=date_from,
            date_to=date_to,
            calculation_type=calculation_type,
            leave_states=leave_states,
        )

        return self._combine_results(payslip_data, leave_data, calculation_type)

    # =========================================================================
    # PROCESADORES DE RESULTADOS
    # =========================================================================

    def _process_payslip_results(self, rows, calculation_type):
        """Procesa resultados de la consulta de nómina."""
        return self._process_results(rows, calculation_type, 'payslip')

    def _process_leave_results(self, rows, calculation_type):
        """Procesa resultados de la consulta de ausencias."""
        return self._process_results(rows, calculation_type, 'leave')

    def _process_results(self, rows, calculation_type, source_type='payslip'):
        """Procesa los resultados según el tipo de cálculo."""
        total = 0.0
        list_detail = []
        by_period = {}
        totals_by_type = self._init_totals_by_type(calculation_type)

        # Estructuras adicionales segun tipo
        by_category = {} if calculation_type == 'retenciones' else None
        by_base_field = {} if calculation_type == 'prestaciones' else None

        # IDs de ausencias (solo para nomina)
        leave_ids_by_period = {}
        leave_line_ids_by_period = {}

        for row in rows:
            total += row['total']
            data_type = row.get('data_type', 'other')

            # Construir detalle
            line_detail = self._build_line_detail(row, source_type, calculation_type)
            list_detail.append(line_detail)

            # Agrupar por período
            period_key = row['period_key']
            if period_key not in by_period:
                by_period[period_key] = {
                    'total': 0.0,
                    'line_ids': [],
                    **{k: 0.0 for k in totals_by_type.keys()}
                }

            by_period[period_key]['total'] += row['total']
            by_period[period_key]['line_ids'].append(row['line_id'])

            # Acumular totales por tipo
            self._accumulate_by_type(
                totals_by_type, by_period[period_key],
                calculation_type, data_type, row['total']
            )

            # Agrupar por categoria (retenciones)
            if by_category is not None:
                cat_code = row['category_code']
                if cat_code not in by_category:
                    by_category[cat_code] = {'total': 0.0, 'line_ids': []}
                by_category[cat_code]['total'] += row['total']
                by_category[cat_code]['line_ids'].append(row['line_id'])

            # Agrupar por base_field (prestaciones)
            if by_base_field is not None:
                base_field = row.get('base_field')
                if base_field:
                    if base_field not in by_base_field:
                        by_base_field[base_field] = {'total': 0.0, 'line_ids': []}
                    by_base_field[base_field]['total'] += row['total']
                    by_base_field[base_field]['line_ids'].append(row['line_id'])

            # Extraer IDs de ausencias (solo nomina)
            if source_type == 'payslip':
                self._extract_leave_ids(
                    row, period_key,
                    leave_ids_by_period, leave_line_ids_by_period
                )

        # Construir resultado
        result = {
            'total': total,
            'totals_by_type': totals_by_type,
            'tree': list_detail,
            'by_period': by_period,
        }

        if source_type == 'payslip':
            if leave_ids_by_period:
                result['leave_ids_by_period'] = {k: list(v) for k, v in leave_ids_by_period.items()}
            if leave_line_ids_by_period:
                result['leave_line_ids_by_period'] = {k: list(v) for k, v in leave_line_ids_by_period.items()}

        if by_category is not None:
            result['by_category'] = by_category
        if by_base_field is not None:
            result['by_base_field'] = by_base_field

        return result

    def _process_auxilio_tope_results(self, rows):
        """Procesa resultados de auxilio tope."""
        total = 0.0
        list_detail = []
        by_period = {}

        for row in rows:
            total += row['total']
            list_detail.append({
                'line_id': row['line_id'],
                'payslip_id': row['payslip_id'],
                'payslip_number': row['payslip_number'],
                'date_from': row['date_from'],
                'date_to': row['date_to'],
                'rule_code': row.get('rule_code_full', row.get('rule_code')),
                'rule_name': row['rule_name'],
                'category_code': row['category_code'],
                'total': row['total'],
                'period_key': row['period_key'],
            })

            period_key = row['period_key']
            if period_key not in by_period:
                by_period[period_key] = {'total': 0.0, 'line_ids': []}
            by_period[period_key]['total'] += row['total']
            by_period[period_key]['line_ids'].append(row['line_id'])

        return {
            'total': total,
            'tree': list_detail,
            'by_period': by_period,
        }

    def _process_auxilio_pagado_results(self, rows):
        """Procesa resultados de auxilio pagado."""
        force_full_days = bool(self.env.context.get('force_auxilio_full_days'))
        vac_slip_ids = set()
        if force_full_days and rows:
            slip_ids = {row['payslip_id'] for row in rows if row.get('payslip_id')}
            if slip_ids:
                vac_worked = self.env['hr.payslip.worked_days'].search_read(
                    [
                        ('payslip_id', 'in', list(slip_ids)),
                        ('code', '=', 'VACDISFRUTADAS'),
                        ('number_of_days', '>', 0),
                    ],
                    ['payslip_id'],
                )
                vac_slip_ids = {l['payslip_id'][0] for l in vac_worked if l.get('payslip_id')}
        total_auxilio = 0.0
        total_basic = 0.0
        total_dias_auxilio = 0.0
        list_detail = []
        by_period = {}
        periodos_con_auxilio = set()

        for row in rows:
            tipo = row.get('tipo_concepto', 'other')
            period_key = row['period_key']
            quincena = row.get('quincena', 1)
            period_quincena_key = f"{period_key}-Q{quincena}"
            quantity = row.get('quantity', 0) or 0
            if force_full_days and tipo == 'auxilio' and row.get('payslip_id') in vac_slip_ids:
                quantity = 30

            list_detail.append({
                'line_id': row['line_id'],
                'payslip_id': row['payslip_id'],
                'payslip_number': row['payslip_number'],
                'date_from': row['date_from'],
                'date_to': row['date_to'],
                'rule_code': row.get('rule_code_full', row.get('rule_code')),
                'rule_name': row['rule_name'],
                'category_code': row['category_code'],
                'total': row['total'],
                'quantity': quantity,
                'period_key': period_key,
                'quincena': quincena,
                'tipo_concepto': tipo,
            })

            if period_quincena_key not in by_period:
                by_period[period_quincena_key] = {
                    'total_auxilio': 0.0,
                    'total_basic': 0.0,
                    'dias_auxilio': 0.0,
                    'line_ids': [],
                    'period_key': period_key,
                    'quincena': quincena,
                }

            by_period[period_quincena_key]['line_ids'].append(row['line_id'])

            if tipo == 'auxilio':
                total_auxilio += row['total']
                total_dias_auxilio += quantity
                by_period[period_quincena_key]['total_auxilio'] += row['total']
                by_period[period_quincena_key]['dias_auxilio'] += quantity
                periodos_con_auxilio.add(period_quincena_key)
            elif tipo == 'basic':
                total_basic += row['total']
                by_period[period_quincena_key]['total_basic'] += row['total']

        count_periods = len(periodos_con_auxilio)

        # Calcular promedio basado en DIAS, no en periodos
        # promedio_diario = total / dias_totales
        # promedio_mensual = promedio_diario * 30
        if total_dias_auxilio > 0:
            promedio_diario_auxilio = total_auxilio / total_dias_auxilio
            promedio_auxilio = promedio_diario_auxilio * 30
        else:
            promedio_diario_auxilio = 0.0
            promedio_auxilio = total_auxilio / count_periods if count_periods > 0 else 0.0

        return {
            'total_auxilio': total_auxilio,
            'total_basic': total_basic,
            'total_dias_auxilio': total_dias_auxilio,
            'count_periods': count_periods,
            'promedio_auxilio': promedio_auxilio,
            'promedio_diario_auxilio': promedio_diario_auxilio,
            'tree': list_detail,
            'by_period': by_period,
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _normalize_states(self, states):
        """Normaliza estados a tupla."""
        if states is None:
            return ('done', 'paid')
        elif isinstance(states, list):
            return tuple(states)
        elif isinstance(states, str):
            return (states,)
        return states

    def _init_totals_by_type(self, calculation_type):
        """Inicializa totales segun tipo de calculo."""
        if calculation_type == 'ibd':
            return {'total_salary': 0.0, 'total_no_salary': 0.0}
        elif calculation_type == 'retenciones':
            return {'total_basic': 0.0, 'total_devengos': 0.0, 'total_dev_no_salarial': 0.0}
        elif calculation_type == 'prestaciones':
            return {'total_basic': 0.0, 'total_variables': 0.0}
        return {}

    def _build_line_detail(self, row, source_type, calculation_type):
        """Construye el detalle de una linea."""
        detail = {
            'line_id': row['line_id'],
            'payslip_id': row['payslip_id'],
            'payslip_number': row['payslip_number'],
            'date_from': row['date_from'],
            'date_to': row['date_to'],
            'rule_code': row['rule_code_full'],
            'rule_name': row['rule_name'],
            'category_code': row['category_code'],
            'category_name': row['category_name'],
            'total': row['total'],
            'amount': row['amount'],
            'quantity': row['quantity'],
            'period_key': row['period_key'],
            'source_type': source_type,
        }

        if 'leave_line_ids' in row and row['leave_line_ids']:
            detail['leave_line_ids'] = row['leave_line_ids']
        if 'leave_ids' in row and row['leave_ids']:
            detail['leave_ids'] = row['leave_ids']
        if calculation_type == 'prestaciones':
            detail['base_field'] = row.get('base_field')

        return detail

    def _accumulate_by_type(self, totals, period_totals, calculation_type, data_type, amount):
        """Acumula totales segun tipo de calculo."""
        if calculation_type == 'ibd':
            if data_type == 'salary':
                totals['total_salary'] += amount
                period_totals['total_salary'] += amount
            elif data_type == 'no_salary':
                totals['total_no_salary'] += amount
                period_totals['total_no_salary'] += amount
        elif calculation_type == 'retenciones':
            if data_type == 'basic':
                totals['total_basic'] += amount
                period_totals['total_basic'] += amount
            elif data_type == 'devengos':
                totals['total_devengos'] += amount
                period_totals['total_devengos'] += amount
            elif data_type == 'dev_no_salarial':
                totals['total_dev_no_salarial'] += amount
                period_totals['total_dev_no_salarial'] += amount
        elif calculation_type == 'prestaciones':
            if data_type == 'basic':
                totals['total_basic'] += amount
                period_totals['total_basic'] += amount
            else:
                totals['total_variables'] += amount
                period_totals['total_variables'] += amount

    def _extract_leave_ids(self, row, period_key, leave_ids_by_period, leave_line_ids_by_period):
        """Extrae IDs de ausencias de una fila."""
        if 'leave_ids' in row and row['leave_ids']:
            if period_key not in leave_ids_by_period:
                leave_ids_by_period[period_key] = set()
            if isinstance(row['leave_ids'], list):
                leave_ids_by_period[period_key].update(row['leave_ids'])
            else:
                leave_ids_by_period[period_key].add(row['leave_ids'])

        if 'leave_line_ids' in row and row['leave_line_ids']:
            if period_key not in leave_line_ids_by_period:
                leave_line_ids_by_period[period_key] = set()
            if isinstance(row['leave_line_ids'], list):
                leave_line_ids_by_period[period_key].update(row['leave_line_ids'])
            else:
                leave_line_ids_by_period[period_key].add(row['leave_line_ids'])

    def _combine_results(self, payslip_data, leave_data, calculation_type):
        """Combina resultados de nómina y ausencias."""
        combined_total = payslip_data['total'] + leave_data['total']

        combined_totals = {}
        for key in payslip_data['totals_by_type'].keys():
            combined_totals[key] = (
                payslip_data['totals_by_type'].get(key, 0.0) +
                leave_data['totals_by_type'].get(key, 0.0)
            )

        combined_list = payslip_data['tree'] + leave_data['tree']

        combined_by_period = {}
        all_periods = set(payslip_data['by_period'].keys()) | set(leave_data['by_period'].keys())
        for period_key in all_periods:
            payslip_period = payslip_data['by_period'].get(period_key, {'total': 0.0, 'line_ids': []})
            leave_period = leave_data['by_period'].get(period_key, {'total': 0.0, 'line_ids': []})

            combined_by_period[period_key] = {
                'total': payslip_period['total'] + leave_period['total'],
                'line_ids': payslip_period['line_ids'] + leave_period['line_ids'],
            }
            for key in combined_totals.keys():
                combined_by_period[period_key][key] = (
                    payslip_period.get(key, 0.0) + leave_period.get(key, 0.0)
                )

        result = {
            'total': combined_total,
            'totals_by_type': combined_totals,
            'tree': combined_list,
            'by_period': combined_by_period,
        }

        if calculation_type == 'retenciones':
            combined_by_category = {}
            all_cats = set(payslip_data.get('by_category', {}).keys()) | set(leave_data.get('by_category', {}).keys())
            for cat in all_cats:
                p = payslip_data.get('by_category', {}).get(cat, {'total': 0.0, 'line_ids': []})
                l = leave_data.get('by_category', {}).get(cat, {'total': 0.0, 'line_ids': []})
                combined_by_category[cat] = {
                    'total': p['total'] + l['total'],
                    'line_ids': p['line_ids'] + l['line_ids'],
                }
            result['by_category'] = combined_by_category

        elif calculation_type == 'prestaciones':
            combined_by_base = {}
            all_bases = set(payslip_data.get('by_base_field', {}).keys()) | set(leave_data.get('by_base_field', {}).keys())
            for base in all_bases:
                p = payslip_data.get('by_base_field', {}).get(base, {'total': 0.0, 'line_ids': []})
                l = leave_data.get('by_base_field', {}).get(base, {'total': 0.0, 'line_ids': []})
                combined_by_base[base] = {
                    'total': p['total'] + l['total'],
                    'line_ids': p['line_ids'] + l['line_ids'],
                }
            result['by_base_field'] = combined_by_base

        return result

    # =========================================================================
    # CONSULTAS DE ACUMULADOS DE NOMINA
    # =========================================================================

    def get_accumulated_payroll_data(
        self,
        contract_id,
        date_from,
        date_to,
        tipo_prestacion='all',
        contexto_base='liquidacion',
        excluded_categories=None,
    ):
        """
        Consulta SQL para datos de ACUMULADOS DE NOMINA (hr_accumulated_payroll).

        Usa las mismas condiciones que las líneas de nómina para prestaciones:
        - Reglas con base_prima, base_cesantias, base_vacaciones, etc.
        - Categorias excluidas

        Args:
            contract_id: ID del contrato
            date_from: Fecha inicio del período
            date_to: Fecha fin del período
            tipo_prestacion: 'prima', 'cesantias', 'vacaciones', 'intereses_cesantias', 'all'
            excluded_categories: Categorías a excluir

        Returns:
            dict con total, tree, by_period
        """
        if excluded_categories is None:
            excluded_categories = ['BASIC', 'DED', 'PROV', 'SSOCIAL', 'PRESTACIONES_SOCIALES', 'NET']

        # Construir condición de base según tipo de prestación
        contexto_base = contexto_base if contexto_base in ('provision', 'liquidacion') else 'liquidacion'

        if tipo_prestacion == 'all':
            base_condition = f"""(hsr.base_prima_{contexto_base} = TRUE OR hsr.base_cesantias_{contexto_base} = TRUE
                    OR hsr.base_vacaciones_{contexto_base} = TRUE OR hsr.base_vacaciones_dinero_{contexto_base} = TRUE
                    OR hsr.base_intereses_cesantias_{contexto_base} = TRUE)"""
        else:
            base_field = get_prestacion_base_field(tipo_prestacion, contexto=contexto_base)
            base_condition = f"hsr.{base_field} = TRUE"

        query = """
        SELECT
            hap.id AS line_id,
            NULL::int AS payslip_id,
            CONCAT('ACUM-', hap.id) AS payslip_number,
            hap.date_from,
            hap.date_to,
            hsr.code AS rule_code_full,
            COALESCE(hsr.name->>'es_CO', hsr.name->>'en_US', hsr.code) AS rule_name,
            hsrc.code AS category_code,
            COALESCE(hsrc.name->>'es_CO', hsrc.name->>'en_US', hsrc.code) AS category_name,
            hap.amount AS total,
            hap.amount AS amount,
            -- Usar quantity si existe, sino 1 por defecto
            COALESCE(NULLIF(hap.quantity, 0), 1) AS quantity,
            TO_CHAR(hap.date, 'YYYY-MM') AS period_key,
            EXTRACT(YEAR FROM hap.date) AS year,
            EXTRACT(MONTH FROM hap.date) AS month,
            'accumulated' AS source_type,
            CASE
                WHEN hsr.base_prima_%(contexto_base)s THEN 'base_prima_%(contexto_base)s'
                WHEN hsr.base_cesantias_%(contexto_base)s THEN 'base_cesantias_%(contexto_base)s'
                WHEN hsr.base_vacaciones_%(contexto_base)s THEN 'base_vacaciones_%(contexto_base)s'
                WHEN hsr.base_vacaciones_dinero_%(contexto_base)s THEN 'base_vacaciones_dinero_%(contexto_base)s'
                WHEN hsr.base_intereses_cesantias_%(contexto_base)s THEN 'base_intereses_cesantias_%(contexto_base)s'
                ELSE NULL
            END AS base_field,
            CASE
                WHEN hsrc.code = 'BASIC' THEN 'basic'
                ELSE 'variable'
            END AS data_type,
            hap.accumulated_type,
            hap.note
        FROM hr_accumulated_payroll hap
        INNER JOIN hr_salary_rule hsr ON hsr.id = hap.salary_rule_id
        INNER JOIN hr_salary_rule_category hsrc ON hsrc.id = hsr.category_id
        WHERE hap.contract_id = %(contract_id)s
          AND hap.date >= %(date_from)s
          AND hap.date <= %(date_to)s
          AND hap.amount != 0
          AND {base_condition}
          AND hsrc.code NOT IN %(excluded_categories)s
        ORDER BY hap.date, hsrc.code, hsr.code
        """.format(base_condition=base_condition).replace('%(contexto_base)s', contexto_base)

        params = {
            'contract_id': contract_id,
            'date_from': date_from,
            'date_to': date_to,
            'excluded_categories': tuple(excluded_categories),
        }

        self._cr.execute(query, params)
        rows = self._cr.dictfetchall()

        return self._process_accumulated_results(rows)

    def _process_accumulated_results(self, rows):
        """Procesa resultados de acumulados de nómina."""
        total = 0.0
        list_detail = []
        by_period = {}
        totals_by_type = {'total_basic': 0.0, 'total_variables': 0.0}
        by_base_field = {}

        for row in rows:
            total += row['total']
            data_type = row.get('data_type', 'variable')

            # Construir detalle
            line_detail = {
                'line_id': row['line_id'],
                'payslip_id': row['payslip_id'],
                'payslip_number': row['payslip_number'],
                'date_from': row['date_from'],
                'date_to': row['date_to'],
                'rule_code': row['rule_code_full'],
                'rule_name': row['rule_name'],
                'category_code': row['category_code'],
                'category_name': row['category_name'],
                'total': row['total'],
                'amount': row['amount'],
                'quantity': row['quantity'],
                'period_key': row['period_key'],
                'source_type': 'accumulated',
                'base_field': row.get('base_field'),
                'accumulated_type': row.get('accumulated_type'),
                'note': row.get('note'),
            }
            list_detail.append(line_detail)

            # Agrupar por período
            period_key = row['period_key']
            if period_key not in by_period:
                by_period[period_key] = {
                    'total': 0.0,
                    'line_ids': [],
                    'total_basic': 0.0,
                    'total_variables': 0.0,
                }

            by_period[period_key]['total'] += row['total']
            by_period[period_key]['line_ids'].append(row['line_id'])

            # Acumular totales por tipo
            if data_type == 'basic':
                totals_by_type['total_basic'] += row['total']
                by_period[period_key]['total_basic'] += row['total']
            else:
                totals_by_type['total_variables'] += row['total']
                by_period[period_key]['total_variables'] += row['total']

            # Agrupar por base_field
            base_field = row.get('base_field')
            if base_field:
                if base_field not in by_base_field:
                    by_base_field[base_field] = {'total': 0.0, 'line_ids': []}
                by_base_field[base_field]['total'] += row['total']
                by_base_field[base_field]['line_ids'].append(row['line_id'])

        return {
            'total': total,
            'totals_by_type': totals_by_type,
            'total_basic': totals_by_type['total_basic'],
            'total_variables': totals_by_type['total_variables'],
            'tree': list_detail,
            'by_period': by_period,
            'by_base_field': by_base_field,
        }

    def _combine_payslip_and_accumulated(self, payslip_data, accumulated_data):
        """Combina resultados de líneas de nómina y acumulados."""
        combined_total = payslip_data['total'] + accumulated_data['total']

        combined_totals = {
            'total_basic': payslip_data.get('total_basic', 0) + accumulated_data.get('total_basic', 0),
            'total_variables': payslip_data.get('total_variables', 0) + accumulated_data.get('total_variables', 0),
        }

        # Combinar árboles (listas de detalles)
        combined_tree = payslip_data['tree'] + accumulated_data['tree']

        # Combinar por período
        combined_by_period = {}
        all_periods = set(payslip_data['by_period'].keys()) | set(accumulated_data['by_period'].keys())
        for period_key in all_periods:
            p_period = payslip_data['by_period'].get(period_key, {'total': 0.0, 'line_ids': [], 'total_basic': 0.0, 'total_variables': 0.0})
            a_period = accumulated_data['by_period'].get(period_key, {'total': 0.0, 'line_ids': [], 'total_basic': 0.0, 'total_variables': 0.0})

            combined_by_period[period_key] = {
                'total': p_period['total'] + a_period['total'],
                'line_ids': p_period['line_ids'] + a_period['line_ids'],
                'total_basic': p_period.get('total_basic', 0) + a_period.get('total_basic', 0),
                'total_variables': p_period.get('total_variables', 0) + a_period.get('total_variables', 0),
            }

        # Combinar por base_field
        combined_by_base = {}
        all_bases = set(payslip_data.get('by_base_field', {}).keys()) | set(accumulated_data.get('by_base_field', {}).keys())
        for base in all_bases:
            p_base = payslip_data.get('by_base_field', {}).get(base, {'total': 0.0, 'line_ids': []})
            a_base = accumulated_data.get('by_base_field', {}).get(base, {'total': 0.0, 'line_ids': []})
            combined_by_base[base] = {
                'total': p_base['total'] + a_base['total'],
                'line_ids': p_base['line_ids'] + a_base['line_ids'],
            }

        return {
            'total': combined_total,
            'total_basic': combined_totals['total_basic'],
            'total_variables': combined_totals['total_variables'],
            'totals_by_type': combined_totals,
            'tree': combined_tree,
            'by_period': combined_by_period,
            'by_base_field': combined_by_base,
        }

    # =========================================================================
    # WRAPPERS PARA PRESTACIONES
    # =========================================================================

    def get_prestaciones_data(
        self,
        contract_id,
        date_from,
        date_to,
        tipo_prestacion,
        contexto_base='liquidacion',
        exclude_payslip_id=None,
        states=('done', 'paid'),
        excluded_categories=None,
        include_accumulated=True,
    ):
        """
        Wrapper para obtener datos de prestaciones.

        Incluye líneas de nómina (hr_payslip_line) y acumulados de nómina
        (hr_accumulated_payroll) con las mismas condiciones de filtro.

        Args:
            include_accumulated: Si True, incluye registros de hr_accumulated_payroll
        """
        # 1. Obtener líneas de nómina
        payslip_result = self.get_period_payslip_data(
            contract_id=contract_id,
            date_from=date_from,
            date_to=date_to,
            calculation_type='prestaciones',
            exclude_payslip_id=exclude_payslip_id,
            states=states,
            tipo_prestacion=tipo_prestacion,
            contexto_base=contexto_base,
            excluded_categories=excluded_categories,
        )

        payslip_data = {
            'total': payslip_result['total'],
            'total_basic': payslip_result['totals_by_type']['total_basic'],
            'total_variables': payslip_result['totals_by_type']['total_variables'],
            'tree': payslip_result['tree'],
            'by_period': payslip_result['by_period'],
            'by_base_field': payslip_result.get('by_base_field', {}),
        }

        # 2. Obtener acumulados de nómina (si está habilitado)
        if include_accumulated:
            accumulated_data = self.get_accumulated_payroll_data(
                contract_id=contract_id,
                date_from=date_from,
                date_to=date_to,
                tipo_prestacion=tipo_prestacion,
                contexto_base=contexto_base,
                excluded_categories=excluded_categories,
            )

            # 3. Combinar resultados si hay acumulados
            if accumulated_data['total'] != 0 or accumulated_data['tree']:
                return self._combine_payslip_and_accumulated(payslip_data, accumulated_data)

        return payslip_data

    def get_aux_lines_in_period(self, contract_id, date_from, date_to, exclude_payslip_id=None, tipo_prestacion='all'):
        """
        Obtiene lineas de categoria AUX en el periodo.

        IMPORTANTE: El auxilio de transporte siempre se incluye en prestaciones
        por ley colombiana, NO necesita tener marcados los bools base_prima,
        base_cesantias, etc. Por eso buscamos TODAS las líneas AUX sin filtrar
        por tipo_prestacion.
        """
        # Buscar auxilio directamente por categoría, SIN filtrar por tipo_prestacion
        # porque el auxilio siempre aplica independiente del bool
        result = self.get_auxilio_transporte_pagado(
            contract_id=contract_id,
            date_from=date_from,
            date_to=date_to,
            exclude_payslip_id=exclude_payslip_id,
        )
        # Retornar las líneas de tipo 'auxilio'
        return [
            line for line in result.get('tree', [])
            if line.get('tipo_concepto') == 'auxilio'
        ]

    def check_aux_in_variable(self, contract_id, date_from, date_to, exclude_payslip_id=None, tipo_prestacion='all'):
        """
        Verifica si hay auxilio en las lineas variables del periodo.

        Args:
            tipo_prestacion: Usar el mismo tipo que el calculo de variable
                             para evitar detectar auxilio que no esta incluido.
        """
        aux_lines = self.get_aux_lines_in_period(
            contract_id, date_from, date_to, exclude_payslip_id, tipo_prestacion
        )

        # Calcular promedio basado en dias
        total_aux = sum(l.get('total', 0) for l in aux_lines)
        if self.env.context.get('force_auxilio_full_days') and aux_lines:
            slip_ids = {l.get('payslip_id') for l in aux_lines if l.get('payslip_id')}
            if slip_ids:
                vac_worked = self.env['hr.payslip.worked_days'].search_read(
                    [
                        ('payslip_id', 'in', list(slip_ids)),
                        ('code', '=', 'VACDISFRUTADAS'),
                        ('number_of_days', '>', 0),
                    ],
                    ['payslip_id'],
                )
                vac_slip_ids = {l['payslip_id'][0] for l in vac_worked if l.get('payslip_id')}
            else:
                vac_slip_ids = set()
            total_dias = sum(
                30 if l.get('payslip_id') in vac_slip_ids else (l.get('quantity', 0) or 0)
                for l in aux_lines
            )
        else:
            total_dias = sum(l.get('quantity', 0) or 0 for l in aux_lines)

        if total_dias > 0:
            promedio_diario = total_aux / total_dias
            promedio_mensual = promedio_diario * 30
        else:
            promedio_diario = 0.0
            promedio_mensual = total_aux / len(aux_lines) if aux_lines else 0.0

        return {
            'aux_en_variable': len(aux_lines) > 0,
            'total_aux': total_aux,
            'total_dias': total_dias,
            'promedio_diario': promedio_diario,
            'promedio_mensual': promedio_mensual,
            'count_lines': len(aux_lines),
            'lineas': aux_lines,
        }

    # =========================================================================
    # CALCULO BASE PRESTACIONES
    # =========================================================================

    def calculate_base_prestacion(self, localdict, date_from, date_to, tipo_prestacion, context='provision', days_info=None):
        """
        Calcula la base para prestaciones.
        NO duplica auxilio - verifica si ya esta en variable.

        Args:
            days_info: Dict con dias_total (dias finales despues de descuentos)
                       Si se proporciona, usa dias_total para el promedio de variable
                       cuando el auxilio esta incluido en variable.
        """
        contract = localdict['contract']
        slip = localdict['slip']

        # Validar elegibilidad
        elegible = self._validate_prestacion_eligibility(localdict, tipo_prestacion, context)
        if not elegible['aplica']:
            return {
                'aplica': False,
                'motivo': elegible['motivo'],
                'salary': 0, 'variable': 0, 'auxilio': 0,
                'base_mensual': 0, 'base_diaria': 0, 'context': context,
            }

        # Obtener salario
        from ..reglas.basic import calculate_weighted_average_wage
        from dateutil.relativedelta import relativedelta

        # Verificar si debe promediar el sueldo basico
        no_promediar = contract.no_promediar_sueldo_prestaciones or False

        # Meses a revisar segun tipo de prestacion:
        # - Prima: 6 meses (semestre)
        # - Cesantias/Intereses: 12 meses (año completo)
        # - Vacaciones: 12 meses (año completo)
        MESES_POR_TIPO = {
            'prima': 6,
            'cesantias': 12,
            'intereses': 12,
            'vacaciones': 12,
            'all': 12,
        }
        MESES_REVISAR = MESES_POR_TIPO.get(tipo_prestacion, 12)

        if no_promediar:
            salary = contract.wage
            salary_info = {
                'salario_promedio': contract.wage,
                'dias_totales': 0, 'segmentos': [],
                'tiene_cambios': False, 'metodo': 'sin_promediar',
            }
        else:
            date_check = date_to - relativedelta(months=MESES_REVISAR)
            if date_check < date_from:
                date_check = date_from
            salary_info = calculate_weighted_average_wage(contract, date_check, date_to)
            salary_info['metodo'] = f'promedio_{MESES_REVISAR}_meses' if salary_info.get('tiene_cambios') else 'salario_actual'
            salary = salary_info.get('salario_promedio', contract.wage)

        # Obtener variable
        # ═══════════════════════════════════════════════════════════════════
        # SIEMPRE incluir líneas de la nómina actual + nóminas anteriores
        # Ejemplo: Prima de junio debe incluir bonificaciones de junio
        # ═══════════════════════════════════════════════════════════════════

        # 1. Obtener líneas VARIABLES de NÓMINAS ANTERIORES del periodo
        #    (estas SÍ requieren los bools base_prima, base_cesantias, etc.)
        variable_result = self.get_prestaciones_data(
            contract_id=contract.id,
            date_from=date_from,
            date_to=date_to,
            tipo_prestacion=tipo_prestacion,
            contexto_base='liquidacion',
            exclude_payslip_id=slip.id,  # Excluir la actual para no duplicar
            excluded_categories=['BASIC', 'DED', 'PROV', 'SSOCIAL', 'PRESTACIONES_SOCIALES', 'NET', 'AUX'],
        )
        variable_lines_previous = variable_result.get('tree', [])

        # 2. Obtener líneas VARIABLES de la NÓMINA ACTUAL desde localdict['rules']
        variable_lines_current = self._get_variable_lines_from_current_slip(
            localdict, tipo_prestacion
        )

        # 2.1 Combinar y calcular variable_total ANTES de validar tope de auxilio
        variable_lines = variable_lines_previous + variable_lines_current
        variable_total = sum(l.get('total', 0) for l in variable_lines)

        # 3. Obtener AUXILIO - VALIDAR CONDICIONES ANTES DE INCLUIR
        #    Debe respetar:
        #    - Configuración global (prima_incluye_auxilio, cesantias_incluye_auxilio, etc.)
        #    - Tope de 2 SMMLV (si el salario supera, no aplica auxilio)
        #    - Campos del contrato (not_pay_auxtransportation, modality_aux)
        auxilio_lines_previous = []
        auxilio_lines_current = []
        auxilio_aplica = False
        auxilio_motivo = ''

        # Obtener modalidad de auxilio del contrato
        # - basico: usar valor fijo del auxilio vigente
        # - variable: promediar auxilio de los meses del periodo
        # - no: no incluir auxilio en prestaciones
        modality_aux = contract.modality_aux or 'basico'

        # Variables para almacenar ajuste de 360 días en auxilio variable
        auxilio_variable_adjusted_dias = None
        auxilio_variable_date_from_adjusted = None

        if tipo_prestacion in ('prima', 'cesantias', 'intereses', 'intereses_cesantias', 'vacaciones', 'all'):
            # Primero verificar si modality_aux = 'no' (no incluir auxilio)
            if modality_aux == 'no':
                auxilio_motivo = 'Contrato: modalidad auxilio = Sin auxilio (no)'
            else:
                # Obtener configuración global
                ICP = self.env['ir.config_parameter'].sudo()
                config_map = {
                    'prima': 'lavish_hr_payroll.prima_incluye_auxilio',
                    'cesantias': 'lavish_hr_payroll.cesantias_incluye_auxilio',
                    'intereses': 'lavish_hr_payroll.intereses_incluye_auxilio',
                    'intereses_cesantias': 'lavish_hr_payroll.intereses_incluye_auxilio',
                    'vacaciones': 'lavish_hr_payroll.vacaciones_incluye_auxilio',
                    'all': 'lavish_hr_payroll.cesantias_incluye_auxilio',  # Para 'all' usar cesantías
                }
                config_param = config_map.get(tipo_prestacion, 'lavish_hr_payroll.prima_incluye_auxilio')
                incluye_auxilio_config = ICP.get_param(config_param, 'True')
                incluye_auxilio_config = str(incluye_auxilio_config).lower() in ('true', '1', 'yes')

                # Verificar si el contrato NO paga auxilio
                not_pay_aux = contract.not_pay_auxtransportation or False

                # Verificar tope de 2 SMMLV
                annual_params = localdict.get('annual_parameters')
                smmlv = annual_params.smmlv_monthly if annual_params else 0
                tope_smmlv = 2  # Por ley, auxilio aplica si salario <= 2 SMMLV
                tope_valor = smmlv * tope_smmlv

                # Obtener base para validar tope (usando only_wage del contrato)
                only_wage = contract.only_wage or 'wage'
                if only_wage == 'wage':
                    base_tope = salary
                elif only_wage == 'wage_dev':
                    base_tope = salary + variable_total
                else:  # wage_dev_exc
                    base_tope = salary + variable_total  # Simplificado, usar variable total

                # Validar tope 2 SMMLV (se salta si variable_sin_tope o not_validate_top)
                saltar_tope = modality_aux == 'variable_sin_tope'
                not_validate_tope = contract.not_validate_top_auxtransportation or False
                supera_tope = base_tope > tope_valor if tope_valor > 0 and not (saltar_tope or not_validate_tope) else False

                # Determinar si aplica auxilio
                if not incluye_auxilio_config:
                    auxilio_motivo = f'Config global: {tipo_prestacion} no incluye auxilio'
                elif not_pay_aux:
                    auxilio_motivo = 'Contrato: no pagar auxilio de transporte'
                elif supera_tope:
                    auxilio_motivo = f'Salario ({base_tope:,.0f}) supera tope 2 SMMLV ({tope_valor:,.0f})'
                else:
                    auxilio_aplica = True

                # Obtener líneas de auxilio (solo si aplica)
                if auxilio_aplica:
                    # Variable: obtener líneas históricas para promediar; Básico: calcular fijo
                    usar_liquidado = modality_aux in ('variable', 'variable_sin_tope')
                    if usar_liquidado:
                        # Límite 360 días para promedio variable
                        from ..reglas.config_reglas import days360
                        dias_periodo = days360(date_from, date_to)

                        if dias_periodo > 360:
                            from dateutil.relativedelta import relativedelta
                            auxilio_variable_date_from_adjusted = date_to - relativedelta(months=12)
                            if auxilio_variable_date_from_adjusted < date_from:
                                auxilio_variable_date_from_adjusted = date_from
                            auxilio_variable_adjusted_dias = days360(auxilio_variable_date_from_adjusted, date_to)
                        else:
                            auxilio_variable_date_from_adjusted = date_from
                            auxilio_variable_adjusted_dias = dias_periodo

                        auxilio_lines_previous = self.get_aux_lines_in_period(
                            contract.id, auxilio_variable_date_from_adjusted, date_to, slip.id
                        )
                        auxilio_lines_current = self._get_auxilio_from_current_slip(localdict)

        # 4. Combinar líneas de auxilio y calcular total
        auxilio_lines = auxilio_lines_previous + auxilio_lines_current

        # Si está activo el check "forzar días completos", normalizar cada
        # línea de auxilio a 30 días y valor mensual completo (según vigencia).
        force_full_auxilio = (
            bool(getattr(slip, 'force_auxilio_full_days', False))
            and tipo_prestacion in ('prima', 'cesantias', 'intereses', 'intereses_cesantias')
        )
        if force_full_auxilio and auxilio_lines:
            company_id = contract.company_id.id if contract and contract.company_id else None
            ap_cache = {}

            def _aux_mensual_for_line(line):
                total_line = float(line.get('total', 0) or 0.0)
                qty_line = float(line.get('quantity', 0) or line.get('dias', 0) or 0.0)
                mensual_from_line = (total_line / qty_line) * 30.0 if qty_line > 0 else total_line
                year = line.get('year')
                if not year:
                    period_key = line.get('period_key') or ''
                    if period_key and '-' in str(period_key):
                        try:
                            year = int(str(period_key).split('-')[0])
                        except Exception:
                            year = None
                if not year and line.get('date_from'):
                    try:
                        year = int(str(line.get('date_from'))[:4])
                    except Exception:
                        year = None
                if not year and slip and slip.date_to:
                    year = slip.date_to.year

                if not year:
                    return mensual_from_line

                cache_key = (year, company_id)
                if cache_key not in ap_cache:
                    ap = self.env['hr.annual.parameters'].get_for_year(
                        year, company_id=company_id, raise_if_not_found=False
                    )
                    ap_cache[cache_key] = float(getattr(ap, 'transportation_assistance_monthly', 0.0) or 0.0)
                return ap_cache[cache_key] or mensual_from_line

            normalized_lines = []
            for line in auxilio_lines:
                line_copy = dict(line)
                aux_mensual = _aux_mensual_for_line(line_copy)
                # Base forzada por periodo: 30 dias y valor mensual completo.
                line_copy['quantity'] = 30.0
                line_copy['total'] = aux_mensual
                line_copy['amount'] = aux_mensual
                line_copy['period_key'] = (
                    line_copy.get('period_key')
                    or (str(line_copy.get('date_from'))[:7] if line_copy.get('date_from') else '')
                )
                normalized_lines.append(line_copy)

            # Consolidar por periodo (YYYY-MM) y completar meses faltantes del rango.
            by_period = {}
            for line in normalized_lines:
                pk = line.get('period_key') or ''
                if not pk:
                    continue
                if pk not in by_period:
                    by_period[pk] = dict(line)
                else:
                    by_period[pk]['total'] = (by_period[pk].get('total', 0) or 0) + (line.get('total', 0) or 0)
                    by_period[pk]['amount'] = by_period[pk]['total']
                    by_period[pk]['quantity'] = 30.0

            from datetime import date as _date
            start_month = _date(date_from.year, date_from.month, 1)
            end_month = _date(date_to.year, date_to.month, 1)
            month_cursor = start_month
            month_keys = []
            while month_cursor <= end_month:
                month_keys.append(f"{month_cursor.year:04d}-{month_cursor.month:02d}")
                if month_cursor.month == 12:
                    month_cursor = _date(month_cursor.year + 1, 1, 1)
                else:
                    month_cursor = _date(month_cursor.year, month_cursor.month + 1, 1)

            filled_lines = []
            for pk in month_keys:
                if pk in by_period:
                    filled_lines.append(by_period[pk])
                else:
                    try:
                        y = int(pk[:4])
                        m = int(pk[5:7])
                        dt = _date(y, m, 1)
                    except Exception:
                        dt = slip.date_from or date_from
                    aux_mensual = _get_auxilio_mensual_for_line({
                        'period_key': pk,
                        'date_from': dt,
                        'year': dt.year if dt else None,
                    })
                    filled_lines.append({
                        'line_id': 0,
                        'payslip_id': None,
                        'payslip_number': '',
                        'date_from': dt,
                        'date_to': None,
                        'rule_code': 'AUX000',
                        'rule_code_full': 'AUX000',
                        'rule_name': 'AUXILIO DE TRANSPORTE',
                        'category_code': 'AUX',
                        'category_name': 'Auxilio',
                        'total': aux_mensual,
                        'amount': aux_mensual,
                        'quantity': 30.0,
                        'period_key': pk,
                        'year': dt.year if dt else 0,
                        'month': dt.month if dt else 0,
                        'source_type': 'filled_period',
                        'es_auxilio_transporte': True,
                    })

            auxilio_lines = filled_lines

        auxilio_total_from_lines = sum(l.get('total', 0) for l in auxilio_lines)

        # Calcular dias del periodo
        from ..reglas.config_reglas import days360
        days_worked = days360(date_from, date_to)

        # Obtener dias finales del periodo (despues de descuentos)
        dias_finales = (days_info or {}).get('dias_total', 0) if days_info else 0

        # ═══════════════════════════════════════════════════════════════════
        # AUXILIO: Calcular según modality_aux del contrato
        # - basico: usar valor fijo del auxilio vigente
        # - variable: promediar auxilio de los meses del periodo
        # - no: no incluir auxilio (ya manejado arriba, auxilio_aplica=False)
        # ═══════════════════════════════════════════════════════════════════

        # Calcular promedio de variable usando DIAS DEL PERIODO menos descuentos
        # FORMULA: (Total Variable / Días Período) × 30
        # - dias_finales: días del período - ausencias (viene de days_info['dias_total'])
        # - days_worked: días del período sin descontar (fallback)
        if dias_finales > 0:
            variable_promedio_diario = variable_total / dias_finales
            variable_promedio = variable_promedio_diario * 30
            dias_usados_promedio = dias_finales
        elif days_worked > 0:
            variable_promedio_diario = variable_total / days_worked
            variable_promedio = variable_promedio_diario * 30
            dias_usados_promedio = days_worked
        else:
            variable_promedio = 0
            variable_promedio_diario = 0
            dias_usados_promedio = 0

        if force_full_auxilio and auxilio_lines and dias_usados_promedio and dias_usados_promedio > 0:
            total_dias_lineas = sum((l.get('quantity', 0) or 0) for l in auxilio_lines)
            dias_objetivo = min(dias_usados_promedio, 360)
            dias_a_descontar = max(0, total_dias_lineas - dias_objetivo)
            if dias_a_descontar > 0:
                # Descontar desde los periodos mas recientes para reflejar licencias no remuneradas.
                for line in reversed(auxilio_lines):
                    if dias_a_descontar <= 0:
                        break
                    qty = float(line.get('quantity', 0) or 0)
                    if qty <= 0:
                        continue
                    total_line = float(line.get('total', 0) or 0)
                    diario_line = (total_line / qty) if qty > 0 else 0.0
                    descuento = min(qty, dias_a_descontar)
                    line['quantity'] = qty - descuento
                    line['total'] = max(0.0, total_line - (diario_line * descuento))
                    line['amount'] = line['total']
                    dias_a_descontar -= descuento

            auxilio_total_from_lines = sum(l.get('total', 0) for l in auxilio_lines)

        # Calcular auxilio según modality_aux
        auxilio = 0
        auxilio_method = 'no_aplica'
        auxilio_promedio_info = 0
        aux_check = {
            'aux_en_variable': False,
            'total_aux': 0,
            'total_dias': 0,
            'promedio_mensual': 0,
            'lineas': [],
            'count_lines': 0,
            'metodo': 'no_aplica',
        }

        if auxilio_aplica:
            usar_liquidado = modality_aux in ('variable', 'variable_sin_tope')
            if usar_liquidado:
                # Promediar auxilio histórico (días ajustados máx 360 para variable)
                if auxilio_lines and auxilio_total_from_lines > 0:
                    # Usar días ajustados (máx 360) si aplica
                    if force_full_auxilio:
                        # Con check activo: cada periodo suma 30 dias y valor mensual completo,
                        # pero el divisor debe respetar descuentos finales (licencias no remuneradas).
                        if dias_usados_promedio and dias_usados_promedio > 0:
                            dias_para_promedio_aux = min(dias_usados_promedio, 360)
                        else:
                            dias_para_promedio_aux = min(len(auxilio_lines) * 30, 360)
                    elif auxilio_variable_adjusted_dias is not None:
                        dias_para_promedio_aux = min(auxilio_variable_adjusted_dias, 360)
                    else:
                        dias_para_promedio_aux = dias_usados_promedio if dias_usados_promedio > 0 else days_worked
                    aux_check = {
                        'aux_en_variable': True,
                        'total_aux': auxilio_total_from_lines,
                        'total_dias': dias_para_promedio_aux,
                        'promedio_mensual': auxilio_total_from_lines,
                        'lineas': auxilio_lines,
                        'count_lines': len(auxilio_lines),
                        'metodo': 'variable_lineas',
                    }
                    # Calcular promedio mensual
                    if dias_para_promedio_aux > 0 and auxilio_total_from_lines > 0:
                        auxilio = (auxilio_total_from_lines / dias_para_promedio_aux) * 30
                    else:
                        auxilio = auxilio_total_from_lines
                    auxilio_method = 'variable_lineas'
                    auxilio_promedio_info = auxilio
                else:
                    # Verificar auxilio en BD (usar fechas ajustadas si aplica)
                    date_from_query = auxilio_variable_date_from_adjusted if auxilio_variable_date_from_adjusted else date_from
                    aux_check_db = self.check_aux_in_variable(
                        contract.id, date_from_query, date_to, slip.id, tipo_prestacion
                    )
                    if aux_check_db.get('aux_en_variable') and aux_check_db.get('total_aux', 0) > 0:
                        aux_check = aux_check_db
                        aux_check['metodo'] = 'variable_bd'
                        lineas_aux_db = aux_check_db.get('lineas', [])
                        if force_full_auxilio and lineas_aux_db:
                            company_id = contract.company_id.id if contract and contract.company_id else None
                            ap_cache = {}

                            def _aux_mensual_for_db_line(line):
                                total_line = float(line.get('total', 0) or 0.0)
                                qty_line = float(line.get('quantity', 0) or line.get('dias', 0) or 0.0)
                                mensual_from_line = (total_line / qty_line) * 30.0 if qty_line > 0 else total_line
                                year = line.get('year')
                                if not year:
                                    period_key = line.get('period_key') or ''
                                    if period_key and '-' in str(period_key):
                                        try:
                                            year = int(str(period_key).split('-')[0])
                                        except Exception:
                                            year = None
                                if not year and line.get('date_from'):
                                    try:
                                        year = int(str(line.get('date_from'))[:4])
                                    except Exception:
                                        year = None
                                if not year and slip and slip.date_to:
                                    year = slip.date_to.year

                                if not year:
                                    return mensual_from_line

                                cache_key = (year, company_id)
                                if cache_key not in ap_cache:
                                    ap = self.env['hr.annual.parameters'].get_for_year(
                                        year, company_id=company_id, raise_if_not_found=False
                                    )
                                    ap_cache[cache_key] = float(getattr(ap, 'transportation_assistance_monthly', 0.0) or 0.0)
                                return ap_cache[cache_key] or mensual_from_line

                            lineas_aux_db_normalized = []
                            for line in lineas_aux_db:
                                line_copy = dict(line)
                                aux_mensual = _aux_mensual_for_db_line(line_copy)
                                # Base forzada por periodo: 30 dias y valor mensual completo.
                                line_copy['quantity'] = 30.0
                                line_copy['total'] = aux_mensual
                                line_copy['amount'] = aux_mensual
                                lineas_aux_db_normalized.append(line_copy)
                            lineas_aux_db = lineas_aux_db_normalized

                        auxilio_total_calculo = sum((l.get('total', 0) or 0) for l in lineas_aux_db) if lineas_aux_db else aux_check_db.get('total_aux', 0)
                        # Usar días ajustados (máx 360) si aplica
                        if force_full_auxilio:
                            if dias_usados_promedio and dias_usados_promedio > 0:
                                dias_para_promedio_aux = min(dias_usados_promedio, 360)
                            else:
                                dias_para_promedio_aux = min(len(lineas_aux_db) * 30, 360) if lineas_aux_db else 0
                        elif auxilio_variable_adjusted_dias is not None:
                            dias_para_promedio_aux = min(auxilio_variable_adjusted_dias, 360)
                        else:
                            dias_para_promedio_aux = dias_usados_promedio if dias_usados_promedio > 0 else days_worked
                        if dias_para_promedio_aux > 0 and auxilio_total_calculo > 0:
                            auxilio = (auxilio_total_calculo / dias_para_promedio_aux) * 30
                        else:
                            auxilio = aux_check_db.get('promedio_mensual', 0) or auxilio_total_calculo
                        aux_check['total_dias'] = dias_para_promedio_aux
                        auxilio_method = 'variable_bd'
                        auxilio_promedio_info = auxilio
                        auxilio_lines = lineas_aux_db
                    else:
                        # No hay auxilio en periodo con modalidad variable, auxilio = 0
                        auxilio = 0
                        auxilio_method = 'variable_sin_lineas'
                        auxilio_promedio_info = 0
            else:
                # BASICO: usar valor fijo del auxilio vigente
                annual_params = localdict.get('annual_parameters')
                if annual_params:
                    auxilio_info = self.env['hr.salary.rule.aux']._calcular_auxilio_provision(
                        annual_params, contract, days_worked,
                        dias_periodo=30, date_from=date_from, date_to=date_to, slip=slip,
                    )
                    auxilio = auxilio_info.get('auxilio', 0)
                    auxilio_method = 'basico_fijo'
                    auxilio_promedio_info = auxilio
                    aux_check = {
                        'aux_en_variable': False,
                        'total_aux': auxilio,
                        'total_dias': 30,
                        'promedio_mensual': auxilio,
                        'lineas': [],
                        'count_lines': 0,
                        'metodo': 'basico_fijo',
                    }
                else:
                    auxilio = 0
                    auxilio_method = 'basico_sin_params'

        # PRV_VAC (provision): mantener piso/base salarial, pero permitir
        # sumar variables y auxilio cuando estén parametrizados.
        if tipo_prestacion == 'vacaciones' and context == 'provision':
            annual_params = localdict.get('annual_parameters')
            year = slip.date_to.year if slip and slip.date_to else 0

            salario_vac_mensual = 0.0
            if year == 2025:
                salario_vac_mensual = 1423500.0
            elif year >= 2026 and annual_params:
                salario_vac_mensual = float(getattr(annual_params, 'smmlv_monthly', 0.0) or 0.0)

            if salario_vac_mensual > 0:
                salary = salario_vac_mensual
            auxilio = 0.0
            auxilio_method = 'no_aplica_prv_vac'
            auxilio_promedio_info = 0.0
            auxilio_lines = []
            aux_check = {
                'aux_en_variable': False,
                'total_aux': 0.0,
                'total_dias': 0.0,
                'promedio_mensual': 0.0,
                'lineas': [],
                'count_lines': 0,
                'metodo': 'no_aplica_prv_vac',
            }

        base_mensual = salary + variable_promedio + auxilio
        base_diaria = base_mensual / 30

        # Para intereses de cesantias, incluir tasa de interes
        tasa_intereses = 0.0
        if tipo_prestacion == 'intereses':
            # Obtener tasa de parametros del sistema o usar default 12%
            ICP = self.env['ir.config_parameter'].sudo()
            tasa_intereses = float(ICP.get_param('lavish_hr_payroll.tasa_intereses_cesantias', '0.12'))

        # Calcular dias reales para trazabilidad (NO se usan en el promedio, solo info)
        variable_dias_reales = sum((l.get('quantity') or 0) for l in variable_lines) if variable_lines else 0
        auxilio_dias_reales = sum((l.get('quantity') or 0) for l in auxilio_lines) if auxilio_lines else 0

        return {
            'aplica': True,
            'tipo_prestacion': tipo_prestacion,
            'salary': salary, 'salary_info': salary_info,
            'variable': variable_promedio, 'variable_total': variable_total, 'variable_lines': variable_lines,
            'variable_dias_reales': variable_dias_reales,  # Dias sumados de las lineas variable
            'dias_usados_promedio': dias_usados_promedio,  # Dias usados para calcular el promedio variable
            'auxilio': auxilio, 'auxilio_method': auxilio_method,
            'auxilio_promedio': auxilio_promedio_info,  # Promedio mensual de auxilio (para trazabilidad)
            'auxilio_lines': auxilio_lines,  # Lineas de auxilio (anteriores + actual)
            'auxilio_dias_reales': auxilio_dias_reales,  # Dias sumados de las lineas de auxilio
            'auxilio_total': aux_check.get('total_aux', 0),  # Total de auxilio de todas las lineas
            'auxilio_en_variable': aux_check['aux_en_variable'], 'auxilio_check': aux_check,
            'auxilio_aplica': auxilio_aplica,  # Si aplica auxilio según validaciones
            'auxilio_motivo_no_aplica': auxilio_motivo,  # Motivo si no aplica
            'modality_aux': modality_aux,  # Modalidad de auxilio del contrato (basico, variable, no)
            'base_mensual': base_mensual, 'base_diaria': base_diaria,
            'days_worked': days_worked, 'context': context,
            'tasa_intereses_cesantias': tasa_intereses,  # Solo usado para intereses (12% = 0.12)
        }

    def _get_variable_lines_from_current_slip(self, localdict, tipo_prestacion):
        """
        Obtiene líneas de variable desde la nómina actual (localdict['rules']).

        Similar a como IBD obtiene sus datos desde rules.
        Usado para incluir líneas de la misma nómina en el cálculo de prestaciones.

        En Odoo 18, localdict['rules'] es un dict donde:
        - Keys: códigos de regla (ej: 'HEYREC001', 'BON001')
        - Values: BrowsableObject con propiedades .rule, .total, .quantity, etc.

        Args:
            localdict: Dict con slip, contract, rules, etc.
            tipo_prestacion: 'prima', 'cesantias', 'vacaciones', 'intereses'

        Returns:
            list: Líneas de variable en formato compatible con SQL query
        """
        rules = localdict.get('rules', {})
        slip = localdict['slip']

        if not rules:
            return []

        # Mapeo de tipo_prestacion a campo de base
        # Categorías a excluir (AUX se obtiene por separado en _get_auxilio_from_current_slip)
        EXCLUDED_CATEGORIES = {'BASIC', 'DED', 'PROV', 'SSOCIAL', 'PRESTACIONES_SOCIALES', 'NET', 'AUX'}

        base_field = None if tipo_prestacion == 'all' else get_prestacion_base_field(
            tipo_prestacion,
            contexto='liquidacion',
        )
        variable_lines = []

        # Iterar sobre las reglas usando el patrón correcto de Odoo 18
        # rules.items() devuelve (code, rule_data) donde rule_data tiene .rule, .total, .quantity
        for code, rule_data in rules.items():
            # Obtener el objeto regla y valores
            # En Odoo 18, rule_data tiene .rule (hr.salary.rule), .total, .quantity
            rule = getattr(rule_data, 'rule', None)
            total = getattr(rule_data, 'total', 0) or 0
            quantity = getattr(rule_data, 'quantity', 0) or 0

            if not rule:
                continue

            # Obtener categoría desde la regla
            category = rule.category_id if hasattr(rule, 'category_id') else None
            cat_code = category.code if category and hasattr(category, 'code') else ''

            # Excluir categorías no deseadas
            if cat_code.upper() in EXCLUDED_CATEGORIES:
                continue

            # Excluir auxilio (se obtiene por separado, no necesita bools)
            if getattr(rule, 'es_auxilio_transporte', False):
                continue

            # Verificar flag de base según tipo de prestación
            if base_field:
                has_base = getattr(rule, base_field, False)
                if not has_base:
                    continue
            else:
                # 'all': verificar cualquier flag de base
                has_any_base = any([
                    getattr(rule, 'base_prima_liquidacion', False),
                    getattr(rule, 'base_cesantias_liquidacion', False),
                    getattr(rule, 'base_vacaciones_liquidacion', False),
                    getattr(rule, 'base_vacaciones_dinero_liquidacion', False),
                    getattr(rule, 'base_intereses_cesantias_liquidacion', False),
                ])
                if not has_any_base:
                    continue

            # Solo incluir si tiene valor positivo
            if total <= 0:
                continue

            # Formatear línea en formato compatible con SQL query
            variable_lines.append({
                'line_id': getattr(rule_data, 'id', 0) or 0,
                'payslip_id': slip.id,
                'payslip_number': slip.number or slip.name,
                'date_from': slip.date_from,
                'date_to': slip.date_to,
                'rule_code': rule.code,
                'rule_code_full': rule.code,
                'rule_name': rule.name,
                'category_code': cat_code,
                'category_name': category.name if category and hasattr(category, 'name') else cat_code,
                'total': total,
                'amount': total,
                'quantity': quantity,
                'period_key': slip.date_from.strftime('%Y-%m') if slip.date_from else '',
                'year': slip.date_from.year if slip.date_from else 0,
                'month': slip.date_from.month if slip.date_from else 0,
                'source_type': 'current_slip',
                'es_auxilio_transporte': getattr(rule, 'es_auxilio_transporte', False),
            })

        return variable_lines

    def _get_auxilio_from_current_slip(self, localdict):
        """
        Obtiene líneas de AUXILIO desde la nómina actual (localdict['rules']).

        El auxilio se identifica por:
        - Categoría 'AUX'
        - O campo es_auxilio_transporte=True en la regla

        NO usa flags de base (base_prima, base_cesantias, etc.) porque
        el auxilio siempre se incluye en prestaciones por ley.

        Args:
            localdict: Dict con slip, contract, rules, etc.

        Returns:
            list: Líneas de auxilio en formato compatible con SQL query
        """
        rules = localdict.get('rules', {})
        slip = localdict['slip']

        if not rules:
            return []

        auxilio_lines = []

        # Iterar sobre las reglas usando el patrón de Odoo 18
        for code, rule_data in rules.items():
            rule = getattr(rule_data, 'rule', None)
            total = getattr(rule_data, 'total', 0) or 0
            quantity = getattr(rule_data, 'quantity', 0) or 0

            if not rule or total <= 0:
                continue

            # Obtener categoría y categoría padre desde la regla
            category = rule.category_id if hasattr(rule, 'category_id') else None
            cat_code = category.code if category and hasattr(category, 'code') else ''
            parent_cat = category.parent_id if category and hasattr(category, 'parent_id') else None
            parent_cat_code = parent_cat.code if parent_cat and hasattr(parent_cat, 'code') else ''
            rule_code = (getattr(rule, 'code', '') or '').upper()
            rule_name = (getattr(rule, 'name', '') or '').upper()

            # Verificar si es auxilio:
            # - Categoría 'AUX' (o que contenga 'AUX')
            # - O categoría padre 'AUX'
            # - O campo es_auxilio_transporte=True
            es_auxilio = (
                cat_code.upper() == 'AUX' or
                'AUX' in cat_code.upper() or
                parent_cat_code.upper() == 'AUX' or
                getattr(rule, 'es_auxilio_transporte', False) or
                rule_code.startswith('AUX') or
                'CONECTIVIDAD' in rule_name or
                'AUXILIO DE TRANSPORTE' in rule_name
            )

            if not es_auxilio:
                continue

            # Formatear línea en formato compatible
            auxilio_lines.append({
                'line_id': getattr(rule_data, 'id', 0) or 0,
                'payslip_id': slip.id,
                'payslip_number': slip.number or slip.name,
                'date_from': slip.date_from,
                'date_to': slip.date_to,
                'rule_code': rule.code,
                'rule_code_full': rule.code,
                'rule_name': rule.name,
                'category_code': cat_code,
                'category_name': category.name if category and hasattr(category, 'name') else cat_code,
                'total': total,
                'amount': total,
                'quantity': quantity,
                'period_key': slip.date_from.strftime('%Y-%m') if slip.date_from else '',
                'year': slip.date_from.year if slip.date_from else 0,
                'month': slip.date_from.month if slip.date_from else 0,
                'source_type': 'current_slip',
                'es_auxilio_transporte': True,
            })

        return auxilio_lines

    def _validate_prestacion_eligibility(self, localdict, tipo_prestacion, context):
        """Valida si el empleado/contrato tiene derecho a la prestacion."""
        contract = localdict['contract']
        employee = localdict.get('employee')

        # Verificar tipo de contrato
        contract_type = contract.contract_type_id
        if contract_type:
            has_field_map = {
                'prima': 'has_prima',
                'cesantias': 'has_cesantias',
                'intereses': 'has_intereses_cesantias',
                'vacaciones': 'has_vacaciones',
            }
            has_field = has_field_map.get(tipo_prestacion)
            if has_field and has_field in contract_type._fields:
                if not contract_type[has_field]:
                    return {'aplica': False, 'motivo': f'Tipo contrato {contract_type.name} no tiene {tipo_prestacion}'}

        # Validaciones por contexto
        slip = localdict['slip']
        struct_process = slip.struct_id.process if slip.struct_id else 'nomina'

        if context == 'provision' and struct_process == 'contrato':
            return {'aplica': False, 'motivo': 'Provision no aplica en liquidacion'}

        if context == 'liquidacion' and struct_process != 'contrato':
            return {'aplica': False, 'motivo': 'Liquidacion solo en nomina liquidacion'}

        if context == 'consolidacion':
            month = slip.date_to.month if slip.date_to else 0
            if tipo_prestacion == 'prima' and month not in (6, 12):
                return {'aplica': False, 'motivo': 'Consolidacion prima solo junio/diciembre'}
            if tipo_prestacion in ('cesantias', 'intereses') and month != 12:
                return {'aplica': False, 'motivo': 'Consolidacion cesantias solo diciembre'}

        # Verificar aprendiz
        if employee:
            try:
                aplica = self.env['hr.salary.rule']._aprendiz_tiene_prestaciones(employee, contract, tipo_prestacion)
                if not aplica:
                    return {'aplica': False, 'motivo': 'Aprendiz sin derecho a prestacion'}
            except AttributeError:
                pass

        return {'aplica': True, 'motivo': ''}
