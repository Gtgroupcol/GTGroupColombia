from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError

class HrAccruedRule(models.Model):
    _name = "hr.accrued.rule"
    _description = "Accrued Rule"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'sequence'

    name = fields.Char(required=True, string='Nombre')
    code = fields.Char(required=True, string='Código')
    sequence = fields.Integer(string='Sequence', required=True)
    active = fields.Boolean(default=True)
    parent_id = fields.Many2one('hr.accrued.rule', 'Categoría principal', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True)
    child_id = fields.One2many('hr.accrued.rule', 'parent_id', 'Reglas Hijas')

    # Control de estructura XML
    rule_type = fields.Selection([
        # Valores simples
        ('simple_amount', 'Monto Simple'),        
        ('simple_with_dates', 'Con Fechas'),         
        ('simple_with_description', 'Con Descripción'),
        # Montos básicos
        ('basic', 'Básico'),                       
        ('transport', 'Transporte'),             

        # Horas extras
        ('hed', 'HED - Extra Diurna'),
        ('hen', 'HEN - Extra Nocturna'),
        ('hrn', 'HRN - Recargo Nocturno'),
        ('heddf', 'HEDDF - Extra Diurna D/F'),
        ('hendf', 'HENDF - Extra Nocturna D/F'),
        ('hrddf', 'HRDDF - Recargo Diurno D/F'),
        ('hrndf', 'HRNDF - Recargo Nocturno D/F'),

        # Ausencias y licencias
        ('vacation_common', 'Vacaciones Comunes'),
        ('vacation_compensated', 'Vacaciones Compensadas'),
        ('incapacity', 'Incapacidad'),
        ('license_mp', 'Licencia Maternidad/Paternidad'),
        ('license_r', 'Licencia Remunerada'),
        ('license_nr', 'Licencia No Remunerada'),

        # Pagos especiales
        ('prima', 'Prima'),
        ('cesantia', 'Cesantía'),
        ('cesantia_interest', 'Intereses Cesantía'),
        ('bonus', 'Bonificación'),
        ('aid', 'Auxilio'),
        ('commission', 'Comisión'),
        ('compensation', 'Compensación'),
        ('bono_epctv', 'Bono EPCTV'),

        # Otros conceptos
        ('third_party', 'Pago Tercero'),
        ('advance', 'Anticipo'),
        ('endowment', 'Dotación'),
        ('support', 'Apoyo Sostenimiento'),
        ('telework', 'Teletrabajo'),
        ('retirement_bonus', 'Bonificación Retiro'),
        ('indemnity', 'Indemnización'),
        ('refund', 'Reintegro'),
        ('legal_strike', 'Huelga Legal'),
        ('other_concept', 'Otro Concepto')
    ], string='Tipo de Regla')

    xml_structure = fields.Selection([
        ('simple', 'Valor Simple'),          # <Dotacion>0.00</Dotacion>
        ('attributes', 'Con Atributos'),     # <Basico DiasTrabajados="0" />
        ('parent', 'Nodo Padre'),           # <Bonificaciones>
        ('child', 'Nodo Hijo')              # <Bonificacion> dentro de <Bonificaciones>
    ], string='Estructura XML', required=True)

    # Control de valores
    has_quantity = fields.Boolean('Tiene Cantidad')
    has_dates = fields.Boolean('Tiene Fechas')
    has_times = fields.Boolean('Tiene Horas')
    has_rate = fields.Boolean('Tiene Porcentaje')
    has_amount = fields.Boolean('Tiene Monto')
    has_ns_value = fields.Boolean('Tiene Valor No Salarial')
    has_description = fields.Boolean('Tiene Descripción')
    has_extra_values = fields.Boolean('Tiene Valores Adicionales')
    is_nodo_text = fields.Boolean(string='Tiene text Nodo')
    # Valores específicos
    overtime_percentage = fields.Float('Porcentaje Hora Extra', digits=(16, 2))
    incapacity_type = fields.Selection([
        ('1', 'Común'),
        ('2', 'Profesional'),
        ('3', 'Laboral')
    ], string='Tipo de Incapacidad')

    # Atributos XML
    xml_tag = fields.Char('Etiqueta XML')
    xml_attributes = fields.Char('Atributos XML')
    xml_child_tag = fields.Char('Etiqueta Hijo XML')

    # Campos computados
    complete_name = fields.Char(
        'Complete Name', compute='_compute_complete_name', 
        recursive=True, store=True)
    display_name = fields.Char(
        'Display Name', compute='_compute_display_name', 
        store=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'El código debe ser único!')
    ]

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for rule in self:
            if rule.parent_id:
                rule.complete_name = f"{rule.parent_id.complete_name} / {rule.name}"
            else:
                rule.complete_name = rule.name

    @api.depends('name', 'code', 'parent_id.name', 'overtime_percentage')
    def _compute_display_name(self):
        for rule in self:
            name = rule.name 
            if rule.overtime_percentage:
                name = f"{name} ({rule.overtime_percentage}%)"
            
            if rule.parent_id:
                rule.display_name = f"{rule.code} - {rule.parent_id.name} / {name}"
            else:
                rule.display_name = name

    @api.model_create_multi
    def create(self, vals_list):
        """Configura valores por defecto según el tipo de regla"""
        for vals in vals_list:
            if vals.get('rule_type'):
                self._set_default_values(vals)
        return super().create(vals_list)

    def _set_default_values(self, vals):
        """Establece valores por defecto según el tipo de regla"""
        rule_type = vals.get('rule_type')
        configs = self._get_rule_configs()
        if rule_type in configs:
            vals.update(configs[rule_type])

    @api.model
    def _get_rule_configs(self):
        """Retorna la configuración completa para cada tipo de regla"""
        return {
            # Configuraciones básicas
            'basic': {
                'xml_structure': 'attributes',
                'xml_tag': 'Basico',
                'xml_attributes': 'DiasTrabajados,SueldoTrabajado',
                'has_quantity': True,
                'has_amount': True
            },
            'transport': {
                'xml_structure': 'attributes',
                'xml_tag': 'Transporte',
                'xml_attributes': 'AuxilioTransporte,ViaticoManuAlojS,ViaticoManuAlojNS',
                'has_amount': True,
                'has_ns_value': True
            },

            # Configuraciones de horas extras
            'hed': {
                'xml_structure': 'child',
                'xml_tag': 'HEDs',
                'xml_child_tag': 'HED',
                'xml_attributes': 'HoraInicio,HoraFin,Cantidad,Porcentaje,Pago',
                'has_times': True,
                'has_quantity': True,
                'has_rate': True,
                'has_amount': True,
                'overtime_percentage': 25.00
            },
            'hen': {
                'xml_structure': 'child',
                'xml_tag': 'HENs',
                'xml_child_tag': 'HEN',
                'xml_attributes': 'HoraInicio,HoraFin,Cantidad,Porcentaje,Pago',
                'has_times': True,
                'has_quantity': True,
                'has_rate': True,
                'has_amount': True,
                'overtime_percentage': 75.00
            },
            'hrn': {
                'xml_structure': 'child',
                'xml_tag': 'HRNs',
                'xml_child_tag': 'HRN',
                'xml_attributes': 'HoraInicio,HoraFin,Cantidad,Porcentaje,Pago',
                'has_times': True,
                'has_quantity': True,
                'has_rate': True,
                'has_amount': True,
                'overtime_percentage': 35.00
            },
            'heddf': {
                'xml_structure': 'child',
                'xml_tag': 'HEDDFs',
                'xml_child_tag': 'HEDDF',
                'xml_attributes': 'HoraInicio,HoraFin,Cantidad,Porcentaje,Pago',
                'has_times': True,
                'has_quantity': True,
                'has_rate': True,
                'has_amount': True,
                'overtime_percentage': 100.00
            },

            # Configuraciones de vacaciones
            'vacation_common': {
                'xml_structure': 'parent',
                'xml_tag': 'Vacaciones',
                'xml_child_tag': 'VacacionesComunes',
                'xml_attributes': 'FechaInicio,FechaFin,Cantidad,Pago',
                'has_dates': True,
                'has_quantity': True,
                'has_amount': True
            },
            'vacation_compensated': {
                'xml_structure': 'parent',
                'xml_tag': 'Vacaciones',
                'xml_child_tag': 'VacacionesCompensadas',
                'xml_attributes': 'Cantidad,Pago',
                'has_quantity': True,
                'has_amount': True
            },

            # Configuraciones de primas y cesantías
            'prima': {
                'xml_structure': 'attributes',
                'xml_tag': 'Primas',
                'xml_attributes': 'Cantidad,Pago,PagoNS',
                'has_quantity': True,
                'has_amount': True,
                'has_ns_value': True
            },
            'cesantia': {
                'xml_structure': 'attributes',
                'xml_tag': 'Cesantias',
                'xml_attributes': 'Pago',
                'has_amount': True
            },
            'cesantia_interest': {
                'xml_structure': 'attributes',
                'xml_tag': 'Cesantias',
                'xml_attributes': 'Porcentaje,PagoIntereses',
                'has_rate': True,
                'has_amount': True
            },

            # Configuraciones de incapacidades y licencias
            'incapacity': {
                'xml_structure': 'child',
                'xml_tag': 'Incapacidades',
                'xml_child_tag': 'Incapacidad',
                'xml_attributes': 'FechaInicio,FechaFin,Cantidad,Tipo,Pago',
                'has_dates': True,
                'has_quantity': True,
                'has_amount': True
            },
            'license_mp': {
                'xml_structure': 'child',
                'xml_tag': 'Licencias',
                'xml_child_tag': 'LicenciaMP',
                'xml_attributes': 'FechaInicio,FechaFin,Cantidad,Pago',
                'has_dates': True,
                'has_quantity': True,
                'has_amount': True
            },
            'license_r': {
                'xml_structure': 'child',
                'xml_tag': 'Licencias',
                'xml_child_tag': 'LicenciaR',
                'xml_attributes': 'FechaInicio,FechaFin,Cantidad,Pago',
                'has_dates': True,
                'has_quantity': True,
                'has_amount': True
            },
            'license_nr': {
                'xml_structure': 'child',
                'xml_tag': 'Licencias',
                'xml_child_tag': 'LicenciaNR',
                'xml_attributes': 'FechaInicio,FechaFin,Cantidad',
                'has_dates': True,
                'has_quantity': True
            },

            # Configuraciones de bonificaciones y auxilios
            'bonus': {
                'xml_structure': 'child',
                'xml_tag': 'Bonificaciones',
                'xml_child_tag': 'Bonificacion',
                'xml_attributes': 'BonificacionS,BonificacionNS',
                'has_amount': True,
                'has_ns_value': True
            },
            'aid': {
                'xml_structure': 'child',
                'xml_tag': 'Auxilios',
                'xml_child_tag': 'Auxilio',
                'xml_attributes': 'AuxilioS,AuxilioNS',
                'has_amount': True,
                'has_ns_value': True
            },

            # Configuraciones de huelgas y otros conceptos
            'legal_strike': {
                'xml_structure': 'child',
                'xml_tag': 'HuelgasLegales',
                'xml_child_tag': 'HuelgaLegal',
                'xml_attributes': 'FechaInicio,FechaFin,Cantidad',
                'has_dates': True,
                'has_quantity': True
            },
            'other_concept': {
                'xml_structure': 'child',
                'xml_tag': 'OtrosConceptos',
                'xml_child_tag': 'OtroConcepto',
                'xml_attributes': 'DescripcionConcepto,ConceptoS,ConceptoNS',
                'has_description': True,
                'has_amount': True,
                'has_ns_value': True
            },

            # Configuraciones de compensaciones
            'compensation': {
                'xml_structure': 'child',
                'xml_tag': 'Compensaciones',
                'xml_child_tag': 'Compensacion',
                'xml_attributes': 'CompensacionO,CompensacionE',
                'has_amount': True,
                'has_extra_values': True
            },

            # Configuraciones de bonos EPCTV
            'bono_epctv': {
                'xml_structure': 'child',
                'xml_tag': 'BonoEPCTVs',
                'xml_child_tag': 'BonoEPCTV',
                'xml_attributes': 'PagoS,PagoNS,PagoAlimentacionS,PagoAlimentacionNS',
                'has_amount': True,
                'has_ns_value': True,
                'has_extra_values': True
            },

            # Configuraciones de comisiones y pagos
            'commission': {
                'xml_structure': 'child',
                'xml_tag': 'Comisiones',
                'xml_child_tag': 'Comision',
                'has_amount': True,
                'is_nodo_text': True
            },
            'third_party': {
                'xml_structure': 'child',
                'xml_tag': 'PagosTerceros',
                'xml_child_tag': 'PagoTercero',
                'has_amount': True,
                'is_nodo_text': True
            },
            'advance': {
                'xml_structure': 'child',
                'xml_tag': 'Anticipos',
                'xml_child_tag': 'Anticipo',
                'has_amount': True,
                'is_nodo_text': True
            },

            # Configuraciones de elementos simples
            'endowment': {
                'xml_structure': 'simple',
                'xml_tag': 'Dotacion',
                'has_amount': True,
                'is_nodo_text': True
            },
            'support': {
                'xml_structure': 'simple',
                'xml_tag': 'ApoyoSost',
                'has_amount': True,
                'is_nodo_text': True
            },
            'telework': {
                'xml_structure': 'simple',
                'xml_tag': 'Teletrabajo',
                'has_amount': True,
                'is_nodo_text': True
            },
            'retirement_bonus': {
                'xml_structure': 'simple',
                'xml_tag': 'BonifRetiro',
                'has_amount': True,
                'is_nodo_text': True
            },
            'indemnity': {
                'xml_structure': 'simple',
                'xml_tag': 'Indemnizacion',
                'has_amount': True,
                'is_nodo_text': True
            },
            'refund': {
                'xml_structure': 'simple',
                'xml_tag': 'Reintegro',
                'has_amount': True,
                'is_nodo_text': True
            }
        }

    def get_xml_attributes(self):
        """Obtiene la lista de atributos XML para la regla"""
        self.ensure_one()
        if self.xml_attributes:
            return self.xml_attributes.split(',')
        return []

    @api.constrains('rule_type', 'xml_structure')
    def _check_xml_structure(self):
        """Valida que la estructura XML sea consistente con el tipo de regla"""
        for rule in self:
            if not rule.xml_structure:
                raise ValidationError(_('Debe definir la estructura XML para la regla'))


    def validate_xml_structure(self):
        """Valida que la estructura XML sea correcta según el tipo de regla"""
        self.ensure_one()
        
        if not self.xml_tag:
            raise ValidationError(_('La regla debe tener una etiqueta XML definida'))

        if self.xml_structure == 'child' and not self.xml_child_tag:
            raise ValidationError(_('Las reglas con estructura hijo deben tener definida la etiqueta del hijo'))

        if self.xml_structure == 'attributes' and not self.xml_attributes:
            raise ValidationError(_('Las reglas con atributos deben tener definidos los atributos XML'))

        if self.has_dates and not ('FechaInicio' in self.xml_attributes and 'FechaFin' in self.xml_attributes):
            raise ValidationError(_('Las reglas con fechas deben incluir FechaInicio y FechaFin en sus atributos'))

        if self.has_times and not ('HoraInicio' in self.xml_attributes and 'HoraFin' in self.xml_attributes):
            raise ValidationError(_('Las reglas con horas deben incluir HoraInicio y HoraFin en sus atributos'))

        if self.has_quantity and not 'Cantidad' in self.xml_attributes:
            raise ValidationError(_('Las reglas con cantidad deben incluir Cantidad en sus atributos'))

        if self.has_rate and not 'Porcentaje' in self.xml_attributes:
            raise ValidationError(_('Las reglas con porcentaje deben incluir Porcentaje en sus atributos'))

        return True

    def get_xml_values(self, line):
        """Obtiene los valores para el XML basado en la línea de nómina"""
        self.ensure_one()
        values = {}
        
        if self.has_dates:
            values.update({
                'FechaInicio': line.fecha_inicio,
                'FechaFin': line.fecha_fin
            })

        if self.has_times:
            values.update({
                'HoraInicio': line.hora_inicio,
                'HoraFin': line.hora_fin
            })

        if self.has_quantity:
            values['Cantidad'] = line.cantidad

        if self.has_rate:
            values['Porcentaje'] = line.porcentaje or self.overtime_percentage

        if self.has_amount:
            values['Pago'] = line.amount

        if self.has_ns_value:
            values[f"{self.code}NS"] = line.amount_ns

        if self.has_description:
            values['DescripcionConcepto'] = line.description

        return values