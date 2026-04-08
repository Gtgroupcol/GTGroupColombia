# SISTEMA DE PRESTACIONES SOCIALES - ÍNDICE PRINCIPAL

**Fecha:** 2026-01-27
**Versión:** 2.0
**Módulo:** lavish_hr_employee

---

## 📚 DOCUMENTACIÓN COMPLETA

Este sistema de documentación está dividido en archivos especializados para facilitar la lectura y mantenimiento.

### 🗂️ Estructura de Archivos

```
docs/prestaciones/
├── 00_INDICE_PRINCIPAL.md .................. Este archivo
├── 01_ARQUITECTURA_GENERAL.md .............. Mapa de módulos y responsabilidades
├── 02_PRESTACIONES_CALCULO.md .............. prestaciones.py (Motor de cálculo)
├── 03_PRESTACIONES_DETALLE.md .............. prestaciones_detail.py (UI/Widget)
├── 04_PRESTACIONES_LIQUIDACION.md .......... prestaciones_liquidacion.py (Pagos)
├── 05_PRESTACIONES_PROVISIONES.md .......... prestaciones_provisiones.py (Provisiones)
├── 06_PRESTACIONES_VACACIONES.md ........... Vacaciones (separado)
├── 07_CONTRATOS_ENTRADA_SALIDA.md .......... Contratos entre métodos
├── 08_FORMULAS_DETALLADAS.md ............... Fórmulas con ejemplos
├── 09_CASOS_ESPECIALES.md .................. Salario integral, aprendices, etc.
└── 10_PRUEBAS_Y_RECOMENDACIONES.md ......... Testing y mejores prácticas
```

---

## 🎯 GUÍA DE LECTURA SEGÚN PERFIL

### Para **Desarrolladores Nuevos**
**Orden recomendado:**
1. [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md) - Entender la arquitectura
2. [07_CONTRATOS_ENTRADA_SALIDA.md](07_CONTRATOS_ENTRADA_SALIDA.md) - Ver contratos de datos
3. [02_PRESTACIONES_CALCULO.md](02_PRESTACIONES_CALCULO.md) - Motor principal
4. [08_FORMULAS_DETALLADAS.md](08_FORMULAS_DETALLADAS.md) - Fórmulas paso a paso

### Para **Mantener o Corregir Bugs**
**Ir directo a:**
1. [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md) - Ubicar el módulo afectado
2. Archivo específico del módulo (02, 03, 04, o 05)
3. [09_CASOS_ESPECIALES.md](09_CASOS_ESPECIALES.md) - Si involucra casos edge

### Para **Agregar Nueva Funcionalidad**
**Revisar:**
1. [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md) - Reglas de separación
2. [07_CONTRATOS_ENTRADA_SALIDA.md](07_CONTRATOS_ENTRADA_SALIDA.md) - No romper contratos
3. Archivo del módulo que modificarás
4. [10_PRUEBAS_Y_RECOMENDACIONES.md](10_PRUEBAS_Y_RECOMENDACIONES.md) - Agregar tests

### Para **Implementar Vacaciones**
**Documentación completa:**
- [06_PRESTACIONES_VACACIONES.md](06_PRESTACIONES_VACACIONES.md) - Todo sobre vacaciones

### Para **Auditar o Revisar Código**
**Checklist:**
1. [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md) - Validar separación de responsabilidades
2. [07_CONTRATOS_ENTRADA_SALIDA.md](07_CONTRATOS_ENTRADA_SALIDA.md) - Verificar contratos
3. [09_CASOS_ESPECIALES.md](09_CASOS_ESPECIALES.md) - Validar casos edge
4. [10_PRUEBAS_Y_RECOMENDACIONES.md](10_PRUEBAS_Y_RECOMENDACIONES.md) - Cobertura de tests

---

## 📖 RESUMEN DE CADA ARCHIVO

