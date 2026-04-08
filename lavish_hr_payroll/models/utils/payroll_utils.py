# -*- coding: utf-8 -*-
"""
Utilidades centralizadas para cálculos de nómina colombiana
"""
from decimal import Decimal, ROUND_HALF_UP
import math

def round_payroll_amount(amount, decimals=0):
    """
    Redondea montos de nómina de forma consistente.

    Por defecto redondea a entero (sin decimales) para evitar descuadres contables.
    Usa Decimal para precisión.

    Args:
        amount: Monto a redondear (float, int o Decimal)
        decimals: Número de decimales (default 0 = entero)

    Returns:
        Decimal redondeado
    """
    if amount is None:
        return Decimal('0')

    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    if decimals == 0:
        return amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    else:
        quantizer = Decimal(10) ** -decimals
        return amount.quantize(quantizer, rounding=ROUND_HALF_UP)

def round_to_100(amount):
    """Redondea al múltiplo de 100 más cercano hacia arriba (ceiling)."""
    return int(math.ceil(float(amount) / 100.0)) * 100

def round_to_1000(amount):
    """Redondea al múltiplo de 1000 más cercano."""
    return round(float(amount), -3)

def round_up_to_integer(amount):
    """Redondea al siguiente entero (ceiling)."""
    return math.ceil(amount)

def round_up_to_hundred_decimal(value):
    """
    Redondea al centenar superior usando Decimal con ROUND_CEILING.
    Útil cuando se necesita precisión decimal.
    """
    from decimal import ROUND_CEILING
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal('1E2'), rounding=ROUND_CEILING)


# =============================================================================
# CÁLCULOS DE VACACIONES
# =============================================================================

def calculate_vacation_days(working_days, unpaid_days):
    """
    Calcula los días de vacaciones proporcionales según normativa colombiana.

    En Colombia: 15 días hábiles de vacaciones por cada 360 días trabajados.
    Los días no remunerados se descuentan del tiempo trabajado.

    Args:
        working_days: Días trabajados
        unpaid_days: Días no remunerados a descontar

    Returns:
        float: Días de vacaciones proporcionales
    """
    return ((working_days - unpaid_days) * 15) / 360


# =============================================================================
# CÁLCULOS DE FECHAS
# =============================================================================

def monthdelta(d1, d2):
    """
    Calcula el número de meses completos entre dos fechas.

    Itera mes a mes desde d1 hasta d2, contando los meses completos
    que caben entre las dos fechas.

    Args:
        d1: Fecha inicial (date o datetime)
        d2: Fecha final (date o datetime)

    Returns:
        int: Número de meses completos entre las fechas
    """
    from calendar import monthrange
    from datetime import timedelta

    delta = 0
    while True:
        mdays = monthrange(d1.year, d1.month)[1]
        d1 += timedelta(days=mdays)
        if d1 <= d2:
            delta += 1
        else:
            break
    return delta
