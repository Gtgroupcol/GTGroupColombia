# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import xlwt
import base64
import io
import xlsxwriter
import requests
import math

#---------------------------Pagos-------------------------------#
    
class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    x_payment_file = fields.Boolean(string='Reportado en archivo de pago')    
    x_description = fields.Text(string='Descripción')
    x_is_advance = fields.Boolean(string=' ¿Es Anticipo?')
    # @api.depends('move_id.line_ids.amount_residual', 'move_id.line_ids.amount_residual_currency', 'move_id.line_ids.account_id','x_description')
    # def _compute_reconciliation_status(self):
    #     ''' Compute the field indicating if the payments are already reconciled with something.
    #     This field is used for display purpose (e.g. display the 'reconcile' button redirecting to the reconciliation
    #     widget).
    #     '''
    #     for pay in self:
    #         liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

    #         if not pay.currency_id or not pay.id:
    #             pay.is_reconciled = False
    #             pay.is_matched = False
    #         elif pay.currency_id.is_zero(pay.amount):
    #             pay.is_reconciled = True
    #             pay.is_matched = True
    #         else:
    #             residual_field = 'amount_residual' if pay.currency_id == pay.company_id.currency_id else 'amount_residual_currency'
    #             if pay.journal_id.default_account_id and pay.journal_id.default_account_id in liquidity_lines.account_id:
    #                 # Allow user managing payments without any statement lines by using the bank account directly.
    #                 # In that case, the user manages transactions only using the register payment wizard.
    #                 pay.is_matched = True
    #             else:
    #                 pay.is_matched = pay.currency_id.is_zero(sum(liquidity_lines.mapped(residual_field)))

    #             reconcile_lines = (counterpart_lines + writeoff_lines).filtered(lambda line: line.account_id.reconcile)
    #             pay.is_reconciled = pay.currency_id.is_zero(sum(reconcile_lines.mapped(residual_field)))

    #         # Adaptación para marcar como conciliada si la cuenta es de gasto y el extracto bancario está validado
    #         if not pay.is_reconciled and pay.move_id:
    #             expense_account = self.env['account.account'].search([('user_type_id.name', '=', 'Expenses')], limit=1)
    #             if expense_account and expense_account in pay.move_id.line_ids.mapped('account_id'):
    #                 bank_statement = self.env['account.bank.statement'].search([('line_ids.move_id', '=', pay.move_id.id)])
    #                 if bank_statement and bank_statement.state == 'validated':
    #                     pay.is_reconciled = True

