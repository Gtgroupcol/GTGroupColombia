# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def pre_migrate(cr, version):
    """Pre-migration: Clean up dian_tax_type references before schema changes"""
    try:
        # Remove constraint if it exists
        cr.execute("""
            ALTER TABLE account_tax 
            DROP CONSTRAINT IF EXISTS account_tax_dian_tax_type_id_fkey
        """)
        _logger.info("Dropped account_tax_dian_tax_type_id_fkey constraint")
    except Exception as e:
        _logger.warning(f"Could not drop constraint: {e}")
    
    try:
        # Set all references to NULL
        cr.execute("""
            UPDATE account_tax 
            SET dian_tax_type_id = NULL 
            WHERE dian_tax_type_id IS NOT NULL
        """)
        _logger.info("Cleaned up dian_tax_type references")
    except Exception as e:
        _logger.warning(f"Could not clean up references: {e}")
