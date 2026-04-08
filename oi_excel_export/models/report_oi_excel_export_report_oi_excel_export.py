'''
Created on Mar 3, 2021

@author: Zuhair Hammadi
'''
from odoo import models, api
import json

class Report(models.AbstractModel):
    _name = 'report.oi_excel_export.report_oi_excel_export'
    _description = _name
    
    @api.model
    def _get_report_values(self, docids, data= {}):    
        record = self.env['oi_excel_export'].browse(docids)
        if record.datas:
            vals = json.loads(record.datas)
            data.update(vals)
        return data