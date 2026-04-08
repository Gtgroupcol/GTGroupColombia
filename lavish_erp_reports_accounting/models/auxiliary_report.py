from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from datetime import datetime,timedelta
from pytz import timezone
import logging
import io
import pandas as pd
import base64
import io
import psutil
import xlsxwriter
import odoo
import threading
import math
import logging
import gc
import os
import time
import json
_logger = logging.getLogger(__name__)

class account_auxiliary_report_filters(models.TransientModel):
    _name = "account.auxiliary.report.filters"
    _description = "Filtros - Reporte auxiliar contabilidad"

    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    date_start = fields.Date(string='Fecha inicial', required=True)
    date_end = fields.Date(string='Fecha final', required=True)
    type_auxiliary = fields.Selection([
        ('1', 'Por Cuenta Contable'),
        ('2', 'Por Cuenta Contable - Tercero'),
        #('2.1', 'Por Tercero - Cuenta Contable'),
        #('3', 'Por Cuenta Contable – Cuenta Analítica'),
        #('3.1', 'Por Cuenta Analítica - Cuenta Contable'),
        ('4', 'Por Cuenta Contable - Tercero - Cuenta Analítica')
    ], string='Tipo de auxiliar', default='1')
    #Filtros
    #--Cuentas
    account_code_from = fields.Many2one(
        comodel_name="account.account", string="Cuentas Desde",
        help="Starting account in a range",
    )
    account_code_to = fields.Many2one(
        comodel_name="account.account", string="Cuentas Hasta",
        help="Ending account in a range",
    )
    filter_show_only_terminal_accounts = fields.Boolean(string='Mostrar solo cuentas terminales')
    filter_exclude_auxiliary_test = fields.Boolean(string='Excluir cuentas parametrizadas')
    filter_accounting_class = fields.Char(string='Clase')
    filter_account_ids = fields.Many2many('account.account', string="Cuentas terminales")
    filter_account_group_ids = fields.Many2many('account.group', string="Cuentas mayores")
    filter_higher_level = fields.Selection([
        ('1', '1'),('2', '2'),('3', '3'),
        ('4', '4'), ('5', '5'), ('6', '6'),
        ('7', '7'), ('8', '8'), ('9', '9')
    ], string='Nivel')
    # --Terceros
    filter_partner_ids = fields.Many2many('res.partner', string="Terceros")
    # --Cuentas Analíticas
    filter_account_analytic_group_ids = fields.Many2many('account.analytic.plan', string="Cuentas analíticas mayores")
    filter_account_analytic_ids = fields.Many2many('account.analytic.account', string="Cuentas analíticas terminales")
    filter_show_only_terminal_account_analytic = fields.Boolean(string='Mostrar solo cuentas analíticas terminales')
    filter_higher_level_analytic = fields.Selection([
        ('1', '1'), ('2', '2'), ('3', '3'),
        ('4', '4'), ('5', '5'), ('6', '6'),
        ('7', '7'), ('8', '8'), ('9', '9')
    ], string='Nivel Analítico')
    # --Diarios
    filter_account_journal_ids = fields.Many2many('account.journal', string="Diarios Excluidos")
    #Cierre de año
    filter_with_close = fields.Boolean(string='Con cierre', default=True)
    #Guardar excel
    excel_file = fields.Binary('Excel file')
    excel_file_name = fields.Char('Excel name')
    #Html
    preview = fields.Html('Reporte Preview')

    def name_get(self):
        result = []
        for record in self:
            period_txt = f'PERIODO {self.date_start} a {self.date_end}'
            type_auxiliary_txt = dict(self._fields['type_auxiliary'].selection).get(self.type_auxiliary)
            name_get = f'Auxiliar {period_txt.lower()} {type_auxiliary_txt}'
            result.append((record.id, name_get))
        return result

    def generate_report_html(self):
        html = self.generate_report(1)
        self.write({'preview': html})
        return {
            'context': self.env.context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.auxiliary.report.filters',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def generate_report(self, return_html=0):
        date_start = self.date_start
        date_end = self.date_end
        # Filtros necesarios para obtener la información
        query_where = self._build_query_where(date_start, date_end)
        # Obtener los niveles de cuenta y cuenta analítica
        #lst_levels_group = self._get_account_levels()
        #lst_levels_group_analytic = self._get_analytic_account_levels()

        # Construir la consulta SQL
        query = self._build_query(date_start, date_end, query_where)
        _logger.error(query)
        self.env.cr.execute(query)
        lst_info = self.env.cr.fetchall()

        if not lst_info:
            raise ValidationError('No se encontró información con los filtros seleccionados. Por favor, verifique.')

        # Obtener los nombres de las columnas
        columns = [desc[0] for desc in self.env.cr.description]

        # Convertir el resultado en un diccionario
        data = [dict(zip(columns, row)) for row in lst_info]
        _logger.error(data)
        # Agrupar información por número de cuenta
        grouped_data = self._group_by_account_number(data)
        _logger.error(grouped_data)
        # Obtener los saldos iniciales
        initial_balances = self.calculate_initial_balances_with_account_code(date_start)
        _logger.error(initial_balances)
        # Integrar los saldos iniciales al reporte
        report_data = self.integrate_initial_balances(grouped_data, initial_balances)
        _logger.error(report_data)
        # Obtener los totales
        totals = self._calculate_totals(data)
        _logger.error(totals)
        # Crear Excel o HTML
        if return_html == 0:
            return self._create_excel(report_data, totals, date_start, date_end)
        else:
            return self._create_html(report_data, totals, date_start, date_end)

    def _build_query_where(self, date_start, date_end):
        query_where = f"WHERE am.company_id = {self.company_id.id} AND aml.parent_state = 'posted' AND aml.date BETWEEN '{date_start}' AND '{date_end}'"

        if len(self.filter_partner_ids) > 0 and self.type_auxiliary in ('2', '2.1'):
            query_where += f"\n and aml.partner_id in {str(self.filter_partner_ids.ids).replace('[', '(').replace(']', ')')} "

        if len(self.filter_account_analytic_ids) > 0 and self.type_auxiliary in ('3', '3.1'):
            query_where += f"\n AND aal.account_id IN {tuple(self.filter_account_analytic_ids.ids)}"

        if len(self.filter_account_analytic_group_ids) > 0:
            raise ValidationError('El filtro de cuentas analíticas mayores está en desarrollo.')

        if len(self.filter_account_journal_ids) > 0:
            query_where += f"\n and aml.journal_id not in {str(self.filter_account_journal_ids.ids).replace('[', '(').replace(']', ')')} "

        if self.filter_accounting_class:
            query_where += f"\n AND aa.accounting_class = '{self.filter_accounting_class}'"

        if len(self.filter_account_ids) > 0:
            query_where += f"\n AND aml.account_id IN {tuple(self.filter_account_ids.ids)}"

        if len(self.filter_account_group_ids) > 0:
            query_where += '\n AND (' + ' OR '.join(f"aa.code LIKE '{filter.code_prefix_start}%'" for filter in self.filter_account_group_ids) + ')'

        if self.filter_exclude_auxiliary_test:
            query_where += "\n AND (aa.exclude_balance_test = false OR aa.exclude_balance_test IS NULL)"

        if not self.filter_with_close:
            query_where += f"\n AND aml.id NOT IN (SELECT aml.id FROM account_move_line AS a INNER JOIN account_move AS b ON aml.move_id = b.id WHERE aml.company_id = {self.company_id.id} AND aml.parent_state = 'posted' AND aml.date >= '{datetime.strptime(str(date_end.year) + '-12-01', '%Y-%m-%d').date()}' AND b.accounting_closing_id IS NOT NULL)"
        if self.account_code_from and self.account_code_to:  
            query_where += f"\n AND aa.code BETWEEN '{self.account_code_from.code}' AND '{self.account_code_to.code}'"
        return query_where

    def _get_account_levels(self):
        obj_account_account = self.env['account.account'].search([])
        lst_levels_group = []

        for account in obj_account_account:
            i = 1
            have_parent = True
            group_account = account.group_id

            while have_parent:
                if group_account.parent_id:
                    name_in_dict = (i, f'Nivel {i}', f'Nivel {i} Descripción')
                    group_account = group_account.parent_id

                    if name_in_dict not in lst_levels_group:
                        lst_levels_group.append(name_in_dict)
                    i += 1
                else:
                    have_parent = False

        return lst_levels_group

    def _get_analytic_account_levels(self):
        obj_account_analytic_account = self.env['account.analytic.account'].search([])
        lst_levels_group_analytic = []

        for account_analytic in obj_account_analytic_account:
            j = 1
            have_parent_analytic = True
            group_analytic_account = account_analytic.plan_id

            while have_parent_analytic:
                if group_analytic_account.parent_id:
                    name_in_dict_analytic = (j, f'Nivel Analítica {j}')
                    group_analytic_account = group_analytic_account.parent_id

                    if name_in_dict_analytic not in lst_levels_group_analytic:
                        lst_levels_group_analytic.append(name_in_dict_analytic)
                    j += 1
                else:
                    have_parent_analytic = False

        return lst_levels_group_analytic

    def _build_query(self, date_start, date_end, query_where):
        query = f'''
            SELECT
                aml.id AS "aml_id",
                aa.code AS "Cuenta", aa.name::jsonb ->> 'en_US' AS "Descripción",
                COALESCE(rp.vat, 'NO ID/CC/NIT') AS "VAT",
                COALESCE(rp.name, rp.name, 'Tercero Vacío') AS "Tercero",
                aaa.name::jsonb ->> 'en_US' AS "Cuenta Analítica",
                am."name" AS "Movimiento",
                am.date AS "Fecha",
                aml."name" AS "Concepto",
                SUM(CASE 
                        WHEN aml.date >= '{date_start}' AND aml.date <= '{date_end}' THEN 
                            CASE 
                                WHEN aal.id IS NULL THEN 0
                                ELSE (aal.amount /  aml.balance)*100
                            END 
                        ELSE 0 
                    END) as  "distribucion",
                SUM(CASE 
                        WHEN aml."date" < '{date_start}' THEN 
                            CASE 
                                WHEN aal.id IS NULL THEN aml.debit - aml.credit 
                                ELSE aal.amount 
                            END 
                        ELSE 0 
                    END) as "Saldo Anterior",
                    
                SUM(CASE 
                        WHEN aml.date >= '{date_start}' AND aml.date <= '{date_end}' THEN 
                            CASE 
                                WHEN aal.id IS NULL THEN aml.debit 
                                ELSE CASE WHEN aal.amount < 0 THEN -aal.amount ELSE 0 END 
                            END 
                        ELSE 0 
                    END) as "Débito",
                    
                SUM(CASE 
                        WHEN aml.date >= '{date_start}' AND aml.date <= '{date_end}' THEN 
                            CASE 
                                WHEN aal.id IS NULL THEN aml.credit 
                                ELSE CASE WHEN aal.amount > 0 THEN aal.amount ELSE 0 END 
                            END 
                        ELSE 0 
                    END) as "Crédito",
                    
                -- Nuevo Saldo: Saldo Anterior + Débitos - Créditos
                SUM(CASE 
                        WHEN aml."date" < '{date_start}' THEN 
                            CASE 
                                WHEN aal.id IS NULL THEN aml.debit - aml.credit 
                                ELSE aal.amount 
                            END 
                        ELSE 0 
                    END) 
                + 
                SUM(CASE 
                        WHEN aml.date >= '{date_start}' AND aml.date <= '{date_end}' THEN 
                            CASE 
                                WHEN aal.id IS NULL THEN aml.debit - aml.credit
                                ELSE aal.amount 
                            END 
                        ELSE 0 
                    END) as "Nuevo Saldo"
            FROM account_move_line AS aml
            INNER JOIN account_move AS am ON aml.move_id = am.id
            INNER JOIN account_account AS aa ON aml.account_id = aa.id
            LEFT JOIN res_partner AS rp ON aml.partner_id = rp.id
            LEFT JOIN account_analytic_line AS aal ON aml.id = aal.move_line_id
            LEFT JOIN account_analytic_account AS aaa ON aal.account_id = aaa.id
            {query_where}
            GROUP BY
                aa.code, 
                aa."name",
                rp.vat,
                rp.name,
                aaa."name",
                am."name",
                am.date,
                aml."name",
                aml.id,
                aal.id
            ORDER BY aa.code, am.date
        '''
        return query

    def _group_by_account_number(self, data):
        grouped_data = {}
        for row in data:
            account_number = row['Cuenta']
            if account_number not in grouped_data:
                grouped_data[account_number] = []
            grouped_data[account_number].append(row)
        return grouped_data

    def _calculate_totals(self, data):
        totals = {
            'Saldo Anterior': 0,
            'Débito': 0,
            'Crédito': 0,
            'Nuevo Saldo': 0
        }
        for row in data:
            totals['Saldo Anterior'] += row['Saldo Anterior'] if row['Saldo Anterior'] is not None else 0
            totals['Débito'] += row['Débito'] if row['Débito'] is not None else 0
            totals['Crédito'] += row['Crédito'] if row['Crédito'] is not None else 0
            totals['Nuevo Saldo'] += row['Nuevo Saldo'] if row['Nuevo Saldo'] is not None else 0
        return totals
    
    def _create_excel(self, report_data, totals, date_start, date_end):
        modality_txt = 'PERIODO' 
        type_balance_txt = dict(self._fields['type_auxiliary'].selection).get(self.type_auxiliary)
        filename = f'Balance {modality_txt.lower()} {str(self.date_start)}-{self.date_end} {type_balance_txt}.xlsx'
    
        # Crear un nuevo libro de Excel y una hoja de trabajo
        workbook = xlsxwriter.Workbook(filename)
        worksheet = workbook.add_worksheet('Reporte Auxiliar')
        cell_format_title = workbook.add_format({'bold': True, 'align': 'center'})
        cell_format_title.set_font_name('Calibri')
        cell_format_title.set_font_size(15)
        cell_format_title.set_font_color('#1F497D')
        cell_format_text_generate = workbook.add_format({'text_wrap': True,'bold': False, 'align': 'left'})
        cell_format_text_generate.set_font_name('Calibri')
        cell_format_text_generate.set_font_size(10)
        cell_format_text_generate.set_font_color('#1F497D')
        # Definir formatos de celda
        header_format = workbook.add_format({'bold': True, 'bg_color': '#CCCCCC'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        money_format = workbook.add_format({'num_format': '$#,##0.00'})
        highlight_format = workbook.add_format({'bg_color': '#B7DEE8'})
        highlight_format_money = workbook.add_format({'bg_color': '#B7DEE8','num_format': '$#,##0.00'})  ## Formato para resaltar en azul
    
        # Encabezado adicional
        cant_columns =  13
        text_generate = 'Generado por: \n %s \nFecha: \n %s %s \nTipo de balance: \n %s' % (
                            self.env.user.name, datetime.now(timezone(self.env.user.tz)).date(),
                            datetime.now(timezone(self.env.user.tz)).time(), type_balance_txt)
        worksheet.merge_range(0, 0, 0, cant_columns - 2, self.company_id.name, cell_format_title)
        worksheet.merge_range(1, 0, 1, cant_columns - 2, self.company_id.vat, cell_format_title)
        worksheet.merge_range(0, cant_columns - 1, 3, cant_columns, text_generate,cell_format_text_generate)
        worksheet.merge_range(2, 0, 2, cant_columns - 2, 'Libro Auxiliar - ' + modality_txt, cell_format_title)
        worksheet.merge_range(3, 0, 3, cant_columns - 2, str(date_start)+' - '+str(date_end),cell_format_title)
    
        # Escribir encabezados de columna
        headers = ['Cuenta', 'Descripción', 'Fecha', 'Tercero', 'NIT/CC','Movimiento', 'Concepto', 'ID Operacion', 'Cuenta Analítica', 'distribucion','Saldo Anterior', 'Débito', 'Crédito', 'Nuevo Saldo']
        for col, header in enumerate(headers):
            worksheet.write(4, col, header, header_format)
    
        # Escribir datos del reporte
        row = 5
        for data in report_data:
            if data['Descripción'] == 'Saldo Inicial' or data['Descripción'] == 'Saldo Final':
                worksheet.write(row, 0, data['Cuenta'], highlight_format)
                worksheet.write(row, 1, str(data['Descripción']), highlight_format)
                worksheet.write(row, 2, data['Fecha'], highlight_format)
                worksheet.write(row, 3, data['Tercero'], highlight_format)
                worksheet.write(row, 4, data['VAT'], highlight_format)
                worksheet.write(row, 5, data['Movimiento'], highlight_format)
                worksheet.write(row, 6, data['Concepto'], highlight_format)
                worksheet.write(row, 7, data['aml_id'], highlight_format)
                worksheet.write(row, 8, '', highlight_format)
                worksheet.write(row, 9, '', highlight_format)
                worksheet.write(row, 10, data['Saldo Anterior'], highlight_format_money)
                worksheet.write(row, 11, data['Débito'], highlight_format_money)
                worksheet.write(row, 12, data['Crédito'], highlight_format_money)
                worksheet.write(row, 13, data['Nuevo Saldo'], highlight_format_money)
                #if data['Descripción'] == 'Saldo Final':
                #    row += 1  # Agregar un salto de línea después de "Saldo Final"
            else:
                worksheet.write(row, 0, data['Cuenta'])
                worksheet.write(row, 1, str(data['Descripción']))
                worksheet.write(row, 2, data['Fecha'], date_format)
                worksheet.write(row, 3, data['Tercero'])
                worksheet.write(row, 4, data['VAT'])
                worksheet.write(row, 5, data['Movimiento'])
                worksheet.write(row, 6, data['Concepto'])
                worksheet.write(row, 7, data['aml_id'])
                worksheet.write(row, 8, data['Cuenta Analítica'])
                worksheet.write(row, 9, data['distribucion'])
                worksheet.write(row, 10, data['Saldo Anterior'], money_format)
                worksheet.write(row, 11, data['Débito'], money_format)
                worksheet.write(row, 12, data['Crédito'], money_format)
                worksheet.write(row, 13, data['Nuevo Saldo'], money_format)
            row += 1
    
        # Escribir totales
        worksheet.write(row, 0, 'Totales', header_format)
        worksheet.write(row, 10, totals['Saldo Anterior'], money_format)
        worksheet.write(row, 11, totals['Débito'], money_format)
        worksheet.write(row, 12, totals['Crédito'], money_format)
        worksheet.write(row, 13, totals['Nuevo Saldo'], money_format)
    
        # Ajustar ancho de columnas
        worksheet.set_column(0, 0, 15)
        worksheet.set_column(1, 1, 30)
        worksheet.set_column(2, 5, 15, money_format)
    
        # Agregar información adicional
        worksheet.write(row + 2, 0, 'Fecha de inicio:', header_format)
        worksheet.write(row + 2, 1, date_start, date_format)
        worksheet.write(row + 3, 0, 'Fecha de fin:', header_format)
        worksheet.write(row + 3, 1, date_end, date_format)
        worksheet.write(row + 4, 0, 'Generado por:', header_format)
        worksheet.write(row + 4, 1, self.env.user.name)
    
        # Guardar el archivo Excel
        try:
            workbook.close()
        except Exception as e:
            # Registrar información de error
            error_msg = f"Error al cerrar el libro de Excel: {str(e)}"
            _logger.error(error_msg)
    
            # Opcionalmente, puedes devolver un mensaje de error al usuario
            return {
                'warning': {
                    'title': "Error",
                    'message': "Ocurrió un error al generar el archivo Excel. Por favor, inténtalo de nuevo más tarde."
                }
            }
    
        # Adjuntar el archivo Excel al registro actual
        with open(filename, 'rb') as file:
            file_data = file.read()
            self.write({
                'excel_file': base64.encodebytes(file_data),
                'excel_file_name': filename,
            })
    
        # Devolver la acción para descargar el archivo Excel
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=account.auxiliary.report.filters&id={self.id}&filename_field=excel_file_name&field=excel_file&download=true&filename={self.excel_file_name}',
            'target': 'self',
        }

    def _create_html(self, report_data, totals, date_start, date_end):
        # Implementación para crear el reporte en formato HTML
        pass

    def calculate_initial_balances_with_account_code(self, date_start, date_end=None):
        if date_end is None:
            date_end = date_start

        query = """
            SELECT aa.code AS Cuenta, 
                COALESCE(SUM(CASE WHEN aml.date < %s THEN aml.debit - aml.credit ELSE 0 END), 0) AS "Saldo Anterior"
            FROM account_account aa
            LEFT JOIN account_move_line aml ON aml.account_id = aa.id
            WHERE aml.company_id = %s
            AND aml.parent_state = 'posted'
            AND aml.date < %s
            GROUP BY aa.code;
        """
        company_id = self.company_id.id

        try:
            self.env.cr.execute(query, (date_start, company_id, date_start))
            result = self.env.cr.fetchall()
            return [{'Cuenta': row[0], 'Saldo Anterior': row[1]} for row in result]
        except Exception as e:
            _logger.error("Error occurred while calculating initial balances: %s", e)
            return []

    def integrate_initial_balances(self, grouped_data, initial_balances):
        report_data = []
        for account_number, rows in grouped_data.items():
            initial_balance = next((b for b in initial_balances if b['Cuenta'] == account_number), None)
            if initial_balance:
                saldo_inicial = initial_balance['Saldo Anterior']
                report_data.append({
                    'Cuenta': account_number,
                    'Descripción': 'Saldo Inicial',
                    'Fecha': '',
                    'VAT': '',
                    'Movimiento': 'Saldo Inicial',
                    'Concepto': 'Saldo Inicial',
                    'Tercero': 'Saldo Inicial',
                    'aml_id': 'Saldo Inicial',
                    'Cuenta Analítica': '',
                    'distribucion': 'Saldo Inicial',
                    'Saldo Anterior': saldo_inicial,
                    'Débito': 0,
                    'Crédito': 0,
                    'Nuevo Saldo': saldo_inicial
                })
            else:
                saldo_inicial = 0
    
            saldo_actual = saldo_inicial
            debito_total = 0
            credito_total = 0
    
            for row in rows:
                debito = row['Débito'] if row['Débito'] is not None else 0
                credito = row['Crédito'] if row['Crédito'] is not None else 0
                saldo_actual += debito - credito
                debito_total += debito
                credito_total += credito
                row['Nuevo Saldo'] = saldo_actual
                report_data.append(row)
    
            report_data.append({
                'Cuenta': account_number,
                'Descripción': 'Saldo Final',
                'Fecha': '',
                 'VAT': '',
                'Movimiento': 'Saldo Final',
                'Concepto': 'Saldo Final',
                'Tercero': 'Saldo Final',
                'aml_id': 'Saldo Final',
                'Cuenta Analítica': '',
                'distribucion': 'Saldo Final',
                'Saldo Anterior': saldo_inicial,
                'Débito': debito_total,
                'Crédito': credito_total,
                'Nuevo Saldo': saldo_actual
            })
    
        return report_data