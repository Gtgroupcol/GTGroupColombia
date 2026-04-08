from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import logging
import gc
import os
import time

_logger = logging.getLogger(__name__)

class lavish_consecutive_audit_report(models.Model):
    _name = 'lavish.consecutive.audit.report'
    _description = 'Informe de auditoria de consecutivos'

    journal_ids = fields.Many2many('account.journal', string='Diarios')
    initial_date = fields.Date(string='Fecha inicial', required=True)
    end_date = fields.Date(string='Fecha final', required=True)


    def generate_report(self):
        datas = {
            'id': self.id,
            'model': 'lavish.consecutive.audit.report'
        }

        return {
            'type': 'ir.actions.report',
            'report_name': 'lavish_erp_reports_accounting.lavish_consecutive_audit_report_document',
            'report_type': 'qweb-html',
            'datas': datas
        }

    def find_missing_sequences(self, journal_id, move_type):
        # Primero, encontramos el número de secuencia máximo y mínimo para el diario y tipo de movimiento especificados
        self.env.cr.execute("""
            SELECT COALESCE(MIN(sequence_number), 1), COALESCE(MAX(sequence_number), 0) 
            FROM account_move 
            WHERE journal_id = %s AND move_type = %s
        """, (journal_id, move_type))
        min_sequence, max_sequence = self.env.cr.fetchone()
        
        # Luego, generamos los números de secuencia faltantes en grupos de 10 desde el mínimo hasta el máximo
        query = """
            WITH NumberSeries AS (
                SELECT generate_series(%s, %s, 10) AS start_range, 
                    LEAST(generate_series(%s + 9, %s + 9, 10), %s) AS end_range
            )
            SELECT start_range, end_range, 
                ARRAY(
                    SELECT generate_series(start_range, end_range) 
                    EXCEPT 
                    SELECT sequence_number 
                    FROM account_move 
                    WHERE journal_id = %s AND move_type = %s
                    ORDER BY sequence_number
                ) AS missing_sequences
            FROM NumberSeries;
        """
        self.env.cr.execute(query, (min_sequence, max_sequence, min_sequence, max_sequence, max_sequence, journal_id, move_type))
        
        return self.env.cr.dictfetchall()  # Esto retornará una lista de diccionarios


    def generate_info(self):

        def get_missing_sequences_text(missing_sequence_number):
            if not missing_sequence_number:
                return "Consecutivos correctos para este documento"

            ranges = []
            start = missing_sequence_number[0]
            end = missing_sequence_number[0]
            for seq in missing_sequence_number[1:]:
                if seq == end + 1:
                    end = seq
                else:
                    if start == end:
                        ranges.append(str(start))
                    else:
                        ranges.append(f"{start} al {end}")
                    start = end = seq

            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start} al {end}")

            return ", ".join(ranges) + " faltan."

        results = []
        document_types_dict = {
            'entry': 'Journal Entry',
            'out_invoice': 'Customer Invoice',
            'out_refund': 'Customer Credit Note',
            'in_invoice': 'Vendor Bill',
            'in_refund': 'Vendor Credit Note',
            'out_receipt': 'Sales Receipt',
            'in_receipt': 'Purchase Receipt',
        }
        for record in self:
            obj_journal = record.journal_ids if record.journal_ids else self.env['account.journal'].search([])

            for journal in obj_journal:
                domain = [
                    #('state', '=', 'posted'),
                    ('date', '>=', record.initial_date),
                    ('date', '<=', record.end_date),
                    ('journal_id', '=', journal.id)
                ]
                obj_account_move = self.env['account.move'].search(domain)
                document_types = list(set([move.move_type for move in obj_account_move]))

                for doc_type in document_types:
                    sequence_numbers = [i.sequence_number for i in obj_account_move if i.move_type == doc_type]
                    min_sequence_number = min(sequence_numbers)
                    max_sequence_number = max(sequence_numbers)

                    for group_start in range(min_sequence_number, max_sequence_number + 1, 10):
                        group_end = min(group_start + 9, max_sequence_number)

                        missing_sequence_number = [sequence for sequence in range(group_start, group_end + 1) if sequence not in sequence_numbers]
                        
                        missing_text = get_missing_sequences_text(missing_sequence_number)
                        doc_type = document_types_dict.get(doc_type, doc_type)
                        results.append({
                            'journal_id':journal.id,
                            'journal_name':journal.name,
                            'document_type': doc_type,
                            'min_sequence_number': group_start,
                            'max_sequence_number': group_end,
                            'missing_sequence_number': missing_text
                        })

        if results:
            return results
        else:
            raise ValidationError('No se encontró información con los filtros seleccionados, por favor verificar.')
