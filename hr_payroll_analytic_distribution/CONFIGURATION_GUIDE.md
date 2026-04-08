# Guía de Configuración de Cuentas Analíticas en Nómina

## 🎯 **Dónde Configurar las Cuentas Analíticas**

### 1. **Formulario de Recibo de Nómina Individual**

**Navegación**:
```
Nómina → Recibos de Nómina → Crear/Editar un recibo
```

**Ubicación del Campo**:
- En el formulario del recibo de nómina
- Campo: **"Distribución Analítica"**
- Posición: Antes del campo "Diario"
- Widget: Selector multicuenta con porcentajes

**Cómo Configurar**:
1. Hacer clic en el campo "Distribución Analítica"
2. Se abre un popup con selector de cuentas
3. Seleccionar múltiples cuentas analíticas
4. Asignar porcentajes a cada cuenta
5. Verificar que la suma sea 100%
6. Guardar el recibo

### 2. **Ejemplo de Configuración**

```json
{
    "Departamento Administrativo": 40%,
    "Departamento Operativo": 35%,
    "Departamento Ventas": 25%
}
```

## 📋 **Prerequisitos - Crear Cuentas Analíticas**

### Antes de configurar en nómina, debes crear las cuentas:

**Navegación**:
```
Facturación → Configuración → Contabilidad Analítica → Cuentas Analíticas
```

**Pasos**:
1. Hacer clic en "Crear"
2. Completar datos de la cuenta:
   - **Nombre**: Ej. "Departamento Administrativo"
   - **Código**: Ej. "ADMIN001"
   - **Compañía**: Seleccionar compañía
   - **Moneda**: Definir si es necesario
3. Guardar la cuenta
4. Repetir para todas las cuentas necesarias

## 🔧 **Configuración Avanzada**

### 1. **Por Defecto desde Contrato**
Si el empleado tiene una cuenta analítica en su contrato:
- El sistema la establece automáticamente al 100%
- Se puede modificar manualmente en el recibo

### 2. **Configuración en Lotes de Nómina**
Para configurar múltiples recibos a la vez:
- Ir a `Nómina → Lotes de Nómina`
- Crear un lote
- Los recibos heredarán la configuración individual

## 🎨 **Casos de Uso Comunes**

### Caso 1: Empleado Administrativo
```
- Administración: 70%
- Soporte TI: 30%
```

### Caso 2: Gerente Multiárea
```
- Ventas: 50%
- Marketing: 30%
- Administración: 20%
```

### Caso 3: Empleado de Proyecto
```
- Proyecto A: 60%
- Proyecto B: 40%
```

## ⚡ **Funcionalidades del Widget**

### Características del Selector:
- **Búsqueda inteligente**: Encuentra cuentas por nombre o código
- **Validación automática**: Verifica que sume 100%
- **Interfaz visual**: Muestra porcentajes de forma clara
- **Múltiples cuentas**: Sin límite en número de cuentas

### Validaciones:
- ✅ Suma debe ser exactamente 100%
- ✅ Porcentajes entre 0% y 100%
- ✅ Solo cuentas analíticas activas
- ✅ Cuentas de la compañía correcta

## 🔄 **Flujo de Trabajo**

1. **Preparación**:
   - Crear cuentas analíticas necesarias
   - Definir estructura de distribución

2. **Configuración**:
   - Abrir recibo de nómina
   - Configurar distribución analítica
   - Validar porcentajes

3. **Procesamiento**:
   - Procesar nómina normalmente
   - Los asientos contables se distribuyen automáticamente

4. **Verificación**:
   - Revisar asientos contables generados
   - Confirmar distribución correcta

## 📊 **Reportes y Análisis**

### Los costos distribuidos aparecen en:
- **Reportes de contabilidad analítica**
- **Balance analítico**
- **Análisis de costos por departamento/proyecto**
- **Reportes de nómina detallados**

## ⚠️ **Notas Importantes**

- La distribución se aplica a **todos** los conceptos de nómina
- Si no se configura, usa la cuenta del contrato (100%)
- La configuración es **por recibo individual**
- Se puede modificar antes de confirmar la nómina

## 🆘 **Resolución de Problemas**

### Error: "La suma debe ser 100%"
- Verificar que los porcentajes sumen exactamente 100%
- Ajustar decimales si es necesario

### No aparece el campo
- Verificar que el módulo esté instalado
- Refrescar la página del navegador

### Cuentas no disponibles
- Verificar que las cuentas analíticas estén activas
- Confirmar que pertenecen a la compañía correcta
