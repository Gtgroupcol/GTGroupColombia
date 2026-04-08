# 📚 DOCUMENTACIÓN - SISTEMA DE PRESTACIONES SOCIALES

**Módulo:** lavish_hr_employee
**Versión:** 2.0 (Modular)
**Última Actualización:** 2026-01-27

---

## 🚀 INICIO RÁPIDO

### ¿Primera vez?
**Leer en este orden:**
1. [00_INDICE_PRINCIPAL.md](00_INDICE_PRINCIPAL.md) - Índice completo
2. [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md) - Arquitectura del sistema
3. [07_CONTRATOS_ENTRADA_SALIDA.md](07_CONTRATOS_ENTRADA_SALIDA.md) - Contratos de datos

### ¿Necesitas implementar algo?
**Busca en el índice:**
- [00_INDICE_PRINCIPAL.md](00_INDICE_PRINCIPAL.md) tiene tablas de búsqueda rápida

---

## 📁 ESTRUCTURA DE LA DOCUMENTACIÓN

```
docs/prestaciones/
├── 00_INDICE_PRINCIPAL.md .............. Navegación completa
├── 01_ARQUITECTURA_GENERAL.md .......... Responsabilidades y flujos
├── 02_PRESTACIONES_CALCULO.md .......... Motor de cálculo (prestaciones.py)
├── 03_PRESTACIONES_DETALLE.md .......... Generador UI (prestaciones_detail.py)
├── 04_PRESTACIONES_LIQUIDACION.md ...... Pagos (prestaciones_liquidacion.py)
├── 05_PRESTACIONES_PROVISIONES.md ...... Provisiones (prestaciones_provisiones.py)
├── 06_PRESTACIONES_VACACIONES.md ....... Todo sobre vacaciones
├── 07_CONTRATOS_ENTRADA_SALIDA.md ...... Contratos entre métodos
├── 08_FORMULAS_DETALLADAS.md ........... Fórmulas con ejemplos
├── 09_CASOS_ESPECIALES.md .............. Casos edge
└── 10_PRUEBAS_Y_RECOMENDACIONES.md ..... Testing y mejores prácticas
```

---

## 🎯 BÚSQUEDA POR TEMA

### Arquitectura y Diseño
- **Arquitectura general:** [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md)
- **Separación de responsabilidades:** [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md)
- **Flujos de datos:** [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md)

### Cálculo de Prestaciones
- **Motor de cálculo (prestaciones.py):** [02_PRESTACIONES_CALCULO.md](02_PRESTACIONES_CALCULO.md)
- **Fórmulas detalladas:** [08_FORMULAS_DETALLADAS.md](08_FORMULAS_DETALLADAS.md)
- **Casos especiales:** [09_CASOS_ESPECIALES.md](09_CASOS_ESPECIALES.md)

