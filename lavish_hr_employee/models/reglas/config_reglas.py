# -*- coding: utf-8 -*-

"""
CONFIGURACIÓN Y CONSTANTES PARA REGLAS SALARIALES
==================================================

Este archivo centraliza todas las configuraciones, constantes y métodos de ayuda
utilizados en el cálculo de reglas salariales para Colombia.

Autor: Sistema de Nómina
Fecha: 2025-11-09
Versión: Odoo 18
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

DAYS_YEAR = 360  
DAYS_NATURAL_YEAR = 365
DAYS_MONTH = 30  



PRESTACIONES_CONFIG = {
    'vacaciones': {
        'campo_base': 'base_vacaciones',
        'tasa_default': 4.17,
        'tasa_field': 'value_porc_provision_vacation',  # Campo en hr.annual.parameters
        'nombre': "VACACIONES",
        'codigo': 'PRV_VAC',
        'tipo_prest': 'vacaciones',
        'periodo': 'variable',
        'incluye_auxilio': False,
        'metodo_forzado': 'simple',
        'descripcion': 'Vacaciones - 15 días hábiles por año trabajado'
    },
    'prima': {
        'campo_base': 'base_prima',
        'tasa_default': 8.33,
        'tasa_field': 'value_porc_provision_bonus',  # Campo en hr.annual.parameters
        'nombre': "PRIMA",
        'codigo': 'PRV_PRIM',
        'tipo_prest': 'prima',
        'periodo': 'semestral',
        'incluye_auxilio': True,
        'metodo_forzado': None,
        'descripcion': 'Prima de servicios - 1 mes de salario por año (2 pagos semestrales)'
    },
    'cesantias': {
        'campo_base': 'base_cesantias',
        'tasa_default': 8.33,
        'tasa_field': 'value_porc_provision_cesantias',  # Campo en hr.annual.parameters
        'nombre': "CESANTÍAS",
        'codigo': 'PRV_CES',
        'tipo_prest': 'cesantias',
        'periodo': 'anual',
        'incluye_auxilio': True,
        'metodo_forzado': None,
        'descripcion': 'Cesantías - 1 mes de salario por año trabajado'
    },
    'intereses': {
        'campo_base': 'base_cesantias',
        'tasa_default': 12,
        'tasa_field': 'value_porc_provision_intcesantias',  # Campo en hr.annual.parameters
        'nombre': "INTERESES CESANTÍAS",
        'codigo': 'PRV_ICES',
        'tipo_prest': 'intereses',
        'periodo': 'anual',
        'incluye_auxilio': False,
        'metodo_forzado': None,
        'dependencia': 'PRV_CES',
        'descripcion': 'Intereses sobre cesantías - 12% anual'
    }
}

PRESTACIONES_BASE_FIELDS = {
    'prima': {
        'legacy': 'base_prima',
        'provision': 'base_prima_provision',
        'liquidacion': 'base_prima_liquidacion',
    },
    'cesantias': {
        'legacy': 'base_cesantias',
        'provision': 'base_cesantias_provision',
        'liquidacion': 'base_cesantias_liquidacion',
    },
    'intereses': {
        'legacy': 'base_intereses_cesantias',
        'provision': 'base_intereses_cesantias_provision',
        'liquidacion': 'base_intereses_cesantias_liquidacion',
    },
    'intereses_cesantias': {
        'legacy': 'base_intereses_cesantias',
        'provision': 'base_intereses_cesantias_provision',
        'liquidacion': 'base_intereses_cesantias_liquidacion',
    },
    'vacaciones': {
        'legacy': 'base_vacaciones',
        'provision': 'base_vacaciones_provision',
        'liquidacion': 'base_vacaciones_liquidacion',
    },
    'vacaciones_dinero': {
        'legacy': 'base_vacaciones_dinero',
        'provision': 'base_vacaciones_dinero_provision',
        'liquidacion': 'base_vacaciones_dinero_liquidacion',
    },
}


def get_prestacion_base_field(tipo_prestacion, contexto='liquidacion'):
    """Retorna el campo base según tipo y contexto."""
    field_config = PRESTACIONES_BASE_FIELDS.get(tipo_prestacion, PRESTACIONES_BASE_FIELDS['prima'])
    if contexto in ('provision', 'liquidacion'):
        return field_config[contexto]
    return field_config['legacy']


def get_contextual_base_field(campo_base_legacy, contexto='liquidacion'):
    """Convierte un campo legacy base_* al campo separado por contexto."""
    if contexto not in ('provision', 'liquidacion'):
        return campo_base_legacy

    for field_config in PRESTACIONES_BASE_FIELDS.values():
        if field_config['legacy'] == campo_base_legacy:
            return field_config[contexto]

    return campo_base_legacy


def get_tasa_prestacion(tipo_prestacion, annual_parameters=None):
    """
    Obtiene la tasa de prestación desde parámetros anuales o usa el default.

    Args:
        tipo_prestacion: Tipo de prestación ('vacaciones', 'prima', 'cesantias', 'intereses')
        annual_parameters: Objeto hr.annual.parameters (opcional)

    Returns:
        float: Porcentaje de la prestación
    """
    config = PRESTACIONES_CONFIG.get(tipo_prestacion)
    if not config:
        return 0.0

    # Si hay parámetros anuales, obtener del campo configurado
    if annual_parameters:
        tasa_field = config.get('tasa_field')
        if tasa_field and hasattr(annual_parameters, tasa_field):
            tasa_from_params = getattr(annual_parameters, tasa_field, 0)
            if tasa_from_params and tasa_from_params > 0:
                return float(tasa_from_params)

    # Fallback al valor por defecto
    return float(config.get('tasa_default', 0.0))



CODIGOS_LIQUIDACION = {
    'vacaciones': 'VACCONTRATO',
    'prima': 'PRIMA',
    'cesantias': 'CESANTIAS',
    'intereses': 'INTCESANTIAS'
}


CATEGORIAS_EXCLUIDAS = ['BASIC', 'AUX']

CATEGORIAS_VARIABLES_ACTUALES = ['HEYREC', 'COMISIONES', 'BONIFICACIONES']
CATEGORIAS_VARIABLES_ACUMULADAS = ['HEYREC', 'o_SALARY', 'COMP', 'O_EARN']

CATEGORIAS_DEVENGOS_SALARIALES = ['DEV_SALARIAL']



TIPOS_COTIZANTES_EXENTOS = ['12', '19']




INDEM_CONFIG = {
    'salario_bajo': {  # < 10 SMMLV
        'limite_smmlv': 10,
        'anio_1': 30,  # días por año 1
        'anios_2_5': 20,  # días por año del 2 al 5
        'anios_6_mas': 13.33,  # días por año del 6 en adelante
    },
    'salario_alto': {  # >= 10 SMMLV
        'limite_smmlv': 10,
        'anio_1': 20,  # días por año 1
        'anios_adicionales': 15,  # días por cada año adicional
    },
    'contrato_obra': {
        'minimo_dias': 15  # Mínimo de días para contrato por obra
    }
}


# ══════════════════════════════════════════════════════════════════════════
# SEGURIDAD SOCIAL - PORCENTAJES
# ══════════════════════════════════════════════════════════════════════════

SEGURIDAD_SOCIAL_CONFIG = {
    'salud': {
        'empleado': 4.0,
        'empleador': 8.5,
        'total': 12.5
    },
    'pension': {
        'empleado': 4.0,
        'empleador': 12.0,
        'total': 16.0
    },
    'arl': {
        'nivel_1': 0.522,
        'nivel_2': 1.044,
        'nivel_3': 2.436,
        'nivel_4': 4.350,
        'nivel_5': 6.960
    },
    'fondo_solidaridad': {
        'rango_4_16': 1.0,  # 4-16 SMMLV
        'rango_16_17': 1.2,  # 16-17 SMMLV
        'rango_17_18': 1.4,  # 17-18 SMMLV
        'rango_18_19': 1.6,  # 18-19 SMMLV
        'rango_19_20': 1.8,  # 19-20 SMMLV
        'rango_20_mas': 2.0,  # > 20 SMMLV
    }
}


# ══════════════════════════════════════════════════════════════════════════
# PARAFISCALES - PORCENTAJES
# ══════════════════════════════════════════════════════════════════════════

PARAFISCALES_CONFIG = {
    'sena': 2.0,
    'icbf': 3.0,
    'caja_compensacion': 4.0
}


# ══════════════════════════════════════════════════════════════════════════
# HORAS EXTRAS Y RECARGOS - PORCENTAJES
# ══════════════════════════════════════════════════════════════════════════

HORAS_EXTRAS_CONFIG = {
    'HED': {
        'nombre': 'Hora Extra Diurna',
        'recargo': 25.0,  # 25% adicional
        'codigo': 'HED'
    },
    'HEN': {
        'nombre': 'Hora Extra Nocturna',
        'recargo': 75.0,  # 75% adicional
        'codigo': 'HEN'
    },
    'HEDF': {
        'nombre': 'Hora Extra Diurna Festiva',
        'recargo': 100.0,  # 100% adicional
        'codigo': 'HEDF'
    },
    'HENF': {
        'nombre': 'Hora Extra Nocturna Festiva',
        'recargo': 150.0,  # 150% adicional
        'codigo': 'HENF'
    },
    'RN': {
        'nombre': 'Recargo Nocturno',
        'recargo': 35.0,  # 35% adicional
        'codigo': 'RN'
    },
    'RDF': {
        'nombre': 'Recargo Dominical/Festivo',
        'recargo': 75.0,  # 75% adicional
        'codigo': 'RDF'
    },
    'RDNF': {
        'nombre': 'Recargo Dominical/Festivo Nocturno',
        'recargo': 110.0,  # 110% adicional
        'codigo': 'RDNF'
    }
}


# ══════════════════════════════════════════════════════════════════════════
# RETENCIÓN EN LA FUENTE - CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════

RETENCION_CONFIG = {
    'conceptos_exentos': [
        'SALUD',
        'PENSION',
        'AFC',  # Ahorro Fondo Cesantías
        'MEDICINA_PREPAGADA',
        'DEPENDIENTES',
        'INTERESES_VIVIENDA'
    ],
    'limites_exencion': {
        'pension_voluntaria': 0.30,  # 30% del ingreso laboral
        'medicina_prepagada': 16,  # 16 UVT mensuales
        'dependientes': 32,  # 32 UVT mensuales
        'intereses_vivienda': 100,  # 100 UVT mensuales
    },
    'renta_exenta_genegal': 0.25,  # 25% del ingreso neto
    'limite_renta_exenta': 790  # 790 UVT mensuales (240*12/12)
}


# ══════════════════════════════════════════════════════════════════════════
# TABLA DE RETENCIÓN EN LA FUENTE (Art. 383 E.T.)
# Formato: (desde_uvt, hasta_uvt, tarifa%, resta_uvt, suma_uvt)
# ══════════════════════════════════════════════════════════════════════════

TABLA_RETENCION = [
    (0, 95, 0, 0, 0),
    (95, 150, 19, 95, 0),
    (150, 360, 28, 150, 10),
    (360, 640, 33, 360, 69),
    (640, 945, 35, 640, 162),
    (945, 2300, 37, 945, 268),
    (2300, float('inf'), 39, 2300, 770)
]


# ══════════════════════════════════════════════════════════════════════════
# MÉTODOS DE UTILIDAD
# ══════════════════════════════════════════════════════════════════════════

def to_decimal(value):
    """
    Convierte un valor a Decimal de manera segura.

    Args:
        value: Valor a convertir (puede ser int, float, str, Decimal, None)

    Returns:
        Decimal: Valor convertido a Decimal
    """
    if isinstance(value, Decimal):
        return value
    elif value is None:
        return Decimal("0")
    return Decimal(str(value))


def decimal_round(value, precision=2):
    """
    Redondea un valor Decimal al número de decimales especificado.

    Args:
        value: Valor a redondear
        precision: Número de decimales (default: 2)

    Returns:
        Decimal: Valor redondeado
    """
    value = to_decimal(value)
    decimal_precision = Decimal(f'0.{"0" * precision}1')
    return value.quantize(decimal_precision, rounding=ROUND_HALF_UP)


def round_payroll_amount(amount, decimals=0):
    """
    Redondea montos de nómina para consistencia en cálculos.

    Por defecto redondea a enteros (decimals=0) para evitar
    discrepancias contables por centavos.

    Compatible con lavish_hr_payroll.models.utils.round_payroll_amount

    Args:
        amount: Monto a redondear (int, float, Decimal, None)
        decimals: Número de decimales (default: 0 para enteros)

    Returns:
        Decimal: Monto redondeado
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


