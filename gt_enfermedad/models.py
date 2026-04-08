from odoo import api, fields, models , _
from odoo.exceptions import ValidationError, UserError

class HrGtEnfermedad(models.Model):
    _name    = 'hr.gt.enfermedad'
    _description = 'hr.gt.enfermedad'
    _rec_name = 'description'
    _rec_names_search = ['description', 'code']

    code     = fields.Char(required=True)
    description     = fields.Text(required=True,string="Descripcion")




class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'
    enfermedad_id = fields.Many2one('hr.gt.enfermedad',string="Enfermedad")