#---------------------------Archivo de pago-------------------------------#
class lavish_Payment_File(models.Model):
    _name = 'lavish.payment.file'
    _description = 'Archivo de pago'
    _rec_name = 'description'
    
    type_file = fields.Selection([
                                        ('1', 'Archivo Plano'),
                                        ('2', 'Excel')     
                                    ], string='Archivo a generar', required=True, default='1')  
    format_file = fields.Selection([
                                        ('bancolombia', 'Bancolombia SAP'),
                                        ('bancolombia_pab', 'Bancolombia PAB'),
                                        ('occired', 'Occired')     
                                    ], string='Tipo de plano', required=True, default='bancolombia')  
    journal_id = fields.Many2one('account.journal', string='Diario', required=True)
    vat_payer = fields.Char(string='NIT Pagador', store=True, readonly=True, related='journal_id.company_id.partner_id.vat', change_default=True)
    payment_type = fields.Selection([
                                        ('220', 'Pago a Proveedores'),
                                        ('225', 'Pago de Nómina'),
                                        ('238', 'Pagos a Terceros'),
                                        ('239', 'Abono Obligatorio con el Bco'),
                                        ('240', 'Pagos Cuenta Maestra'),
                                        ('320', 'Credipago a Proveedores'),
                                        # ('325', 'Credipago Nómina'),
                                        # ('820', 'Pago Nómina Efectivo'),
                                        # ('920', 'Pago Proveedores Efectivo')                                        
                                    ], string='Tipo de pago', required=True, default='220')
    application = fields.Selection([
                                        ('I', 'Inmediata'),
                                        ('M', 'Medio día'),
                                        ('N', 'Noche')                                      
                                    ], string='Aplicación', required=True)
    sequence = fields.Char(string='Secuencia de envío', size=2,required=True)
    account_debit = fields.Char(string='Nro. Cuenta a debitar', store=True, readonly=True, related='journal_id.bank_account_id.acc_number', change_default=True)
    account_type_debit = fields.Selection([
                                        ('S', 'Ahorros'),
                                        ('D', 'Corriente')                                  
                                    ], string='Tipo de cuenta a debitar', required=True)
    description = fields.Char(string='Descripción del pago', size=10,required=True)
    payment_date = fields.Date(string='Fecha de Pago', required=True, default=fields.Date.today())
    
    payment_ids = fields.Many2many('account.payment', string='Pagos', required=True, domain="['&', ('state', '=', 'posted'),('partner_type', '=', 'supplier'), ('x_payment_file', '=', False),('journal_id', '=', journal_id)]")    
    
    excel_file = fields.Binary('Excel file')
    excel_file_name = fields.Char('Excel name', size=64)
    
    txt_file = fields.Binary('TXT file')
    txt_file_name = fields.Char('TXT name', size=64)
    
    def name_get(self):
        result = []
        for record in self:            
            result.append((record.id, "Archivo de Pago - ".format(record.description)))
        return result
    
    #Retonar columnas
    def get_columns_encab(self):
        columns = 'NIT PAGADOR,TIPO DE PAGO,APLICACIÓN,SECUENCIA DE ENVÍO,NRO CUENTA A DEBITAR,TIPO DE CUENTA A DEBITAR,DESCRIPCIÓN DEL PAGO'
        _columns = columns.split(",")
        return _columns
    
    def get_columns_detail(self):
        columns = 'Tipo Documento Beneficiario,Nit Beneficiario,Nombre Beneficiario,Tipo Transaccion,Código Banco,No Cuenta Beneficiario,Email,Documento Autorizado,Referencia,OficinaEntrega,ValorTransaccion,Fecha de aplicación'
        _columns = columns.split(",")
        return _columns
    
    #Ejecutar consulta SQL
    def run_sql(self):
        
        #Fecha actual        
        date_today = fields.Date.context_today(self)
            
        #Obtener Pagos
        payments_ids = ''        
        for payment_id in self.payment_ids:
            id = payment_id.id
            if payments_ids == '':
                payments_ids = str(id)
            else:
                payments_ids = payments_ids+','+str(id)
            
        #raise ValidationError(_(payments_ids))
        
        #Consulta final
        query = '''
            Select distinct coalesce(case when b.document_type = '12' then '4' --Tarjeta de Identidad
				 when b.document_type = '13' then '1' --Cedula de ciudadania
				 when b.document_type = '22' then '2' --Cedula de extranjeria
				 when b.document_type = '31' then '3' --NIT
				 when b.document_type = '41' then '5' --Pasaporte
                    else '' end,'') as TipoDocumentoBeneficiario,
                    coalesce(b.vat,'') as NitBeneficiario,
                    coalesce(substring(b."name" from 1 for 30),'') as NombreBeneficiario,        
                    coalesce(case when f.type_account = 'C' then '27'when f.type_account = 'A' then '37'else null end,'') as TipoTransaccion,
                    coalesce(d.bic,coalesce(g.bic,'')) as Banco,coalesce(f.acc_number,'') as NoCuentaBeneficiario,
                    coalesce(b.email,''),coalesce(substring(a."name" from 6 for 21),'') as DocumentoAutorizado,coalesce(substring(a.communication from 1 for 21),'') as Referencia,'' as OficinaEntrega,coalesce(a.amount,0) as ValorTransaccion,		
                    coalesce(cast(extract(year from a.payment_date) as varchar) || lpad(extract(month from a.payment_date)::text, 2, '0') ||  lpad(extract(day from a.payment_date)::text, 2, '0'),'') as FechaAplicacion,
                    coalesce(cast(b.x_digit_verification as varchar),'') as DigitoNitBeneficiario	
            From account_payment a
            inner join res_partner b on a.partner_id = b.id
            left join res_partner_bank c on a.partner_bank_account_id = c.id 
            left join res_bank d on c.bank_id = d.id
            left join res_partner_bank f on b.id = f.partner_id and f.is_main = true and f.company_id = %s 
            left join res_bank g on f.bank_id = g.id
            where partner_type = 'supplier' and a.id in (%s)
        ''' % (self.env.company.id,payments_ids)
        
        self._cr.execute(query)
        _res = self._cr.dictfetchall()
        return _res

    def validate_info_bank(self,vat,name,bank):
        if bank == '':
            raise ValidationError(_(f'El tercero {vat}-{name} no tiene información bancaria o no esta marcada como principal para la compañía {self.env.company.name}, por favor verificar.'))

    #Actualizar Pagos
    def update_payments(self):
        values_update = {
          'x_payment_file' : True
        }
        for payment in self.payment_ids:
            payment.update(values_update)
        
    #Lógica de bancolombia SAP
    def get_excel_bancolombia(self):        
        
        if self.payment_type != '220':
            raise ValidationError(_('El tipo de pago seleccionado no esta desarrollado por ahora, seleccione otro por favor.'))     
        
        result_columns_encab = self.get_columns_encab()
        result_columns_detail = self.get_columns_detail()
        result_query = self.run_sql()
        
        #Logica Archivo Plano
        if self.type_file == '1':
            filename= 'Archivo de Pago '+str(self.description)+'.txt'
            filler = ' '
            
            def left(s, amount):
                return s[:amount]
            
            def right(s, amount):
                return s[-amount:]
            
            #Encabezado - parte 1          
            tipo_registro_encab = '1'
            vat_payer = str(self.vat_payer).split("-")
            nit_entidad_originadora = right('0'*10+vat_payer[0],10)
            #aplicaicon = self.application
            #filler_one = 15*filler
            name_company = left(self.journal_id.company_id.name+16*filler,16)
            clase_de_transaccion = self.payment_type
            descripcion_proposito = left(self.description+10*filler,10)
            
            date_today = fields.Date.context_today(self)
            fecha_transmision = right('0000'+str(date_today.year),2)+right('00'+str(date_today.month),2)+right('00'+str(date_today.day),2)
            
            secuencia_envio = left(self.sequence+filler,1) 
            fecha_aplicacion = fecha_transmision
            numero_registro = 'NumRegs'
            sumatoria_debitos = '0'*12
            sumatoria_creditos = 'SumatoriaCreditos'
            cuenta_cliente = right('00000000000'+str(self.account_debit).replace("-",""),11)
            tipo_cuenta = self.account_type_debit
            
            encab_content_txt = '''%s%s%s%s%s%s%s%s%s%s%s%s%s''' % (tipo_registro_encab,nit_entidad_originadora,name_company,clase_de_transaccion,descripcion_proposito,fecha_transmision,secuencia_envio,fecha_aplicacion,numero_registro,sumatoria_debitos,sumatoria_creditos,cuenta_cliente,tipo_cuenta)
            
            #Detalle
            det_content_txt = ''''''
            tipo_registro_det = '6'
            indicador_lugar = 'S'
            numero_fax = 15*filler
            numero_identificacion_autorizado = 15*filler
            filler_three = 27*filler
            
            columns = 0
            cant_detalle = 0
            total_valor_transaccion = 0.0
            #Agregar query
            for query in result_query: 
                cant_detalle = cant_detalle + 1
                for row in query.values():
                    if columns == 0:
                        tipo_documento = row
                    if columns == 1:
                        nit_beneficiario = right('0'*15+row,15) 
                    if columns == 2: 
                        nombre_beneficiario = left(row+18*filler,18) 
                    if columns == 3:
                        tipo_transaccion = right('  '+row,2)
                    if columns == 4:
                        self.validate_info_bank(nit_beneficiario,nombre_beneficiario,row)
                        banco_destino = right('000000000'+row,9) 
                    if columns == 5:
                        no_cuenta_beneficiario = right('0'*17+row,17)
                    if columns == 6:
                        email = left(row+80*filler,80)
                    if columns == 7:
                        documento_autorizado = row
                    if columns == 8:
                        referencia = left(row+21*filler,21)
                    if columns == 9:
                        oficina_entrega = '0'*5
                    if columns == 10:
                        total_valor_transaccion = total_valor_transaccion + row
                        parte_decimal, parte_entera = math.modf(row)
                        parte_entera = str(parte_entera).split(".")
                        parte_decimal = str(parte_decimal).split(".")
                        valor_transaccion = right('0'*10+str(parte_entera[0]),10) #+left(str(parte_decimal[1])+'00',2)  
                    if columns == 11:
                        fecha_aplicacion = row
                        
                    columns = columns + 1
                columns = 0
                
                content_line = '''%s%s%s%s%s%s%s%s%s%s''' % (tipo_registro_det,nit_beneficiario,nombre_beneficiario,banco_destino,no_cuenta_beneficiario,indicador_lugar,tipo_transaccion,valor_transaccion,referencia,filler)
                if cant_detalle == 1:
                    det_content_txt = content_line
                else:
                    det_content_txt = det_content_txt +'\n'+ content_line
                
            #Encabezado - parte 2            
            encab_content_txt = encab_content_txt.replace("NumRegs", right('000000000'+str(cant_detalle),6))
            parte_decimal, parte_entera = math.modf(total_valor_transaccion)
            parte_entera = str(parte_entera).split(".")
            parte_decimal = str(parte_decimal).split(".")
            encab_content_txt = encab_content_txt.replace("SumatoriaCreditos", right('0'*12+str(parte_entera[0]),12)) # +left(str(parte_decimal[1])+'00',2)
            
            #Unir Encabezado y Detalle
            content_txt = encab_content_txt +'\n'+ det_content_txt            
            
            #Actualizar pagos
            self.update_payments()

            #Crear archivo        
            self.write({
                'txt_file': base64.encodestring((content_txt).encode()),
                'txt_file_name': filename,
            })

            action = {
                        'name': 'ArchivoPagos',
                        'type': 'ir.actions.act_url',
                        'url': "web/content/?model=lavish.payment.file&id=" + str(self.id) + "&filename_field=txt_file_name&field=txt_file&download=true&filename=" + self.txt_file_name,
                        'target': 'self',
                    }
            return action
        
        
        #Logica Excel
        if self.type_file == '2':        
            filename= 'Archivo de Pago '+str(self.description)+'.xlsx'
            stream = io.BytesIO()
            book = xlsxwriter.Workbook(stream, {'in_memory': True})
            sheet = book.add_worksheet('FORMATOPAB')

            #Estilos - https://xlsxwriter.readthedocs.io/format.html 

            ##Encabezado - Encab
            cell_format_header = book.add_format({'bold': True, 'font_color': 'white'})
            cell_format_header.set_bg_color('#34839b')
            cell_format_header.set_font_name('Calibri')
            cell_format_header.set_font_size(11)
            cell_format_header.set_align('center')
            cell_format_header.set_align('vcenter')        

            ##Detalle - Encab
            cell_format_det = book.add_format()
            cell_format_det.set_font_name('Calibri')
            cell_format_det.set_font_size(11)   

            ###Campos númericos monetarios
            number_format = book.add_format({'num_format': '#,##'})
            number_format.set_font_name('Calibri')
            number_format.set_font_size(11)        

            ###Campos tipo número
            number = book.add_format()
            number.set_num_format(0)
            number.set_font_name('Calibri')
            number.set_font_size(11)

            #Agregar columnas - Encab
            aument_columns = 0
            for columns in result_columns_encab:            
                sheet.write(0, aument_columns, columns, cell_format_header)
                aument_columns = aument_columns + 1

            #Agregar fila - Encab        
            vat_payer = str(self.vat_payer).split("-")
            sheet.write(1, 0, vat_payer[0], number)
            sheet.write(1, 1, self.payment_type, number)
            sheet.write(1, 2, self.application, cell_format_det)
            sheet.write(1, 3, self.sequence, cell_format_det)
            sheet.write(1, 4, str(self.account_debit).replace("-",""), number)
            sheet.write(1, 5, self.account_type_debit, cell_format_det)
            sheet.write(1, 6, self.description, cell_format_det)

            #Agregar columnas - Detail
            aument_columns = 0
            for columns in result_columns_detail:            
                sheet.write(2, aument_columns, columns, cell_format_header)
                aument_columns = aument_columns + 1

            #Agregar query
            aument_columns = 0
            aument_rows = 3
            for query in result_query: 
                for row in query.values():
                    if aument_columns == 2 or aument_columns == 8:
                        row = str(row).replace("/","")
                        row = str(row).replace(".","")
                        row = str(row).replace(",","")
                        row = str(row).replace(":","")
                        row = str(row).replace(";","")
                    
                    if aument_columns == 10:
                        sheet.write(aument_rows, aument_columns, row, number_format)
                    else:
                        sheet.write(aument_rows, aument_columns, row, cell_format_det)
                    aument_columns = aument_columns + 1
                aument_rows = aument_rows + 1
                aument_columns = 0

            #Tamaño columnas
            sheet.set_column('A:B', 25)
            sheet.set_column('C:C', 30)
            sheet.set_column('D:D', 25)
            sheet.set_column('E:F', 40)
            sheet.set_column('G:G', 50)
            sheet.set_column('H:L', 25)

            book.close()            

            #Actualizar pagos
            self.update_payments()

            #Crear archivo        
            self.write({
                'excel_file': base64.encodestring(stream.getvalue()),
                'excel_file_name': filename,
            })

            action = {
                        'name': 'ArchivoPagos',
                        'type': 'ir.actions.act_url',
                        'url': "web/content/?model=lavish.payment.file&id=" + str(self.id) + "&filename_field=excel_file_name&field=excel_file&download=true&filename=" + self.excel_file_name,
                        'target': 'self',
                    }
            return action
    
    #Lógica de bancolombia PAB
    def get_excel_bancolombia_pab(self):        
        
        if self.payment_type != '220':
            raise ValidationError(_('El tipo de pago seleccionado no esta desarrollado por ahora, seleccione otro por favor.'))     
        
        result_columns_encab = self.get_columns_encab()
        result_columns_detail = self.get_columns_detail()
        result_query = self.run_sql()
        
        #Logica Archivo Plano
        if self.type_file == '1':
            filename= 'Archivo de Pago '+str(self.description)+'.txt'
            filler = ' '
            
            def left(s, amount):
                return s[:amount]
            
            def right(s, amount):
                return s[-amount:]
            
            #Encabezado - parte 1          
            tipo_registro_encab = '1'
            vat_payer = str(self.vat_payer).split("-")
            nit_entidad_originadora = right('0'*15+vat_payer[0],15)
            application = self.application
            filler_one = 15*filler
            clase_de_transaccion = self.payment_type
            descripcion_proposito = left(self.description+10*filler,10)
            date_today = fields.Date.context_today(self)
            fecha_transmision = right('0000'+str(date_today.year),4)+right('00'+str(date_today.month),2)+right('00'+str(date_today.day),2)
            secuencia_envio = right('00'+self.sequence,2)
            fecha_aplicacion = fecha_transmision
            num_registros = 'NumRegs' # Mas adelante se reeemplaza con el valor correcto
            sum_debitos = 17*'0'
            sum_creditos = 'SumCreditos' # Mas adelante se reeemplaza con el valor correcto
            cuenta_cliente = right(11*'0'+str(self.account_debit).replace("-",""),11)
            tipo_cuenta = self.account_type_debit
            filler_two = filler*149
            
            encab_content_txt = '%s%s%s%s%s%s%s%s%s%s%s%s%s%s%s' % (tipo_registro_encab,nit_entidad_originadora,application,filler_one,clase_de_transaccion,descripcion_proposito,fecha_transmision,secuencia_envio,fecha_aplicacion,num_registros,sum_debitos,sum_creditos,cuenta_cliente,tipo_cuenta,filler_two)
            
            #Detalle
            det_content_txt = ''
            tipo_registro_det = '6'
            indicador_lugar = 'S'
            numero_fax = 15*filler
            numero_identificacion_autorizado = 15*filler
            filler_three = 27*filler
            
            columns = 0
            cant_detalle = 0
            total_valor_transaccion = 0.0
            #Agregar query
            for query in result_query: 
                cant_detalle = cant_detalle + 1
                for row in query.values():
                    if columns == 0:
                        tipo_documento = row
                    if columns == 1:
                        nit_beneficiario = left(row+15*filler,15) 
                    if columns == 2: 
                        nombre_beneficiario = left(row+30*filler,30) 
                    if columns == 3:
                        tipo_transaccion = right('  '+row,2)
                    if columns == 4:
                        self.validate_info_bank(nit_beneficiario, nombre_beneficiario, row)
                        banco_destino = right('000000000'+row,9) 
                    if columns == 5:
                        no_cuenta_beneficiario = left(row+' '*17,17)
                    if columns == 6:
                        email = left(row+80*filler,80)
                    if columns == 7:
                        documento_autorizado = row
                    if columns == 8:
                        referencia = left(row+21*filler,21)
                    if columns == 9:
                        oficina_entrega = '0'*5
                    if columns == 10:
                        total_valor_transaccion = total_valor_transaccion + row
                        parte_decimal, parte_entera = math.modf(row)
                        parte_entera = str(parte_entera).split(".")
                        parte_decimal = str(parte_decimal).split(".")
                        valor_transaccion = right('0'*15+str(parte_entera[0]),15)+'00'#left(str(parte_decimal[0])+'00',2)  
                    if columns == 11:
                        fecha_aplicacion = row
                        
                    columns = columns + 1
                columns = 0
                
                content_line = '%s%s%s%s%s%s%s%s%s%s%s%s%s%s%s%s' % (tipo_registro_det,nit_beneficiario,nombre_beneficiario,banco_destino,no_cuenta_beneficiario,indicador_lugar,tipo_transaccion,valor_transaccion,fecha_aplicacion,referencia,tipo_documento,oficina_entrega,numero_fax,email,numero_identificacion_autorizado,filler_three)
                
                if cant_detalle == 1:
                    det_content_txt = content_line
                else:
                    det_content_txt = det_content_txt +'\n'+ content_line
                
            #Encabezado - parte 2            
            encab_content_txt = encab_content_txt.replace("NumRegs", right(6*'0'+str(cant_detalle),6))
            parte_decimal, parte_entera = math.modf(total_valor_transaccion)
            parte_entera = str(parte_entera).split(".")
            parte_decimal = str(parte_decimal).split(".")
            encab_content_txt = encab_content_txt.replace("SumCreditos", right('0'*15+str(parte_entera[0]),15)+'00')#left(str(parte_decimal[0])+'00',2)
            
            #Unir Encabezado y Detalle
            content_txt = encab_content_txt +'\n'+ det_content_txt            
            
            #Actualizar pagos
            self.update_payments()

            #Crear archivo        
            self.write({
                'txt_file': base64.encodestring((content_txt).encode()),
                #base64.encodestring((content).encode()).decode().strip()
                'txt_file_name': filename,
            })

            action = {
                        'name': 'ArchivoPagos',
                        'type': 'ir.actions.act_url',
                        'url': "web/content/?model=lavish.payment.file&id=" + str(self.id) + "&filename_field=txt_file_name&field=txt_file&download=true&filename=" + self.txt_file_name,
                        'target': 'self',
                    }
            return action

        #Logica Excel
        if self.type_file == '2':        
            raise ValidationError(_('El formato Bancolombia PAB no posee vista de excel.'))

    #Lógica de occired
    def get_excel_occired(self):        
        
        if self.payment_type != '220':
            raise ValidationError(_('El tipo de pago seleccionado no esta desarrollado por ahora, seleccione otro por favor.'))     
        
        result_columns_encab = self.get_columns_encab()
        result_columns_detail = self.get_columns_detail()
        result_query = self.run_sql()
        
        #Logica Archivo Plano
        if self.type_file == '1':
            filename= 'Archivo de Pago '+str(self.description)+'.txt'
            filler = ' '
            
            def left(s, amount):
                return s[:amount]
            
            def right(s, amount):
                return s[-amount:]
            
            #Encabezado - parte 1          
            tipo_registro_encab = '1'
            consecutivo = '0000'
            date_today = self.payment_date
            fecha_pago = str(date_today.year)+right('00'+str(date_today.month),2)+right('00'+str(date_today.day),2) 
            numero_registro = 'NumRegs'
            valor_total = 'ValTotal'
            cuenta_principal = right(16*'0'+str(self.account_debit).replace("-",""),16)
            identificacion_del_archivo = 6*'0'
            ceros = 142*'0'            
         
            encab_content_txt = '''%s%s%s%s%s%s%s%s''' % (tipo_registro_encab,consecutivo,fecha_pago,numero_registro,valor_total,cuenta_principal,identificacion_del_archivo,ceros)
            
            #Detalle
            det_content_txt = ''''''
            tipo_registro_det = '2'

            columns = 0
            cant_detalle = 0
            total_valor_transaccion = 0.0
            #Agregar query
            for query in result_query: 
                cant_detalle = cant_detalle + 1
                consecutivo = right('0000'+str(cant_detalle),4)
                forma_de_pago = '3' # 1: Pago en Cheque  2: Pago abono a cuenta  - Banco de Occidente  3: Abono a cuenta otras entidades
                for row in query.values():
                    if columns == 0:
                        tipo_documento = row
                    if columns == 1:
                        nit_beneficiario = right(11*'0'+row,11) 
                    if columns == 2: 
                        nombre_beneficiario = left(row+30*filler,30) 
                    if columns == 3:
                        tipo_transaccion = 'A' if row == '37' else 'A'
                        tipo_transaccion = 'C' if row == '27' else tipo_transaccion                        
                    if columns == 4:
                        self.validate_info_bank(nit_beneficiario, nombre_beneficiario, row)
                        banco_destino = '0'+right(3*'0'+row,3)
                        forma_de_pago = '2' if row == '1023' else forma_de_pago
                    if columns == 5:
                        no_cuenta_beneficiario = left(str(row).replace("-","")+filler*16,16)
                    if columns == 6:
                        email = left(row+80*filler,80)
                    if columns == 7:
                        numbers = [temp for temp in row.split("/") if temp.isdigit()]
                        documento_autorizado = ''
                        for i in numbers:
                            documento_autorizado = documento_autorizado + str(i)
                        documento_autorizado = right(filler*12+documento_autorizado,12)
                    if columns == 8:
                        referencia = left(row+80*filler,80)
                    if columns == 9:
                        oficina_entrega = '0'*5
                    if columns == 10:
                        total_valor_transaccion = total_valor_transaccion + round(row,0)
                        parte_decimal, parte_entera = math.modf(round(row,0))
                        parte_entera = str(parte_entera).split(".")
                        parte_decimal = str(parte_decimal).split(".")
                        valor_transaccion = right(13*'0'+str(parte_entera[0]),13)+'00'#left(str(parte_decimal[1])+'00',2)
                    if columns == 11:
                        fecha_aplicacion = row
                    if columns == 12:
                        digito_verificacion = str(row)
                        if str(tipo_documento) == '3':
                            nit_beneficiario = right(11*'0'+str(nit_beneficiario)+str(digito_verificacion),11)
                        
                    columns = columns + 1
                columns = 0
                    
                content_line = '''%s%s%s%s%s%s%s%s%s%s%s%s%s''' % (tipo_registro_det,consecutivo,cuenta_principal,nombre_beneficiario,nit_beneficiario,banco_destino,fecha_pago,forma_de_pago,valor_transaccion,no_cuenta_beneficiario,documento_autorizado,tipo_transaccion,referencia)
                if cant_detalle == 1:
                    det_content_txt = content_line
                else:
                    det_content_txt = det_content_txt +'\n'+ content_line
                
            #Encabezado - parte 2            
            encab_content_txt = encab_content_txt.replace("NumRegs", right('0000'+str(cant_detalle),4))
            parte_decimal, parte_entera = math.modf(total_valor_transaccion)
            parte_entera = str(parte_entera).split(".")
            parte_decimal = str(parte_decimal).split(".")
            encab_content_txt = encab_content_txt.replace("ValTotal", right(16*'0'+str(parte_entera[0]),16)+'00') #left(str(parte_decimal[1])+'00',2))
            
            #Totales
            tipo_registro_tot = '3'
            secuencia = '9999'
            numero_registro = right('0000'+str(cant_detalle),4)
            parte_decimal, parte_entera = math.modf(total_valor_transaccion)
            parte_entera = str(parte_entera).split(".")
            parte_decimal = str(parte_decimal).split(".")
            valor_total = right(16*'0'+str(parte_entera[0]),16)+'00'#left(str(parte_decimal[1])+'00',2)
            ceros = 172*'0'

            tot_content_txt = '''%s%s%s%s%s''' % (tipo_registro_tot,secuencia,numero_registro,valor_total,ceros)

            #Unir Encabezado, Detalle y Totales
            content_txt = encab_content_txt +'\n'+ det_content_txt +'\n'+ tot_content_txt            
            
            #Actualizar pagos
            self.update_payments()

            #Crear archivo        
            self.write({
                'txt_file': base64.encodestring((content_txt).encode()),
                #base64.encodestring((content).encode()).decode().strip()
                'txt_file_name': filename,
            })

            action = {
                        'name': 'ArchivoPagos',
                        'type': 'ir.actions.act_url',
                        'url': "web/content/?model=lavish.payment.file&id=" + str(self.id) + "&filename_field=txt_file_name&field=txt_file&download=true&filename=" + self.txt_file_name,
                        'target': 'self',
                    }
            return action
        
        
        #Logica Excel
        if self.type_file == '2':        
            raise ValidationError(_('El formato Occired no posee vista de excel.'))

    def get_excel(self):
        if self.format_file == 'bancolombia':
            return self.get_excel_bancolombia()
        if self.format_file == 'bancolombia_pab':
            return self.get_excel_bancolombia_pab()
        if self.format_file == 'occired':
            return self.get_excel_occired()

