# -*- coding: utf-8 -*-

from odoo import fields, models, _ , api, Command
from datetime import datetime, timedelta, date, time
from collections import defaultdict
import logging
import xmltodict
import re
_logger = logging.getLogger(__name__)

    # Definición del orden exacto según estructura XML
XML_STRUCTURE_ORDER = {
    'devengados': [
        'Basico',
        'Transporte',
        'HEDs',
        'HENs',
        'HRNs',
        'HEDDFs',
        'HRDDFs',
        'HENDFs',
        'HRNDFs',
        'Vacaciones',
        'Primas',
        'Cesantias',
        'Incapacidades',
        'Licencias',
        'Bonificaciones',
        'Auxilios',
        'HuelgasLegales',
        'OtrosConceptos',
        'Compensaciones',
        'BonoEPCTVs',
        'Comisiones',
        'PagosTerceros',
        'Anticipos',
        'Dotacion',
        'ApoyoSost',
        'Teletrabajo',
        'BonifRetiro',
        'Indemnizacion',
        'Reintegro'
    ],
    'deducciones': [
        'Salud',
        'FondoPension',
        'FondoSP',
        'Sindicatos',
        'Sanciones',
        'Libranzas',
        'PagosTerceros',
        'Anticipos',
        'OtrasDeducciones',
        'PensionVoluntaria',
        'RetencionFuente',
        'AFC',
        'Cooperativa',
        'EmbargoFiscal',
        'PlanComplementarios',
        'Educacion',
        'Reintegro',
        'Deuda'
    ]
}

CONCEPT_STRUCTURE = {
    # Devengados repetibles
    'HED': {'parent': 'HEDs', 'requires_hours': True, 'sequence': 30},
    'HEN': {'parent': 'HENs', 'requires_hours': True, 'sequence': 40},
    'HRN': {'parent': 'HRNs', 'requires_hours': True, 'sequence': 50},
    'HEDDF': {'parent': 'HEDDFs', 'requires_hours': True, 'sequence': 60},
    'HRDDF': {'parent': 'HRDDFs', 'requires_hours': True, 'sequence': 70},
    'HENDF': {'parent': 'HENDFs', 'requires_hours': True, 'sequence': 80},
    'HRNDF': {'parent': 'HRNDFs', 'requires_hours': True, 'sequence': 90},
    'VacacionesComunes': {'parent': 'Vacaciones', 'requires_dates': True, 'sequence': 100},
    'VacacionesCompensadas': {'parent': 'Vacaciones', 'sequence': 100},
    'Incapacidad': {'parent': 'Incapacidades', 'requires_dates': True, 'sequence': 130},
    'LicenciaMP': {'parent': 'Licencias', 'requires_dates': True, 'sequence': 140},
    'LicenciaR': {'parent': 'Licencias', 'requires_dates': True, 'sequence': 140},
    'LicenciaNR': {'parent': 'Licencias', 'requires_dates': True, 'sequence': 140},
    'Bonificacion': {'parent': 'Bonificaciones', 'sequence': 150},
    'Auxilio': {'parent': 'Auxilios', 'sequence': 160},
    'HuelgaLegal': {'parent': 'HuelgasLegales', 'requires_dates': True, 'sequence': 170},
    'OtroConcepto': {'parent': 'OtrosConceptos', 'requires_description': True, 'sequence': 180},

    # Devengados únicos
    'Basico': {'sequence': 10},
    'Transporte': {'sequence': 20},
    'Primas': {'sequence': 110},
    'Cesantias': {'sequence': 120},
    'Compensacion': {'sequence': 190},
    'BonoEPCTV': {'sequence': 200},
    'Comision': {'sequence': 210},
    'PagoTercero': {'sequence': 220},
    'Anticipo': {'sequence': 230},
    'Dotacion': {'sequence': 240},
    'ApoyoSost': {'sequence': 250},
    'Teletrabajo': {'sequence': 260},
    'BonifRetiro': {'sequence': 270},
    'Indemnizacion': {'sequence': 280},
    'Reintegro': {'sequence': 290},

    # Deducciones
    'Salud': {'sequence': 300},
    'FondoPension': {'sequence': 310},
    'FondoSP': {'sequence': 320},
    'Sindicato': {'parent': 'Sindicatos', 'sequence': 330},
    'Sancion': {'parent': 'Sanciones', 'sequence': 340},
    'Libranza': {'parent': 'Libranzas', 'requires_description': True, 'sequence': 350},
    'OtraDeduccion': {'parent': 'OtrasDeducciones', 'sequence': 390}
}