def days360(date_from, date_to):
    """
    Calcula dias entre dos fechas usando el metodo comercial colombiano 360 dias.
    Metodo: Cada mes tiene 30 dias, año tiene 360 dias.
    Febrero tambien se trata como 30 dias (28 o 29 de febrero = dia 30).
    Incluye ambos dias (inicio y fin) en el calculo.

    Args:
        date_from: Fecha inicial
        date_to: Fecha final

    Returns:
        int: Numero de dias calculados (inclusivo)
    """
    if not date_from or not date_to:
        return 0

    day1 = date_from.day
    day2 = date_to.day

    if day1 == 31 or (date_from.month == 2 and day1 >= 28):
        day1 = 30
    else:
        day1 = min(day1, 30)

    if day2 == 31 or (date_to.month == 2 and day2 >= 28):
        day2 = 30
    else:
        day2 = min(day2, 30)

    return (
        (date_to.year - date_from.year) * 360 +
        (date_to.month - date_from.month) * 30 +
        (day2 - day1) + 1
    )


def normalizar_base_dias(base_dias, default=DAYS_YEAR):
    """
    Normaliza la base de dias para calculos (360/365).

    Args:
        base_dias: Valor origen (str/int/None)
        default: Base por defecto si no es valida

    Returns:
        int: Base de dias (360 o 365)
    """
    try:
        base_val = int(base_dias)
    except (TypeError, ValueError):
        return default

    if base_val == DAYS_NATURAL_YEAR:
        return DAYS_NATURAL_YEAR
    if base_val == DAYS_YEAR:
        return DAYS_YEAR
    return default