### [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md)
**Contenido:**
- Mapa de módulos y propósito de cada archivo
- Diagrama de arquitectura
- Responsabilidades por archivo
- Reglas de interacción (CLARAS Y CONCISAS)
- Flujos de llamadas permitidos

**Cuándo leer:** Antes de cualquier cambio

---

### [02_PRESTACIONES_CALCULO.md](02_PRESTACIONES_CALCULO.md)
**Archivo fuente:** `prestaciones.py`
**Modelo:** `hr.salary.rule.prestaciones`

**Contenido:**
- `calculate_prestacion()` - Orquestador principal
- `_get_period()` - Cálculo de periodos
- `_calculate_days()` - Días y ausencias
- `_calculate_value()` - Fórmulas matemáticas
- `_get_conditions()` - Configuración centralizada
- `_validate_conditions()` - Validaciones
- Métodos auxiliares públicos

**Responsabilidad:** SOLO calcula, NO adapta, NO presenta

---

### [03_PRESTACIONES_DETALLE.md](03_PRESTACIONES_DETALLE.md)
**Archivo fuente:** `prestaciones_detail.py`
**Modelo:** `hr.salary.rule.prestaciones.detail`

**Contenido:**
- `generate()` - Generador de 12 secciones
- Métodos `_build_*()` para cada sección
- Estructura completa del dict `detail`
- Ejemplos de salida JSON

**Responsabilidad:** SOLO presenta, NO calcula

---

### [04_PRESTACIONES_LIQUIDACION.md](04_PRESTACIONES_LIQUIDACION.md)
**Archivo fuente:** `prestaciones_liquidacion.py`
**Modelo:** `hr.salary.rule.prestaciones.liquidacion`

**Contenido:**
- Métodos de reglas: `_prima()`, `_cesantias()`, `_intcesantias()`, `_vaccontrato()`
- Año anterior: `_ces_year()`, `_intces_year()`
- `_adapt_result_for_slip()` - Adaptador crítico
- `liquidar_todas()` - Batch completo
- Validaciones de liquidación

**Responsabilidad:** Puente entre cálculo y nómina

---

### [05_PRESTACIONES_PROVISIONES.md](05_PRESTACIONES_PROVISIONES.md)
**Archivo fuente:** `prestaciones_provisiones.py`
**Modelo:** `hr.salary.rule.prestaciones.provisiones`

**Contenido:**
- Reglas de provisión: `_prv_prim()`, `_prv_ces()`, `_prv_ices()`, `_prv_vac()`
- Motor de provisión: `_calculate_provision_rule()`
- Consolidación: `_calculate_consolidacion()`
- Consultas: `_get_provision_acumulada()`, `_get_saldo_cuenta()`
- Integración contable

**Responsabilidad:** Provisiones mensuales y consolidación

---

### [06_PRESTACIONES_VACACIONES.md](06_PRESTACIONES_VACACIONES.md)
**Contenido completo de VACACIONES:**
- Cálculo de vacaciones en provisión
- Cálculo de vacaciones en liquidación
- Días acumulados y pendientes
- Fórmulas específicas
- Casos especiales de vacaciones
- Disfrutar vs liquidar
- Ejemplos detallados

**Por qué separado:** Las vacaciones tienen lógica diferente (disfrutar, acumular, compensar)

---

### [07_CONTRATOS_ENTRADA_SALIDA.md](07_CONTRATOS_ENTRADA_SALIDA.md)
**Contenido:**
- Contrato de `localdict` (entrada común)
- Contrato de `calculate_prestacion()` (salida estándar)
- Estructura de `detail` dict (12+ secciones)
- Contrato de `_adapt_result_for_slip()` (hr_slip)
- Contrato de `_calculate_consolidacion()` (consolidación)
- Campos críticos y obligatorios

**Crítico:** NO romper estos contratos

---

