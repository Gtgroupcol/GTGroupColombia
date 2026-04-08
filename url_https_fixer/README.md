# URL HTTPS Fixer

Módulo simple que hace exactamente lo que pediste:

## Funcionamiento

1. **Consulta SQL cada minuto**: 
   ```sql
   SELECT key, value FROM ir_config_parameter WHERE key = 'web.base.url';
   ```

2. **Cambia HTTP a HTTPS automáticamente**
3. **EXCEPCIÓN**: No modifica URLs que contengan `localhost`

## Logs

Puedes ver la actividad en tiempo real:

```bash
# Ver logs del módulo
sudo journalctl -u odoo17 -f | grep "URL HTTPS Fixer"
```

### Tipos de mensajes:

- `✓ URL ya usa HTTPS` - Todo correcto
- `✓ Localhost detectado, no se cambia` - Localhost respetado
- `⚠️ HTTP cambiado a HTTPS` - Se realizó corrección
- `❌ Error verificando URL` - Ocurrió un problema

## Instalación

1. Instala desde Apps → URL HTTPS Fixer
2. Se activará automáticamente cada minuto

## Desactivar

Si necesitas desactivarlo:
1. Apps → URL HTTPS Fixer → Desinstalar

El módulo es completamente automático y respeta localhost como solicitaste.
