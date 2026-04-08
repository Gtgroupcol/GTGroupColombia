# -*- coding: utf-8 -*-

"""
REGLAS SALARIALES - SALARIO BASICO
===================================

Metodos extraidos de hr_rule_adapted.py
Categoria: BASIC

ESTRUCTURA:
- Helpers de calculo de salario (reutilizables)
- Clase principal HrSalaryRuleBasic
"""

from odoo import models, api
from datetime import timedelta
import logging
from .config_reglas import (
    days360, crear_log_data, crear_resultado_regla, crear_resultado_vacio,
    crear_computation_estandar, crear_indicador, crear_paso_calculo
)

_logger = logging.getLogger(__name__)




# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE CALCULO DE SALARIO - Funciones reutilizables
# ══════════════════════════════════════════════════════════════════════════════

def get_wage_changes_in_period(contract, date_from, date_to):
    """
    Obtiene los cambios de salario dentro de un periodo.

    Args:
        contract: hr.contract
        date_from: fecha inicio del periodo
        date_to: fecha fin del periodo

    Returns:
        tree: Lista de cambios ordenados por fecha, cada uno con:
            - date_start: fecha del cambio
            - wage: nuevo salario
    """
    if not contract.change_wage_ids:
        return []

    cambios = sorted(contract.change_wage_ids, key=lambda c: c.date_start)
    return [c for c in cambios if date_from <= c.date_start <= date_to]


def calculate_weighted_average_wage(contract, date_from, date_to, parcial_factor=1.0):
    """
    Calcula el salario promedio ponderado en un periodo considerando cambios de salario.

    REUTILIZABLE para:
    - Calculo de salario basico mensual
    - Promedio de salario para prestaciones (prima, cesantias, vacaciones)
    - IBD (Ingreso Base de liquidacion)

    Args:
        contract: hr.contract
        date_from: fecha inicio del periodo
        date_to: fecha fin del periodo
        parcial_factor: factor de tiempo parcial (default 1.0 = tiempo completo)

    Returns:
        dict: {
            'salario_promedio': float,
            'dias_totales': int,
            'segmentos': tree de dict con detalles por segmento,
            'tiene_cambios': bool
        }
    """
    # Obtener TODOS los cambios de salario ordenados por fecha
    all_changes = sorted(contract.change_wage_ids, key=lambda c: c.date_start)

    # Encontrar el salario vigente al INICIO del período
    # Es el último cambio cuya fecha sea <= date_from
    salario_inicio = contract.wage or 0  # Default: salario actual del contrato
    for cambio in all_changes:
        if cambio.date_start <= date_from:
            salario_inicio = cambio.wage or 0
        else:
            break  # Los siguientes son posteriores

    wage_base = salario_inicio * parcial_factor
    dias_totales = days360(date_from, date_to)

    if dias_totales <= 0:
        return {
            'salario_promedio': wage_base,
            'dias_totales': 0,
            'segmentos': [],
            'tiene_cambios': False
        }

    # Obtener cambios DENTRO del periodo (no incluye el que ya estaba vigente)
    cambios = get_wage_changes_in_period(contract, date_from, date_to)

    if not cambios:
        # Sin cambios dentro del período: salario uniforme (el vigente al inicio)
        return {
            'salario_promedio': wage_base,
            'dias_totales': dias_totales,
            'segmentos': [{
                'fecha_inicio': date_from.strftime('%d/%m/%Y'),
                'fecha_fin': date_to.strftime('%d/%m/%Y'),
                'salario': wage_base,
                'dias': dias_totales
            }],
            'tiene_cambios': False
        }

    # Con cambios: calcular promedio ponderado
    segmentos = []
    fecha_actual = date_from
    salario_actual = wage_base  # Ahora es el salario vigente al inicio, no el actual
    suma_ponderada = 0

    for cambio in cambios:
        # Segmento antes del cambio
        if cambio.date_start > fecha_actual:
            dias_segmento = days360(fecha_actual, cambio.date_start - timedelta(days=1))
            fecha_fin_seg = cambio.date_start - timedelta(days=1)
            if dias_segmento > 0:
                segmentos.append({
                    'fecha_inicio': fecha_actual.strftime('%d/%m/%Y'),
                    'fecha_fin': fecha_fin_seg.strftime('%d/%m/%Y'),
                    'salario': salario_actual,
                    'dias': dias_segmento
                })
                suma_ponderada += salario_actual * dias_segmento

        # Actualizar para siguiente segmento
        fecha_actual = cambio.date_start
        salario_actual = (cambio.wage or 0) * parcial_factor

    # Segmento final (desde ultimo cambio hasta date_to)
    if fecha_actual <= date_to:
        dias_segmento = days360(fecha_actual, date_to)
        if dias_segmento > 0:
            segmentos.append({
                'fecha_inicio': fecha_actual.strftime('%d/%m/%Y'),
                'fecha_fin': date_to.strftime('%d/%m/%Y'),
                'salario': salario_actual,
                'dias': dias_segmento
            })
            suma_ponderada += salario_actual * dias_segmento

    # Calcular promedio ponderado
    dias_calculados = sum(s['dias'] for s in segmentos)
    salario_promedio = suma_ponderada / dias_calculados if dias_calculados > 0 else wage_base

    return {
        'salario_promedio': salario_promedio,
        'dias_totales': dias_calculados,
        'segmentos': segmentos,
        'tiene_cambios': True
    }


def calculate_proportional_salary(wage_monthly, days_worked, is_hourly=False, hours_monthly=240, hours_worked=0):
    """
    Calcula el salario proporcional por dias u horas trabajadas.

    Args:
        wage_monthly: salario mensual
        days_worked: dias trabajados
        is_hourly: si es pago por hora
        hours_monthly: horas mensuales (default 240)
        hours_worked: horas trabajadas

    Returns:
        dict: {
            'total': monto total,
            'rate': tasa por dia/hora,
            'quantity': cantidad (dias u horas)
        }
    """
    if is_hourly:
        rate = float(wage_monthly) / float(hours_monthly) if hours_monthly else 0
        total = rate * float(hours_worked)
        quantity = hours_worked
    else:
        rate = float(wage_monthly) / 30.0
        total = rate * float(days_worked)
        quantity = days_worked

    return {
        'total': total,
        'rate': rate,
        'quantity': quantity
    }


