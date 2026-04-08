from odoo import api, models, fields, _

class MailingMailing(models.Model):
    _inherit = 'mailing.mailing'

    def action_put_in_queue(self):
        res = super().action_put_in_queue()

        cron = self.env.ref('mass_mailing.ir_cron_mass_mailing_queue')
        cron.method_direct_trigger()

        return res


