/** @odoo-module **/

/**
 * Index de Sub-componentes para PayslipLineDetail
 *
 * Este archivo exporta todos los sub-componentes creados para facilitar
 * la auditoría y mantenimiento del widget de detalle de línea de nómina.
 *
 * Estructura de componentes:
 *
 * PayslipLineDetail (principal)
 * ├── PayslipLineHeader       - Cabecera con código, nombre, badge devengo/deducción
 * ├── PayslipLineContextual   - Info contextual (préstamos, novedades, ausencias, vacaciones)
 * │
 * ├── Componentes por Tipo de Visualización:
 * │   ├── PayslipLineSimple       - Vista simple con KPIs en fila (reglas básicas)
 * │   ├── PayslipLineProvision    - Vista detallada de provisiones (4 pasos)
 * │   ├── PayslipLineSocialSecurity - Vista seguridad social y distribución de aportes
 * │   ├── PayslipLinePrestacion   - Vista de prestaciones (prima, cesantías, vacaciones)
 * │   ├── PayslipLineMultiPaso    - Vista multi-paso con timeline (IBD, retenciones)
 * │   └── PayslipLineFormula      - Vista de fórmula con 2 columnas + tablas
 * │
 * └── Componentes Especializados por Tipo de Regla:
 *     ├── PayslipLineBasic        - Salario básico (BASIC)
 *     ├── PayslipLineAuxilio      - Auxilios (AUX000, AUX00C)
 *     ├── PayslipLineIBD          - Base de cotización (IBD/IBC)
 *     ├── PayslipLineSSocial      - Seguridad social (SSOCIAL001-004)
 *     ├── PayslipLineRetencion    - Retención en la fuente (RTEFTE)
 *     ├── PayslipLineHorasExtras  - Horas extras y recargos (HEYREC)
 *     └── PayslipLineIndemnizacion - Indemnización (INDEM)
 */

// ============================================================================
// Componentes Comunes
// ============================================================================

// Header
export { PayslipLineHeader } from "./header/PayslipLineHeader";

// Contextual
export { PayslipLineContextual } from "./contextual/PayslipLineContextual";

// ============================================================================
// Componentes por Tipo de Visualización
// ============================================================================

// Simple View
export { PayslipLineSimple } from "./simple/PayslipLineSimple";

// Provision View
export { PayslipLineProvision } from "./provision/PayslipLineProvision";

// Social Security View
export { PayslipLineSocialSecurity } from "./social_security/PayslipLineSocialSecurity";

// Prestación View
export { PayslipLinePrestacion } from "./prestacion/PayslipLinePrestacion";

// Multi-Paso View
export { PayslipLineMultiPaso } from "./multi_paso/PayslipLineMultiPaso";

// Formula View
export { PayslipLineFormula } from "./formula/PayslipLineFormula";

// ============================================================================
// Componentes Especializados por Tipo de Regla
// ============================================================================

// Salario Básico (BASIC, BASIC001, BASIC002)
export { PayslipLineBasic } from "./basic/PayslipLineBasic";

// Auxilios (AUX000 transporte, AUX00C conectividad)
export { PayslipLineAuxilio } from "./auxilio/PayslipLineAuxilio";

// Ingreso Base de Cotización (IBD, IBC)
export { PayslipLineIBD } from "./ibd/PayslipLineIBD";

// Seguridad Social (SSOCIAL001 salud, SSOCIAL002 pensión, etc.)
export { PayslipLineSSocial } from "./ssocial/PayslipLineSSocial";

// Retención en la Fuente (RT_MET_01, RT_MET_02, RTEFTE)
export { PayslipLineRetencion } from "./retencion/PayslipLineRetencion";

// Horas Extras y Recargos (HEYREC, HE_ED, HE_EN, etc.)
export { PayslipLineHorasExtras } from "./horas_extras/PayslipLineHorasExtras";

// Indemnización por Despido (INDEM)
export { PayslipLineIndemnizacion } from "./indemnizacion/PayslipLineIndemnizacion";
