def migrate(cr, version):
    """Elimina vistas, acciones y menús del módulo antes de la migración 18→17"""
    if not version:
        return

    module = 'tax_base_threshold'

    # Eliminar menús
    cr.execute("""
        DELETE FROM ir_ui_menu
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = %s AND model = 'ir.ui.menu'
        )
    """, (module,))

    # Eliminar acciones
    cr.execute("""
        DELETE FROM ir_act_window
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = %s AND model = 'ir.actions.act_window'
        )
    """, (module,))

    # Eliminar vistas
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = %s AND model = 'ir.ui.view'
        )
    """, (module,))

    # Limpiar ir_model_data de los registros eliminados
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = %s
        AND model IN ('ir.ui.view', 'ir.actions.act_window', 'ir.ui.menu')
    """, (module,))
