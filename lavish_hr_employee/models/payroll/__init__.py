# -*- coding: utf-8 -*-
# Estructuras de datos compartidas (utilidades Python puras)
from . import hr_payslip_constants
from . import hr_slip_data_structures
from . import hr_slip_utils

from . import (
    hr_annual_parameters,
    hr_parameterization,
    hr_payroll_hours_helper,
    hr_retencion_service,
    hr_rule_adapted,
    hr_deduction_priority,
    hr_leave,
)

# NOTA: hr_slip_acumulacion contiene modelos de Odoo que dependen de
# lavish_hr_payroll y se cargan cuando ese módulo se instala