### Prestaciones Específicas
- **Prima:** [08_FORMULAS_DETALLADAS.md](08_FORMULAS_DETALLADAS.md#prima-de-servicios)
- **Cesantías:** [08_FORMULAS_DETALLADAS.md](08_FORMULAS_DETALLADAS.md#cesantías)
- **Intereses:** [08_FORMULAS_DETALLADAS.md](08_FORMULAS_DETALLADAS.md#intereses-de-cesantías)
- **Vacaciones:** [06_PRESTACIONES_VACACIONES.md](06_PRESTACIONES_VACACIONES.md)

### Operaciones
- **Liquidación:** [04_PRESTACIONES_LIQUIDACION.md](04_PRESTACIONES_LIQUIDACION.md)
- **Provisión:** [05_PRESTACIONES_PROVISIONES.md](05_PRESTACIONES_PROVISIONES.md)
- **Consolidación:** [05_PRESTACIONES_PROVISIONES.md](05_PRESTACIONES_PROVISIONES.md)

### Desarrollo
- **Contratos de datos:** [07_CONTRATOS_ENTRADA_SALIDA.md](07_CONTRATOS_ENTRADA_SALIDA.md)
- **Pruebas unitarias:** [10_PRUEBAS_Y_RECOMENDACIONES.md](10_PRUEBAS_Y_RECOMENDACIONES.md)
- **Widget UI:** [03_PRESTACIONES_DETALLE.md](03_PRESTACIONES_DETALLE.md)

---

## ⚡ ACCESO RÁPIDO

### Por Archivo de Código

| Archivo Código | Documentación |
|----------------|---------------|
| `prestaciones.py` | [02_PRESTACIONES_CALCULO.md](02_PRESTACIONES_CALCULO.md) |
| `prestaciones_detail.py` | [03_PRESTACIONES_DETALLE.md](03_PRESTACIONES_DETALLE.md) |
| `prestaciones_liquidacion.py` | [04_PRESTACIONES_LIQUIDACION.md](04_PRESTACIONES_LIQUIDACION.md) |
| `prestaciones_provisiones.py` | [05_PRESTACIONES_PROVISIONES.md](05_PRESTACIONES_PROVISIONES.md) |

### Por Método

| Método | Archivo |
|--------|---------|
| `calculate_prestacion()` | [02_PRESTACIONES_CALCULO.md](02_PRESTACIONES_CALCULO.md) |
| `_calculate_value()` | [02_PRESTACIONES_CALCULO.md](02_PRESTACIONES_CALCULO.md), [08_FORMULAS_DETALLADAS.md](08_FORMULAS_DETALLADAS.md) |
| `generate()` (detail) | [03_PRESTACIONES_DETALLE.md](03_PRESTACIONES_DETALLE.md) |
| `_adapt_result_for_slip()` | [04_PRESTACIONES_LIQUIDACION.md](04_PRESTACIONES_LIQUIDACION.md), [07_CONTRATOS_ENTRADA_SALIDA.md](07_CONTRATOS_ENTRADA_SALIDA.md) |
| `_calculate_consolidacion()` | [05_PRESTACIONES_PROVISIONES.md](05_PRESTACIONES_PROVISIONES.md) |

### Por Error Común

| Error | Solución |
|-------|----------|
| Intereses incorrectos | [08_FORMULAS_DETALLADAS.md](08_FORMULAS_DETALLADAS.md#intereses-de-cesantías) |
| Consolidación no cuadra | [05_PRESTACIONES_PROVISIONES.md](05_PRESTACIONES_PROVISIONES.md) |
| Falta `monto_total` | [07_CONTRATOS_ENTRADA_SALIDA.md](07_CONTRATOS_ENTRADA_SALIDA.md) |
| Días incorrectos | [08_FORMULAS_DETALLADAS.md](08_FORMULAS_DETALLADAS.md#cálculo-de-días) |

---

## 🎓 GUÍAS DE LECTURA

### Para Desarrolladores Nuevos
```
1. 00_INDICE_PRINCIPAL.md (navegación)
2. 01_ARQUITECTURA_GENERAL.md (entender sistema)
3. 07_CONTRATOS_ENTRADA_SALIDA.md (contratos de datos)
4. 02_PRESTACIONES_CALCULO.md (motor principal)
```

### Para Corregir Bugs
```
1. 00_INDICE_PRINCIPAL.md (buscar tema)
2. Archivo específico del módulo afectado
3. 09_CASOS_ESPECIALES.md (si es caso edge)
```

### Para Agregar Funcionalidad
```
1. 01_ARQUITECTURA_GENERAL.md (reglas de separación)
2. 07_CONTRATOS_ENTRADA_SALIDA.md (no romper contratos)
3. Archivo del módulo a modificar
4. 10_PRUEBAS_Y_RECOMENDACIONES.md (agregar tests)
```

---

## ⚠️ REGLAS CRÍTICAS

### 1. Separación de Responsabilidades
```
prestaciones.py → CALCULA (fórmulas)
prestaciones_detail.py → PRESENTA (UI)
prestaciones_liquidacion.py → ADAPTA (nómina)
prestaciones_provisiones.py → ADAPTA (contabilidad)
```

### 2. Campo Obligatorio
```python
detail['monto_total'] = valor  # hr_slip.py lo busca
```

### 3. Intereses de Cesantías
```python
# ✅ CORRECTO
cesantias = base_info.get('cesantias_calculadas', 0)

# ❌ INCORRECTO
cesantias = (base * dias) / 360  # NO recalcular
```

### 4. Exclusión de Auxilio
```python
# Líneas AUX se excluyen de variable
if category_code.upper() == 'AUX':
    continue
```

---

## 📞 SOPORTE

### Reportar Problemas
- GitHub Issues: [gtgroupcolombia](https://github.com/alejoxdc/gtgroupcolombia)

### Actualizar Documentación
1. Editar el archivo correspondiente
2. Actualizar fecha en metadata
3. Validar links internos
4. Ejecutar pruebas

---

## 🔗 ENLACES ÚTILES

### Código Fuente
- `lavish_hr_employee/models/reglas/prestaciones.py`
- `lavish_hr_employee/models/reglas/prestaciones_detail.py`
- `lavish_hr_employee/models/reglas/prestaciones_liquidacion.py`
- `lavish_hr_employee/models/reglas/prestaciones_provisiones.py`

### Documentación Relacionada
- Configuración de parámetros
- Guía de instalación
- Changelog

---

**¡Documentación lista para usar!** 📚✨

**Siguiente paso:** Leer [00_INDICE_PRINCIPAL.md](00_INDICE_PRINCIPAL.md)