class HrPaySlip(models.Model):
    _name = 'hr.payslip.edi'
    _inherit = ['hr.payslip.edi', 'hr.payslip.abstract']

    nes_dev_line_ids = fields.One2many('hr.payslip.nes.line', 'slip_id2', string='Reglas Nomina Electronica', readonly=True)
    nes_ded_line_ids = fields.One2many('hr.payslip.nes.line.ded', 'slip_id2', string='Reglas Nomina Electronica', readonly=True)
    refusal_reason = fields.Text('Motivo/s de rechazo', compute="_compute_refusal")
    
    @api.depends('state_dian', 'xml_response_dian')
    def _compute_refusal(self):
        for rec in self:
            if rec.state_dian == 'rechazado':
                rec.refusal_reason = []
                pattern = r'<c:string>(.*?)<\/c:string>'
                matches = re.findall(pattern, rec.xml_response_dian)
                if matches:
                    rec.refusal_reason = matches
            else:
                rec.refusal_reason = []

    def get_field_move(self):
        if hasattr(self, 'partner_id'):
            return True
        elif hasattr(self, 'employee_id'):
            return False

    def hook_mail_template(self):
        return "l10n_co_e-payroll_ee.email_template_hr_payslip"

    def refund_sheet(self):
        for payslip in self:
            # dian_constants = self._get_dian_constants()
            # template_basic_data_nomina_individual_xml = self._template_nomina_individual(
            #     dian_constants
            # )
            # payslip.xml_sended = template_basic_data_nomina_individual_xml  
            #payslip.current_cune = payslip.ZipKey 
            copied_payslip = payslip.copy(
                {"credit_note": True, "name": _("Refund: %s") % payslip.name}
            )
            number = copied_payslip.number or self.env["ir.sequence"].next_by_code(
                "salary.slip.note"
            )
            copied_payslip.write({"number": number, 'previous_cune': payslip.current_cune, 'type_note': '2'})
            #payslip.pay_refund = copied_payslip.id
            #copied_payslip.compute_sheet()
            #copied_payslip.action_payslip_done()
        formview_ref = self.env.ref('epayroll.view_hr_payslip_edi_form', False)
        treeview_ref = self.env.ref('epayroll.view_hr_payslip_edi_tree', False)
        return {
            "name": ("Refund Payslip"),
            "view_mode": "tree, form",
            "view_id": False,
            "res_model": "hr.payslip.edi",
            "type": "ir.actions.act_window",
            "target": "current",
            "domain": "[('id', 'in', %s)]" % copied_payslip.ids,
            "views": [
                (treeview_ref and treeview_ref.id or False, "tree"),
                (formview_ref and formview_ref.id or False, "form"),
            ],
            "context": {},
        }

    def compute_sheet_nes(self):
        """Método principal para computar las líneas de nómina electrónica"""
        for payslip in self:
            # Limpiar líneas existentes
            payslip.write({
                'nes_dev_line_ids': [Command.clear()],
                'nes_ded_line_ids': [Command.clear()]
            })

            # Obtener datos agrupados
            devengos, deducciones = payslip._get_grouped_data_orm()
            
            # Crear líneas
            payslip._create_nes_lines(devengos, deducciones)
            payslip.state = 'verify'
        return True

    def _get_xml_structure(self):
        """Obtiene la estructura XML y sus relaciones usando ORM"""
        fields_to_get = [
            'id', 'code', 'name', 'xml_tag', 'xml_child_tag',
            'xml_structure', 'parent_id', 'sequence', 'has_times',
            'has_dates', 'has_amount', 'has_rate', 'has_quantity'
        ]

        accrued_rules = self.env['hr.accrued.rule'].search_read(
            domain=[('xml_tag', '!=', False)],
            fields=fields_to_get,
            order='sequence'
        )

        deduct_rules = self.env['hr.deduct.rule'].search_read(
            domain=[('xml_tag', '!=', False)],
            fields=fields_to_get,
            order='sequence'
        )

        all_rules = {}
        for rule in accrued_rules + deduct_rules:
            all_rules[rule['id']] = {
                'id': rule['id'],
                'code': rule['code'],
                'name': rule['name'],
                'xml_tag': rule['xml_tag'],
                'xml_child_tag': rule['xml_child_tag'],
                'xml_structure': rule['xml_structure'],
                'parent_id': rule['parent_id'] and rule['parent_id'][0],
                'sequence': rule['sequence'],
                'has_times': rule['has_times'],
                'has_dates': rule['has_dates'],
                'has_amount': rule['has_amount'],
                'has_rate': rule['has_rate'],
                'has_quantity': rule['has_quantity'],
            }

        return all_rules

    def _get_grouped_data_orm(self):
        """Obtiene datos agrupados usando ORM con estructura XML"""
        xml_structure = self._get_xml_structure()
        devengos = {}
        deducciones = {}

        # Obtener líneas relevantes
        lines = self.line_ids.filtered(
            lambda x: (x.salary_rule_id.devengado_rule_id or x.salary_rule_id.deduccion_rule_id)
        )

        # Procesar líneas
        for line in lines:
            rule = line.salary_rule_id
            
            # Datos base de la línea
            line_data = {
                'salary_rule_id': rule.id,
                'name': str(line.name),
                'code': line.salary_rule_id.devengado_rule_id.code or line.salary_rule_id.deduccion_rule_id.code,
                'contract_id': line.contract_id.id,
                'employee_id': line.employee_id.id,
                'quantity': float(line.quantity),
                'amount': float(abs(line.amount)),
                'rate': float(line.rate),
                'total': float(abs(line.total)),
                'departure_date': line.initial_accrual_date,
                'return_date': line.final_accrual_date,
                'leave_id': line.leave_id.id if line.leave_id else False,
            }

            if rule.devengado_rule_id:
                dev_rule = rule.devengado_rule_id
                xml_info = xml_structure.get(dev_rule.id, {})
                
                # Agregar secuencia según estructura XML
                line_data['sequence'] = xml_info.get('sequence', 999)
                
                # Manejo de horas extra si aplica
                if xml_info.get('has_times'):
                    line_data['rate'] = self._get_type_overtime(rule.id)
                
                # Determinar dónde insertar según estructura XML
                xml_tag = xml_info.get('xml_tag')
                if not xml_tag:
                    continue

                if xml_info.get('xml_structure') == 'child':
                    parent_tag = xml_info.get('xml_tag')
                    if parent_tag not in devengos:
                        devengos[parent_tag] = {'lines': []}
                    devengos[parent_tag]['lines'].append(line_data)
                else:
                    # Manejo especial para Cesantías e Intereses
                    if xml_tag == 'Cesantias':
                        interes_line = self._get_interes_cesantias_line(line)
                        if interes_line:
                            line_data.update({
                                'salary_rule_id_2': interes_line.salary_rule_id.id,
                                'total_2': float(abs(interes_line.total)),
                                'rate_2': float(interes_line.rate),
                            })
                    devengos[xml_tag] = line_data

            elif rule.deduccion_rule_id:
                ded_rule = rule.deduccion_rule_id
                xml_info = xml_structure.get(ded_rule.id, {})
                
                # Agregar secuencia según estructura XML
                line_data['sequence'] = xml_info.get('sequence', 999)
                
                # Manejo del FSP
                if ded_rule.code.startswith('SSOCIAL'):
                    line_data['rate'] = float(self._get_porc_fsp(ded_rule.code))

                # Determinar dónde insertar según estructura XML
                xml_tag = xml_info.get('xml_tag')
                if not xml_tag:
                    continue

                if xml_info.get('xml_structure') == 'child':
                    parent_tag = xml_info.get('xml_tag')
                    if parent_tag not in deducciones:
                        deducciones[parent_tag] = {'lines': []}
                    deducciones[parent_tag]['lines'].append(line_data)
                else:
                    # Manejo especial para FondoSP
                    if xml_tag == 'FondoSP':
                        sub_line = self._get_fondosp_sub_line(line)
                        if sub_line:
                            line_data.update({
                                'salary_rule_id_2': sub_line.salary_rule_id.id,
                                'total_2': float(abs(sub_line.total)),
                                'rate_2': float(self._get_porc_fsp('SSOCIAL004')),
                            })
                    deducciones[xml_tag] = line_data

        # Asegurar conceptos base (Básico, Salud, Pensión)
        self._ensure_base_concepts(devengos, deducciones, xml_structure)

        return devengos, deducciones

    def _get_interes_cesantias_line(self, cesantias_line):
        """Obtiene la línea de intereses de cesantías relacionada"""
        return self.line_ids.filtered(
            lambda x: x.salary_rule_id.devengado_rule_id.code == 'InteresesCesantias'
        )[:1]

    def _get_fondosp_sub_line(self, fondosp_line):
        """Obtiene la línea subsidiaria de FondoSP"""
        return self.line_ids.filtered(
            lambda x: x.salary_rule_id.deduccion_rule_id.code == 'FondoSPSub'
        )[:1]


    def _ensure_base_concepts(self, devengos, deducciones, xml_structure):
        """Asegura que existan los conceptos base"""
        basic_codes = ['WORK100', 'COMPENSATORIO', 'WORK110']
        BASIC = self.env['hr.salary.rule'].search([('code', '=', 'BASIC')], limit=1)
        salud = self.env['hr.salary.rule'].search([('code', '=', 'SSOCIAL001')], limit=1)
        pension = self.env['hr.salary.rule'].search([('code', '=', 'SSOCIAL002')], limit=1)

        base_concepts = {
            'Basico': {
                'days': self._get_days_amount(basic_codes),
                'xml_info': next((info for info in xml_structure.values() if info['xml_tag'] == 'Basico'), {}),
                'salary_rule_id': BASIC.id,
                'code': BASIC.code,
                'is_devengo': True
            },
            'Salud': {
                'rate': 4.0,
                'xml_info': next((info for info in xml_structure.values() if info['xml_tag'] == 'Salud'), {}),
                'salary_rule_id': salud.id,
                'code': salud.code,
                'is_devengo': False
            },
            'FondoPension': {
                'rate': 4.0,
                'salary_rule_id': pension.id,
                'code': pension.code,
                'xml_info': next((info for info in xml_structure.values() if info['xml_tag'] == 'FondoPension'), {}),
                'is_devengo': False
            }
        }

        for code, data in base_concepts.items():
            if code not in (devengos if data['is_devengo'] else deducciones):
                xml_info = data['xml_info']
                line_data = {
                    'salary_rule_id': data['salary_rule_id'],
                    'code': data['code'],
                    'sequence': xml_info.get('sequence', 999),
                    'name': str(code),
                    'contract_id': self.contract_id.id,
                    'employee_id': self.employee_id.id,
                    'quantity': float(data.get('days', 1.0)),
                    'amount': 0.0,
                    'rate': float(data.get('rate', 0.0)),
                    'total': 0.0,
                }
                if data['is_devengo']:
                    devengos[code] = line_data
                else:
                    deducciones[code] = line_data

    def _get_days_amount(self, lst_codes):
        """Obtiene la cantidad de días para los códigos dados"""
        days = 0
        for entries in self.worked_days_line_ids:
            days += entries.number_of_days if entries.work_entry_type_id.code in lst_codes else 0
        return int(days)

    def _get_type_overtime(self, rule_id):
        """Obtiene el porcentaje de la hora extra"""
        return self.env['hr.type.overtime'].search(
            [('salary_rule.id', '=', rule_id)], limit=1
        ).percentage or 0.0

    def _get_porc_fsp(self, code):
        """Calcula el porcentaje FSP"""
        if code in ["SSOCIAL001", "SSOCIAL002"]:
            return 4.0

        company_id = self.company_id.id if self.company_id else None
        annual_parameters = self.env['hr.annual.parameters'].get_for_year(
            self.date_to.year, company_id=company_id, raise_if_not_found=False
        )
        if not annual_parameters:
            return 0.0

        value_base = sum(
            abs(line.total) 
            for line in self.line_ids 
            if line.salary_rule_id.category_id.code in ['DEV_SALARIAL'] or 
               (line.salary_rule_id.category_id.parent_id and 
                line.salary_rule_id.category_id.parent_id.code == 'DEV_SALARIAL')
        )

        smmlv_ratio = value_base / annual_parameters.smmlv_monthly

        if code == "SSOCIAL004" and smmlv_ratio >= 4:
            return 0.5

        if code == "SSOCIAL003":
            if 4 <= smmlv_ratio < 16:
                return 0.5
            elif 16 <= smmlv_ratio <= 17:
                return 0.6
            elif 17 < smmlv_ratio <= 18:
                return 0.7
            elif 18 < smmlv_ratio <= 19:
                return 0.8
            elif 19 < smmlv_ratio <= 20:
                return 0.9
            elif smmlv_ratio > 20:
                return 1.0

        return 0.0

    def _create_nes_lines(self, devengos, deducciones):
        """Crea las líneas NES respetando el orden XML"""
        dev_commands = []
        ded_commands = []

        # Crear devengos en orden XML
        for xml_tag in XML_STRUCTURE_ORDER['devengados']:
            if xml_tag in devengos:
                data = devengos[xml_tag]
                if isinstance(data, dict):
                    if 'lines' in data:
                        # Ordenar líneas por fecha y secuencia
                        sorted_lines = sorted(
                            data['lines'],
                            key=lambda x: (
                                x.get('initial_accrual_date') or '',
                                x.get('sequence', 999),
                                x.get('name', '')
                            )
                        )
                        for line in sorted_lines:
                            dev_commands.append(Command.create(line))
                    else:
                        dev_commands.append(Command.create(data))

        # Crear deducciones en orden XML
        for xml_tag in XML_STRUCTURE_ORDER['deducciones']:
            if xml_tag in deducciones:
                data = deducciones[xml_tag]
                if isinstance(data, dict):
                    if 'lines' in data:
                        # Ordenar líneas por secuencia y nombre
                        sorted_lines = sorted(
                            data['lines'],
                            key=lambda x: (
                                x.get('sequence', 999),
                                x.get('name', '')
                            )
                        )
                        for line in sorted_lines:
                            ded_commands.append(Command.create(line))
                    else:
                        ded_commands.append(Command.create(data))

        # Escribir todas las líneas
        if dev_commands:
            self.write({'nes_dev_line_ids': dev_commands})
        if ded_commands:
            self.write({'nes_ded_line_ids': ded_commands})