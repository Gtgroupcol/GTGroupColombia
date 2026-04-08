# -*- coding: utf-8 -*-
"""
Módulos de reportes de nómina
=============================

Archivos y modelos que contienen:
- hr_accumulated_reports     -> hr.accumulated.reports
- hr_auditing_reports        -> hr.auditing.reports
- hr_consolidated_reports    -> hr.consolidated.reports
- hr_exogena_2276            -> hr.config.rule.exogena, hr.config.rule.concepts,
                                hr.report.2276.exogena.wizard, hr.exogena.report
- hr_payroll_report_filter   -> hr.payroll.report.lavish.filter
- hr_payslip_excel           -> Extensión hr.payslip (export Excel acumulados/base)
- hr_payslip_excel_retencion -> Extensión hr.payslip (export Excel retención)
- hr_payslip_excel_prestaciones -> Extensión hr.payslip (export Excel prestaciones)
- hr_payslip_lines_grid      -> report.lavish_hr_payroll.report_payslip_lines_grid
- hr_payslip_run_entity      -> Extensión hr.payslip.run
- hr_report_absenteeism_history -> hr.report.absenteeism.history
- hr_reports_template        -> hr.payslip.reports.template
- hr_vacation_book           -> hr.vacation.book, hr.vacation.book.line, hr.vacation.book.detail
- hr_withholding_and_income_certificate -> hr.withholding.and.income.certificate
"""

from . import hr_accumulated_reports
from . import hr_auditing_reports
from . import hr_consolidated_reports
from . import hr_exogena_2276
from . import hr_payroll_report_filter
from . import hr_payslip_excel
from . import hr_payslip_excel_retencion
from . import hr_payslip_excel_prestaciones
from . import hr_payslip_lines_grid
from . import hr_payslip_run_entity
from . import hr_report_absenteeism_history
from . import hr_reports_template
from . import hr_vacation_book
from . import hr_withholding_and_income_certificate
