from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from datetime import datetime,timedelta
from pytz import timezone

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

_logger = logging.getLogger(__name__)

class account_balance_report_filters(models.TransientModel):
    _name = "account.balance.report.filters"
    _description = "Filtros - Reporte balance contabilidad"

    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    modality = fields.Selection([
        ('1', 'Periodo'),
        ('2', 'Anual'),
        ('3', 'Rango de periodos')
    ], string='Modalidad', required=True, default='1')
    ano_filter = fields.Integer(string='Año', required=True)
    month_filter = fields.Selection([
        ('1', 'Enero'),
        ('2', 'Febrero'),
        ('3', 'Marzo'),
        ('4', 'Abril'),
        ('5', 'Mayo'),
        ('6', 'Junio'),
        ('7', 'Julio'),
        ('8', 'Agosto'),
        ('9', 'Septiembre'),
        ('10', 'Octubre'),
        ('11', 'Noviembre'),
        ('12', 'Diciembre')
    ], string='Mes', required=True)
    ano_filter_two = fields.Integer(string='Año 2')
    month_filter_two = fields.Selection([
        ('1', 'Enero'),
        ('2', 'Febrero'),
        ('3', 'Marzo'),
        ('4', 'Abril'),
        ('5', 'Mayo'),
        ('6', 'Junio'),
        ('7', 'Julio'),
        ('8', 'Agosto'),
        ('9', 'Septiembre'),
        ('10', 'Octubre'),
        ('11', 'Noviembre'),
        ('12', 'Diciembre')
    ], string='Mes 2')
    type_balance = fields.Selection([
        ('1', 'Por Cuenta Contable'),
        ('2', 'Por Cuenta Contable - Tercero'),
        ('2.1', 'Por Tercero - Cuenta Contable'),
       # ('3', 'Por Cuenta Contable – Cuenta Analítica'),
       # ('3.1', 'Por Cuenta Analítica - Cuenta Contable')
    ], string='Tipo de balance', required=True, default='1')
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
    filter_exclude_balance_test = fields.Boolean(string='Excluir cuentas parametrizadas')
    filter_not_accumulated_partner = fields.Boolean(string='No acumula por tercero')
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
            modality_txt = 'PERIODO' if self.modality == '1' else 'ANUAL' if self.modality == '2' else 'RANGO DE PERIODOS'
            type_balance_txt = dict(self._fields['type_balance'].selection).get(self.type_balance)
            name_get = f'Balance {modality_txt.lower()} {str(self.ano_filter)}-{self.month_filter} {type_balance_txt}'
            result.append((record.id, name_get))
        return result

    def generate_report_html(self):
        html = self.generate_report(1)
        self.write({'preview': html})
        return {
            'context': self.env.context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.balance.report.filters',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def generate_report(self,return_html=0):
        # Obtener traducciones
        lang = self.env.user.lang or 'en_US'
        account_name = f"COALESCE(c.name->>'{lang}', c.name->>'en_US')" if \
            self.pool['account.account'].name.translate else 'c.name'
        group_name = f"COALESCE(c0.name->>'{lang}', c0.name->>'en_US')" if \
            self.pool['account.group'].name.translate else 'c0.name'
        analytic_name = f"COALESCE(e.name->>'{lang}', e.name->>'en_US')" if \
            self.pool['account.analytic.account'].name.translate else 'e.name'
        analytic_plan_name = f"COALESCE(e0.name->>'{lang}', e0.name->>'en_US')" if \
            self.pool['account.analytic.plan'].name.translate else 'e0.name'

        # Armar fecha dependiendo el tipo seleccionado
        date_start = ''
        date_end = ''
        x_ano = self.ano_filter
        x_month = int(self.month_filter)
        x_ano_two = self.ano_filter_two
        x_month_two = int(self.month_filter_two)
        
        # Periodo
        if self.modality == '1':
            date_start = str(x_ano) + '-' + str(x_month) + '-01'
            if x_month == 12:
                x_ano = x_ano + 1
                x_month = 1
            else:
                x_month = str(int(x_month) + 1)
            date_end = str(x_ano) + '-' + str(x_month) + '-01'
        # Anual
        elif self.modality == '2':
            date_start = str(x_ano) + '-01-01'
            if x_month == 12:
                x_ano = x_ano + 1
                x_month = 1
            else:
                x_month = str(int(x_month) + 1)
            date_end = str(x_ano) + '-' + str(x_month) + '-01'
        # Comparativo
        elif self.modality == '3':
            date_start = str(x_ano) + '-' + str(x_month) + '-01'
            if x_month_two == 12:
                x_ano_two = x_ano_two + 1
                x_month_two = 1
            else:
                x_month_two = str(int(x_month_two) + 1)
            date_end = str(x_ano_two) + '-' + str(x_month_two) + '-01'

        #-----------------------------Variable necesarias para generar el reporte-------------------------------------
        date_start = datetime.strptime(date_start, '%Y-%m-%d').date()
        date_end = datetime.strptime(date_end, '%Y-%m-%d').date() - timedelta(days=1)
        
        #-----------------------------Filtros necesarios para obtener la información----------------------------------
        query_where = f"where b.company_id = {self.company_id.id} and a.parent_state = 'posted' and a.date <= '{date_end}' "
        
        # --Terceros
        if len(self.filter_partner_ids) > 0 and self.type_balance in ('2','2.1'):
            query_where += f"\n and a.partner_id in {str(self.filter_partner_ids.ids).replace('[', '(').replace(']', ')')} "
        # --Cuentas Analíticas
        if len(self.filter_account_analytic_ids) > 0 and self.type_balance in ('3', '3.1'):
            query_where += f"\n and a.analytic_distribution ->>'id' in {str(self.filter_account_analytic_ids.ids).replace('[', '(').replace(']', ')')} "
        if len(self.filter_account_analytic_group_ids) > 0:  # Cuentas analiticas mayores
            raise ValidationError('El filtro de cuentas analiticas mayores esta en desarrollo.')
        # --Excluir Diarios
        if len(self.filter_account_journal_ids) > 0:
            query_where += f"\n and a.journal_id not in {str(self.filter_account_journal_ids.ids).replace('[', '(').replace(']', ')')} "
        # --Cuentas
        if self.filter_accounting_class:  # Clase
            query_where += f"\n and c.accounting_class = '{self.filter_accounting_class}' "
        if len(self.filter_account_ids) > 0:  # Cuentas terminales
            query_where += f"\n and a.account_id in {str(self.filter_account_ids.ids).replace('[', '(').replace(']', ')')} "
        if self.account_code_from and self.account_code_to:  
            query_where += f"\n AND c.code BETWEEN '{self.account_code_from.code}' AND '{self.account_code_to.code}'"
        if len(self.filter_account_group_ids) > 0:  # Cuentas mayores
            query_where += '\n and ('
            j = len(self.filter_account_group_ids)
            i = 1
            for filter in self.filter_account_group_ids:
                if i == j:
                    query_where += f"c.code like '{filter.code_prefix_start}%'"
                else:
                    query_where += f"c.code like '{filter.code_prefix_start}%' or "
                i += 1
            query_where += ')'
        if self.filter_exclude_balance_test:
            query_where += f"\n and (c.exclude_balance_test = false or c.exclude_balance_test is null) "

        #--------------------------------------Filtro de Cierre de Año------------------------------------------------
        if self.filter_with_close == False:
            query_where += f"\n and a.id not in (select a.id from account_move_line as a inner join account_move as b on a.move_id = b.id where a.company_id = {self.company_id.id} and a.parent_state = 'posted' and a.date >= '{datetime.strptime(str(date_end.year)+'-12-01', '%Y-%m-%d').date()}' and b.accounting_closing_id is not null) "

        #----------------------------------------Obtener información--------------------------------------------------
        #--------------------------------LOGICA POR SQL--------------------------------------------------------------
        #Obtener la cantidad de niveles existentes en el plan de cuenta
        obj_account_account = self.env['account.account'].search([])
        lst_levels_group = []
        lst_levels_group_str = []
        df_name_columns_account = []
        for account in obj_account_account:
            i = 1
            have_parent = True
            group_account = account.group_id
            while have_parent:
                if group_account.parent_id:
                    name_in_dict = (i,'Nivel ' + str(i),'Nivel ' + str(i) + ' Descripción')
                    group_account = group_account.parent_id
                    if not name_in_dict in lst_levels_group:
                        lst_levels_group.append(name_in_dict)
                        lst_levels_group_str.append('Nivel ' + str(i))
                        df_name_columns_account.append('Nivel ' + str(i))
                        df_name_columns_account.append('Nivel ' + str(i) + ' Descripción')
                        df_name_columns_account.append('Nivel ' + str(i) + ' Tercero')
                        df_name_columns_account.append('Nivel ' + str(i) + ' VAT')
                        df_name_columns_account.append('Nivel ' + str(i) + ' Cuenta Analítica')
                    i += 1
                else:
                    have_parent = False

        # Construir selects y joins para grupos de cuenta con traducciones
        query_select_levels_group = ''
        query_from_levels_group = ''
        for q_group in lst_levels_group:
            group_name = f"COALESCE(c{q_group[0]}.name->>'{lang}', c{q_group[0]}.name->>'en_US')" if \
                self.pool['account.group'].name.translate else f"c{q_group[0]}.name"
                
            query_select_levels_group += f'''
                c{q_group[0]}.code_prefix_start as "{q_group[1]}", 
                {group_name} as "{q_group[2]}",
                ' ' as "Nivel {q_group[0]} Tercero", 
                ' ' as "Nivel {q_group[0]} VAT",
                ' ' as "Nivel {q_group[0]} Cuenta Analítica",
            '''
            query_from_levels_group += f'left join account_group as c{q_group[0]} on c{q_group[0]-1}.parent_id = c{q_group[0]}.id '

        query_select_levels_group = '--NO HAY GRUPOS DE CUENTA' if query_select_levels_group == '' else query_select_levels_group
        query_from_levels_group = '--NO HAY GRUPOS DE CUENTA' if query_from_levels_group == '' else query_from_levels_group

        # Obtener la cantidad de niveles existentes en el plan de cuentas analiticas
        obj_account_analytic_account = self.env['account.analytic.account'].search([])
        lst_levels_group_analytic = []
        lst_levels_group_analytic_str = []
        df_name_columns_analytic = []
        for account_analytic in obj_account_analytic_account:
            j = 1
            have_parent_analytic = True
            group_analytic_account = account_analytic.plan_id
            while have_parent_analytic:
                if group_analytic_account.parent_id:
                    name_in_dict_analytic = (j,'Nivel Analítica ' + str(j))
                    group_analytic_account = group_analytic_account.parent_id
                    if not name_in_dict_analytic in lst_levels_group_analytic:
                        lst_levels_group_analytic.append(name_in_dict_analytic)
                        lst_levels_group_analytic_str.append('Nivel Analítica ' + str(j))
                        df_name_columns_analytic.append('Nivel Analítica ' + str(j))
                    j += 1
                else:
                    have_parent_analytic = False

        # Construir selects y joins para grupos analíticos con traducciones
        query_select_levels_group_analytic = ''
        query_from_levels_group_analytic = ''
        for q_group_analytic in lst_levels_group_analytic:
            plan_name = f"COALESCE(e{q_group_analytic[0]}.name->>'{lang}', e{q_group_analytic[0]}.name->>'en_US')" if \
                self.pool['account.analytic.plan'].name.translate else f"e{q_group_analytic[0]}.name"
                
            str_empty = "'Cuenta Analítica Vacia'"
            query_select_levels_group_analytic += f'COALESCE({plan_name}, {str_empty}) as "Nivel Analítica {q_group_analytic[0]}", '
            query_from_levels_group_analytic += f'left join account_analytic_plan as e{q_group_analytic[0]} on e{q_group_analytic[0]-1}.parent_id = e{q_group_analytic[0]}.id '

        query_select_levels_group_analytic = '--NO HAY GRUPOS DE CUENTA ANALITICA' if query_select_levels_group_analytic == '' else query_select_levels_group_analytic
        query_from_levels_group_analytic = '--NO HAY GRUPOS DE CUENTA ANALITICA' if query_from_levels_group_analytic == '' else query_from_levels_group_analytic

        #--------------QUERY FINAL
        df_name_columns = df_name_columns_account + ['Nivel 0', 'Nivel 0 Descripción','Nivel 0 Tercero','Nivel 0 VAT',
                                                'Nivel 0 Cuenta Analítica','Cuenta','Descripción','Tercero','VAT']
        df_name_columns = df_name_columns + df_name_columns_analytic
        df_name_columns = df_name_columns + ['Nivel Analítica 0','Cuenta Analítica','Saldo Anterior','Débito','Crédito',
                                        'Nuevo Saldo','Total']

        query = f'''
        SELECT 
            {query_select_levels_group}
            c0.code_prefix_start as "Nivel 0", 
            c0.name as "Nivel 0 Descripción",
            ' ' as "Nivel 0 VAT",
            ' ' as "Nivel 0 Tercero", 
            ' ' as "Nivel 0 Cuenta Analítica",
            c.code as "Cuenta", 
            {account_name} as "Descripción",
            --Tercero
            CASE 
                WHEN {str(self.filter_not_accumulated_partner).lower()} = 'true' 
                AND '{self.type_balance}' IN ('2','2.1') 
                AND c.not_disaggregate_partner_balance_test 
                THEN 'NO_PERMITE_DESAGREGAR_POR_TERCERO' 
                ELSE COALESCE(d.name, 'Tercero Vacio') 
            END AS "Tercero",
            --Tercero VAT
            CASE 
                WHEN {str(self.filter_not_accumulated_partner).lower()} = 'true' 
                AND '{self.type_balance}' IN ('2','2.1') 
                AND c.not_disaggregate_partner_balance_test 
                THEN 'NO_PERMITE_DESAGREGAR_POR_TERCERO' 
                ELSE COALESCE(d.vat_co, 'NO NIT') 
            END AS "VAT",
            --Cuenta Analítica
            {query_select_levels_group_analytic}
            COALESCE({analytic_plan_name}, 'Cuenta Analítica Vacia') as "Nivel Analítica 0",
            COALESCE({analytic_name}, 'Cuenta Analítica Vacia') as "Cuenta Analítica",
            --Valores
            CASE 
                WHEN a.date < '{date_start}' THEN a.debit - a.credit
                ELSE 0 
            END as "Saldo Anterior",
            CASE 
                WHEN a.date >= '{date_start}' AND a.date <= '{date_end}' THEN a.debit
                ELSE 0 
            END as "Débito",	
            CASE 
                WHEN a.date >= '{date_start}' AND a.date <= '{date_end}' THEN a.credit
                ELSE 0 
            END as "Crédito",
                      (CASE 
                WHEN a.date < '{date_start}' THEN a.debit - a.credit
                ELSE 0 
            END) + 
            ((CASE 
                WHEN a.date >= '{date_start}' AND a.date <= '{date_end}' THEN a.debit
                ELSE 0 
            END) - 
                (CASE 
                    WHEN a.date >= '{date_start}' AND a.date <= '{date_end}' THEN a.credit
                    ELSE 0 
                END)) as "Nuevo Saldo",                            
                '--TOTAL--' as "Total"
            FROM account_move_line as a
            INNER JOIN account_move as b ON a.move_id = b.id 
            INNER JOIN account_account as c ON a.account_id = c.id
            LEFT JOIN res_partner as d ON a.partner_id = d.id  
            LEFT JOIN account_analytic_account as e ON a.analytic_distribution ->>'account_id' = e.id::TEXT
            LEFT JOIN account_group as c0 ON c.group_id = c0.id
            {query_from_levels_group}
            LEFT JOIN account_analytic_plan as e0 ON e.plan_id = e0.id      
            {query_from_levels_group_analytic}  
            {query_where}
            ORDER BY 
                c.code,
                CASE 
                    WHEN {str(self.filter_not_accumulated_partner).lower()} = 'true' 
                    AND '{self.type_balance}' IN ('2','2.1') 
                    AND c.not_disaggregate_partner_balance_test 
                    THEN 1
                    ELSE 2
                END,
                d.name NULLS LAST
        '''
    
        #self.env.cr.execute(query)
        #lst_info = self.env.cr.fetchall()
        # ----------------------------------------DATAFRAMES PANDAS--------------------------------------------------
        lst_levels_group, lst_levels_group_analytic = lst_levels_group_str, lst_levels_group_analytic_str
        # Obtener estadísticas de memoria
        mem = psutil.virtual_memory()
        # Mostrar la memoria disponible en bytes, megabytes y porcentaje
        chunks_report_original = pd.read_sql(query, self._cr.connection, chunksize=250000)  # self.env.cr.connection
        _logger.info(chunks_report_original)
        # Recorrer y procesar cada chunk
        chunk_count = 0
        df_report_finally = False
        df_total = False
        for df_report_original in chunks_report_original:
            chunk_count += 1
            df_report_original.set_axis(df_name_columns, axis=1, inplace=True )
            _logger.info(df_report_original)
            if len(df_report_original) == 0:
                raise ValidationError(_('No se encontro información con los filtros seleccionados, por favor verificar.'))
            _logger.info(f'(CREAR DATAFRAME CHUNK {str(chunk_count)}) BALANCE DE PRUEBA - CANT REGISTROS:{str(len(df_report_original))}.')
            _logger.info(f'(USO DE PANDAS PARA AGRUPAR LA INFORMACIÓN) BALANCE DE PRUEBA.')
            lst_levels_group = sorted(lst_levels_group,reverse=True)
            lst_levels_group_analytic = sorted(lst_levels_group_analytic, reverse=True)
            #Agrupar información de acuerdo al tipo de balance
            lst_dataframes,lst_group_by,lst_levels_group_by,lst_levels_group_analytic_by = [],[],[],[]
            cant_levels = len(lst_levels_group) + 2 #La cantidad de niveles encontrados + los 2 por defecto
            cant_levels_analytic = len(lst_levels_group_analytic) + 2  # La cantidad de niveles encontrados + los 2 por defecto
            filter_higher_level = int(self.filter_higher_level) if self.filter_higher_level else 9999
            filter_higher_level_analytic = int(self.filter_higher_level_analytic) if self.filter_higher_level_analytic else 9999
            if self.type_balance == '1': # Balance por Cuenta Contable
                lst_group_by = ['Cuenta', 'Descripción']
                lst_levels_group_by = ['Nivel 0', 'Nivel 0 Descripción']
            elif self.type_balance == '2': # Balance por Cuenta Contable - Tercero
                lst_group_by = ['Cuenta', 'Descripción','Tercero','VAT',]
                lst_levels_group_by = ['Nivel 0', 'Nivel 0 Descripción','Nivel 0 Tercero','Nivel 0 VAT']
            elif self.type_balance == '2.1': # Balance por Tercero - Cuenta Contable
                lst_group_by = ['Tercero','VAT','Cuenta', 'Descripción']
                lst_levels_group_by = ['Tercero','Nivel 0 VAT','Nivel 0', 'Nivel 0 Descripción']
            elif self.type_balance == '3': # Balance por Cuenta Contable – Cuenta Analítica
                lst_group_by = ['Cuenta', 'Descripción', 'Cuenta Analítica']
                lst_levels_group_by = ['Nivel 0', 'Nivel 0 Descripción', 'Nivel 0 Cuenta Analítica']
                lst_levels_group_analytic_by = ['Cuenta', 'Descripción', 'Nivel Analítica 0']
            elif self.type_balance == '3.1': # Balance por Cuenta Analítica - Cuenta Contable
                lst_group_by = ['Cuenta Analítica','Cuenta', 'Descripción']
                top_analytic = lst_levels_group_analytic[filter_higher_level_analytic-1] if filter_higher_level_analytic <= len(lst_levels_group_analytic) else 'Nivel Analítica 0'
                top_analytic = 'Cuenta Analítica' if filter_higher_level_analytic > len(lst_levels_group_analytic)+1 else top_analytic
                lst_levels_group_by = [top_analytic,'Nivel 0', 'Nivel 0 Descripción']
                lst_levels_group_analytic_by = ['Nivel Analítica 0','Cuenta', 'Descripción']
            _logger.info(df_report_original)
            df_report = df_report_original.groupby(by=lst_group_by, group_keys=False,as_index=False).sum()
            # Agrupar información niveles cuentas
            lst_agroup_higher_level = []
            if self.filter_show_only_terminal_accounts == False:
                if filter_higher_level >= cant_levels - 1:
                    lst_levels_group_by_dinamic = []
                    if self.type_balance in ('2', '3') and filter_higher_level == cant_levels - 1:
                        for index, group in enumerate(lst_levels_group_by):
                            lst_agroup_higher_level.append(lst_levels_group_by[index])
                            level_replace = lst_levels_group_by[index] if lst_levels_group_by[index] != 'Nivel 0 Tercero' else 'Tercero'
                            level_replace = level_replace if lst_levels_group_by[index] != 'Nivel 0 Cuenta Analítica' else 'Cuenta Analítica'
                            lst_levels_group_by_dinamic.append(level_replace)
                    else:
                        lst_levels_group_by_dinamic = lst_levels_group_by
                    df_level_0 = df_report_original.groupby(by=lst_levels_group_by_dinamic, group_keys=False,as_index=False).sum()
                    lst_dataframes.append(df_level_0)
                item_level = 1
                for level in lst_levels_group: #Se recorren los niveles de las cuentas contables y se mayoriza
                    if filter_higher_level >= item_level:
                        lst_levels_group_by_dinamic = []
                        for index, group in enumerate(lst_levels_group_by):
                            if self.type_balance in ('2','3') and filter_higher_level == item_level:
                                lst_agroup_higher_level.append(lst_levels_group_by[index].replace('Nivel 0',level))
                                level_replace = lst_levels_group_by[index].replace('Nivel 0', level) if lst_levels_group_by[index] != 'Nivel 0 Tercero' else 'Tercero'
                                level_replace = level_replace if lst_levels_group_by[index] != 'Nivel 0 Cuenta Analítica' else 'Cuenta Analítica'
                                lst_levels_group_by_dinamic.append(level_replace)
                            else:
                                lst_levels_group_by_dinamic.append(lst_levels_group_by[index].replace('Nivel 0',level))
                        df_level = df_report_original.groupby(by=lst_levels_group_by_dinamic, group_keys=False,as_index=False).sum()
                        lst_dataframes.append(df_level)
                    item_level += 1
            # Agrupar información niveles cuentas analíticas cuando el tipo de balance lo requiere
            lst_agroup_higher_level_analytic = []
            if self.filter_show_only_terminal_account_analytic == False and self.type_balance in ('3','3.1'):
                if self.type_balance == '3':
                    if filter_higher_level >= cant_levels:
                        lst_dinamic_inherit_account = lst_levels_group_analytic_by
                    else:
                        lst_dinamic_inherit_account = [lst_levels_group_by_dinamic[0],lst_levels_group_by_dinamic[1],'Nivel Analítica 0']
                    if filter_higher_level_analytic >= cant_levels_analytic - 1:
                        df_level_analytic_0 = df_report_original.groupby(by=lst_dinamic_inherit_account, group_keys=False,
                                                                as_index=False).sum()
                        lst_dataframes.append(df_level_analytic_0)
                    item_level = 1
                    for level in lst_levels_group_analytic:  # Se recorren los niveles de las cuentas contables y se mayoriza
                        if filter_higher_level_analytic >= item_level:
                            lst_levels_group_by_dinamic = []
                            for index, group in enumerate(lst_dinamic_inherit_account):
                                lst_levels_group_by_dinamic.append(lst_dinamic_inherit_account[index].replace('Nivel Analítica 0', level))
                            df_level = df_report_original.groupby(by=lst_levels_group_by_dinamic, group_keys=False, as_index=False).sum()
                            lst_dataframes.append(df_level)
                        item_level += 1
                else:
                    if filter_higher_level >= cant_levels:
                        lst_dinamic_inherit_account = ['Nivel Analítica 0', 'Cuenta', 'Descripción']
                    else:
                        lst_dinamic_inherit_account = lst_levels_group_by_dinamic
                    lst_level_0_group_by_dinamic = ['Nivel Analítica 0',  'Nivel 0 Tercero', 'Nivel 0 VAT', 'Nivel 0 Cuenta Analítica']
                    if filter_higher_level_analytic >= cant_levels_analytic - 1:
                        if filter_higher_level_analytic == cant_levels_analytic - 1:
                            lst_level_0_group_by_dinamic = ['Nivel Analítica 0',lst_dinamic_inherit_account[1],lst_dinamic_inherit_account[2]]

                        df_level_analytic_0 = df_report_original.groupby(by=lst_level_0_group_by_dinamic, group_keys=False,
                                                                         as_index=False).sum()
                        lst_dataframes.append(df_level_analytic_0)
                    item_level = 1
                    lst_level_0_group_by_dinamic = ['Nivel Analítica 0','Nivel 0 Tercero', 'Nivel 0 VAT','Nivel 0 Cuenta Analítica']
                    for level in lst_levels_group_analytic:  # Se recorren los niveles de las cuentas contables y se mayoriza
                        if filter_higher_level_analytic >= item_level:
                            lst_levels_group_by_dinamic = []
                            if filter_higher_level_analytic == item_level:
                                lst_levels_group_by_dinamic = [level,lst_dinamic_inherit_account[1],lst_dinamic_inherit_account[2]]
                            else:
                                for index, group in enumerate(lst_level_0_group_by_dinamic):
                                    lst_levels_group_by_dinamic.append(lst_level_0_group_by_dinamic[index].replace('Nivel Analítica 0', level))
                            df_level = df_report_original.groupby(by=lst_levels_group_by_dinamic, group_keys=False,
                                                                  as_index=False).sum()
                            lst_dataframes.append(df_level)
                        item_level += 1
            #Agrupar por tipo de balance
            if self.type_balance in ['2','3']:
                if filter_higher_level >= cant_levels:  # Si es balance con tercero o cuenta analitica se crea la sumatoria de la cuenta contable
                    df_account = df_report_original.groupby(by=['Cuenta', 'Descripción', 'Nivel 0 Tercero','Nivel 0 VAT'],group_keys=False,as_index=False).sum()
                    lst_dataframes.append(df_account)
                else:
                    df_account = df_report_original.groupby(by=lst_agroup_higher_level,group_keys=False, as_index=False).sum()
                    lst_dataframes.append(df_account)
            if self.type_balance in ['2.1']:  # Si es balance por tercero - cuenta contable, se crea la sumatoria del tercero
                df_account = df_report_original.groupby(by=['Tercero','VAT','Nivel 0 Tercero', 'Nivel 0 VAT', 'Nivel 0 Cuenta Analítica'],group_keys=False,as_index=False).sum()
                lst_dataframes.append(df_account)
            if self.type_balance in ['3.1']:  # Si es balance por cuenta analitica - cuenta contable, se crea la sumatoria de la cuenta analitica
                df_account = df_report_original.groupby(by=[top_analytic, 'Nivel 0 Tercero', 'Nivel 0 VAT', 'Nivel 0 Cuenta Analítica'], group_keys=False,as_index=False).sum()
                lst_dataframes.append(df_account)
            #Concatenar dataframes
            if filter_higher_level >= cant_levels and filter_higher_level_analytic >= cant_levels_analytic:
                lst_dataframes.append(df_report)
            columns = lst_group_by + ['Saldo Anterior', 'Débito', 'Crédito', 'Nuevo Saldo']
            for df in lst_dataframes:
                df.columns = columns
                if type(df_report_finally) is bool:
                    df_report_finally = df
                else:
                    df_report_finally = df_report_finally.append(df)
            try:
                df_report_finally = df_report_finally.sort_values(by=lst_group_by)
            except:
                df_report_finally = df_report_finally.sort_values(by=lst_levels_group_by_dinamic)
            #Eliminar duplicados para garantizar la información
            df_report_finally = df_report_finally.groupby(by=lst_group_by, group_keys=False,as_index=False).sum()
            df_report_finally = df_report_finally.drop_duplicates()
            #Eliminar filas con todos sus valores en 0
            df_report_finally = df_report_finally[(df_report_finally['Saldo Anterior'] != 0) | (df_report_finally['Débito'] != 0) | (df_report_finally['Crédito'] != 0) | (df_report_finally['Nuevo Saldo'] != 0)]
            if self.filter_not_accumulated_partner and self.type_balance in ['2', '2.1']:
                df_report_finally = df_report_finally[(df_report_finally['Tercero'] != 'NO_PERMITE_DESAGREGAR_POR_TERCERO')]
            #Dataframe totales
            if type(df_total) is bool:
                df_total = df_report_original.groupby(by=['Total'], group_keys=False,as_index=False).sum()
            else:
                df_total = df_total.append(df_report_original.groupby(by=['Total'], group_keys=False,as_index=False).sum())
                df_total = df_total.groupby(by=['Total'], group_keys=False, as_index=False).sum()
        #-------------------------------------------Crear Excel------------------------------------------------------
        if return_html == 0:
            modality_txt = 'PERIODO' if self.modality == '1' else 'ANUAL' if self.modality == '2' else 'RANGO DE PERIODOS'
            type_balance_txt = dict(self._fields['type_balance'].selection).get(self.type_balance)
            filename = f'Balance {modality_txt.lower()} {str(self.ano_filter)}-{self.month_filter} {type_balance_txt}.xlsx'
            stream = io.BytesIO()
            writer = pd.ExcelWriter(stream, engine='xlsxwriter')
            writer.book.filename = stream
            columns = lst_group_by + ['Saldo Anterior', 'Débito', 'Crédito', 'Nuevo Saldo']
            df_report_finally.to_excel(writer, sheet_name='Balance', float_format="%.2f", columns=columns, header=columns, index=False, startrow=4, startcol=0)
            df_total.to_excel(writer, sheet_name='Balance', float_format="%.2f", columns=['Total','Saldo Anterior', 'Débito', 'Crédito', 'Nuevo Saldo'], header=False, index=False, startrow=len(df_report_finally)+8, startcol=len(lst_group_by) - 1)
            worksheet = writer.sheets['Balance']
            # Agregar formatos al excel
            cell_format_title = writer.book.add_format({'bold': True, 'align': 'center'})
            cell_format_title.set_font_name('Calibri')
            cell_format_title.set_font_size(15)
            cell_format_title.set_font_color('#1F497D')
            cell_format_text_generate = writer.book.add_format({'text_wrap': True,'bold': False, 'align': 'left'})
            cell_format_text_generate.set_font_name('Calibri')
            cell_format_text_generate.set_font_size(10)
            cell_format_text_generate.set_font_color('#1F497D')
            #Encabezado
            cant_columns = (len(lst_group_by) - 1) + 4
            text_generate = 'Generado por: \n %s \nFecha: \n %s %s \nTipo de balance: \n %s' % (
                                self.env.user.name, datetime.now(timezone(self.env.user.tz)).date(),
                                datetime.now(timezone(self.env.user.tz)).time(), type_balance_txt)
            worksheet.merge_range(0, 0, 0, cant_columns - 2, self.company_id.name, cell_format_title)
            worksheet.merge_range(1, 0, 1, cant_columns - 2, self.company_id.vat, cell_format_title)
            worksheet.merge_range(0, cant_columns - 1, 3, cant_columns, text_generate,cell_format_text_generate)
            worksheet.merge_range(2, 0, 2, cant_columns - 2, 'BALANCE DE PRUEBA - ' + modality_txt, cell_format_title)
            worksheet.merge_range(3, 0, 3, cant_columns - 2, str(date_start)+' - '+str(date_end),cell_format_title)
            # Dar tamaño a las columnas y formato
            position_initial = 0
            for c in columns:
                size = len(c)
                size_tmp = max(len(str(j)) for j in df_report_original[c])
                size = size if size >= size_tmp else size_tmp

                format_align = writer.book.add_format({'align': 'left'})
                number_format = writer.book.add_format({'num_format': '#,##0.00'})
                if c in ['Saldo Anterior','Débito','Crédito','Nuevo Saldo']:
                    worksheet.set_column(position_initial, position_initial, size + 10,number_format)
                else:
                    worksheet.set_column(position_initial, position_initial, size + 10,format_align)
                position_initial +=1
            # Guardar excel
            writer.save()

            self.write({
                'excel_file': base64.encodebytes(stream.getvalue()),
                'excel_file_name': filename,
            })

            action = {
                'name': filename,
                'type': 'ir.actions.act_url',
                'url': "web/content/?model=account.balance.report.filters&id=" + str(
                    self.id) + "&filename_field=excel_file_name&field=excel_file&download=true&filename=" + self.excel_file_name,
                'target': 'self',
            }
            return action
        # -------------------------------------------Crear HTML------------------------------------------------------
        else:
            columns = lst_group_by + ['Saldo Anterior', 'Débito', 'Crédito', 'Nuevo Saldo']
            sizes = []
            for c in columns:
                size = len(c)
                size_tmp = max(len(str(j)) for j in df_report_original[c])
                size = size if size >= size_tmp else size_tmp
                size = size*15 if size*15 <= 500 else 500
                sizes.append(size)

            columns = lst_group_by + ['Saldo Anterior', 'Débito', 'Crédito', 'Nuevo Saldo']
            modality_txt = 'PERIODO' if self.modality == '1' else 'ANUAL' if self.modality == '2' else 'RANGO DE PERIODOS'
            type_balance_txt = dict(self._fields['type_balance'].selection).get(self.type_balance)
            text_generate = 'Generado por: %s <br/> Fecha: %s %s <br/> Tipo de balance: %s' % (
                self.env.user.name, datetime.now(timezone(self.env.user.tz)).date(),
                datetime.now(timezone(self.env.user.tz)).time(), type_balance_txt)

            html = '''
                    <div class="d-flex bd-highlight">                        
                        <div class="p-2 flex-grow-3 bd-highlight" style="width: 2600px;">
                            <h4>%s</h4>
                            <h4>%s</h4>
                            <h4>%s</h4>
                            <h4>%s</h4>
                        </div>
                        <div class="p-2 bd-highlight" style="text-align: end;">
                            <p>%s</p>
                        </div>
                    </div>
                    <br/>  
                    <div class="d-flex justify-content-center">                  
            ''' % (self.company_id.name,self.company_id.vat,'BALANCE DE PRUEBA - ' + modality_txt,
                   str(date_start)+' - '+str(date_end),text_generate)
            html += df_report_finally.to_html(col_space='200px', columns=columns, float_format='{:,.2f}'.format, index=False, justify='left',classes=['table','table-sm','table-bordered'])
            html += '''
                    </div>
                    <br/>
                    <div class="d-flex justify-content-center">
            '''
            html += df_total.to_html(col_space='200px', float_format='{:,.2f}'.format, index=False, justify='left',classes=['table','table-sm','table-bordered'])
            html += '</div>'
            return html