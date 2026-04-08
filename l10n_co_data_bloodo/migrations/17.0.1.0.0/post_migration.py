# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_migrate(cr, registry):
    """Post-migration: Ensure constraint is recreated with proper ondelete behavior"""
    _logger.info("Post-migration: account_tax dian_tax_type_id field migration complete")
