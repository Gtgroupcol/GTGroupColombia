# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from pytz import timezone
import time
import base64
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

CONTRACT_GROUP_ID_HELP = """
Este campo permite agrupar los contratos, según se va a calcular la nómina.
Sirve para grupos que no sea por banco, centro de costo y/o ciudad de desempeño.
"""
ARL_ID_HELP = "ARL en el caso que el empleado sea independiente"
ANALYTIC_DISTRIBUTION_TOTAL_WARN = """: La suma de las distribuciones analíticas debe ser 100.0%%,
Valor actual: %s%%"""
CONTRACT_EXTENSION_NO_RECORD_WARN = """
Para prorrogar el contrato por favor registre una prorroga
"""
CONTRACT_EXTENSION_MAX_WARN = """
No es posible realizar una prórroga por un periodo inferior
a un año despues de tener 3 o más prórrogas
"""
NO_PARTNER_REF_WARN = """
No se encontró el numero de documento en el contacto
"""
IN_FORCE_CONTRACT_WARN = """
El empleado yá tiene un contrato activo: %s.
"""

NO_WAGE_HISTORY = """
El contrato %s no tiene un historial de salarios.
"""

MANY_WAGE_HISTORY = """
El contrato %s tiene %s cambios salariales en este rango %s a %s.
Solo se permite 1 por periodo.
"""

LAST_ONE = -1
import calendar
import logging
from typing import Dict, List, Union, Optional, Tuple, Any, TypeVar, cast
from odoo.tools.safe_eval import safe_eval
_logger = logging.getLogger(__name__)

PRECISION_TECHNICAL = 10
PRECISION_DISPLAY = 2

T = TypeVar('T')

# days360 centralizado en config_reglas.py - usar: from ..reglas.config_reglas import days360


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'
    
    pass