def dias_periodo_base(date_from, date_to, base_dias, incluir_inicio=True):
    """
    Calcula dias entre fechas segun base 360 o 365.

    Args:
        date_from: Fecha inicial
        date_to: Fecha final
        base_dias: Base anual (360 o 365)
        incluir_inicio: Si incluye el dia inicial

    Returns:
        int: Dias calculados
    """
    if not date_from or not date_to or date_from > date_to:
        return 0

    base_dias = normalizar_base_dias(base_dias)

    if base_dias == DAYS_NATURAL_YEAR:
        delta = (date_to - date_from).days
        return delta + (1 if incluir_inicio else 0)

    if incluir_inicio:
        return days360(date_from, date_to)
    if date_from >= date_to:
        return 0
    return days360(date_from + timedelta(days=1), date_to)






def crear_log_data(status, tipo, **kwargs):
    """
    Crea diccionario de log/debug estandarizado para reglas.

    Args:
        status: 'success', 'rejected', 'error', 'no_data', etc.
        tipo: Tipo de regla ('basic', 'auxilio', 'prestacion', etc.)
        **kwargs: Datos adicionales del cálculo

    Returns:
        dict: Diccionario de log estructurado
    """
    log = {
        'status': status,
        'tipo': tipo,
        'fecha_calculo': date.today().strftime('%Y-%m-%d'),
    }
    log.update(kwargs)
    return log


