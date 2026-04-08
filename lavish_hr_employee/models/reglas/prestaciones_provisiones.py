# -*- coding: utf-8 -*-
"""
PRESTACIONES - PROVISIONES Y CONSOLIDACION
===========================================
Metodos de provision y consolidacion para reglas salariales.

Codigos de reglas de PROVISION:
- PRV_PRIM: _prv_prim()
- PRV_CES: _prv_ces()
- PRV_ICES: _prv_ices()
- PRV_VAC: _prv_vac()

Codigos de reglas de CONSOLIDACION:
- CESANTIAS_CONS: _cesantias_cons()
- INTCESANTIAS_CONS: _intcesantias_cons()
- VACACIONES_CONS: _vacaciones_cons()

Consolidacion:
- Prima: Junio y Diciembre
- Cesantias/Intereses: Diciembre (antes del 14 de febrero)

Cuentas contables (configurables):
- Provision (26XX): 261005 Cesantias, 261010 Intereses, 261015 Vacaciones
- Obligacion (25XX): 2510 Cesantias, 2515 Intereses, 2525 Vacaciones
"""
from odoo import models, api
from datetime import date
import logging
from .config_reglas import get_prestacion_base_field

_logger = logging.getLogger(__name__)

class HrSalaryRulePrestacionesProvisiones(models.AbstractModel):
    """
    Servicio para provisiones y consolidacion de prestaciones sociales.

    Metodos de provision (llamados por reglas con amount_select='concept'):
    - _prv_prim(): Codigo PRV_PRIM
    - _prv_ces(): Codigo PRV_CES
    - _prv_ices(): Codigo PRV_ICES
    - _prv_vac(): Codigo PRV_VAC

    Metodos de consolidacion:
    - _cesantias_cons(): Codigo CESANTIAS_CONS
    - _intcesantias_cons(): Codigo INTCESANTIAS_CONS
    - _vacaciones_cons(): Codigo VACACIONES_CONS
    """
    _name = 'hr.salary.rule.prestaciones.provisiones'
    _description = 'Provisiones de Prestaciones Sociales'

    # =========================================================================
    # CONFIGURACION DE CUENTAS CONTABLES
    # =========================================================================

    CUENTAS_PRESTACIONES = {
        'cesantias': {
            'provision': '261005',      # Pasivos estimados - Cesantias
            'obligacion': '2510',       # Obligaciones laborales - Cesantias
            'param_provision': 'lavish_hr_payroll.cuenta_provision_cesantias_id',
            'param_obligacion': 'lavish_hr_payroll.cuenta_consolidacion_cesantias_id',
        },
        'intereses': {
            'provision': '261010',      # Pasivos estimados - Int. Cesantias
            'obligacion': '2515',       # Obligaciones laborales - Int. Cesantias
            'param_provision': 'lavish_hr_payroll.cuenta_provision_intereses_id',
            'param_obligacion': 'lavish_hr_payroll.cuenta_consolidacion_intereses_id',
        },
        'vacaciones': {
            'provision': '261015',      # Pasivos estimados - Vacaciones
            'obligacion': '2525',       # Obligaciones laborales - Vacaciones
            'param_provision': 'lavish_hr_payroll.cuenta_provision_vacaciones_id',
            'param_obligacion': 'lavish_hr_payroll.cuenta_consolidacion_vacaciones_id',
        },
        'prima': {
            'provision': '261020',      # Pasivos estimados - Prima (si aplica)
            'obligacion': '2520',       # Obligaciones laborales - Prima
            'param_provision': 'lavish_hr_payroll.cuenta_provision_prima_id',
            'param_obligacion': 'lavish_hr_payroll.cuenta_consolidacion_prima_id',
        },
    }

    # Mapeo tipo_prestacion -> (codigo_regla, codigo_provision)
    REGLA_MAP = {
        'prima': ('PRIMA', 'PRV_PRIM'),
        'cesantias': ('CESANTIAS', 'PRV_CES'),
        'intereses': ('INTCESANTIAS', 'PRV_ICES'),
        'vacaciones': ('VACACIONES', 'PRV_VAC'),
    }

    def _get_cuentas_provision_contables(self, tipo_prestacion):
        """Busca cuenta de balance (credito de provision) desde hr.salary.rule."""
        result = {
            'cuenta_debito_id': False, 'cuenta_credito_id': False,
            'cuenta_debito_code': '', 'cuenta_credito_code': '',
            'cuenta_balance_id': False, 'cuenta_balance_code': '',
        }
        codes = self.REGLA_MAP.get(tipo_prestacion)
        if not codes:
            _logger.warning(f"[CUENTAS] No hay REGLA_MAP para tipo={tipo_prestacion}")
            return result

        codigo_regla, codigo_provision = codes
        SalaryRule = self.env['hr.salary.rule']

        regla = SalaryRule.search([('code', '=', codigo_regla)], limit=1)
        if regla and regla.salary_rule_accounting:
            for acc in regla.salary_rule_accounting:
                if acc.debit_account:
                    result['cuenta_debito_id'] = acc.debit_account.id
                    result['cuenta_debito_code'] = acc.debit_account.code
                    break
        else:
            _logger.warning(f"[CUENTAS] Regla {codigo_regla} no encontrada o sin accounting")

        provision = SalaryRule.search([('code', '=', codigo_provision)], limit=1)
        if provision and provision.salary_rule_accounting:
            for acc in provision.salary_rule_accounting:
                if acc.credit_account:
                    result['cuenta_credito_id'] = acc.credit_account.id
                    result['cuenta_credito_code'] = acc.credit_account.code
                    result['cuenta_balance_id'] = acc.credit_account.id
                    result['cuenta_balance_code'] = acc.credit_account.code
                    break
        else:
            _logger.warning(f"[CUENTAS] Provision {codigo_provision} no encontrada o sin accounting")

        return result

    # =========================================================================
    # METODOS DE PROVISION - Llamados por reglas salariales
    # =========================================================================

    def _prv_prim(self, localdict):
        return self._calculate_provision_rule(localdict, 'prima')

    def _prv_ces(self, localdict):
        return self._calculate_provision_rule(localdict, 'cesantias')

    def _prv_ices(self, localdict):
        return self._calculate_provision_rule(localdict, 'intereses')

    def _prv_vac(self, localdict):
        return self._calculate_provision_rule(localdict, 'vacaciones')

    def _get_prv_vac_salario_base(self, localdict):
        """
        Piso salarial mensual para PRV_VAC por vigencia:
        - Desactivado: PRV_VAC siempre usa salario del contrato.
        """
        return 0.0

    FIELD_MAP = {
        'prima': get_prestacion_base_field('prima', contexto='provision'),
        'cesantias': get_prestacion_base_field('cesantias', contexto='provision'),
        'intereses': get_prestacion_base_field('intereses', contexto='provision'),
        'vacaciones': get_prestacion_base_field('vacaciones', contexto='provision'),
    }

    def _calculate_provision_rule(self, localdict, tipo_prestacion):
        """Simple o completa segun config. Agrega saldo contable acumulado al data."""
        annual_params = localdict.get('annual_parameters')
        # La configuracion de la empresa es la principal. Parametros anuales
        # solo deben habilitar simple_provisions cuando la empresa no lo tiene activo.
        simple_provisions = self.env.company.simple_provisions
        if not simple_provisions and annual_params:
            simple_provisions = annual_params.simple_provisions

        if simple_provisions:
            result = self._calculate_simple_provision(localdict, tipo_prestacion)
        else:
            result = self._calculate_completa_provision(localdict, tipo_prestacion)

        if not result or len(result) < 6:
            _logger.warning(f"[PROV_RULE] Resultado invalido: {result}")

        return self._enrich_provision_with_saldo(result, localdict, tipo_prestacion)

    def _is_liquidacion(self, slip):
        """Detecta si el payslip es de liquidación de contrato."""
        if not slip or not slip.struct_id:
            return False
        return slip.struct_id.process == 'contrato'

    def _enrich_provision_with_saldo(self, result, localdict, tipo_prestacion):
        """Agrega provision acumulada y ajuste al data dict de la provision."""
        if not result or len(result) < 6:
            _logger.warning(f"[ENRICH] Resultado invalido, retornando sin enriquecer")
            return result
        monto, qty, rate, nombre, log, data = result
        if not isinstance(data, dict) or not data.get('aplica'):
            _logger.warning(f"[ENRICH] Data no aplica o no es dict, retornando sin enriquecer")
            return result

        slip = localdict['slip']
        contract = localdict['contract']
        employee = localdict.get('employee')
        date_to = slip.date_to
        es_liquidacion = self._is_liquidacion(slip)

        cuentas_regla = self._get_cuentas_provision_contables(tipo_prestacion)
        cuentas_config = self.CUENTAS_PRESTACIONES.get(tipo_prestacion, {})

        integrar_contabilidad = self.env['ir.config_parameter'].sudo().get_param(
            'lavish_hr_payroll.integrar_consolidacion_liquidacion', False
        )

        provision_acumulada = 0
        usa_contabilidad = False

        # Siempre calcular las fechas del periodo (usadas para navegación JS y fallback nóminas)
        date_period_from, date_period_to = self._get_period_dates(tipo_prestacion, date_to)

        # Liquidación: siempre usar contabilidad para obtener el saldo real provisionado
        # Primero verificar si ya se calculó (cached por regla de liquidación)
        cached = localdict.get('_prov_saldos', {}).get(tipo_prestacion)
        if cached is not None and (integrar_contabilidad or es_liquidacion):
            provision_acumulada = cached
            usa_contabilidad = True
        elif integrar_contabilidad or es_liquidacion:
            saldo = self._get_saldo_cuenta_provision(cuentas_regla, cuentas_config, date_to, employee)
            cuenta_existe = bool(cuentas_regla.get('cuenta_balance_id'))
            if saldo or (es_liquidacion and cuenta_existe):
                provision_acumulada = saldo
                usa_contabilidad = True
                # Cachear para que la regla de liquidación no repita la consulta
                localdict.setdefault('_prov_saldos', {})[tipo_prestacion] = provision_acumulada

        provision_lineas = []
        if not usa_contabilidad:
            prov_data = self._get_provision_acumulada(
                contract_id=contract.id,
                tipo_prestacion=tipo_prestacion,
                date_period_from=date_period_from,
                date_period_to=date_period_to,
                exclude_slip_id=slip.id,
            )
            provision_acumulada = prov_data.get('total', 0)
            # Extraer lineas individuales para detalle en el widget
            for ln in prov_data.get('lineas', []):
                slip_ref = ln.get('slip_id')
                provision_lineas.append({
                    'id': ln.get('id', 0),
                    'code': ln.get('code', ''),
                    'total': ln.get('total', 0),
                    'name': ln.get('name', ''),
                    'slip_id': slip_ref[0] if isinstance(slip_ref, (list, tuple)) else slip_ref,
                    'slip_name': slip_ref[1] if isinstance(slip_ref, (list, tuple)) and len(slip_ref) > 1 else '',
                })

        ajuste = monto - provision_acumulada

        data['monto_total'] = monto
        data['provision_acumulada'] = provision_acumulada
        data['ajuste'] = ajuste
        data['usa_contabilidad'] = usa_contabilidad
        data['provision_lineas'] = provision_lineas

        # Inyectar en data_kpi para que el parser JS los encuentre
        if 'data_kpi' not in data:
            data['data_kpi'] = {}
        data['data_kpi']['provision_calculada'] = monto
        data['data_kpi']['provision_acumulada'] = provision_acumulada
        data['data_kpi']['ajuste'] = ajuste
        data['data_kpi']['usa_contabilidad'] = usa_contabilidad
        data['data_kpi']['provision_lineas'] = provision_lineas
        data['data_kpi']['cuenta_balance_code'] = cuentas_regla.get('cuenta_balance_code', '')
        data['data_kpi']['cuenta_debito_code'] = cuentas_regla.get('cuenta_debito_code', '')
        data['data_kpi']['fuente_acumulado'] = 'contabilidad' if usa_contabilidad else 'nominas'

        # IDs para navegación desde el widget JS
        data['data_kpi']['slip_id'] = slip.id
        data['data_kpi']['contract_id'] = contract.id
        data['data_kpi']['employee_id'] = employee.id if employee else False
        partner = employee.work_contact_id if employee and employee.work_contact_id else False
        data['data_kpi']['partner_id'] = partner.id if partner else False
        data['data_kpi']['cuenta_balance_id'] = cuentas_regla.get('cuenta_balance_id', False)
        data['data_kpi']['tipo_prestacion'] = tipo_prestacion
        data['data_kpi']['date_period_from'] = str(date_period_from) if date_period_from else ''
        data['data_kpi']['date_period_to'] = str(date_period_to) if date_period_to else ''

        # Provision completa: el amount de la linea es el ajuste (total - acumulado)
        # Provision simple: el amount es el monto fijo mensual (sin restar)
        # Liquidación: siempre usar ajuste (obligacion - contabilidad) para cuadrar saldos
        es_completa = data.get('tipo_provision') == 'completa'
        amount = ajuste if (es_completa or es_liquidacion) else monto

        return (amount, qty, rate, nombre, log, data)

    def _calculate_simple_provision(self, localdict, tipo_prestacion):
        """Provision simple: usa lineas del slip y prorratea por dias pagados (WORK100/manual_days)."""
        slip = localdict['slip']
        contract = localdict['contract']
        annual_params = localdict.get('annual_parameters')

        sueldo_contrato = contract.wage or 0.0
        field_bool = self.FIELD_MAP.get(tipo_prestacion)
        fragment_vac = annual_params.fragment_vac if annual_params else False

        rules_current = localdict.get('rules', {})
        total_variable = 0.0
        total_auxilio = 0.0

        for code, rule_data in (rules_current.items() if hasattr(rules_current, 'items') else []):
            rule = rule_data.rule if hasattr(rule_data, 'rule') else None
            if not rule:
                continue
            has_leave = getattr(rule_data, 'has_leave', False)
            # Regla de precedencia: si la regla está marcada para la base de la
            # prestación, se incluye aunque sea novedad/ausencia.
            if has_leave and not (field_bool and getattr(rule, field_bool, False)):
                continue
            rule_total = getattr(rule_data, 'total', 0) or 0
            if rule_total == 0:
                continue

            # Vacaciones fragmentadas: solo lineas del mes
            if tipo_prestacion == 'vacaciones' and fragment_vac:
                leave_id = getattr(rule_data, 'leave_id', 0)
                if leave_id:
                    continue

            # Auxilio de transporte
            es_auxilio = getattr(rule, 'es_auxilio_transporte', False)
            if not es_auxilio and rule.category_id:
                cat = rule.category_id
                es_auxilio = cat.code == 'AUX' or (cat.parent_id and cat.parent_id.code == 'AUX')
            if es_auxilio:
                total_auxilio += rule_total
                continue

            # Regla con campo base (excluir BASIC = sueldo)
            if field_bool and getattr(rule, field_bool, False):
                cat_code = rule.category_id.code if rule.category_id else ''
                if cat_code != 'BASIC':
                    total_variable += rule_total

        method = self._get_provision_days_method(annual_params)
        dias_periodo = self._get_period_days_for_provision(slip)
        dias_pagados = dias_periodo
        days_source = 'periodo'
        if method == 'worked_days':
            dias_worked = self._get_worked_days_for_provision(slip)
            if dias_worked > 0:
                dias_pagados = dias_worked
                days_source = 'worked_days'

        dias_pagados = max(0.0, min(dias_periodo, dias_pagados))
        sueldo = (sueldo_contrato / dias_periodo) * dias_pagados if dias_periodo else 0.0

        # Variable y auxilio ya vienen del slip (normalmente ya proporcionalizados), no re-prorratear.
        if tipo_prestacion == 'vacaciones':
            salario_vac_mensual = self._get_prv_vac_salario_base(localdict)
            salary_base_data = salario_vac_mensual if salario_vac_mensual > 0 else sueldo
            base_mensual = salary_base_data + total_variable
        else:
            base_mensual = sueldo + total_variable + total_auxilio
            salary_base_data = sueldo

        porcentajes = {'prima': 8.33333, 'cesantias': 8.33333, 'intereses': 1.0, 'vacaciones': 4.16667}
        pct = porcentajes.get(tipo_prestacion, 8.33333)

        cesantias_causadas = 0.0
        fuente_ices = 'formula_base_mensual'
        if tipo_prestacion == 'intereses':
            # Si PRV_CES ya existe en la nómina actual, usarla como base de intereses.
            ces_prv = self._get_rule_total(localdict, 'PRV_CES')
            if ces_prv is not None:
                cesantias_causadas = ces_prv
                fuente_ices = 'regla_prv_ces'
            else:
                # Fallback histórico cuando PRV_CES no está en el contexto.
                cesantias_causadas = base_mensual * (porcentajes['cesantias'] / 100)
            monto = cesantias_causadas * 0.12
        else:
            monto = base_mensual * (pct / 100)

        year = slip.date_to.year if slip.date_to else date.today().year
        month = slip.date_to.month if slip.date_to else date.today().month
        nombres = {
            'prima': f"PROVISION PRIMA {month:02d}/{year}",
            'cesantias': f"PROVISION CESANTIAS {month:02d}/{year}",
            'intereses': f"PROVISION INT. CESANTIAS {month:02d}/{year}",
            'vacaciones': f"PROVISION VACACIONES {month:02d}/{year}",
        }
        nombre = nombres.get(tipo_prestacion, f"PROVISION {tipo_prestacion.upper()}")

        total_variable_data = total_variable
        total_auxilio_data = 0.0 if tipo_prestacion == 'vacaciones' else total_auxilio
        data = {
            'monto_total': monto,
            'tipo_provision': 'simple',
            'aplica': True,
            'data_kpi': {
                'base_mensual': base_mensual,
                'sueldo': sueldo,
                'sueldo_contrato': sueldo_contrato,
                'promedio': total_variable_data, 'auxilio': total_auxilio_data,
                'porcentaje': pct, 'tipo_prestacion': tipo_prestacion,
                # Alias keys para widget JS (PayslipLineProvision / PayslipLinePrestacion)
                'salary_base': salary_base_data,
                'salary_variable': total_variable_data,
                'subsidy': total_auxilio_data,
                'days_worked': dias_pagados,
                'dias_pagados': dias_pagados,
                'dias_periodo': dias_periodo,
                'dias_computables': dias_pagados,
                'days_method': method,
                'days_source': days_source,
                'cesantias_causadas': cesantias_causadas,
                'tasa_intereses': 0.12 if tipo_prestacion == 'intereses' else 0.0,
                'fuente_ices': fuente_ices if tipo_prestacion == 'intereses' else '',
            },
        }
        return (monto, 1, 100, nombre, '', data)

    def _get_provision_days_method(self, annual_params):
        """Obtiene método de días para provisión con fallback seguro."""
        if annual_params and getattr(annual_params, 'provision_days_method', False):
            return annual_params.provision_days_method
        return 'periodo'

    def _get_period_days_for_provision(self, slip):
        """
        Días completos del período para provisión:
        - Quincenas: días exactos del rango (normalmente 15/16).
        - Mes completo: 30 días (convención nómina).
        """
        if not slip or not slip.date_from or not slip.date_to:
            return 30.0
        period_days = (slip.date_to - slip.date_from).days + 1
        if period_days <= 0:
            return 30.0
        return float(period_days if period_days <= 16 else 30.0)

    def _get_worked_days_for_provision(self, slip):
        """Obtiene días trabajados desde worked_days_line_ids con fallback WORK100 -> WORK_D."""
        if not slip or not slip.worked_days_line_ids:
            return 0.0

        for code in ('WORK100', 'WORK_D'):
            line = slip.worked_days_line_ids.filtered(lambda l: l.code == code)[:1]
            if line:
                return float(getattr(line, 'number_of_days', 0.0) or getattr(line, 'days', 0.0) or 0.0)
        return 0.0

    def _get_rule_total(self, localdict, code):
        """
        Obtiene el total de una regla ya calculada en localdict['rules'].
        Devuelve None si no existe en el contexto actual.
        """
        rules_current = localdict.get('rules', {})
        if hasattr(rules_current, 'get'):
            rule_data = rules_current.get(code)
            if rule_data is not None:
                return float(getattr(rule_data, 'total', 0.0) or 0.0)
        return None

    def _compute_cesantias_causadas(self, base_mensual, dias_a_pagar):
        """Calcula cesantias causadas sobre una base mensual y dias liquidados."""
        dias = max(dias_a_pagar or 0.0, 0.0)
        if not dias:
            return 0.0
        return (base_mensual * dias) / 360.0

    def _calculate_completa_provision(self, localdict, tipo_prestacion):
        """Provision completa: mismo patron que liquidacion al corte (slip.date_to)."""
        slip = localdict['slip']
        prestaciones_svc = self.env['hr.salary.rule.prestaciones']

        sueldo_info = prestaciones_svc._get_sueldo_dias_a_pagar(localdict, tipo_prestacion)
        variable_base = prestaciones_svc._get_variable_base(
            localdict,
            tipo_prestacion,
            contexto_base='provision',
        )
        promedio = prestaciones_svc._compute_promedio(localdict, sueldo_info, variable_base, 'provision')
        auxilio = prestaciones_svc._get_auxilio(localdict, tipo_prestacion, promedio, sueldo_info)
        auxilio_valor = auxilio.get('promedio_auxilio', 0) if auxilio.get('aplica') else 0

        sueldo = sueldo_info.get('sueldo', 0)
        if tipo_prestacion == 'vacaciones':
            salario_vac_mensual = self._get_prv_vac_salario_base(localdict)
            salary_base_data = salario_vac_mensual if salario_vac_mensual > 0 else sueldo
            base_mensual = salary_base_data + promedio
            auxilio_valor = 0.0
        else:
            base_mensual = sueldo + promedio + auxilio_valor
            salary_base_data = sueldo
        dias_a_pagar = sueldo_info.get('dias_a_pagar', 0)

        divisores = {'prima': 180, 'cesantias': 360, 'intereses': 360, 'vacaciones': 720}
        divisor = divisores.get(tipo_prestacion, 360)

        cesantias_causadas = 0.0
        fuente_ices = 'formula_base_mensual'
        if tipo_prestacion in ('cesantias', 'intereses'):
            cesantias_causadas = self._compute_cesantias_causadas(base_mensual, dias_a_pagar)

        if tipo_prestacion == 'intereses':
            ces_prv = self._get_rule_total(localdict, 'PRV_CES')
            if ces_prv is not None:
                cesantias_causadas = ces_prv
                fuente_ices = 'regla_prv_ces'
            monto = cesantias_causadas * 0.12
        elif tipo_prestacion == 'cesantias':
            monto = cesantias_causadas
        else:
            monto = (base_mensual * dias_a_pagar) / divisor if divisor else 0

        year = slip.date_to.year if slip.date_to else date.today().year
        month = slip.date_to.month if slip.date_to else date.today().month
        nombres = {
            'prima': f"PROVISION PRIMA {month:02d}/{year}",
            'cesantias': f"PROVISION CESANTIAS {month:02d}/{year}",
            'intereses': f"PROVISION INT. CESANTIAS {month:02d}/{year}",
            'vacaciones': f"PROVISION VACACIONES {month:02d}/{year}",
        }
        nombre = nombres.get(tipo_prestacion, f"PROVISION {tipo_prestacion.upper()}")

        promedio_data = promedio
        auxilio_data = auxilio_valor

        data = {
            'monto_total': monto,
            'tipo_provision': 'completa',
            'aplica': True,
            'data_kpi': {
                'base_mensual': base_mensual, 'sueldo': sueldo,
                'promedio': promedio_data, 'auxilio': auxilio_data,
                'days_worked': dias_a_pagar, 'divisor': divisor,
                'tipo_prestacion': tipo_prestacion,
                # Alias keys para widget JS (PayslipLineProvision / PayslipLinePrestacion)
                'salary_base': salary_base_data,
                'salary_variable': promedio_data,
                'subsidy': auxilio_data,
                'dias_pagados': dias_a_pagar,
                'dias_periodo': sueldo_info.get('dias_periodo', 360) if sueldo_info else 360,
                'dias_computables': dias_a_pagar,
                'cesantias_causadas': cesantias_causadas,
                'tasa_intereses': 0.12 if tipo_prestacion == 'intereses' else 0.0,
                'fuente_ices': fuente_ices if tipo_prestacion == 'intereses' else '',
            },
            'detail': {
                'sueldo_info': sueldo_info,
                'variable_base': variable_base,
                'auxilio': auxilio,
            },
        }
        return (monto, 1, 100, nombre, '', data)

    # =========================================================================
    # METODOS DE CONSOLIDACION - Compara provision vs obligacion contable
    # =========================================================================

    def _cesantias_cons(self, localdict):
        """
        CONSOLIDACION CESANTIAS - Codigo regla: CESANTIAS_CONS

        Compara saldo de provision (261005) vs obligacion (2510).
        Genera ajuste si hay diferencia.

        Returns:
            tuple: (amount, qty, rate, name, log, data)
        """
        return self._calculate_consolidacion(localdict, 'cesantias')

    def _intcesantias_cons(self, localdict):
        """
        CONSOLIDACION INTERESES CESANTIAS - Codigo regla: INTCESANTIAS_CONS

        Compara saldo de provision (261010) vs obligacion (2515).
        Genera ajuste si hay diferencia.

        Returns:
            tuple: (amount, qty, rate, name, log, data)
        """
        return self._calculate_consolidacion(localdict, 'intereses')

    # Alias para codigo CONS_CES
    def _cons_ces(self, localdict):
        """Alias para CONS_CES -> consolidacion cesantias."""
        return self._calculate_consolidacion(localdict, 'cesantias')

    # Alias para codigo CONS_INT
    def _cons_int(self, localdict):
        """Alias para CONS_INT -> consolidacion intereses."""
        return self._calculate_consolidacion(localdict, 'intereses')

    def _vacaciones_cons(self, localdict):
        """
        CONSOLIDACION VACACIONES - Codigo regla: VACACIONES_CONS

        Compara saldo de provision (261015) vs obligacion (2525).
        Genera ajuste si hay diferencia.

        Returns:
            tuple: (amount, qty, rate, name, log, data)
        """
        return self._calculate_consolidacion(localdict, 'vacaciones')

    # Alias para codigo CONS_VAC
    def _cons_vac(self, localdict):
        """Alias para CONS_VAC -> consolidacion vacaciones."""
        return self._calculate_consolidacion(localdict, 'vacaciones')

    def _calculate_consolidacion(self, localdict, tipo_prestacion):
        """Calcula ajuste de consolidacion: obligacion real vs provision acumulada."""
        slip = localdict['slip']
        contract = localdict['contract']
        employee = localdict.get('employee')
        date_to = slip.date_to
        es_liquidacion = self._is_liquidacion(slip)
        es_consolidacion = bool(slip.struct_id and slip.struct_id.process == 'consolidacion')

        # 1. Obligacion real (liquidacion al corte)
        prestaciones_service = self.env['hr.salary.rule.prestaciones']
        result = prestaciones_service.calculate_prestacion(
            localdict, tipo_prestacion, context='consolidacion', provision_type='simple'
        )
        if not result or len(result) < 6:
            _logger.error(f"[CONSOLIDACION] Error en calculate_prestacion para {tipo_prestacion}")
            return (0, 0, 0, 'Error en calculo', '', {'aplica': False})

        base_diaria, dias, porcentaje, nombre, log, detail = result
        obligacion_real = detail.get('metricas', {}).get('valor_total', 0) if isinstance(detail, dict) else 0

        # 2. Cuentas contables desde reglas salariales
        cuentas_regla = self._get_cuentas_provision_contables(tipo_prestacion)
        cuentas_config = self.CUENTAS_PRESTACIONES.get(tipo_prestacion, {})

        integrar_contabilidad = self.env['ir.config_parameter'].sudo().get_param(
            'lavish_hr_payroll.integrar_consolidacion_liquidacion', False
        )

        # 3. Provision acumulada: contabilidad vs nominas
        saldo_provision = 0
        saldo_obligacion = 0
        provision_acumulada = 0
        provision_acumulada_data = {}
        usa_contabilidad = False

        # Consolidacion: este reporte es para conciliacion nomina vs contabilidad,
        # por lo tanto SIEMPRE se deben traer saldos contables si es posible.
        # Liquidación: también siempre usar contabilidad para cuadrar saldos reales.
        if integrar_contabilidad or es_liquidacion or es_consolidacion:
            # Saldo cuenta provision (pasivo: credito - debito)
            saldo_provision = self._get_saldo_cuenta_provision(
                cuentas_regla, cuentas_config, date_to, employee)

            # Saldo cuenta consolidacion/obligacion
            saldo_obligacion = self._get_saldo_cuenta_obligacion(
                cuentas_regla, cuentas_config, date_to, employee)

            # Determinar que cuenta usar para el ajuste
            cuenta_prov_id = cuentas_regla.get('cuenta_balance_id')
            cuenta_cons_id = cuentas_regla.get('cuenta_debito_id')
            misma_cuenta = (cuenta_cons_id == cuenta_prov_id) or not cuenta_cons_id

            cuenta_existe = bool(cuenta_prov_id or cuenta_cons_id)
            if saldo_provision or (es_liquidacion and cuenta_existe):
                provision_acumulada = saldo_provision
                usa_contabilidad = True
            elif misma_cuenta and (saldo_obligacion or (es_liquidacion and cuenta_existe)):
                provision_acumulada = saldo_obligacion
                usa_contabilidad = True

        if not usa_contabilidad:
            # Fallback: provisiones desde lineas de nomina
            date_period_from, date_period_to = self._get_period_dates(tipo_prestacion, date_to)
            provision_acumulada_data = self._get_provision_acumulada(
                contract_id=contract.id,
                tipo_prestacion=tipo_prestacion,
                date_period_from=date_period_from,
                date_period_to=date_period_to,
                exclude_slip_id=slip.id,
            )
            provision_acumulada = provision_acumulada_data.get('total', 0)

        # 4. Ajuste = obligacion - provision acumulada
        ajuste = obligacion_real - provision_acumulada

        # Nombre
        year = date_to.year if date_to else date.today().year
        month = date_to.month if date_to else date.today().month
        nombres = {
            'cesantias': f"CONSOLIDACION CESANTIAS {month:02d}/{year}",
            'intereses': f"CONSOLIDACION INT. CESANTIAS {month:02d}/{year}",
            'vacaciones': f"CONSOLIDACION VACACIONES {month:02d}/{year}",
        }
        nombre_cons = nombres.get(tipo_prestacion, f"CONSOLIDACION {tipo_prestacion.upper()}")

        detail_metricas = detail.get('metricas', {}) if isinstance(detail, dict) else {}
        cuenta_prov_code = cuentas_regla.get('cuenta_balance_code') or cuentas_config.get('provision', '')
        cuenta_cons_code = cuentas_regla.get('cuenta_debito_code') or cuentas_config.get('obligacion', '')

        data = {
            'monto_total': ajuste,
            'ajuste': ajuste,
            'obligacion_real': obligacion_real,
            'saldo_provision': saldo_provision,
            'saldo_obligacion': saldo_obligacion,
            'cuenta_provision': cuenta_prov_code,
            'cuenta_obligacion': cuenta_cons_code,
            'fecha_corte': str(date_to) if date_to else None,
            'tipo_prestacion': tipo_prestacion,
            'aplica': True,
            'usa_contabilidad': usa_contabilidad,
            'detail': detail,
            'metricas': {
                'base_mensual': detail_metricas.get('base_mensual', 0),
                'base_diaria': detail_metricas.get('base_diaria', base_diaria),
                'dias_trabajados': detail_metricas.get('dias_trabajados', dias),
                'valor_total': obligacion_real,
            },
            'saldo_contable': {
                'cuenta_provision': cuenta_prov_code,
                'cuenta_obligacion': cuenta_cons_code,
                'provision_acumulada': provision_acumulada,
                'obligacion_real': obligacion_real,
                'ajuste': ajuste,
                'saldo_provision_contable': saldo_provision,
                'saldo_obligacion_contable': saldo_obligacion,
                'diferencia_pct': round((ajuste / obligacion_real * 100), 2) if obligacion_real else 0,
                'usa_contabilidad': usa_contabilidad,
            },
            'formula_explicacion': {
                'formula_aplicada': "Ajuste = Obligacion Real - Provision Acumulada",
                'desarrollo': f"Ajuste = ${obligacion_real:,.0f} - ${provision_acumulada:,.0f} = ${ajuste:,.0f}",
                'fuente': 'contabilidad' if usa_contabilidad else 'nominas',
            },
            'provisiones_detalle': provision_acumulada_data.get('detalle', []),
        }

        return (ajuste, 1, 100, nombre_cons, '', data)

    def _get_saldo_cuenta_provision(self, cuentas_regla, cuentas_config, date_to, employee):
        """Saldo de cuenta de provision (pasivo). Busca por regla, fallback a config."""
        if cuentas_regla.get('cuenta_balance_id'):
            cuenta = self.env['account.account'].browse(cuentas_regla['cuenta_balance_id']).exists()
            if cuenta:
                saldo = self._get_saldo_cuenta_by_id(cuenta, date_to, employee)
                if saldo:
                    return saldo
        return self._get_saldo_cuenta(
            cuentas_config.get('param_provision'), cuentas_config.get('provision'),
            date_to, employee)

    def _get_saldo_cuenta_obligacion(self, cuentas_regla, cuentas_config, date_to, employee):
        """Saldo de cuenta de consolidacion/obligacion. Busca por regla, fallback a config."""
        cuenta_cons_id = cuentas_regla.get('cuenta_debito_id')
        cuenta_prov_id = cuentas_regla.get('cuenta_balance_id')
        if cuenta_cons_id and cuenta_cons_id != cuenta_prov_id:
            cuenta = self.env['account.account'].browse(cuenta_cons_id).exists()
            if cuenta:
                saldo = self._get_saldo_cuenta_by_id(cuenta, date_to, employee)
                if saldo:
                    return saldo
        return self._get_saldo_cuenta(
            cuentas_config.get('param_obligacion'), cuentas_config.get('obligacion'),
            date_to, employee)

    def _get_saldo_cuenta(self, param_key, prefijo_default, date_to, employee=None):
        """Obtiene saldo de una cuenta contable. Param -> ID -> Prefijo."""
        get_param = self.env['ir.config_parameter'].sudo().get_param

        cuenta_id = get_param(param_key, False) if param_key else False

        if cuenta_id:
            try:
                cuenta_id = int(cuenta_id)
                cuenta = self.env['account.account'].browse(cuenta_id).exists()
                if cuenta:
                    return self._get_saldo_cuenta_by_id(cuenta, date_to, employee)
            except (ValueError, TypeError):
                _logger.warning(f"[SALDO_CTA] cuenta_id={cuenta_id} no es valido")

        if prefijo_default:
            return self._get_saldo_cuenta_by_prefijo(prefijo_default, date_to, employee)

        return 0

    def _get_saldo_cuenta_by_id(self, cuenta, date_to, employee=None):
        """Obtiene saldo de una cuenta especifica por ID."""
        if not cuenta:
            return 0

        domain = [
            ('account_id', '=', cuenta.id),
            ('date', '<=', date_to),
            ('parent_state', '=', 'posted'),
        ]

        partner = None
        if employee:
            partner = employee.work_contact_id
            if partner:
                domain.append(('partner_id', '=', partner.id))
            else:
                _logger.warning(f"[BY_ID] Employee {employee.id} sin work_contact_id")

        try:
            moves = self.env['account.move.line'].search_read(
                domain,
                fields=['debit', 'credit'],
                limit=10000,
            )
            total_debit = sum(m.get('debit', 0) for m in moves)
            total_credit = sum(m.get('credit', 0) for m in moves)
            saldo = total_credit - total_debit
            return saldo

        except Exception as e:
            _logger.error(f"[BY_ID] Error cuenta {cuenta.code}: {e}")
            return 0

    def _get_saldo_cuenta_by_prefijo(self, prefijo, date_to, employee=None):
        """Obtiene saldo de cuentas que coincidan con un prefijo."""
        if not prefijo:
            return 0

        try:
            cuentas = self.env['account.account'].search([
                ('code', '=like', f'{prefijo}%'),
                ('company_ids', 'in', [self.env.company.id]),
            ])

            if not cuentas:
                return 0

            domain = [
                ('account_id', 'in', cuentas.ids),
                ('date', '<=', date_to),
                ('parent_state', '=', 'posted'),
            ]

            if employee:
                partner = employee.work_contact_id
                if partner:
                    domain.append(('partner_id', '=', partner.id))

            moves = self.env['account.move.line'].search_read(
                domain,
                fields=['debit', 'credit'],
                limit=10000,
            )
            total_debit = sum(m.get('debit', 0) for m in moves)
            total_credit = sum(m.get('credit', 0) for m in moves)
            saldo = total_credit - total_debit
            return saldo

        except Exception as e:
            _logger.error(f"[BY_PREFIJO] Error prefijo {prefijo}: {e}")
            return 0

    # =========================================================================
    # METODO PRINCIPAL DE PROVISION (Servicio)
    # =========================================================================

    def calculate_provision(self, localdict, tipo_prestacion, provision_type='auto'):
        """
        Calcula provision mensual de una prestacion.

        Args:
            localdict: Diccionario con slip, contract, employee, annual_parameters
            tipo_prestacion: 'prima', 'cesantias', 'intereses', 'vacaciones'
            provision_type: 'simple' | 'promediado' | 'porcentaje_fijo' | 'auto'

        Returns:
            tuple: (base_diaria, dias, porcentaje, nombre, log, detail)
        """
        # Determinar tipo de provision si es 'auto'
        if provision_type == 'auto':
            provision_type = self._get_provision_type(localdict, tipo_prestacion)

        # Usar logica unificada con context='provision'
        prestaciones_service = self.env['hr.salary.rule.prestaciones']
        result = prestaciones_service.calculate_prestacion(
            localdict,
            tipo_prestacion,
            context='provision',
            provision_type=provision_type
        )

        # Agregar info de consolidacion si aplica
        slip = localdict['slip']
        if self._is_period_close(slip, tipo_prestacion):
            if len(result) > 5 and isinstance(result[5], dict):
                result[5]['consolidacion'] = self._get_consolidation_info(
                    localdict, tipo_prestacion
                )

        return result

    def _get_provision_type(self, localdict, tipo_prestacion):
        """
        Determina el tipo de provision segun configuracion.

        Returns:
            str: 'simple' | 'promediado' | 'porcentaje_fijo'
        """
        get_param = self.env['ir.config_parameter'].sudo().get_param

        # Mapeo de parametros por tipo
        param_map = {
            'prima': 'lavish_hr_payroll.usar_porcentaje_fijo_prima',
            'cesantias': 'lavish_hr_payroll.usar_porcentaje_fijo_cesantias',
            'intereses': 'lavish_hr_payroll.usar_porcentaje_fijo_intereses',
            'vacaciones': 'lavish_hr_payroll.usar_porcentaje_fijo_vacaciones',
        }

        param_key = param_map.get(tipo_prestacion, '')
        usar_porcentaje = get_param(param_key, 'False').lower() in ('true', '1', 'yes')

        return 'porcentaje_fijo' if usar_porcentaje else 'simple'

    # =========================================================================
    # METODOS ESPECIFICOS POR TIPO (Servicio)
    # =========================================================================

    def provision_prima(self, localdict, provision_type='auto'):
        """
        Calcula provision mensual de prima.

        Porcentaje estandar: 8.33% (1/12 del salario)
        Consolidacion: Junio y Diciembre
        """
        return self.calculate_provision(localdict, 'prima', provision_type)

    def provision_cesantias(self, localdict, provision_type='auto'):
        """
        Calcula provision mensual de cesantias.

        Porcentaje estandar: 8.33% (1/12 del salario)
        Consolidacion: Diciembre
        """
        return self.calculate_provision(localdict, 'cesantias', provision_type)

    def provision_intereses(self, localdict, provision_type='auto'):
        """
        Calcula provision mensual de intereses sobre cesantias.

        Porcentaje estandar: 1% mensual (12% anual / 12)
        Consolidacion: Diciembre
        """
        return self.calculate_provision(localdict, 'intereses', provision_type)

    def provision_vacaciones(self, localdict, provision_type='auto'):
        """
        Calcula provision mensual de vacaciones.

        Porcentaje estandar: 4.17% (15 dias / 360)
        Consolidacion: Continua (no tiene cierre especifico)
        """
        return self.calculate_provision(localdict, 'vacaciones', provision_type)

    # =========================================================================
    # CONSOLIDACION - Cierre de periodo
    # =========================================================================

    def _is_period_close(self, slip, tipo_prestacion):
        """
        Determina si es cierre de periodo para consolidacion.

        Returns:
            bool: True si es mes de consolidacion
        """
        month = slip.date_to.month

        if tipo_prestacion == 'prima':
            return month in (6, 12)  # Junio y Diciembre
        elif tipo_prestacion in ('cesantias', 'intereses'):
            return month == 12  # Diciembre
        elif tipo_prestacion == 'vacaciones':
            return month == 12  # Diciembre para cierre anual

        return False

    def _get_consolidation_info(self, localdict, tipo_prestacion):
        """
        Obtiene informacion de consolidacion.

        Incluye:
        - Provision acumulada desde nominas
        - Saldo contable (si consolidacion activa)

        Returns:
            dict: Info de consolidacion
        """
        contract = localdict['contract']
        slip = localdict['slip']
        employee = localdict.get('employee')

        # Fechas del periodo
        date_period_from, date_period_to = self._get_period_dates(tipo_prestacion, slip.date_to)

        # Obtener provisiones acumuladas del periodo (desde nominas)
        provision_acumulada = self._get_provision_acumulada(
            contract_id=contract.id,
            tipo_prestacion=tipo_prestacion,
            date_period_from=date_period_from,
            date_period_to=date_period_to,
            exclude_slip_id=slip.id,
        )

        # Obtener saldo contable (si consolidacion esta activa)
        cuentas = self.CUENTAS_PRESTACIONES.get(tipo_prestacion, {})
        saldo_contable = self._get_saldo_cuenta(
            cuentas.get('param_provision'),
            cuentas.get('provision'),
            date_period_to,
            employee
        )

        return {
            'es_cierre': True,
            'provision_acumulada': provision_acumulada['total'],
            'provision_detalle': provision_acumulada,
            'saldo_contable': saldo_contable,
            'tipo_prestacion': tipo_prestacion,
            'periodo_cierre': self._get_periodo_cierre_label(tipo_prestacion, slip),
            'date_period_from': date_period_from.isoformat(),
            'date_period_to': date_period_to.isoformat(),
        }

    def _get_period_dates(self, tipo_prestacion, date_to):
        """
        Obtiene fechas del periodo segun tipo de prestacion.

        Args:
            tipo_prestacion: Tipo de prestacion
            date_to: Fecha fin del periodo

        Returns:
            tuple: (date_from, date_to)
        """
        if tipo_prestacion == 'prima':
            if date_to.month <= 6:
                date_from = date(date_to.year, 1, 1)
            else:
                date_from = date(date_to.year, 7, 1)
        else:
            # Cesantias, intereses, vacaciones: ano completo
            date_from = date(date_to.year, 1, 1)

        return date_from, date_to

    def _get_provision_acumulada(self, contract_id, tipo_prestacion, date_period_from, date_period_to, exclude_slip_id=None):
        """Obtiene suma de provisiones del periodo usando search_read."""
        code_map = {
            'prima': ['PROV_PRIMA', 'PROVISION_PRIMA', 'PRV_PRIM', 'PRV_PRIMA'],
            'cesantias': ['PROV_CESANTIAS', 'PROVISION_CESANTIAS', 'PRV_CES', 'PRV_CESANTIAS'],
            'intereses': ['PROV_INT_CESANTIAS', 'PROVISION_INT_CESANTIAS', 'PROV_INTERESES', 'PRV_ICES', 'PRV_INT'],
            'vacaciones': ['PROV_VACACIONES', 'PROVISION_VACACIONES', 'PRV_VAC', 'PRV_VACACIONES'],
        }
        codes = code_map.get(tipo_prestacion, [])

        if not codes:
            _logger.warning(f"[PROV_ACUM] Sin codes para tipo={tipo_prestacion}")
            return {'total': 0, 'count': 0, 'lineas': []}

        try:
            domain = [
                ('slip_id.contract_id', '=', contract_id),
                ('slip_id.date_from', '>=', date_period_from),
                ('slip_id.date_to', '<=', date_period_to),
                ('slip_id.state', 'in', ['done', 'paid']),
                ('code', 'in', codes),
            ]

            if exclude_slip_id:
                domain.append(('slip_id', '!=', exclude_slip_id))

            lines_data = self.env['hr.payslip.line'].search_read(
                domain,
                fields=['id', 'code', 'total', 'slip_id', 'name'],
                limit=1000,
            )

            total = sum(line.get('total', 0) for line in lines_data)

            return {
                'total': total,
                'count': len(lines_data),
                'lineas': lines_data,
                'codes_buscados': codes,
            }

        except Exception as e:
            _logger.error(f"[PROV_ACUM] Error: {e}")
            return {'total': 0, 'count': 0, 'lineas': [], 'error': str(e)}

    def _get_periodo_cierre_label(self, tipo_prestacion, slip):
        """
        Genera etiqueta del periodo de cierre.

        Returns:
            str: Etiqueta descriptiva
        """
        year = slip.date_to.year
        month = slip.date_to.month

        if tipo_prestacion == 'prima':
            semestre = 1 if month <= 6 else 2
            return f"Prima {semestre} Semestre {year}"
        elif tipo_prestacion in ('cesantias', 'intereses'):
            return f"Cesantias/Intereses Ano {year}"
        elif tipo_prestacion == 'vacaciones':
            return f"Vacaciones Ano {year}"

        return f"{tipo_prestacion.title()} {year}"
