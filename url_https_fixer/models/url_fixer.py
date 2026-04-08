import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class UrlHttpsFixer(models.Model):
    _name = 'url.https.fixer'
    _description = 'URL HTTPS Fixer'

    @api.model
    def fix_url_https(self):
        """Consulta web.base.url y cambia HTTP a HTTPS (excepto localhost)"""
        try:
            # Consulta directa a ir_config_parameter como en tu consulta SQL
            self.env.cr.execute("""
                SELECT key, value 
                FROM ir_config_parameter 
                WHERE key = 'web.base.url'
            """)
            
            result = self.env.cr.fetchone()
            
            if not result:
                _logger.warning('URL HTTPS Fixer: No se encontró web.base.url en ir_config_parameter')
                return False
            
            key, current_url = result
            _logger.info('URL HTTPS Fixer: Consultando %s = %s', key, current_url)
            
            if not current_url:
                _logger.warning('URL HTTPS Fixer: web.base.url está vacío')
                return False
            
            # Si ya es HTTPS, todo está bien
            if current_url.startswith('https://'):
                _logger.info('URL HTTPS Fixer: ✓ URL ya usa HTTPS: %s', current_url)
                return True
            
            # Si contiene localhost, no cambiar
            if 'localhost' in current_url.lower():
                _logger.info('URL HTTPS Fixer: ✓ Localhost detectado, no se cambia: %s', current_url)
                return True
            
            # Si es HTTP (y no localhost), cambiar a HTTPS
            if current_url.startswith('http://'):
                new_url = current_url.replace('http://', 'https://', 1)
                
                # Actualizar en la base de datos
                self.env.cr.execute("""
                    UPDATE ir_config_parameter 
                    SET value = %s 
                    WHERE key = 'web.base.url'
                """, (new_url,))
                
                # Confirmar la transacción
                self.env.cr.commit()
                
                _logger.warning('URL HTTPS Fixer: ⚠️ HTTP cambiado a HTTPS: %s -> %s', current_url, new_url)
                return True
            
            # Si no tiene protocolo, agregar HTTPS (excepto localhost)
            if not current_url.startswith(('http://', 'https://')):
                if 'localhost' not in current_url.lower():
                    new_url = f'https://{current_url}'
                    
                    # Actualizar en la base de datos
                    self.env.cr.execute("""
                        UPDATE ir_config_parameter 
                        SET value = %s 
                        WHERE key = 'web.base.url'
                    """, (new_url,))
                    
                    # Confirmar la transacción
                    self.env.cr.commit()
                    
                    _logger.warning('URL HTTPS Fixer: ⚠️ HTTPS agregado: %s -> %s', current_url, new_url)
                else:
                    _logger.info('URL HTTPS Fixer: ✓ Localhost sin protocolo, no se modifica: %s', current_url)
                return True
                
        except Exception as e:
            _logger.error('URL HTTPS Fixer: ❌ Error verificando URL: %s', str(e))
            return False
