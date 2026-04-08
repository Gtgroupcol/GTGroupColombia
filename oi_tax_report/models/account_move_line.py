'''
Created on Feb 25, 2021

@author: Zuhair Hammadi
'''
from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    
    parent_type = fields.Selection(related='move_id.move_type', store=True, readonly=True)