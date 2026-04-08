# -*- coding: utf-8 -*-
# =============================================================================
# MODELOS ORGANIZADOS POR TIPO
# =============================================================================

# Reglas de cálculo de nómina
from . import reglas

# Modelos por categoría
from . import (
    employee,      # Empleados, skills, usuarios
    payroll,       # Parámetros, constantes, retenciones, reglas
    contract,      # Contratos, modificaciones, historial
    certificates,  # Certificados laborales y de ingresos
    config,        # Configuración contable y settings
    epp_dotacion,  # Equipos de protección personal
    medical,       # Exámenes médicos
    services,      # Servicios de consultas consolidadas
)
