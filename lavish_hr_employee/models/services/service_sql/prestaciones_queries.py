# -*- coding: utf-8 -*-
"""
Consultas de Prestaciones
=========================

Builder especializado para consultas de prestaciones sociales.
"""
from typing import List, Dict, Any
from .period_queries import PeriodQueryBuilder
from odoo.addons.lavish_hr_employee.models.reglas.config_reglas import get_prestacion_base_field


class PrestacionesQueryBuilder(PeriodQueryBuilder):
    """
    Builder para consultas de Prestaciones sociales.

    Filtros:
    - base_prima, base_cesantias, base_vacaciones, etc.
    - Categorias excluibles

    Uso:
        builder = PrestacionesQueryBuilder()
        query, params = (builder
            .for_contract(contract_id)
            .in_period(date_from, date_to)
            .tipo_prestacion('prima')
            .exclude_categories(['BASIC', 'DED', 'PROV'])
            .build()
        )
    """

    DEFAULT_EXCLUDED_CATEGORIES = ['BASIC', 'DED', 'PROV', 'SSOCIAL', 'PRESTACIONES_SOCIALES', 'NET']

    def __init__(self):
        super().__init__()
        self._tipo_prestacion = 'all'
        self._excluded_categories = self.DEFAULT_EXCLUDED_CATEGORIES.copy()
        self._contexto_base = 'liquidacion'

    def tipo_prestacion(self, tipo: str) -> 'PrestacionesQueryBuilder':
        """Tipo de prestacion: 'prima', 'cesantias', 'vacaciones', 'intereses_cesantias', 'all'."""
        self._tipo_prestacion = tipo
        return self

    def exclude_categories(self, categories: List[str]) -> 'PrestacionesQueryBuilder':
        """Categorias a excluir."""
        self._excluded_categories = categories
        return self

    def contexto_base(self, contexto: str) -> 'PrestacionesQueryBuilder':
        """Contexto de base: provision o liquidacion."""
        self._contexto_base = contexto if contexto in ('provision', 'liquidacion') else 'liquidacion'
        return self

    def _get_extra_select_fields(self) -> List[str]:
        contexto = self._contexto_base
        return [
            f"""CASE
                WHEN hsr.base_prima_{contexto} THEN 'base_prima_{contexto}'
                WHEN hsr.base_cesantias_{contexto} THEN 'base_cesantias_{contexto}'
                WHEN hsr.base_vacaciones_{contexto} THEN 'base_vacaciones_{contexto}'
                WHEN hsr.base_vacaciones_dinero_{contexto} THEN 'base_vacaciones_dinero_{contexto}'
                WHEN hsr.base_intereses_cesantias_{contexto} THEN 'base_intereses_cesantias_{contexto}'
                ELSE NULL
            END AS base_field""",
            """CASE
                WHEN hsrc.code = 'BASIC' THEN 'basic'
                ELSE 'variable'
            END AS data_type""",
            # Campo para identificar auxilio de transporte
            "COALESCE(hsr.es_auxilio_transporte, FALSE) AS es_auxilio_transporte",
        ]

    def _get_type_where_conditions(self) -> List[str]:
        conditions = []
        contexto = self._contexto_base

        # Filtro de base segun tipo_prestacion
        if self._tipo_prestacion == 'all':
            conditions.append(
                f"""(hsr.base_prima_{contexto} = TRUE OR hsr.base_cesantias_{contexto} = TRUE
                    OR hsr.base_vacaciones_{contexto} = TRUE OR hsr.base_vacaciones_dinero_{contexto} = TRUE
                    OR hsr.base_intereses_cesantias_{contexto} = TRUE)"""
            )
        else:
            base_field = get_prestacion_base_field(self._tipo_prestacion, contexto=contexto)
            conditions.append(f"hsr.{base_field} = TRUE")

        # Filtro de categorias excluidas
        if self._excluded_categories:
            conditions.append("hsrc.code NOT IN %(excluded_categories)s")

        return conditions

    def _get_extra_params(self) -> Dict[str, Any]:
        params = {}
        if self._excluded_categories:
            params['excluded_categories'] = tuple(self._excluded_categories)
        return params
