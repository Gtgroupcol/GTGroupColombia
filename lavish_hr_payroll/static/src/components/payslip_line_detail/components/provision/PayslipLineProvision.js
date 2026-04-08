/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * PayslipLineProvision - Vista detallada de provisiones
 * Muestra 4 pasos: Base, Días, Fórmula, Resultado
 *
 * Props:
 * - provisionData: Object - Datos de la provisión procesados
 * - ruleConfig: Object - Configuración visual de la regla
 * - formatCurrency: Function - Función para formatear moneda
 * - formatValue: Function - Función para formatear valores
 * - getLeyUrl: Function - Función para obtener URL de ley
 */

const PROVISION_CODE_MAP = {
    'prima': ['PROV_PRIMA', 'PROVISION_PRIMA', 'PRV_PRIM', 'PRV_PRIMA'],
    'cesantias': ['PROV_CESANTIAS', 'PROVISION_CESANTIAS', 'PRV_CES', 'PRV_CESANTIAS'],
    'intereses': ['PROV_INT_CESANTIAS', 'PROVISION_INT_CESANTIAS', 'PROV_INTERESES', 'PRV_ICES', 'PRV_INT'],
    'vacaciones': ['PROV_VACACIONES', 'PROVISION_VACACIONES', 'PRV_VAC', 'PRV_VACACIONES'],
};

export class PayslipLineProvision extends Component {
    static template = "lavish_hr_payroll.PayslipLineProvision";
    static props = {
        provisionData: { type: Object },
        ruleConfig: { type: Object },
        formatCurrency: { type: Function },
        formatValue: { type: Function },
        getLeyUrl: { type: Function },
    };

    setup() {
        this.state = useState({
            expandedSteps: { 1: true, 2: true, 3: true, 4: true },
        });
        this.actionService = useService("action");
    }

    toggleStep(stepNum) {
        this.state.expandedSteps[stepNum] = !this.state.expandedSteps[stepNum];
    }

    isStepExpanded(stepNum) {
        return this.state.expandedSteps[stepNum] || false;
    }

    scrollToStep(stepNum) {
        if (!this.state.expandedSteps[stepNum]) {
            this.state.expandedSteps[stepNum] = true;
        }
    }

    get data() {
        return this.props.provisionData || {};
    }

    get hasConceptos() {
        return this.data.conceptosIncluidos && this.data.conceptosIncluidos.length > 0;
    }

    get hasFormulaPasos() {
        return this.data.formulaPasos && this.data.formulaPasos.length > 0;
    }

    get hasIndicadores() {
        return this.data.indicadores && this.data.indicadores.length > 0;
    }

    get hasWarnings() {
        return this.data.warnings && this.data.warnings.length > 0;
    }

    get hasProvisionLineas() {
        return this.data.provisionLineas && this.data.provisionLineas.length > 0;
    }

    get showComparativa() {
        return this.data.valorAnterior > 0;
    }

    get showFechas() {
        return this.data.fechaInicio || this.data.fechaCorte;
    }

    get canNavigateAccumulated() {
        const d = this.data;
        if (d.fuenteAcumulado === 'contabilidad') {
            return !!d.cuentaBalanceId;
        }
        return !!(d.contractId && d.tipoPrestacion);
    }

    openAccumulatedRecords() {
        const d = this.data;
        if (d.fuenteAcumulado === 'contabilidad') {
            this._openAccountingEntries(d);
        } else {
            this._openPayslipLines(d);
        }
    }

    _openPayslipLines(d) {
        const codes = PROVISION_CODE_MAP[d.tipoPrestacion] || [];
        if (!codes.length || !d.contractId) return;

        const domain = [
            ['code', 'in', codes],
            ['slip_id.contract_id', '=', d.contractId],
            ['slip_id.state', 'in', ['done', 'paid']],
        ];
        if (d.datePeriodFrom) {
            domain.push(['slip_id.date_from', '>=', d.datePeriodFrom]);
        }
        if (d.datePeriodTo) {
            domain.push(['slip_id.date_to', '<=', d.datePeriodTo]);
        }
        if (d.slipId) {
            domain.push(['slip_id', '!=', d.slipId]);
        }

        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: `Provisiones Acumuladas - ${d.tipoProvision || d.tipoPrestacion}`,
            res_model: 'hr.payslip.line',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'new',
        });
    }

    _openAccountingEntries(d) {
        if (!d.cuentaBalanceId) return;

        const domain = [
            ['account_id', '=', d.cuentaBalanceId],
        ];
        if (d.partnerId) {
            domain.push(['partner_id', '=', d.partnerId]);
        }

        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: `Apuntes Contables - ${d.tipoProvision || 'Provisión'} (${d.cuentaBalanceCode || ''})`,
            res_model: 'account.move.line',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'new',
        });
    }
}