### [08_FORMULAS_DETALLADAS.md](08_FORMULAS_DETALLADAS.md)
**Contenido:**
- Prima: Fórmulas por contexto y provision_type
- Cesantías: Fórmulas detalladas
- Intereses: Todas las variantes (simple, promediado, porcentaje_fijo, liquidación)
- Vacaciones: Fórmulas y ejemplos
- Cálculo de días y ausencias
- Consolidación: Fórmula de ajuste
- Ejemplos numéricos completos

**Útil para:** Validar cálculos, debugging

---

### [09_CASOS_ESPECIALES.md](09_CASOS_ESPECIALES.md)
**Contenido:**
- Salario integral
- Aprendices (Ley 2466/2025)
- Auxilio de transporte (tope 2 SMMLV)
- Promedio de salario
- Variables y bonos
- Año anterior (CES_YEAR, INTCES_YEAR)
- Provisiones con `simple_provisions`
- Consolidación contable

**Útil para:** Casos edge, validaciones especiales

---

### [10_PRUEBAS_Y_RECOMENDACIONES.md](10_PRUEBAS_Y_RECOMENDACIONES.md)
**Contenido:**
- Pruebas unitarias recomendadas por archivo
- Ejemplos de tests
- Documentación recomendada
- Refactorización futura
- Monitoreo y logging
- Checklist de desarrollo
- Mejores prácticas

**Útil para:** Asegurar calidad, mantenimiento

---

## 🔍 BÚSQUEDA RÁPIDA

### Buscar por Tema

| Tema | Archivo |
|------|---------|
| Arquitectura general | 01_ARQUITECTURA_GENERAL.md |
| Método `calculate_prestacion()` | 02_PRESTACIONES_CALCULO.md |
| Fórmula de prima | 08_FORMULAS_DETALLADAS.md |
| Fórmula de cesantías | 08_FORMULAS_DETALLADAS.md |
| Fórmula de intereses | 08_FORMULAS_DETALLADAS.md |
| Fórmula de vacaciones | 06_PRESTACIONES_VACACIONES.md |
| Detalle para widget | 03_PRESTACIONES_DETALLE.md |
| Estructura de `detail` | 07_CONTRATOS_ENTRADA_SALIDA.md |
| Liquidación de contrato | 04_PRESTACIONES_LIQUIDACION.md |
| Provisión mensual | 05_PRESTACIONES_PROVISIONES.md |
| Consolidación | 05_PRESTACIONES_PROVISIONES.md |
| Salario integral | 09_CASOS_ESPECIALES.md |
| Aprendices | 09_CASOS_ESPECIALES.md |
| Auxilio de transporte | 09_CASOS_ESPECIALES.md |
| Año anterior | 09_CASOS_ESPECIALES.md |
| Pruebas unitarias | 10_PRUEBAS_Y_RECOMENDACIONES.md |
| Parámetros configurables | 01_ARQUITECTURA_GENERAL.md |

### Buscar por Método

| Método | Archivo |
|--------|---------|
| `calculate_prestacion()` | 02_PRESTACIONES_CALCULO.md |
| `_get_period()` | 02_PRESTACIONES_CALCULO.md |
| `_calculate_days()` | 02_PRESTACIONES_CALCULO.md |
| `_calculate_value()` | 02_PRESTACIONES_CALCULO.md, 08_FORMULAS_DETALLADAS.md |
| `_get_conditions()` | 02_PRESTACIONES_CALCULO.md |
| `generate()` (detail) | 03_PRESTACIONES_DETALLE.md |
| `_build_*()` | 03_PRESTACIONES_DETALLE.md |
| `_prima()`, `_cesantias()` | 04_PRESTACIONES_LIQUIDACION.md |
| `_adapt_result_for_slip()` | 04_PRESTACIONES_LIQUIDACION.md |
| `liquidar_todas()` | 04_PRESTACIONES_LIQUIDACION.md |
| `_prv_*()` | 05_PRESTACIONES_PROVISIONES.md |
| `_calculate_consolidacion()` | 05_PRESTACIONES_PROVISIONES.md |
| `_get_provision_acumulada()` | 05_PRESTACIONES_PROVISIONES.md |

