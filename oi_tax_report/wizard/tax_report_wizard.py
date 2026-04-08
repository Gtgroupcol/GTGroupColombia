'''
Created on Feb 18, 2021

@author: Zuhair Hammadi
'''
from odoo import models, fields, api, _
from odoo.tools.misc import groupby


label_move_type = {
    'entry': 'Asiento contable' ,
    'out_invoice': 'Factura de cliente',
    'out_refund': 'Nota de crédito del cliente',
    'in_invoice': 'Factura de proveedor',
    'in_refund': 'Nota de crédito de proveedor' ,
    'out_receipt': 'Recibo de ventas',
    'in_receipt': 'Recibo de compra'
}

class TaxReportWizard(models.TransientModel):
    _name='tax.report.wizard'
    _description = 'Tax Report Wizard'
    
    @api.model
    def _get_move_type_ids_domain(self):
        return [('field_id', '=', self.env['ir.model.fields']._get('account.move','move_type').id)]
    
    @api.model
    def _get_move_state_ids_domain(self):
        return [('field_id', '=', self.env['ir.model.fields']._get('account.move','state').id), ('value','!=', 'cancel')]
    
    @api.model
    def _get_move_state_ids(self):
        domain =  [('field_id', '=', self.env['ir.model.fields']._get('account.move','state').id), ('value','=', 'posted')]
        return self.env['ir.model.fields.selection'].search(domain)
            
    @api.model
    def _get_type_tax_use_id_domain(self):
        return [('field_id', '=', self.env['ir.model.fields']._get('account.tax','type_tax_use').id)]

        
    date_from = fields.Date(required = True)
    date_to = fields.Date(required = True)
    company_id = fields.Many2one('res.company', required = True, default = lambda self : self.env.company)
    journal_ids = fields.Many2many('account.journal')
    tax_ids = fields.Many2many('account.tax')    
    tax_group_ids = fields.Many2many('account.tax.group')    
    tag_ids = fields.Many2many(string="Tags", comodel_name='account.account.tag')
    move_type_ids = fields.Many2many('ir.model.fields.selection', string="Entry Type", domain = _get_move_type_ids_domain, relation= "tax_report_wizard_move_type_rel")
    move_state_ids = fields.Many2many('ir.model.fields.selection', 
                                      string="Entry Status", 
                                      domain = _get_move_state_ids_domain, 
                                      relation= "tax_report_wizard_move_state_rel", 
                                      default = _get_move_state_ids)
    type_tax_use_ids = fields.Many2many('ir.model.fields.selection', 
                                        string='Tax Scope', 
                                        relation= "tax_report_wizard_move_tax_use_rel", 
                                        domain = _get_type_tax_use_id_domain)
    
    
    def name_get(self):
        res = []
        for record in self:
            res.append((record.id, _('Tax Report')))
        return res


            
    
    def _get_columns(self):
        res = [
                (_('Date'),False, lambda record: record.env['ir.qweb.field.date'].value_to_html(record.date, {})),
                (_('Document No'),False, lambda record: record.move_id.name or ''),  
                (_('Document Type'), False, lambda record: label_move_type[record.move_id.move_type] if record.move_id.move_type else ''),
                (_('Partner'),False, lambda record: record.partner_id.name or ''),           
                (_('Partner Tax ID'), False, lambda record: record.partner_id.vat or ''),                                              
                (_('Tax'), False, lambda record: record.tax_line_id.description or record.tax_line_id.display_name),        
                (_("Base Amount"), False, lambda record: record.tax_base_amount),
                (_("Tax Amount"), True, lambda record: record.balance * (record.tax_line_id.type_tax_use == "sale" and -1 or 1)),
                (_("Total Amount"), True, lambda record: record.move_id.amount_total_signed * (record.tax_line_id.type_tax_use == "sale" and 1 or -1)),
            ]
        if self.env.user.has_group('analytic.group_analytic_tags'):
            res.insert(3, (_('Analytic Tags'), False, lambda record: ', '.join(record.mapped('move_id.line_ids.analytic_tag_ids.name'))))
            
        return res
            
        
    def _get_domain(self):
        domain = [('date','>=', self.date_from),
                  ('date','<=', self.date_to), 
                  ('tax_line_id','!=', False), 
                  ('parent_state','!=', 'cancel'), 
                  ('company_id','=', self.company_id.id), 
                  ]
        
        if self.journal_ids:
            domain.append(('journal_id','in', self.journal_ids.ids))
        
        if self.tax_ids:
            domain.append(('tax_line_id','in', self.tax_ids.ids))
        
        if self.tax_group_ids:
            domain.append(('tax_group_id','in', self.tax_group_ids.ids))
            
        if self.tag_ids:
            domain.append(('tax_tag_ids','in', self.tag_ids.ids))
                
        if self.move_type_ids:
            domain.append(('parent_type','in', self.mapped('move_type_ids.value')))
            
        if self.move_state_ids:
            domain.append(('parent_state','in', self.mapped('move_state_ids.value')))
            
        if self.type_tax_use_ids:
            domain.append(('tax_line_id.type_tax_use','in', self.mapped('type_tax_use_ids.value')))
        
        return domain
        
    def _get_domain_zero_tax(self):
        domain = [('date','>=', self.date_from),
                  ('date','<=', self.date_to), 
                  ('tax_ids.amount','=', 0), 
                  ('parent_state','!=', 'cancel'), 
                  ('company_id','=', self.company_id.id),                   
                  ]
        
        if self.journal_ids:
            domain.append(('journal_id','in', self.journal_ids.ids))
        
        if self.tax_ids:
            domain.append(('tax_ids','in', self.tax_ids.ids))
        
        if self.tax_group_ids:
            domain.append(('tax_ids.tax_group_id','in', self.tax_group_ids.ids))
            
        if self.tag_ids:
            domain.append(('tax_tag_ids','in', self.tag_ids.ids))
                
        if self.move_type_ids:
            domain.append(('parent_type','in', self.mapped('move_type_ids.value')))
            
        if self.move_state_ids:
            domain.append(('parent_state','in', self.mapped('move_state_ids.value')))
            
        if self.type_tax_use_ids:
            domain.append(('tax_ids.type_tax_use','in', self.mapped('type_tax_use_ids.value')))
        
        return domain
    
    def _get_data(self):
        domain = self._get_domain()
            
        records = self.env['account.move.line'].search(domain, order = 'date,id')

        #raise ValueError([records,domain])
        
        domain = self._get_domain_zero_tax()
        
        zero_based_records = self.env['account.move.line'].search(domain, order = 'date,id')
        
        if zero_based_records:
            existing_records = set(records.mapped(lambda record: (record.move_id.id, record.tax_line_id.id)))
            new_records = self.env['account.move.line']
            
            for record in zero_based_records:
                move = record.move_id
                base_line = record
                if move.is_invoice(include_receipts=True):
                    sign = -1 if move.is_inbound() else 1
                    quantity = base_line.quantity
                    price_unit_wo_discount = sign * base_line.price_unit * (1 - (base_line.discount / 100.0))
                else:
                    price_unit_wo_discount = base_line.amount_currency
                    quantity = 1.0
                                
                for tax in record.tax_ids:
                    if tax.amount !=0:
                        continue
                    if (record.move_id.id, tax.id) in existing_records:
                        continue
                    tax_base_amount = abs(price_unit_wo_discount * quantity)
                    
                    new_records += self.env['account.move.line'].new({
                        'move_id' : record.move_id.id,
                        'tax_line_id' : tax.id,
                        'date' : record.date,
                        'partner_id' : record.partner_id.id,
                        'debit' : 0,
                        'credit' : 0,
                        'balance' : 0,
                        'tax_base_amount' : tax_base_amount          
                        })      
                    
            for (move_id, tax_id), move_new_records in groupby(new_records, key = lambda record: (record.move_id, record.tax_line_id)):  # @UnusedVariable
                new_record = move_new_records[0]
                new_record.tax_base_amount = sum(rec.tax_base_amount for rec in move_new_records)
                records += new_record
                    
            records = records.sorted(key = lambda rec : (rec.date, rec.move_id.id, rec.id or 0))
        
        tax_scope_names = dict(self.env['account.tax']._fields['type_tax_use']._description_selection(self.env))
        
        rows = []
        header = []
        summary_rows = []
        title_rows = []
        empty_rows = []
        row_merge_cells = []
        columns_count = 0
        
        for name,add_total, func in self._get_columns():
            header.append(name)
            columns_count +=1
        rows.append(header)
        
        grand_totals = []
        
        no_total_cols = 0
        for name,add_total, func in self._get_columns():
            if add_total:
                break
            no_total_cols +=1
            
        total_groups = 0                 
                        
        for tax_scope_value, tax_scope_records in sorted(groupby(records, key = lambda record : record.tax_line_id.type_tax_use), reverse = True):  # @UnusedVariable
            tax_scope_name = tax_scope_names.get(tax_scope_value)
            totals = []
            title = []
            total_groups +=1
            
            move_added = set()
            
            for name,add_total, func in self._get_columns():
                if not totals:
                    totals.append(_('Total For %s') % tax_scope_name)
                    title.append(tax_scope_name)
                    
                    if not grand_totals:
                        grand_totals.append(_('Grand Total'))
                    
                    continue
                value = 0 if add_total else None
                totals.append(value)
                title.append(None)
                if len(grand_totals) < columns_count:
                    grand_totals.append(value)
                                
            title_rows.append(len(rows))  
            row_merge_cells.append((len(rows), 0, columns_count -1 ))
            rows.append(title)
            
            for record in tax_scope_records:
                                
                row = []
                for col_idx, (name,add_total, func) in enumerate(self._get_columns()):
                    value = func(record)
                    row.append(value)
                    if add_total:
                        if name !=_("Total Amount") or record.move_id.id not in move_added:
                            totals[col_idx] += value or 0
                            grand_totals[col_idx] += (value or 0) * (tax_scope_value=="purchase" and -1 or 1)
                        
                move_added.add(record.move_id.id)
                                            
                rows.append(row)
            
            summary_rows.append(len(rows))  
            row_merge_cells.append((len(rows), 0, no_total_cols -1 ))
            rows.append(totals)
        
        if total_groups > 1:
        
            empty_rows.append(len(rows))  
            rows.append([None] * columns_count)
        
            summary_rows.append(len(rows))  
            row_merge_cells.append((len(rows), 0, no_total_cols -1 ))
            rows.append(grand_totals)            
            
        format_date = lambda value : self.env['ir.qweb.field.date'].value_to_html(value, {})
        filename =  _('Tax Report %s - %s') % (format_date(self.date_from), format_date(self.date_to))
        return {
            'rows' : rows,
            'summary_rows' : summary_rows,
            'title_rows' : title_rows,
            'empty_rows' : empty_rows,            
            'row_merge_cells' : row_merge_cells,
            'add_row_total' : False,
            'filename' : filename,
            'worksheet_name' : '%s - %s' % (self.date_from, self.date_to),
            'page_header' : filename,
            'decimal_places' : self.company_id.currency_id.decimal_places
            }
            
    
    def action_excel(self):        
        data = self._get_data()
        #raise ValueError(data)
        return self.env['oi_excel_export'].export(**data)
    
    def action_qweb(self):
        data = self._get_data()
        data.update({
            'report_title' : data['filename'],
            'wizard_ref' : "%s,%d" % (self._name, self.id)
            })
        action = self.env['oi_excel_export'].export_qweb(data)
        if self._context.get('report_type'):
            action['report_type'] = self._context.get('report_type')
        
        action.update({
            'display_name' : data['filename']
            })
        return action
            