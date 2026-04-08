# -*- coding: utf-8 -*-
"""
Utilidades compartidas para modelos de contrato.
Centraliza imports, constantes y funciones usadas por multiples archivos.
"""
import calendar
import logging

_logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES DE PRECISION
# =============================================================================
PRECISION_TECHNICAL = 10
PRECISION_DISPLAY = 2

# =============================================================================
# MENSAJES DE ADVERTENCIA (usados principalmente en hr_contract.py)
# =============================================================================
CONTRACT_GROUP_ID_HELP = """
Este campo permite agrupar los contratos, segun se va a calcular la nomina.
Sirve para grupos que no sea por banco, centro de costo y/o ciudad de desempeño.
"""

ARL_ID_HELP = "ARL en el caso que el empleado sea independiente"

ANALYTIC_DISTRIBUTION_TOTAL_WARN = """: La suma de las distribuciones analiticas debe ser 100.0%%,
Valor actual: %s%%"""

CONTRACT_EXTENSION_NO_RECORD_WARN = """
Para prorrogar el contrato por favor registre una prorroga
"""

CONTRACT_EXTENSION_MAX_WARN = """
No es posible realizar una prorroga por un periodo inferior
a un año despues de tener 3 o mas prorrogas
"""

NO_PARTNER_REF_WARN = """
No se encontro el numero de documento en el contacto
"""

IN_FORCE_CONTRACT_WARN = """
El empleado ya tiene un contrato activo: %s.
"""

NO_WAGE_HISTORY = """
El contrato %s no tiene un historial de salarios.
"""

MANY_WAGE_HISTORY = """
El contrato %s tiene %s cambios salariales en este rango %s a %s.
Solo se permite 1 por periodo.
"""

LAST_ONE = -1


# =============================================================================
# FUNCIONES COMPARTIDAS - Importadas desde config_reglas (fuente única)
# =============================================================================

from ..reglas.config_reglas import days360