### Buscar por Error Común

| Error | Dónde buscar |
|-------|--------------|
| Intereses incorrectos | 08_FORMULAS_DETALLADAS.md, 02_PRESTACIONES_CALCULO.md |
| Consolidación no cuadra | 05_PRESTACIONES_PROVISIONES.md |
| Auxilio no incluido | 09_CASOS_ESPECIALES.md |
| Días incorrectos | 02_PRESTACIONES_CALCULO.md, 08_FORMULAS_DETALLADAS.md |
| Widget no muestra datos | 03_PRESTACIONES_DETALLE.md, 07_CONTRATOS_ENTRADA_SALIDA.md |
| `monto_total` no existe | 07_CONTRATOS_ENTRADA_SALIDA.md |
| Salario integral no aplica | 09_CASOS_ESPECIALES.md |

---

## ⚠️ REGLAS CRÍTICAS (RESUMEN)

### 1. Separación de Responsabilidades
```
prestaciones.py → CALCULA (fórmulas matemáticas)
prestaciones_detail.py → PRESENTA (formatea para UI)
prestaciones_liquidacion.py → ADAPTA para nómina
prestaciones_provisiones.py → ADAPTA para contabilidad
```

### 2. Fuente Única de Verdad
```
TODO cálculo pasa por prestaciones.calculate_prestacion()
Los adaptadores NO recalculan, solo reformatean
```

### 3. Campo Crítico: monto_total
```python
# OBLIGATORIO en detail
detail['monto_total'] = valor  # hr_slip.py lo busca
```

### 4. Intereses de Cesantías
```python
# ✅ CORRECTO
cesantias = base_info.get('cesantias_calculadas', 0)

# ❌ INCORRECTO
cesantias = (base * dias) / 360  # NO recalcular
```

### 5. Exclusión de Auxilio
```python
# Líneas AUX se excluyen de variable
if category_code.upper() == 'AUX':
    continue
```

---

## 📞 CONTACTO Y MANTENIMIENTO

**Versión del Plan:** 2.0 (Modular)
**Última Actualización:** 2026-01-27

**Al Actualizar:**
1. Leer el archivo relevante completo
2. Actualizar la sección correspondiente
3. Ejecutar pruebas unitarias
4. Validar que no se rompan contratos
5. Actualizar ejemplos si cambian fórmulas

**Archivos de Código:**
- `lavish_hr_employee/models/reglas/prestaciones.py`
- `lavish_hr_employee/models/reglas/prestaciones_detail.py`
- `lavish_hr_employee/models/reglas/prestaciones_liquidacion.py`
- `lavish_hr_employee/models/reglas/prestaciones_provisiones.py`

---

## 🚀 INICIO RÁPIDO

### Primera vez leyendo esta documentación
```
1. Leer: 01_ARQUITECTURA_GENERAL.md
2. Revisar: 07_CONTRATOS_ENTRADA_SALIDA.md
3. Explorar: Archivo del módulo que te interesa (02-06)
```

### Necesitas implementar algo
```
1. Buscar tema en tabla "Búsqueda Rápida"
2. Ir al archivo indicado
3. Revisar contratos en 07_CONTRATOS_ENTRADA_SALIDA.md
4. Consultar ejemplos en 08_FORMULAS_DETALLADAS.md
```

### Necesitas corregir un bug
```
1. Identificar módulo afectado en 01_ARQUITECTURA_GENERAL.md
2. Revisar método específico en archivo del módulo
3. Verificar casos especiales en 09_CASOS_ESPECIALES.md
4. Agregar test en 10_PRUEBAS_Y_RECOMENDACIONES.md
```

---

**¡Documentación lista para usar!** 📚✨