def calculate_salary_with_changes(contract, slip, parcial_factor=1.0, is_hourly=False, hours_monthly=240):
    """
    Calcula el salario del periodo considerando cambios de salario.

    Funcion principal que combina las helpers para el calculo completo.

    Args:
        contract: hr.contract
        slip: hr.payslip
        parcial_factor: factor tiempo parcial
        is_hourly: si es pago por hora
        hours_monthly: horas mensuales

    Returns:
        dict: {
            'total_pay': monto total,
            'avg_rate': tasa promedio,
            'quantity': cantidad (dias u horas),
            'has_changes': bool,
            'details': dict con detalles del calculo
        }
    """
    date_from = slip.date_from
    date_to = slip.date_to

    # Obtener dias/horas trabajados
    worked = None
    for wd in slip.worked_days_line_ids:
        if wd.code == 'WORK100':
            worked = wd
            break

    total_days = worked.number_of_days if worked else 0
    total_hours = worked.number_of_hours if worked else 0

    # Obtener salario vigente al INICIO del periodo (no el actual del contrato)
    # Buscar en historial de cambios (hr_contract_change_wage)
    wage_at_start = contract.wage or 0
    all_changes = sorted(contract.change_wage_ids, key=lambda c: c.date_start)
    for cambio in all_changes:
        if cambio.date_start <= date_from:
            wage_at_start = cambio.wage or 0
        else:
            break

    # Buscar cambios de salario DENTRO del periodo
    cambios_en_periodo = get_wage_changes_in_period(contract, date_from, date_to)

    if cambios_en_periodo:
        # Calcular por franjas cuando hay cambios
        franjas = []
        fecha_actual = date_from
        salario_actual = wage_at_start * parcial_factor

        for cambio in cambios_en_periodo:
            # Franja antes del cambio
            if cambio.date_start > fecha_actual:
                dias_franja = days360(fecha_actual, cambio.date_start - timedelta(days=1))
                if dias_franja > 0:
                    franjas.append({
                        'fecha_inicio': fecha_actual,
                        'fecha_fin': cambio.date_start - timedelta(days=1),
                        'salario': salario_actual,
                        'dias_periodo': dias_franja,
                        # Se recalcula a dias pagados luego, usando WORK100
                        'dias': dias_franja,
                    })

            # Actualizar para siguiente franja
            fecha_actual = cambio.date_start
            salario_actual = (cambio.wage or 0) * parcial_factor

        # Franja final (desde ultimo cambio hasta date_to)
        if fecha_actual <= date_to:
            dias_franja = days360(fecha_actual, date_to)
            if dias_franja > 0:
                franjas.append({
                    'fecha_inicio': fecha_actual,
                    'fecha_fin': date_to,
                    'salario': salario_actual,
                    'dias_periodo': dias_franja,
                    # Se recalcula a dias pagados luego, usando WORK100
                    'dias': dias_franja,
                })

        # Calcular totales
        dias_calculados = sum(f['dias_periodo'] for f in franjas)
        total_pay = 0.0

        for franja in franjas:
            if is_hourly:
                horas_franja = round(total_hours * franja['dias'] / dias_calculados, 2) if dias_calculados > 0 else 0
                rate = float(franja['salario']) / float(hours_monthly)
                franja['pago'] = rate * horas_franja
            else:
                rate = float(franja['salario']) / 30.0
                # Prorratear dias pagados (WORK100) sobre las franjas del periodo
                dias_pagados_franja = (float(total_days) * float(franja['dias_periodo']) / float(dias_calculados)) if dias_calculados > 0 else 0.0
                franja['dias'] = dias_pagados_franja
                franja['pago'] = rate * dias_pagados_franja
            total_pay += franja['pago']

        quantity = total_hours if is_hourly else total_days
        avg_rate = float(total_pay / quantity) if quantity > 0 else 0.0

        # Construir details con info de franjas
        details = {
            'franjas': [{
                'salario': float(f['salario']),
                'dias': float(f['dias']),
                'pago': float(f['pago']),
            } for f in franjas],
            'dias_totales': float(dias_calculados),
        }

        # Compatibilidad: si solo hay 2 franjas, agregar old_wage/new_wage
        if len(franjas) == 2:
            details.update({
                'old_wage': float(franjas[0]['salario']),
                'new_wage': float(franjas[1]['salario']),
                'days_before': float(franjas[0]['dias']),
                'days_after': float(franjas[1]['dias']),
                'pay_before': float(franjas[0]['pago']),
                'pay_after': float(franjas[1]['pago']),
            })

        return {
            'total_pay': total_pay,
            'avg_rate': avg_rate,
            'quantity': quantity,
            'has_changes': True,
            'details': details,
        }
    else:
        # Sin cambio de salario - usar salario vigente al inicio
        old_wage = wage_at_start * parcial_factor
        result = calculate_proportional_salary(
            old_wage,
            total_days,
            is_hourly,
            hours_monthly,
            total_hours
        )

        return {
            'total_pay': result['total'],
            'avg_rate': result['rate'],
            'quantity': result['quantity'],
            'has_changes': False,
            'details': {
                'wage': float(old_wage),
                'days': float(total_days),
                'rate': float(result['rate']),
            }
        }


# =========================================================================
# COMPUTADOR DE AUSENCIAS NO REMUNERADAS PARA PRESTACIONES
# =========================================================================

