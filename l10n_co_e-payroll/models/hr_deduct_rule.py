from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, date
import logging

_logger = logging.getLogger(__name__)

class HrDeductRule(models.Model):
    _name = 'hr.deduct.rule'
    _description = 'Deduct Rule'
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char(required=True, string='Nombre')
    code = fields.Char(required=True, string='Código')
    sub_element = fields.Boolean(string='Sub Elemento')
    sequence = fields.Integer(
        string='Sequence',
        required=True
    )
    has_quantity = fields.Boolean('Tiene Cantidad')
    has_dates = fields.Boolean('Tiene Fechas')
    has_times = fields.Boolean('Tiene Horas')
    has_rate = fields.Boolean('Tiene Porcentaje')
    has_amount = fields.Boolean('Tiene Monto')
    has_ns_value = fields.Boolean('Tiene Valor No Salarial')
    has_description = fields.Boolean('Tiene Descripción')
    has_extra_values = fields.Boolean('Tiene Valores Adicionales')
    is_nodo_text = fields.Boolean(string='Tiene text Nodo')
    # Atributos XML
    xml_structure = fields.Selection([
        ('simple', 'Valor Simple'),          # <Dotacion>0.00</Dotacion>
        ('attributes', 'Con Atributos'),     # <Basico DiasTrabajados="0" />
        ('parent', 'Nodo Padre'),           # <Bonificaciones>
        ('child', 'Nodo Hijo')              # <Bonificacion> dentro de <Bonificaciones>
    ], string='Estructura XML', required=True)
    xml_tag = fields.Char('Etiqueta XML')
    xml_attributes = fields.Char('Atributos XML')
    xml_child_tag = fields.Char('Etiqueta Hijo XML')
    # Campos adicionales para deducciones específicas
    deduction_type = fields.Selection([
        ('salud', 'Salud'),
        ('pension', 'Pensión'),
        ('fondo_sp', 'Fondo de Solidaridad Pensional'),
        ('sindicato', 'Sindicato'),
        ('sancion', 'Sanción'),
        ('libranza', 'Libranza'),
        ('embargo', 'Embargo Fiscal'),
        ('otra', 'Otra Deducción')
    ], string='Tipo de Deducción')
    
    base_percentage = fields.Float(
        string='Porcentaje Base',
        help='Porcentaje base para la deducción (ej: 4% para salud)',
        digits=(5, 2)
    )

    requires_third_party = fields.Boolean(
        string='Requiere Tercero',
        help='Indica si la deducción requiere un tercero (ej: libranzas)'
    )

    requires_description = fields.Boolean(
        string='Requiere Descripción',
        help='Indica si la deducción requiere una descripción adicional'
    )

    complete_name = fields.Char(
        'Complete Name', 
        compute='_compute_complete_name',
        recursive=True,
        store=True
    )

    display_name = fields.Char(
        string='Nombre a Mostrar',
        compute='_compute_display_name',
        store=True,
        index=True
    )

    parent_id = fields.Many2one(
        'hr.deduct.rule',
        'Categoría principal',
        index=True,
        ondelete='cascade'
    )
    parent_path = fields.Char(index=True)
    child_id = fields.One2many('hr.deduct.rule', 'parent_id', 'Child Categories')
    attributes = fields.Char(
        string='Atributos XML',
        help='Lista de atributos XML separados por comas que debe tener este elemento'
    )
    # Campos para estructura XML
    xml_node_type = fields.Selection([
        ('single', 'Nodo Simple'),           # Para <Dotacion>0.00</Dotacion>
        ('parent', 'Nodo Padre'),            # Para <Bonificaciones>
        ('child', 'Nodo Hijo'),              # Para <Bonificacion> dentro de <Bonificaciones>
        ('composite', 'Nodo Compuesto')      # Para <Transporte AuxilioTransporte="0.0" .../>
    ], string='Tipo de Nodo XML', required=True, default='single')

    parent_rule_id = fields.Many2one('hr.accrued.rule', 'Regla Padre',
        help='Regla padre donde se agruparán los valores')

    # Campos para agrupación y totalización
    accumulates_lines = fields.Boolean('Acumula Líneas',
        help='Indica si múltiples líneas deben sumarse')
        

    @api.depends('xml_node_type', 'parent_rule_id')
    def _compute_xml_node_name(self):
        """Computa el nombre del nodo XML basado en su tipo y jerarquía."""
        for rule in self:
            if rule.xml_node_type == 'child' and rule.parent_rule_id:
                # Si es un nodo hijo, usa el nombre singular del padre
                parent_name = rule.parent_rule_id.name
                if parent_name.endswith('s'):
                    rule.xml_node_name = parent_name[:-1]
                else:
                    rule.xml_node_name = parent_name
            else:
                rule.xml_node_name = rule.name

    def get_xml_attributes(self):
        """Retorna la lista de atributos XML para esta regla"""
        self.ensure_one()
        if self.attributes:
            return self.attributes.split(',')
        return []

    # @api.constrains('attributes', 'is_multi_nodo', 'is_nodo_text')
    # def _check_attributes(self):
    #     """Valida que los atributos sean consistentes con el tipo de nodo"""
    #     for record in self:
    #         if record.is_nodo_text and record.attributes:
    #             raise ValidationError(_('Un nodo de texto no puede tener atributos'))
    #         if record.is_multi_nodo and not record.attributes:
    #             raise ValidationError(_('Un nodo múltiple debe tener atributos definidos'))

    def _get_concept_type(self):
        """Obtiene el tipo de concepto para el display name"""
        self.ensure_one()
        if self.deduction_type:
            return dict(self._fields['deduction_type'].selection).get(self.deduction_type, '')
        elif self.is_nodo_principal:
            return 'Categoría Principal'
        elif self.is_multi_rule:
            return 'Multiple'
        elif self.is_rate:
            return f'Porcentaje ({self.base_percentage}%)'
        return 'Concepto'

    @api.depends('name', 'code', 'parent_id.name')
    def _compute_display_name(self):
        for rule in self:
            if rule.parent_id:
                
                rule.display_name = f"{rule.parent_id.name} / {rule.name}"
            else:
                rule.display_name = rule.name


    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive categories.'))

    @api.onchange('deduction_type')
    def _onchange_deduction_type(self):
        """Establece valores por defecto según el tipo de deducción"""
        if self.deduction_type:
            # Configuración por tipo
            if self.deduction_type in ['salud', 'pension']:
                self.has_rate = True
                self.base_percentage = 4.0 if self.deduction_type == 'salud' else 4.0
                self.requires_third_party = True
                self.requires_description = False
            elif self.deduction_type == 'fondo_sp':
                self.has_rate = True
                self.requires_third_party = False
                self.requires_description = False
            elif self.deduction_type == 'libranza':
                self.has_rate = False
                self.requires_third_party = True
                self.requires_description = True
            elif self.deduction_type == 'embargo':
                self.has_rate = True
                self.requires_third_party = True
                self.requires_description = True

    @api.constrains('base_percentage')
    def _check_percentage(self):
        """Valida que el porcentaje esté en un rango válido"""
        for record in self:
            if record.has_rate and record.base_percentage:
                if record.base_percentage < 0 or record.base_percentage > 100:
                    raise ValidationError(_('El porcentaje debe estar entre 0 y 100'))