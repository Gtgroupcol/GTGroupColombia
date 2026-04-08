from odoo import fields, models, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    entity_code_cgn = fields.Char(string='Código de la entidad - CGN')
    
    # Temporary fields for Enterprise modules compatibility
    l10n_co_edi_username = fields.Char(string='EDI Username')
    documents_product_settings = fields.Boolean(string='Documents Product Settings')
    documents_account_settings = fields.Boolean(string='Documents Account Settings')
    documents_approvals_settings = fields.Boolean(string='Documents Approvals Settings')
    documents_hr_settings = fields.Boolean(string='Documents HR Settings')
    product_folder = fields.Many2one('documents.folder', string='Product Folder')
    account_folder = fields.Many2one('documents.folder', string='Account Folder')
    approvals_folder_id = fields.Many2one('documents.folder', string='Approvals Folder')
    recruitment_folder_id = fields.Many2one('documents.folder', string='Recruitment Folder')
    documents_hr_folder = fields.Many2one('documents.folder', string='HR Folder')
    documents_spreadsheet_folder_id = fields.Many2one('documents.folder', string='Spreadsheet Folder')

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    entity_code_cgn = fields.Char(related='company_id.entity_code_cgn', string='Código de la entidad - CGN', readonly=False)
    qty_thread_moves_balance = fields.Integer(string='Cantidad de registros - Hilos balance', default=10000)
    qty_thread_balance = fields.Integer(string='Cantidad de bloques - Hilos balance', default=5)
    
    # Temporary fields to fix Enterprise modules compatibility
    l10n_co_edi_username = fields.Char(related='company_id.l10n_co_edi_username', string='EDI Username', readonly=False, help='Temporary field for compatibility')
    documents_product_settings = fields.Boolean(related='company_id.documents_product_settings', string='Documents Product Settings', readonly=False, help='Temporary field for compatibility')
    documents_account_settings = fields.Boolean(related='company_id.documents_account_settings', string='Documents Account Settings', readonly=False, help='Temporary field for compatibility')
    documents_approvals_settings = fields.Boolean(related='company_id.documents_approvals_settings', string='Documents Approvals Settings', readonly=False, help='Temporary field for compatibility')
    documents_hr_settings = fields.Boolean(related='company_id.documents_hr_settings', string='Documents HR Settings', readonly=False, help='Temporary field for compatibility')
    product_folder = fields.Many2one('documents.folder', related='company_id.product_folder', string='Product Folder', readonly=False, help='Temporary field for compatibility')
    account_folder = fields.Many2one('documents.folder', related='company_id.account_folder', string='Account Folder', readonly=False, help='Temporary field for compatibility')
    approvals_folder_id = fields.Many2one('documents.folder', related='company_id.approvals_folder_id', string='Approvals Folder', readonly=False, help='Temporary field for compatibility')
    recruitment_folder_id = fields.Many2one('documents.folder', related='company_id.recruitment_folder_id', string='Recruitment Folder', readonly=False, help='Temporary field for compatibility')
    documents_hr_folder = fields.Many2one('documents.folder', related='company_id.documents_hr_folder', string='HR Folder', readonly=False, help='Temporary field for compatibility')
    documents_spreadsheet_folder_id = fields.Many2one('documents.folder', related='company_id.documents_spreadsheet_folder_id', string='Spreadsheet Folder', readonly=False, help='Temporary field for compatibility')

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param
        set_param('lavish_account.qty_thread_moves_balance', self.qty_thread_moves_balance)
        set_param('lavish_account.qty_thread_balance', self.qty_thread_balance)

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res['qty_thread_moves_balance'] = get_param('lavish_account.qty_thread_moves_balance')
        res['qty_thread_balance'] = get_param('lavish_account.qty_thread_balance')
        return res



