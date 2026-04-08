# -*- coding: utf-8 -*-

import logging
from os.path import join, dirname, realpath
from odoo import api, SUPERUSER_ID, tools

#from . import controllers
from . import models


_logger = logging.getLogger(__name__)


# def _setup_tax_type(cr, registry):
def post_init_hook(env):
    # Código unspcs
    #_load_unspsc_codes(env)
    _assign_codes_uom(env)
    
    # Clean up dian_tax_type references to avoid constraint issues
    try:
        env.cr.execute("""
            UPDATE account_tax 
            SET dian_tax_type_id = NULL 
            WHERE dian_tax_type_id IS NOT NULL
        """)
        env.cr.commit()
        _logger.info("Cleaned up dian_tax_type references from account_tax")
    except Exception as e:
        _logger.warning(f"Could not clean up dian_tax_type references: {e}")

    # Asignar tipo de impuestos
    # env = api.Environment(env, SUPERUSER_ID, {})
    # chart_template = env.ref(
    #     'l10n_co.l10n_co_chart_template_generic', raise_if_not_found=False)
    # if chart_template:
    #     companies = env['res.company'].search(
    #         [('chart_template_id', '=', chart_template.id)]
    #     )
        # tax_templates = env['account.tax.template'].search(
        #     [('chart_template_id', '=', chart_template.id),
        #      ('type_tax_use', '=', 'sale'),
        #      ('dian_tax_type_id', '!=', False)]
        # )
        # xml_ids = tax_templates.get_external_id()
        # for company in companies:
        #     for tax_template in tax_templates:
        #         module, xml_id = xml_ids.get(tax_template.id).split('.')
        #         tax = env.ref(
        #             '%s.%s_%s' % (module, company.id, xml_id),
        #             raise_if_not_found=False
        #         )
        #         if tax:
        #             tax.dian_tax_type_id = tax_template.dian_tax_type_id


# def post_init_hook(cr, registry):
#     _load_unspsc_codes(cr, registry)
#     _assign_codes_uom(cr, registry)

def uninstall_hook(env):
    env.cr.execute("DELETE FROM product_unspsc_code;")
    env.cr.execute("DELETE FROM ir_model_data WHERE model='product_unspsc_code';")


# def _load_unspsc_codes(env):
#     """Import CSV data as it is faster than xml and because we can't use
#     noupdate anymore with csv
#     Even with the faster CSVs, it would take +30 seconds to load it with
#     the regular ORM methods, while here, it is under 3 seconds
#     """
#     csv_path = join(dirname(realpath(__file__)), 'data',
#                     'product.unspsc.code.csv')
#     with tools.misc.file_open(csv_path, 'rb') as csv_file:
#         csv_file.readline() # Read the header, so we avoid copying it to the db
#         env.cr.copy_expert(
#             """COPY product_unspsc_code (code, name, applies_to, active)
#                FROM STDIN WITH DELIMITER '|'""", csv_file)
#     # Create xml_id, to allow make reference to this data
#     env.cr.execute(
#         """INSERT INTO ir_model_data
#            (name, res_id, module, model, noupdate)
#            SELECT concat('unspsc_code_', code), id, 'l10n_co_data_bloodo', 'product.unspsc.code', 't'
#            FROM product_unspsc_code""")


def _assign_codes_uom(env):
    """Assign the codes in UoM of each data, this is here because the data is
    created in the last method"""
    pass
    # tools.convert.convert_file(
    #     env, 'l10n_co_data_bloodo', 'data/uom_data.xml', None, mode='init',
    #     kind='data')