def crear_data_kpi(base, dias, total, **kwargs):
    """
    Crea diccionario de KPIs para visualización en widgets.

    Compatible con la estructura usada en prestaciones_sociales.py.

    Args:
        base: Base de cálculo (salario diario, valor hora, etc.)
        dias: Días o cantidad usada en el cálculo
        total: Total calculado
        **kwargs: KPIs adicionales

    Returns:
        dict: Diccionario de KPIs
    """
    kpi = {
        'base': float(base),
        'dias': float(dias),
        'total': float(total),
        'formula': kwargs.get('formula', f'{base:,.2f} x {dias} = {total:,.2f}'),
    }
    kpi.update(kwargs)
    return kpi


def crear_resultado_regla(amount, quantity, rate, nombre, log_data=None, data_kpi=None, **extras):
    """
    Crea la tupla de retorno estándar para métodos de reglas.

    Los métodos de reglas retornan: (amount, quantity, rate, name, log_html, data_dict)

    Args:
        amount: Monto/rate por unidad
        quantity: Cantidad (días, horas, etc.)
        rate: Porcentaje (0-100)
        nombre: Nombre descriptivo para la línea
        log_data: Diccionario de log (opcional)
        data_kpi: Diccionario de KPIs (opcional)
        **extras: Datos adicionales para el diccionario final

    Returns:
        tuple: (amount, quantity, rate, nombre, '', data_dict)
    """
    data = {}

    if log_data:
        data['log'] = log_data

    if data_kpi:
        data['data_kpi'] = data_kpi

    data.update(extras)

    return (float(amount), float(quantity), float(rate), nombre, '', data)


