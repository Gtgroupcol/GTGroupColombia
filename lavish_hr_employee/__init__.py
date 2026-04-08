# -*- coding: utf-8 -*-

from . import models
from . import report
from . import wizards
from .hooks import post_init_hook, uninstall_hook

def pre_init_hook(env):
    import logging
    _logger = logging.getLogger(__name__)

    # Verificar si la tabla existe antes de modificar
    env.cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'res_company'
        )
    """)
    if not env.cr.fetchone()[0]:
        _logger.info("Tabla res_company no existe, saltando pre_init_hook")
        return

    # Eliminar constraint de foreign key de validated_certificate si existe
    try:
        env.cr.execute("""
            ALTER TABLE res_company
            DROP CONSTRAINT IF EXISTS res_company_validated_certificate_fkey
        """)
        _logger.info("Constraint res_company_validated_certificate_fkey eliminado")
    except Exception as e:
        _logger.warning(f"No se pudo eliminar constraint: {e}")

    # Importar Environment solo si se necesita

    # Limpiar vistas de portal en caché (Odoo 18 compatible)
    try:
        env.cr.execute("""
            DELETE FROM ir_ui_view
            WHERE key LIKE 'lavish_hr_employee.employee_portal%%'
            AND type = 'qweb'
        """)
        _logger.info("Vistas de portal limpiadas correctamente")
    except Exception as e:
        _logger.warning(f"No se pudieron limpiar vistas de portal: {e}")

    # Limpiar datos de caché en ir_model_data
    try:
        env.cr.execute("""
            DELETE FROM ir_model_data
            WHERE module = 'lavish_hr_employee'
            AND model = 'ir.ui.view'
            AND name LIKE '%%portal%%'
        """)
        _logger.info("Datos de caché de portal limpiados")
    except Exception as e:
        _logger.warning(f"No se pudieron limpiar datos de caché: {e}")

    # Renombrar campos personalizados legacy
    fields_to_rename = [
        ('res.partner', 'x_type_thirdparty', 'type_thirdparty'),
        ('res.partner', 'x_document_type', 'document_type'),
        ('res.partner', 'x_digit_verification', 'digit_verification'),
        ('res.partner', 'x_business_name', 'business_name'),
        ('res.partner', 'x_first_name', 'first_name'),
        ('res.partner', 'x_second_name', 'second_name'),
        ('res.partner', 'x_first_lastname', 'first_lastname'),
        ('res.partner', 'x_second_lastname', 'second_lastname'),
        ('res.partner', 'x_digit_verification', 'digit_verification'),
    ]

    for model, old_field_name, new_field_name in fields_to_rename:
        if env['ir.model.fields'].search([('model', '=', model), ('name', '=', old_field_name)]):
            env.cr.execute(f'ALTER TABLE {model.replace(".", "_")} RENAME COLUMN {old_field_name} TO {new_field_name}')