"""
Configuração de encoding por entidade.
Define qual coluna é cidade, qual é estado, e quais devem ser puladas.

Usado pelo encoding_fix.py pra saber como tratar cada entidade.
"""

# Mapeamento: entity_name → configuração de encoding
ENTITY_ENCODING_CONFIG = {

    # ── PARTNERS ──────────────────────────────────────
    "dim_company": {
        "city_column": "city",
        "state_column": "state",
        "skip_columns": ["company_code", "tax_id", "state_registration"],
    },
    "dim_partner": {
        "city_column": "city",
        "state_column": "state",
        "skip_columns": ["partner_code", "tax_id", "email", "phone"],
    },
    "dim_carrier": {
        "city_column": "city",
        "state_column": "state",
        "skip_columns": ["carrier_code", "tax_id"],
    },

    # ── PRODUCTS ──────────────────────────────────────
    "dim_item": {
        "city_column": None,  # sem cidade
        "state_column": None,
        "skip_columns": ["item_code", "family_code", "group_code", "tax_class_code", "unit_code"],
    },
    "dim_family": {
        "city_column": None,
        "state_column": None,
        "skip_columns": ["family_code"],
    },
    "dim_group": {
        "city_column": None,
        "state_column": None,
        "skip_columns": ["group_code"],
    },

    # ── ORDERS ────────────────────────────────────────
    "fact_purchase_order": {
        "city_column": None,
        "state_column": None,
        "skip_columns": ["order_number", "partner_code", "company_code", "nature_code",
                         "nfe_key", "invoice_series", "supplier_order_ref"],
    },
    "fact_sales_order": {
        "city_column": None,
        "state_column": None,
        "skip_columns": ["order_number", "partner_code", "company_code", "nature_code", "nfe_key",
                         "channel_code", "salesperson_code"],
    },

    # ── IMPORTS ───────────────────────────────────────
    "fact_import_order": {
        "city_column": None,
        "state_column": None,
        "skip_columns": ["import_number", "order_number"],
        # supplier_name pode ter encoding issues
    },
}


def get_encoding_config(entity_name: str) -> dict:
    """
    Retorna config de encoding pra uma entidade.
    Se não tiver config específica, retorna defaults seguros.
    """
    return ENTITY_ENCODING_CONFIG.get(entity_name, {
        "city_column": None,
        "state_column": None,
        "skip_columns": [],
    })