def crear_resultado_vacio(nombre, razon='', tipo=''):
    """
    Crea resultado vacío para cuando una regla no aplica.

    Args:
        nombre: Nombre de la regla
        razon: Razón por la que no aplica
        tipo: Tipo de regla

    Returns:
        tuple: (0, 0, 0, nombre, '', log_data)
    """
    log_data = crear_log_data('rejected', tipo, reason=razon) if razon else {}
    return (0, 0, 0, nombre, '', log_data)


# ══════════════════════════════════════════════════════════════════════════
# VALIDACIONES Y REGLAS DE NEGOCIO
# ══════════════════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════════════════
# ESTRUCTURA ESTANDAR DE COMPUTATION PARA VISUALIZACION
# ══════════════════════════════════════════════════════════════════════════

# Tipos de visualizacion disponibles
TIPOS_VISUALIZACION = {
    'basico': {
        'nombre': 'Salario Basico',
        'template': 'generic',
        'mostrar_formula': True,
    },
    'auxilio': {
        'nombre': 'Auxilio de Transporte',
        'template': 'generic',
        'mostrar_formula': True,
    },
    'ibd': {
        'nombre': 'Ingreso Base de Cotizacion',
        'template': 'ibd',
        'mostrar_formula': True,
        'mostrar_pasos': True,
        'mostrar_base_legal': True,
    },
    'seguridad_social': {
        'nombre': 'Seguridad Social',
        'template': 'seguridad_social',
        'mostrar_formula': True,
    },
    'prestacion': {
        'nombre': 'Prestacion Social',
        'template': 'prestacion',
        'mostrar_formula': True,
        'mostrar_pasos': True,
    },
    'retencion': {
        'nombre': 'Retencion en la Fuente',
        'template': 'retencion',
        'mostrar_formula': True,
        'mostrar_pasos': True,
        'mostrar_base_legal': True,
    },
    'hora_extra': {
        'nombre': 'Hora Extra / Recargo',
        'template': 'hora_extra',
        'mostrar_formula': True,
        'mostrar_detalle': True,
    },
    'indemnizacion': {
        'nombre': 'Indemnizacion',
        'template': 'indemnizacion',
        'mostrar_formula': True,
        'mostrar_pasos': True,
        'mostrar_base_legal': True,
    },
    'prestamo': {
        'nombre': 'Prestamo / Deduccion',
        'template': 'prestamo',
        'mostrar_saldo': True,
    },
    'novedad': {
        'nombre': 'Novedad / Ausencia',
        'template': 'novedad',
    },
    'generic': {
        'nombre': 'Calculo General',
        'template': 'generic',
        'mostrar_formula': True,
    },
}