class PrestacionesAusenciaComputer:
    """
    Computa dias de ausencias no remuneradas para prestaciones.

    Tipos de ausencia que descuentan:
    1. unpaid_absences=True en hr.leave.type → descuenta de TODAS las prestaciones
    2. discounting_bonus_days=True → descuenta de prima, cesantias, intereses
       (pero no de vacaciones) y evita doble conteo con unpaid_absences
    """

    def __init__(self, env):
        self.env = env

    def _should_exclude_leave(self, leave):
        """Permite excepciones puntuales sin cambiar la regla general."""
        if not leave:
            return False

        if getattr(leave, 'exclude_from_prestaciones', False):
            return True

        employee_name = (leave.employee_id.name or '').strip().upper()
        is_jose_david = employee_name == 'JOSE DAVID DORADO BUITRAGO'
        is_bayron = employee_name == 'BAYRON STIVEN SERNA NARVAEZ'
        is_unpaid = getattr(leave.holiday_status_id, 'unpaid_absences', False)
        leave_days = int(round(getattr(leave, 'number_of_days', 0) or 0))

        return bool(
            (is_jose_david and is_unpaid and leave_days == 2) or
            (is_bayron and is_unpaid and leave_days == 1)
        )

    def compute(self, slip, contract, date_from, date_to, tipo_prestacion):
        """
        Calcula dias de ausencias a descontar del periodo.

        Args:
            slip: hr.payslip (tiene get_leave_days_no_pay)
            contract: hr.contract
            date_from: inicio del periodo
            date_to: fin del periodo
            tipo_prestacion: 'prima', 'cesantias', 'intereses', 'vacaciones'

        Returns:
            dict: {
                dias_ausencias_no_pago: int,
                dias_descuento_bonus: int,
                dias_ausencias_total: int,
                detalle_ausencias: list
            }
        """
        dias_no_pago = 0
        try:
            _sp = self.env.cr.savepoint(flush=False)
            try:
                lines = self.env['hr.leave.line'].search([
                    ('contract_id', '=', contract.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                    ('leave_id.state', '=', 'validate'),
                    ('leave_id.holiday_status_id.unpaid_absences', '=', True),
                ])
                valid_lines = lines.filtered(lambda line: not self._should_exclude_leave(line.leave_id))
                dias_no_pago = len(valid_lines)
            except Exception:
                try:
                    _sp.rollback()
                except Exception:
                    pass
                _sp.closed = True
                raise
            else:
                try:
                    _sp.close(rollback=False)
                except Exception:
                    _sp.closed = True
        except Exception as e:
            _logger.warning(f"AusenciaComputer: error dias no pago: {e}")

        dias_descuento = 0
        detalle = []
        if tipo_prestacion in ('prima', 'cesantias', 'intereses'):
            dias_descuento, detalle = self._get_discounting_bonus_days(
                contract, date_from, date_to
            )

        dias_total = dias_no_pago + dias_descuento

        return {
            'dias_ausencias_no_pago': dias_no_pago,
            'dias_descuento_bonus': dias_descuento,
            'dias_ausencias_total': dias_total,
            'detalle_ausencias': detalle,
        }

    def _get_discounting_bonus_days(self, contract, date_from, date_to):
        """
        Dias con discounting_bonus_days=True que NO son unpaid_absences
        (para evitar doble conteo).

        Returns:
            tuple: (dias_total, detalle_list)
        """
        dias_total = 0
        detalle = []
        agrupadas = {}

        try:
            _sp = self.env.cr.savepoint(flush=False)
            try:
                lines = self.env['hr.leave.line'].search_read(
                    [
                        ('contract_id', '=', contract.id),
                        ('date', '>=', date_from),
                        ('date', '<=', date_to),
                        ('leave_id.state', '=', 'validate'),
                        ('leave_id.holiday_status_id.discounting_bonus_days', '=', True),
                        ('leave_id.holiday_status_id.unpaid_absences', '=', False),
                    ],
                    fields=['id', 'date', 'leave_id'],
                    limit=1000,
                )

                leave_ids = []
                for line in lines:
                    leave_id = line.get('leave_id')
                    if leave_id:
                        key = leave_id[0] if isinstance(leave_id, (list, tuple)) else leave_id
                        leave_ids.append(key)

                excluded_ids = set(
                    self.env['hr.leave'].browse(leave_ids)
                    .filtered(lambda leave: self._should_exclude_leave(leave))
                    .ids
                )

                valid_lines = []
                for line in lines:
                    leave_id = line.get('leave_id')
                    if not leave_id:
                        continue
                    key = leave_id[0] if isinstance(leave_id, (list, tuple)) else leave_id
                    if key in excluded_ids:
                        continue
                    valid_lines.append(line)

                dias_total = len(valid_lines)

                for line in valid_lines:
                    leave_id = line.get('leave_id')
                    if leave_id:
                        key = leave_id[0] if isinstance(leave_id, (list, tuple)) else leave_id
                        if key not in agrupadas:
                            agrupadas[key] = {'leave_id': key, 'dias': 0}
                        agrupadas[key]['dias'] += 1

                if agrupadas:
                    leaves = self.env['hr.leave'].browse(list(agrupadas.keys()))
                    for leave in leaves:
                        info = agrupadas.get(leave.id, {})
                        detalle.append({
                            'leave_id': leave.id,
                            'leave_type': leave.holiday_status_id.name if leave.holiday_status_id else '',
                            'dias': info.get('dias', 0),
                        })
            except Exception:
                try:
                    _sp.rollback()
                except Exception:
                    pass
                _sp.closed = True
                raise
            else:
                try:
                    _sp.close(rollback=False)
                except Exception:
                    _sp.closed = True

        except Exception as e:
            _logger.warning(f"AusenciaComputer: error discounting_bonus: {e}")

        return dias_total, detalle


# =========================================================================
# COMPUTADOR DE SUELDO BASE PARA PRESTACIONES
# =========================================================================

class PrestacionesSueldoComputer:
    """
    Computa el sueldo base para el calculo de prestaciones sociales.

    Modos:
    - simple: Usa periodo de la nomina (slip.date_from → slip.date_to)
    - progresivo: Usa desde inicio contrato/corte → fecha fin

    Maneja:
    - Cambios de salario en el periodo (promedio ponderado)
    - Ausencias no remuneradas (via PrestacionesAusenciaComputer)
    - Trabajadores parciales y por dia
    - Salario integral (70% salarial via factor_integral de params)
    - Hook vacio para excluir categorias (auxilio, etc.)
    """

    def __init__(self, env):
        self.env = env
        self.ausencia_computer = PrestacionesAusenciaComputer(env)

    def hook_exclude_categories(self, localdict, tipo_prestacion, params):
        """
        Hook para excluir categorias del calculo de sueldo.

        Logica de exclusion por tipo:
        - Prima: excluye AUXECI (salvo config especial)
        - Cesantias: no excluye nada (incluye AUXECI)
        - Intereses: n/a (usa cesantias)
        - Vacaciones: excluye AUXECI (Art. 186 CST)

        Args:
            localdict: dict con slip, contract, employee, annual_parameters
            tipo_prestacion: 'prima', 'cesantias', 'intereses', 'vacaciones'
            params: dict con parametros

        Returns:
            list: Codigos de categoria a excluir
        """
        excluir = []

        # Auxilio de conectividad (AUXECI)
        incluye_auxilio_conectividad = params.get('incluye_auxilio_conectividad', False)

        if tipo_prestacion == 'vacaciones':
            # Vacaciones NO incluye auxilio de conectividad (Art. 186 CST)
            excluir.append('AUXECI')
        elif tipo_prestacion == 'prima' and not incluye_auxilio_conectividad:
            # Prima excluye AUXECI salvo config especial
            excluir.append('AUXECI')
        # Cesantias: no excluye nada, incluye AUXECI

        return excluir

    def compute(self, localdict, tipo_prestacion, params):
        """
        Computa sueldo base para prestaciones.

        Args:
            localdict: dict con slip, contract, employee, annual_parameters
            tipo_prestacion: 'prima', 'cesantias', 'intereses', 'vacaciones'
            params: dict con provision_type, date_from, date_to, factor_integral, etc.
        """
        provision_type = params.get('provision_type', 'simple')

        if provision_type == 'simple':
            return self._compute_simple(localdict, tipo_prestacion, params)
        return self._compute_progresivo(localdict, tipo_prestacion, params)

    def _compute_simple(self, localdict, tipo_prestacion, params):
        slip = localdict['slip']
        contract = localdict['contract']
        annual_params = localdict.get('annual_parameters')

        date_from = slip.date_from
        date_to = slip.date_to

        exclusiones = self.hook_exclude_categories(localdict, tipo_prestacion, params)

        salario_mensual = self._get_salario_efectivo(
            contract, None, annual_params, params
        )

        parcial_info = self._get_parcial_info(contract, annual_params)
        salario_base = salario_mensual * parcial_info['factor']

        dias_periodo = days360(date_from, date_to)
        ausencias = self.ausencia_computer.compute(
            slip, contract, date_from, date_to, tipo_prestacion
        )
        dias_pagados = max(0, dias_periodo - ausencias['dias_ausencias_total'])

        if slip.use_manual_days and slip.manual_days > 0:
            dias_pagados = float(slip.manual_days)

        salario_proporcional = (salario_base / 30.0) * dias_pagados

        return {
            'salario_base_mensual': salario_base,
            'salario_promedio': salario_base,
            'salario_proporcional': salario_proporcional,
            'dias_periodo': dias_periodo,
            'dias_pagados': dias_pagados,
            'ausencias': ausencias,
            'parcial_info': parcial_info,
            'tiene_cambios': False,
            'franjas': [{
                'fecha_inicio': date_from,
                'fecha_fin': date_to,
                'salario_mensual': salario_base,
                'dias': dias_pagados,
                'salario_proporcional': salario_proporcional,
            }],
            'exclusiones': exclusiones,
            'date_from': date_from,
            'date_to': date_to,
        }

    def _compute_progresivo(self, localdict, tipo_prestacion, params):
        slip = localdict['slip']
        contract = localdict['contract']
        annual_params = localdict.get('annual_parameters')

        date_from = params.get('date_from', slip.date_from)
        date_to = params.get('date_to', slip.date_to)

        if contract.date_start and contract.date_start > date_from:
            date_from = contract.date_start
        if contract.date_end and contract.date_end < date_to:
            date_to = contract.date_end

        exclusiones = self.hook_exclude_categories(localdict, tipo_prestacion, params)

        parcial_info = self._get_parcial_info(contract, annual_params)

        ausencias = self.ausencia_computer.compute(
            slip, contract, date_from, date_to, tipo_prestacion
        )
        dias_periodo = days360(date_from, date_to)
        dias_pagados = max(0, dias_periodo - ausencias['dias_ausencias_total'])

        cambios = self._get_cambios_salario(contract, date_from, date_to)

        if not cambios:
            salario_mensual = self._get_salario_efectivo(
                contract, None, annual_params, params
            )
            salario_base = salario_mensual * parcial_info['factor']
            salario_proporcional = (salario_base / 30.0) * dias_pagados

            return {
                'salario_base_mensual': salario_base,
                'salario_promedio': salario_base,
                'salario_proporcional': salario_proporcional,
                'dias_periodo': dias_periodo,
                'dias_pagados': dias_pagados,
                'ausencias': ausencias,
                'parcial_info': parcial_info,
                'tiene_cambios': False,
                'franjas': [{
                    'fecha_inicio': date_from,
                    'fecha_fin': date_to,
                    'salario_mensual': salario_base,
                    'dias': dias_pagados,
                    'salario_proporcional': salario_proporcional,
                }],
                'exclusiones': exclusiones,
                'date_from': date_from,
                'date_to': date_to,
            }

        franjas = self._build_franjas(
            contract, annual_params, params, parcial_info,
            date_from, date_to, cambios
        )

        dias_franjas = sum(f['dias'] for f in franjas)
        suma_ponderada = sum(f['salario_mensual'] * f['dias'] for f in franjas)
        salario_promedio = suma_ponderada / dias_franjas if dias_franjas > 0 else 0

        if ausencias['dias_ausencias_total'] > 0 and dias_franjas > 0:
            factor_descuento = max(0, dias_pagados / dias_franjas)
            for franja in franjas:
                franja['dias_despues_descuento'] = franja['dias'] * factor_descuento
                franja['salario_despues_descuento'] = franja['salario_proporcional'] * factor_descuento

        salario_proporcional = (salario_promedio / 30.0) * dias_pagados

        return {
            'salario_base_mensual': franjas[-1]['salario_mensual'] if franjas else 0,
            'salario_promedio': salario_promedio,
            'salario_proporcional': salario_proporcional,
            'dias_periodo': dias_periodo,
            'dias_pagados': dias_pagados,
            'ausencias': ausencias,
            'parcial_info': parcial_info,
            'tiene_cambios': True,
            'franjas': franjas,
            'exclusiones': exclusiones,
            'date_from': date_from,
            'date_to': date_to,
        }

    def _get_salario_efectivo(self, contract, wage_base, annual_params, params):
        wage = wage_base if wage_base is not None else (contract.wage or 0)
        modality = contract.modality_salary or 'basico'
        subcontract = contract.subcontract_type

        if modality == 'integral' and not subcontract:
            factor = params.get('factor_integral', 1.0)
            return wage * factor

        if modality == 'sostenimiento' and not subcontract:
            if contract.apprentice_wage:
                return contract.apprentice_wage
            if annual_params:
                smmlv = annual_params.smmlv_monthly or 0
                pct = 100.0 if contract.apprentice_stage == 'productiva' else 75.0
                return smmlv * (pct / 100.0)
            return wage

        if subcontract in ('obra_parcial', 'obra_integral'):
            return wage * 0.5

        return wage

    def _get_parcial_info(self, contract, annual_params):
        full_hours = 48.0
        if annual_params:
            if annual_params.hours_weekly:
                full_hours = annual_params.hours_weekly
            elif annual_params.hours_monthly:
                full_hours = (annual_params.hours_monthly / 30.0) * 7
            elif annual_params.hours_daily:
                full_hours = annual_params.hours_daily * 7

        es_parcial = contract.parcial
        es_por_dia = bool(contract.subcontract_type)
        factor = 1.0
        horas_semanales = full_hours

        if es_parcial:
            horas_semanales = contract.partial_hours_weekly or full_hours
            factor = horas_semanales / full_hours if full_hours else 0.5

        return {
            'es_parcial': es_parcial,
            'es_por_dia': es_por_dia,
            'factor': factor,
            'horas_semanales': horas_semanales,
            'horas_completa': full_hours,
        }

    def _get_cambios_salario(self, contract, date_from, date_to):
        if not contract.change_wage_ids:
            return []

        return sorted(
            [
                {'fecha': c.date_start, 'salario': c.wage}
                for c in contract.change_wage_ids
                if date_from < c.date_start <= date_to
            ],
            key=lambda x: x['fecha']
        )

    def _get_salario_vigente_al(self, contract, fecha):
        salario = contract.wage or 0
        if not contract.change_wage_ids:
            return salario

        for cambio in sorted(contract.change_wage_ids, key=lambda c: c.date_start):
            if cambio.date_start <= fecha:
                salario = cambio.wage or 0
            else:
                break
        return salario

    def _build_franjas(self, contract, annual_params, params, parcial_info,
                       date_from, date_to, cambios):
        franjas = []
        fecha_actual = date_from
        salario_raw = self._get_salario_vigente_al(contract, date_from)
        salario_actual = self._get_salario_efectivo(
            contract, salario_raw, annual_params, params
        ) * parcial_info['factor']

        for cambio in cambios:
            if cambio['fecha'] > fecha_actual:
                fecha_fin_franja = cambio['fecha'] - timedelta(days=1)
                dias_franja = days360(fecha_actual, fecha_fin_franja)
                if dias_franja > 0:
                    franjas.append({
                        'fecha_inicio': fecha_actual,
                        'fecha_fin': fecha_fin_franja,
                        'salario_mensual': salario_actual,
                        'dias': dias_franja,
                        'salario_proporcional': (salario_actual / 30.0) * dias_franja,
                    })

            fecha_actual = cambio['fecha']
            salario_actual = self._get_salario_efectivo(
                contract, cambio['salario'], annual_params, params
            ) * parcial_info['factor']

        if fecha_actual <= date_to:
            dias_franja = days360(fecha_actual, date_to)
            if dias_franja > 0:
                franjas.append({
                    'fecha_inicio': fecha_actual,
                    'fecha_fin': date_to,
                    'salario_mensual': salario_actual,
                    'dias': dias_franja,
                    'salario_proporcional': (salario_actual / 30.0) * dias_franja,
                })

        return franjas

# ══════════════════════════════════════════════════════════════════════════════
# CLASE PRINCIPAL - Reglas de Salario Basico
# ══════════════════════════════════════════════════════════════════════════════

class HrSalaryRuleBasic(models.AbstractModel):
    """Mixin para reglas de salario basico"""

    _name = 'hr.salary.rule.basic'
    _description = 'Metodos para Reglas de Salario Basico'


    def _obtener_salario_efectivo_contrato(self, contract, wage_base=None, annual_parameters=None):
        """
        Obtiene el salario efectivo del contrato segun su modalidad.

        Considera las diferentes modalidades de salario:
        - basico/especie/variable: wage o partial_wage_computed
        - integral: wage * 0.7 (excluye factor prestacional 30%)
        - sostenimiento: cuota de sostenimiento basada en SMMLV
        - parcial: partial_wage_computed
        - subcontrato (obra_parcial/obra_integral): wage * factor

        Args:
            contract: Contrato del empleado
            wage_base: Salario base opcional (para cambios de salario)
            annual_parameters: Parametros anuales (para sostenimiento)

        Returns:
            float: Salario efectivo mensual
        """
        wage = wage_base if wage_base is not None else (contract.wage or 0)
        modality = contract.modality_salary or 'basico'
        subcontract = contract.subcontract_type
        full_hours = 48.0
        if annual_parameters:
            if annual_parameters.hours_weekly:
                full_hours = annual_parameters.hours_weekly
            elif annual_parameters.hours_monthly:
                full_hours = (annual_parameters.hours_monthly / 30.0) * 7
            elif annual_parameters.hours_daily:
                full_hours = annual_parameters.hours_daily * 7

        # 1. Salario Integral: solo 70% (excluye factor prestacional 30%)
        if modality == 'integral' and not subcontract:
            return wage * 0.7

        # 2. Sostenimiento (aprendices): usar cuota calculada de SMMLV
        if modality == 'sostenimiento' and not subcontract:
            if contract.apprentice_wage:
                return contract.apprentice_wage
            if annual_parameters:
                smmlv = annual_parameters.smmlv_monthly or 0
                pct = 100.0 if contract.apprentice_stage == 'productiva' else 75.0
                return smmlv * (pct / 100.0)
            return wage

        # 3. Tiempo parcial: usar salario proporcional calculado
        if contract.parcial:
            if wage_base is not None:
                hours = contract.partial_hours_weekly or full_hours
                proportion = hours / full_hours if full_hours else 0
                return wage_base * proportion
            return contract.partial_wage_computed or wage

        # 4. Subcontrato obra parcial/integral: aplicar factor 0.5
        if subcontract in ('obra_parcial', 'obra_integral'):
            factor = 0.5
            if contract.parcial:
                hours = contract.partial_hours_weekly or full_hours
                factor = factor * (hours / full_hours if full_hours else 0)
            return wage * factor

        # 5. Basico/especie/variable: salario directo
        return wage


    def _calcular_salario_periodo_con_cambios(self, contract, slip, date_from, date_to,
                                              dias_ausencias_no_pagadas=0, descontar_suspensiones=True,
                                              detectar_cambios_salario=True, annual_parameters=None):
        """
        Calcula el salario del periodo considerando cambios de salario y ausencias.

        Si hay cambios de salario en el periodo, calcula proporcional por cada franja.
        Las ausencias no pagadas se descuentan de la franja donde ocurrieron.

        IMPORTANTE: Usa _obtener_salario_efectivo_contrato para considerar las
        diferentes modalidades de salario (integral, sostenimiento, parcial, etc.)

        IMPORTANTE: Si el contrato termina antes de date_to, usa la fecha de fin
        del contrato para calcular los días.

        Args:
            contract: Contrato del empleado
            slip: Nomina actual
            date_from: Fecha inicio del periodo
            date_to: Fecha fin del periodo
            dias_ausencias_no_pagadas: Dias de ausencias no pagadas a descontar
            descontar_suspensiones: Si True, resta los dias no pagados
            detectar_cambios_salario: Si True, busca cambios de salario en el periodo
            annual_parameters: Parametros anuales (requerido para sostenimiento)

        Returns:
            dict: {
                'salario_total': float - Salario proporcional del periodo,
                'dias_pagados': float - Dias efectivos pagados,
                'franjas': tree - Detalle de cada franja de salario,
                'hubo_cambio_salario': bool - Si hubo cambio de salario en el periodo
            }
        """
        # AJUSTE: Si el contrato termina ANTES del fin del período, usar fecha fin contrato
        date_to_efectivo = date_to
        ajuste_fin_contrato = False
        if contract.date_end and contract.date_end < date_to:
            date_to_efectivo = contract.date_end
            ajuste_fin_contrato = True

        # AJUSTE: Si el contrato inicia DESPUÉS del inicio del período, usar fecha inicio contrato
        date_from_efectivo = date_from
        ajuste_inicio_contrato = False
        if contract.date_start and contract.date_start > date_from:
            date_from_efectivo = contract.date_start
            ajuste_inicio_contrato = True

        hubo_cambio = False
        cambios_salario = []

        if detectar_cambios_salario:
            for change in sorted(contract.change_wage_ids, key=lambda x: x.date_start):
                if change.date_start <= date_to_efectivo:
                    cambios_salario.append({
                        'fecha': change.date_start,
                        'salario': change.wage
                    })
            cambios_en_periodo = [c for c in cambios_salario if date_from_efectivo <= c['fecha'] <= date_to_efectivo]
            hubo_cambio = len(cambios_en_periodo) > 0

        if not hubo_cambio:
            dias_periodo = days360(date_from_efectivo, date_to_efectivo)
            usar_dias_manuales = False
            dias_manuales = 0
            if slip and slip.use_manual_days:
                usar_dias_manuales = True
                dias_manuales = slip.manual_days or 0

            salario_mensual = self._obtener_salario_efectivo_contrato(
                contract, wage_base=None, annual_parameters=annual_parameters
            )

            dias_pagados = float(dias_manuales) if usar_dias_manuales and dias_manuales > 0 else dias_periodo

            if descontar_suspensiones and dias_ausencias_no_pagadas > 0:
                dias_pagados = max(0, dias_pagados - dias_ausencias_no_pagadas)

            salario_proporcional = (salario_mensual / 30.0) * dias_pagados

            return {
                'salario_total': salario_proporcional,
                'dias_pagados': dias_pagados,
                'dias_periodo': dias_periodo,
                'dias_manuales_usados': usar_dias_manuales,
                'ajuste_fin_contrato': ajuste_fin_contrato,
                'ajuste_inicio_contrato': ajuste_inicio_contrato,
                'date_from_efectivo': date_from_efectivo,
                'date_to_efectivo': date_to_efectivo,
                'franjas': [{
                    'fecha_inicio': date_from_efectivo,
                    'fecha_fin': date_to_efectivo,
                    'salario_mensual': salario_mensual,
                    'dias': dias_pagados,
                    'salario_proporcional': salario_proporcional
                }],
                'hubo_cambio_salario': False,
                'salario_mensual_actual': salario_mensual
            }

        franjas = []
        fecha_actual = date_from_efectivo
        wage_inicial = contract.get_wage_in_date(date_from_efectivo)
        salario_actual = self._obtener_salario_efectivo_contrato(
            contract, wage_base=wage_inicial, annual_parameters=annual_parameters
        )

        cambios_aplicables = sorted(
            [c for c in cambios_salario if c['fecha'] > date_from_efectivo and c['fecha'] <= date_to_efectivo],
            key=lambda x: x['fecha']
        )

        for cambio in cambios_aplicables:
            fecha_fin_franja = cambio['fecha'] - timedelta(days=1)
            if fecha_fin_franja >= fecha_actual:
                dias_franja = days360(fecha_actual, fecha_fin_franja)
                franjas.append({
                    'fecha_inicio': fecha_actual,
                    'fecha_fin': fecha_fin_franja,
                    'salario_mensual': salario_actual,
                    'dias': dias_franja,
                    'salario_proporcional': (salario_actual / 30.0) * dias_franja
                })

            fecha_actual = cambio['fecha']
            salario_actual = self._obtener_salario_efectivo_contrato(
                contract, wage_base=cambio['salario'], annual_parameters=annual_parameters
            )

        if fecha_actual <= date_to_efectivo:
            dias_franja = days360(fecha_actual, date_to_efectivo)
            franjas.append({
                'fecha_inicio': fecha_actual,
                'fecha_fin': date_to_efectivo,
                'salario_mensual': salario_actual,
                'dias': dias_franja,
                'salario_proporcional': (salario_actual / 30.0) * dias_franja
            })

        dias_total = sum(f['dias'] for f in franjas)
        salario_total = sum(f['salario_proporcional'] for f in franjas)

        if descontar_suspensiones and dias_ausencias_no_pagadas > 0:
            factor_descuento = max(0, (dias_total - dias_ausencias_no_pagadas) / dias_total) if dias_total > 0 else 0
            salario_total = salario_total * factor_descuento
            dias_total = max(0, dias_total - dias_ausencias_no_pagadas)

            for franja in franjas:
                franja['dias_despues_descuento'] = franja['dias'] * factor_descuento
                franja['salario_despues_descuento'] = franja['salario_proporcional'] * factor_descuento

        usar_dias_manuales = False
        dias_manuales = 0
        if slip and slip.use_manual_days:
            usar_dias_manuales = True
            dias_manuales = slip.manual_days or 0

        dias_periodo_original = sum(f['dias'] for f in franjas)
        if usar_dias_manuales and dias_manuales > 0 and dias_periodo_original > 0:
            factor_manual = float(dias_manuales) / float(dias_periodo_original)
            salario_total = salario_total * factor_manual
            dias_total = float(dias_manuales)

        return {
            'salario_total': salario_total,
            'dias_pagados': dias_total,
            'dias_periodo': dias_periodo_original,
            'dias_manuales_usados': usar_dias_manuales,
            'ajuste_fin_contrato': ajuste_fin_contrato,
            'ajuste_inicio_contrato': ajuste_inicio_contrato,
            'date_from_efectivo': date_from_efectivo,
            'date_to_efectivo': date_to_efectivo,
            'franjas': franjas,
            'hubo_cambio_salario': True,
            'salario_mensual_actual': salario_actual
        }


    def _get_rule_name(self, salary_type, localdict=None, **kwargs):
        """Genera el nombre de la regla salarial segun el tipo."""
        parcial_percentage = kwargs.get('parcial_percentage', 100)
        total_days = kwargs.get('total_days', 0)

        names = {
            'basic': 'SUELDO BASICO',
            'integral': 'SUELDO BASICO INTEGRAL',
            'parcial': f'SUELDO TIEMPO PARCIAL ({parcial_percentage}%)',
            'por_dia': f'SUELDO POR DIA ({int(total_days)} dias)',
        }

        if salary_type == 'sostenimiento' and localdict:
            employee = localdict.get('employee')
            if employee and employee.tipo_coti_id:
                tipo_coti = employee.tipo_coti_id.code
                return 'CUOTA DE SOSTENIMIENTO LECTIVO' if tipo_coti == '12' else 'CUOTA DE SOSTENIMIENTO PRODUCTIVO'
            return 'CUOTA DE SOSTENIMIENTO'

        return names.get(salary_type, f'SALARIO {salary_type.upper()}')


    def _calculate_salary_generic(self, localdict, salary_type='basic'):
        """
        Metodo generico para calcular salarios - solo construccion de datos.
        Soporta: basic, integral, sostenimiento, parcial, por_dia

        Usa las funciones helper para el calculo real.
        """

        contract = localdict['contract']
        slip = localdict['slip']

        if salary_type == 'basic' and (contract.subcontract_type or contract.parcial or contract.modality_salary not in ('basico', 'especie', 'variable')):
            return crear_resultado_vacio('SUELDO BASICO', 'Modalidad no aplicable', 'basic')

        if salary_type == 'integral' and (contract.subcontract_type or contract.modality_salary != 'integral'):
            return crear_resultado_vacio('SUELDO INTEGRAL', 'Modalidad integral no aplicable', 'basic')

        if salary_type == 'sostenimiento' and (contract.subcontract_type or contract.modality_salary != 'sostenimiento'):
            return crear_resultado_vacio('SOSTENIMIENTO', 'Modalidad sostenimiento no aplicable', 'basic')

        if salary_type == 'parcial' and contract.subcontract_type:
            return crear_resultado_vacio('SUELDO PARCIAL', 'No aplica para subcontratos', 'basic')

        if salary_type == 'por_dia' and not contract.subcontract_type:
            return crear_resultado_vacio('SUELDO POR DIA', 'Solo aplica para subcontratos', 'basic')

        # Obtener dias/horas trabajados
        worked = localdict['worked_days'].get('WORK100')
        total_days = worked.number_of_days if worked else 0
        total_hours = worked.number_of_hours if worked else 0

        if salary_type == 'por_dia':
            dias_calculo = localdict.get('dias_calculo', 0)
            if slip.use_manual_days and slip.manual_days > 0:
                dias_calculo = float(slip.manual_days)
            elif not dias_calculo:
                dias_calculo = (slip.date_to - slip.date_from).days + 1
            total_days = dias_calculo

        is_hourly = slip.struct_type_id.wage_type == 'hourly'
        hours_monthly = localdict['annual_parameters'].hours_monthly

        # Factor parcial
        parcial_factor = 1.0
        parcial_percentage = 100
        if salary_type == 'parcial':
            parcial_factor = contract.factor or 50 / 100.0
            parcial_percentage = int(parcial_factor * 100)

        # Usar helper para calcular con cambios de salario
        calc_result = calculate_salary_with_changes(
            contract,
            slip,
            parcial_factor,
            is_hourly,
            hours_monthly
        )

        # Ajustar para por_dia - SIEMPRE usar dias manuales cuando aplica
        if salary_type == 'por_dia':
            old_wage = (contract.wage or 0) * parcial_factor
            rate = float(old_wage) / 30.0
            calc_result['total_pay'] = rate * float(total_days)
            calc_result['quantity'] = total_days
            calc_result['avg_rate'] = rate
            calc_result['has_changes'] = False  # Reset para no afectar log

        total_pay = calc_result['total_pay']
        quantity = calc_result['quantity']
        avg_rate = calc_result['avg_rate']

        # Log data
        if calc_result['has_changes']:
            log_data = crear_log_data(
                'success', 'basic',
                has_changes=True,
                salary_type=salary_type,
                **calc_result['details']
            )
        else:
            log_data = crear_log_data(
                'success', 'basic',
                has_changes=False,
                total=float(total_pay),
                salary_type=salary_type,
                **calc_result['details']
            )

        # Nombre segun tipo - usando metodo generico
        name = self._get_rule_name(
            salary_type,
            localdict=localdict,
            parcial_percentage=parcial_percentage,
            total_days=total_days
        )

        # Crear computation estandarizada para el widget
        indicadores = [
            crear_indicador('Dias', float(quantity), 'info', 'number'),
        ]
        if salary_type == 'parcial':
            indicadores.append(crear_indicador('Factor', f'{parcial_percentage}%', 'warning', 'text'))

        old_wage = calc_result['details'].get('wage', calc_result['details'].get('old_wage', 0))

        pasos = [
            crear_paso_calculo('Salario Mensual', float(old_wage), 'currency'),
            crear_paso_calculo('Dias Trabajados', float(quantity), 'number'),
            crear_paso_calculo('Valor Dia', float(avg_rate), 'currency'),
            crear_paso_calculo('Total', float(avg_rate * quantity), 'currency', highlight=True),
        ]

        if calc_result['has_changes']:
            details = calc_result['details']
            # Solo mostrar old/new si existen (cuando son exactamente 2 franjas)
            if 'old_wage' in details:
                pasos = [
                    crear_paso_calculo('Salario Anterior', float(details['old_wage']), 'currency'),
                    crear_paso_calculo('Salario Nuevo', float(details['new_wage']), 'currency'),
                    crear_paso_calculo('Dias Salario Anterior', float(details['days_before']), 'number'),
                    crear_paso_calculo('Dias Salario Nuevo', float(details['days_after']), 'number'),
                    crear_paso_calculo('Total', float(total_pay), 'currency', highlight=True),
                ]
            else:
                # Multiples cambios de salario - mostrar franjas
                franjas = details.get('franjas', [])
                pasos = []
                for i, franja in enumerate(franjas, 1):
                    pasos.append(crear_paso_calculo(f'Franja {i}: Salario', float(franja.get('salario', 0)), 'currency'))
                    pasos.append(crear_paso_calculo(f'Franja {i}: Dias', float(franja.get('dias', 0)), 'number'))
                pasos.append(crear_paso_calculo('Total', float(total_pay), 'currency', highlight=True))

        computation = crear_computation_estandar(
            'basico',
            titulo=name,
            formula='Salario / 30 x Dias',
            indicadores=indicadores,
            pasos=pasos,
            base_legal='Art. 127 CST',
            datos=log_data,
        )

        return crear_resultado_regla(avg_rate, quantity, 100.0, name, log_data=log_data, data_kpi=computation)


    def _basic(self, localdict):
        """Calcula sueldo basico para modalidades: basico, especie, variable."""
        return self._calculate_salary_generic(localdict, salary_type='basic')

    def _basic002(self, localdict):
        """Calcula sueldo basico integral. Incluye factor prestacional (30%)."""
        return self._calculate_salary_generic(localdict, salary_type='integral')

    def _basic003(self, localdict):
        """Calcula cuota de sostenimiento para aprendices (etapa lectiva/productiva)."""
        return self._calculate_salary_generic(localdict, salary_type='sostenimiento')

    def _basic004(self, localdict):
        """Calcula sueldo tiempo parcial. Aplica factor configurado en contrato (contract.factor)."""
        contract = localdict['contract']

        # Solo aplica si el contrato tiene marcado tiempo parcial
        if not contract.parcial:
            return crear_resultado_vacio('SUELDO TIEMPO PARCIAL', 'Contrato no es tiempo parcial', 'parcial')

        return self._calculate_salary_generic(localdict, salary_type='parcial')

    def _basic005(self, localdict):
        """Calcula sueldo por dias especificos. Usa localdict['dias_calculo'] o slip.manual_days."""
        return self._calculate_salary_generic(localdict, salary_type='por_dia')
