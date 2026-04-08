# -*- coding: utf-8 -*-
{
    'name': "lavish_hr_employee",
    'summary': """
        Módulo de nómina para la localización colombiana | Prametrización & Hoja de Vida Empleado & Contrato""",
    'description': """
        Módulo de nómina para la localización colombiana | Prametrización &  Hoja de Vida Empleado & Contrato      
    """,
    'author': "lavish S.A.S",
    'category': 'Human Resources',
    'version': '1.35',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'documents',
        'lavish_erp',
        'hr',
        'hr_skills',
        'hr_payroll',
        'hr_contract',
        'hr_holidays',
        'hr_payroll_account',
        'hr_work_entry_contract_enterprise',
        'stock',
        'purchase',
    ],
    "data": [
        # =====================================================================
        # DATA - Secuencias y datos iniciales
        # =====================================================================
        "data/ir_sequences.xml",
        "data/hr_certificate_income_data.xml",
        "data/hr_contract_type_data.xml",
        "data/hr_indicador_especial_pensiones_data.xml",
        "data/hr_labor_certificate_template_data.xml",
        "data/mail_template_labor_certificate.xml",
        "data/mail_template_change_wage.xml",
        "data/epp_dotacion/ir_cron_epp.xml",
        "data/epp_batch/mail_template_epp.xml",
        "data/hr_epp_item_type_data.xml",
        "data/hr_epp_size_data.xml",
        "data/hr_medical_certificate_type_data.xml",
        # =====================================================================
        # SECURITY
        # =====================================================================
        "security/hr_security.xml",
        "security/ir_rule.xml",
        "security/ir.model.access.csv",
        # =====================================================================
        # ACTIONS - Acciones (deben cargar ANTES de las vistas que las referencian)
        # =====================================================================
        "views/menus/employee_actions.xml",
        "views/menus/contract_actions.xml",
        "views/menus/payroll_actions.xml",
        "views/menus/epp_actions.xml",
        "views/menus/medical_actions.xml",
        "views/menus/certificates_actions.xml",
        "views/menus/config_actions.xml",
        # =====================================================================
        # VIEWS - Vistas por categoría (solo ir.ui.view)
        # =====================================================================
        "views/employee/employee_views.xml",
        "views/contract/contract_views.xml",
        "views/payroll/payroll_views.xml",
        "views/epp/epp_views.xml",
        "views/medical/medical_views.xml",
        "views/certificates/certificates_views.xml",
        "views/config/config_views.xml",
        # =====================================================================
        # MENUS - Menús finales
        # =====================================================================
        "views/menus.xml",
        # =====================================================================
        # WIZARDS
        # =====================================================================
        "wizards/hr_certificate_income_wizard_views.xml",
        "wizards/hr_labor_certificate_wizard_views.xml",
        "wizards/hr_annual_parameters_copy_wizard_views.xml",
        "wizards/wizard_mass_epp_request_views.xml",
        # =====================================================================
        # REPORTS
        # =====================================================================
        "report/report_change_wage_template.xml",
        "report/report_change_wage.xml",
        "report/report_birthday_list_template.xml",
        "report/report_birthday_list.xml",
        "report/report_certification_template.xml",
        "report/report_certification.xml",
        "report/report_personal_data_form_template.xml",
        "report/report_personal_data_form.xml",
        "report/report_print_badge_template.xml",
        "report/report_print_badge.xml",
        "report/report_retirement_severance_pay_template.xml",
        "report/report_retirement_severance_pay.xml",
        "report/report_epp_request_formal.xml",
        "report/epp_dotacion/report_epp_delivery.xml",
        "report/epp_batch/report_batch_delivery.xml",
        "report/epp_batch/report_batch_stock_moves.xml",
        "report/medical/report_medical_certificate.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'lavish_hr_employee/static/src/views/widgets/**/*',
        ],
    },
    'installable': True,
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