def crear_computation_estandar(tipo_visualizacion, **kwargs):
    """
    Crea una estructura de computation estandarizada para el widget.

    Esta estructura es la que el widget debe leer directamente,
    sin necesidad de recalcular nada en el frontend.

    Args:
        tipo_visualizacion: Tipo de visualizacion (ibd, retencion, prestacion, etc.)
        **kwargs: Datos especificos del calculo

    Returns:
        dict: Estructura estandarizada para el widget
    """
    config = TIPOS_VISUALIZACION.get(tipo_visualizacion, TIPOS_VISUALIZACION['generic'])

    computation = {
        # Metadatos de visualizacion
        'tipo_visualizacion': tipo_visualizacion,
        'template': config.get('template', 'generic'),
        'titulo': kwargs.get('titulo', config.get('nombre', '')),

        # Formula y explicacion (siempre presente)
        'formula': kwargs.get('formula', ''),
        'explicacion': kwargs.get('explicacion', ''),

        # Indicadores KPI (badges/chips en el widget)
        'indicadores': kwargs.get('indicadores', []),
        # Ejemplo: [{'label': 'Dias', 'value': 30, 'color': 'info'}]

        # Pasos del calculo (para visualizacion detallada)
        'pasos': kwargs.get('pasos', []),
        # Ejemplo: [{'label': 'Base', 'value': 1000000, 'format': 'currency'}]

        # Base legal (para reglas con normativa)
        'base_legal': kwargs.get('base_legal', ''),
        'elemento_ley': kwargs.get('elemento_ley', ''),
        'articulos': kwargs.get('articulos', []),

        # Datos crudos para calculos adicionales si se necesitan
        'datos': kwargs.get('datos', {}),

        # IDs de lineas relacionadas (para trazabilidad)
        'line_ids': kwargs.get('line_ids', []),
        'acum_line_ids': kwargs.get('acum_line_ids', []),

        # Comparacion con periodo anterior
        'valor_anterior': kwargs.get('valor_anterior', None),
        'variacion': kwargs.get('variacion', None),

        # Timestamp
        'fecha_calculo': date.today().strftime('%Y-%m-%d'),
    }

    # Agregar campos opcionales segun tipo
    if config.get('mostrar_pasos'):
        computation['mostrar_pasos'] = True
    if config.get('mostrar_base_legal'):
        computation['mostrar_base_legal'] = True
    if config.get('mostrar_detalle'):
        computation['mostrar_detalle'] = True
    if config.get('mostrar_saldo'):
        computation['mostrar_saldo'] = True

    return computation


def crear_indicador(label, value, color='secondary', formato='text'):
    """
    Crea un indicador KPI para mostrar en el widget.

    Args:
        label: Etiqueta del indicador
        value: Valor a mostrar
        color: Color del badge (primary, secondary, success, warning, danger, info)
        formato: Formato del valor (text, currency, number, percentage)

    Returns:
        dict: Indicador formateado
    """
    return {
        'label': label,
        'value': value,
        'color': color,
        'formato': formato,
    }


def crear_paso_calculo(label, value, formato='currency', highlight=False, base_legal=None,
                       items=None, descripcion=None, formula=None, notas=None):
    """
    Crea un paso de calculo para mostrar en el widget.

    Args:
        label: Descripcion del paso (etiqueta corta)
        value: Valor del paso
        formato: Formato del valor (currency, number, text, percentage)
        highlight: Si True, resalta este paso como resultado final
        base_legal: Referencia legal opcional
        items: Lista de items detallados para expandir (opcional)
               Cada item: {'nombre': str, 'valor': float, 'formato': str, 'nota': str,
                          'esResta': bool, 'esSuma': bool, 'icono': str}
        descripcion: Explicacion del paso (texto largo)
        formula: Formula del calculo (texto)
        notas: Lista de notas adicionales [{'texto': str, 'icono': str}]

    Returns:
        dict: Paso de calculo formateado
    """
    paso = {
        'label': label,
        'value': value,
        'format': formato,
    }
    if highlight:
        paso['highlight'] = True
    if base_legal:
        paso['base_legal'] = base_legal
    if items:
        paso['items'] = items
    if descripcion:
        paso['descripcion'] = descripcion
    if formula:
        paso['formula_texto'] = formula
    if notas:
        paso['notas'] = notas
    return paso
