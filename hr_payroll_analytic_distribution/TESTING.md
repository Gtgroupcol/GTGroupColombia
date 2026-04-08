# Instrucciones para Pruebas del Módulo

## Verificación de Instalación

1. **Instalar el módulo**:
   - Ir a Apps
   - Buscar "HR Payroll Analytic Distribution"
   - Instalar

2. **Verificar dependencias**:
   - Verificar que `hr_payroll` esté instalado
   - Verificar que `analytic` esté activado
   - Verificar que `lavish_hr_payroll` esté funcional

## Pruebas Funcionales

### 1. Crear Cuentas Analíticas de Prueba

```
Facturación > Configuración > Contabilidad Analítica > Cuentas Analíticas
```

Crear al menos 3 cuentas:
- Departamento A
- Departamento B  
- Departamento C

### 2. Probar Widget de Distribución

1. Ir a Nómina > Recibos de Nómina
2. Crear/editar un recibo de nómina
3. Localizar campo "Distribución Analítica"
4. Hacer clic en el widget
5. Seleccionar múltiples cuentas
6. Asignar porcentajes que sumen 100%
7. Guardar

### 3. Validar Restricciones

#### Prueba de Suma Incorrecta:
- Configurar porcentajes que sumen 90%
- Intentar guardar
- Debe mostrar error: "La distribución analítica debe sumar 100%"

#### Prueba de Suma Correcta:
- Configurar: Cuenta A: 60%, Cuenta B: 40%
- Guardar
- Debe guardarse sin errores

### 4. Verificar Integración Contable

1. Procesar la nómina completamente
2. Ir a los asientos contables generados
3. Verificar que las líneas tengan distribución analítica
4. Confirmar que los porcentajes se aplican correctamente

### 5. Probar Comportamiento por Defecto

1. Crear empleado con contrato
2. Asignar cuenta analítica al contrato
3. Crear recibo de nómina para ese empleado
4. Verificar que se establezca distribución al 100% automáticamente

## Casos de Prueba Específicos

### Caso 1: Distribución 50/50
```
Cuenta A: 50%
Cuenta B: 50%
Total: 100%
```

### Caso 2: Distribución 3 Cuentas
```
Cuenta A: 60%
Cuenta B: 25%
Cuenta C: 15%
Total: 100%
```

### Caso 3: Distribución con Decimales
```
Cuenta A: 33.33%
Cuenta B: 33.33%
Cuenta C: 33.34%
Total: 100%
```

## Verificaciones de Regresión

1. **Nóminas sin distribución**: Deben funcionar normalmente
2. **Nóminas existentes**: No deben verse afectadas
3. **Reportes**: Deben mantener funcionalidad
4. **Dispersiones**: Deben incluir distribución analítica

## Problemas Conocidos

- Verificar compatibilidad con versiones específicas de Odoo
- Asegurar que el widget analytic_distribution esté disponible
- Validar permisos de usuario para cuentas analíticas

## Log de Errores Esperados

### Durante Desarrollo:
```
ValidationError: La distribución analítica debe sumar 100%
```
Este error es esperado y correcto cuando los porcentajes no suman 100%.

### Errores de Instalación:
```
ModuleNotFoundError: No module named 'analytic'
```
Instalar y activar el módulo `analytic`.

## Contacto

Para reportar problemas o sugerir mejoras, contactar al equipo de desarrollo.
