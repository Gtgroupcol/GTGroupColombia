# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)


class ir_model(models.Model):
    _inherit = 'ir.model'

    abstract = fields.Boolean('Abstract', readonly=True)

    def name_get(self):
        res = super().name_get()
        if self._context.get('is_access_rights'):
            res = []
            for model in self:
                res.append((model.id, "{} ({})".format(model.name, model.model)))
        return res


class IrModelField(models.Model):
    _inherit = 'ir.model.fields'

    def name_get(self):
        res = super().name_get()
        if self._context.get('is_access_rights'):
            res = []
            for field in self:
                res.append(
                    (field.id, "{} => {} ({})".format(field.field_description, field.name, field.model_id.model)))
        return res


class ir_module_module(models.Model):
    _inherit = 'ir.module.module'

    def _button_immediate_function(self, function):
        res = super(ir_module_module, self)._button_immediate_function(function)
        if function.__name__ in ['button_install', 'button_upgrade']:
            for record in self.env['ir.model'].search([]):
                if record.name == 'Email Thread':
                    pass
                # Verificar que el modelo existe en el registro antes de acceder a él
                if record.model in self.env.registry:
                    try:
                        record.abstract = self.env[record.model]._abstract
                    except Exception as e:
                        # Log del error pero continuar con otros modelos
                        _logger.warning("No se pudo acceder al modelo %s: %s", record.model, str(e))
                else:
                    # El modelo no está disponible en el registro actual
                    _logger.warning("Modelo %s no encontrado en el registro, saltando...", record.model)
        return res
