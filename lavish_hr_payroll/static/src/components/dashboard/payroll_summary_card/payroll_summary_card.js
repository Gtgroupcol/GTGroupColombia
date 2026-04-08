/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PayrollSummaryCard extends Component {
    static template = "lavish_hr_payroll.PayrollSummaryCard";

    setup() {
        this.action = useService("action");
        this.state = useState({
            isFullscreen: false,
            activeTab: 'devengos',
        });
    }

    get hasData() {
        return this.props.summaryData && (
               (this.props.summaryData.items && this.props.summaryData.items.length > 0) ||
               (this.props.summaryData.payslips_count && this.props.summaryData.payslips_count > 0)
        );
    }

    get totalDevengos() {
        return this.props.summaryData?.formatted_devengos || '$0';
    }

    get totalDeducciones() {
        return this.props.summaryData?.formatted_deducciones || '$0';
    }

    get totalNeto() {
        return this.props.summaryData?.formatted_neto || '$0';
    }

    get payslipsCount() {
        return this.props.summaryData?.payslips_count || 0;
    }

    get employeesCount() {
        return this.props.summaryData?.employees_count || 0;
    }

    get devengosItems() {
        if (!this.props.summaryData?.items) return [];
        return this.props.summaryData.items.filter(item => item.type === 'earning');
    }

    get deduccionesItems() {
        if (!this.props.summaryData?.items) return [];
        return this.props.summaryData.items.filter(item => item.type === 'deduction');
    }

    get allItems() {
        return this.props.summaryData?.items || [];
    }

    getColorClass(color) {
        const colors = {
            'danger': 'text-danger',
            'success': 'text-success',
            'warning': 'text-warning',
            'info': 'text-info',
            'primary': 'text-primary',
            'secondary': 'text-secondary',
            'purple': 'text-purple',
            'pink': 'text-pink'
        };
        return colors[color] || 'text-secondary';
    }

    getBgColorClass(color) {
        const colors = {
            'danger': 'bg-danger',
            'success': 'bg-success',
            'warning': 'bg-warning',
            'info': 'bg-info',
            'primary': 'bg-primary',
            'secondary': 'bg-secondary',
            'purple': 'bg-purple',
            'pink': 'bg-pink'
        };
        return colors[color] || 'bg-secondary';
    }

    getFontAwesomeIcon(key) {
        // Iconos Font Awesome compatibles con Odoo 17
        const icons = {
            'sueldo': 'fa fa-money',
            'auxilio': 'fa fa-bus',
            'horas_extras': 'fa fa-clock-o',
            'comisiones': 'fa fa-handshake-o',
            'vacaciones': 'fa fa-sun-o',
            'incapacidades': 'fa fa-medkit',
            'licencias': 'fa fa-calendar-minus-o',
            'prestaciones': 'fa fa-gift',
            'devengos_salariales': 'fa fa-money',
            'devengos_no_salariales': 'fa fa-plus-square',
            'seguridad_social': 'fa fa-shield',
            'retencion': 'fa fa-percent',
            'deducciones': 'fa fa-minus-circle'
        };
        return icons[key] || 'fa fa-file-text-o';
    }

    toggleFullscreen() {
        this.state.isFullscreen = !this.state.isFullscreen;
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    async onViewPayslips() {
        if (this.props.onAction) {
            const params = {};
            if (this.props.period?.id) {
                params.period_id = this.props.period.id;
            }
            await this.props.onAction('view_payslips', params);
        }
    }

    async onViewDetail(key) {
        // Buscar el item por key
        const item = this.allItems.find(i => i.key === key);

        if (item && item.line_ids && item.line_ids.length > 0) {
            // Usar el servicio de acción directamente con los line_ids
            await this.action.doAction({
                type: 'ir.actions.act_window',
                name: item.name,
                res_model: 'hr.payslip.line',
                view_mode: 'tree,pivot,graph',
                target: 'new',
                domain: [['id', 'in', item.line_ids]],
                context: {
                    search_default_group_employee: 1,
                    group_by: ['employee_id', 'salary_rule_id'],
                },
            });
        } else if (this.props.onAction) {
            // Fallback al método anterior
            const params = { category_code: key };
            if (this.props.period?.id) {
                params.period_id = this.props.period.id;
            }
            await this.props.onAction('view_payslip_lines_by_category', params);
        }
    }
}
