"""
Configuração central do pipeline ETL.
Domínios, entidades, ordem de carga e schemas BigQuery.
Schema v5.0 — 8 Domínios | 36 Entidades
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
QUERIES_DIR = BASE_DIR / "extract" / "queries"

# ── SQL Server (ERP) ────────────────────────────────────
SQL_SERVER_CONFIG = {
    "driver": os.getenv("SQL_SERVER_DRIVER"),
    "server": os.getenv("SQL_SERVER_HOST"),
    "port": os.getenv("SQL_SERVER_PORT"),
    "database": os.getenv("SQL_SERVER_DATABASE"),
    "uid": os.getenv("SQL_SERVER_USER"),
    "pwd": os.getenv("SQL_SERVER_PASSWORD"),
}

# ── BigQuery (DW) ────────────────────────────────────────
BQ_PROJECT = os.getenv("BQ_PROJECT_ID")
BQ_DATASET = os.getenv("BQ_DATASET")
BQ_LOCATION = os.getenv("BQ_LOCATION", "us-east1")

# ── Pipeline ─────────────────────────────────────────────
# defaults explícitos: variável opcional faltando NÃO derruba o import (era um
# foot-gun — int(os.getenv(...)) com env vazia estourava TypeError).
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY_SECONDS", "5"))
QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", "300"))   # 5 min
LOCK_TIMEOUT_MS = int(os.getenv("LOCK_TIMEOUT_MS", "5000"))              # 5 seg


# ══════════════════════════════════════════════════════════
# ORDEM DE CARGA — respeita dependências entre domínios
# ══════════════════════════════════════════════════════════
DOMAIN_LOAD_ORDER = [
    "PARTNERS",       # zero dependências — carrega primeiro
    "PRODUCTS",       # auto-contido
    "QUOTES",         # depende de PARTNERS, PRODUCTS
    "ORDERS",         # depende de QUOTES, PARTNERS, PRODUCTS
    "INVENTORY",      # depende de PRODUCTS, ORDERS
    "PAYMENTS",       # depende de PARTNERS
    "IMPORTS",        # depende de PRODUCTS, ORDERS
    "PRODUCTION",     # depende de PRODUCTS (baixa prioridade)
]


# ══════════════════════════════════════════════════════════
# REGISTRO DE ENTIDADES — 36 entidades, 8 domínios
# ══════════════════════════════════════════════════════════
#
# Cada entrada define:
#   domain       → domínio de negócio
#   entity_type  → DIM | FACT | BRIDGE | SNAPSHOT
#   query_file   → arquivo .sql em extract/queries/
#   bq_table     → nome da tabela destino no BigQuery
#   sk_column    → nome da surrogate key (gerada no pipeline)
#   load_order   → sequência dentro do domínio
#   bq_schema    → lista de (coluna, tipo_bigquery)


# ══════════════════════════════════════════════════════════
# MAPA DOMÍNIO → DATASET BigQuery
# Os 8 datasets já foram criados manualmente no BQ
# ══════════════════════════════════════════════════════════
DOMAIN_DATASET_MAP = {
        "PARTNERS":   "dm_partners",
        "PRODUCTS":   "dm_products",
        "QUOTES":     "dm_quotes",
        "ORDERS":     "dm_orders",
        "PRODUCTION": "dm_production",
        "INVENTORY":  "dm_inventory",
        "IMPORTS":    "dm_imports",
        "PAYMENTS":   "dm_payments",
    }

ENTITIES = {

    # ══════════════════════════════════════════════════════
    # 1. PARTNERS — Parceiros de Negócio e Empresa
    # ══════════════════════════════════════════════════════

    "dim_company": {
        "domain": "PARTNERS",
        "entity_type": "DIM",
        "query_file": "dim_company.sql",
        "bq_table": "dim_company",
        "sk_column": "sk_company",
        "load_order": 1,
        "bq_schema": [
            ("sk_company",          "INT64"),
            ("company_code",        "INT64"),
            ("company_name",        "STRING"),
            ("tax_id",              "STRING"),
            ("state_registration",  "STRING"),
            ("city",                "STRING"),
            ("state",               "STRING"),
            ("is_active",           "BOOL"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
            ("updated_at",          "TIMESTAMP"),
        ],
    },

    "dim_partner": {
        "domain": "PARTNERS",
        "entity_type": "DIM",
        "query_file": "dim_partner.sql",
        "bq_table": "dim_partner",
        "sk_column": "sk_partner",
        "load_order": 2,
        "bq_schema": [
            ("sk_partner",      "INT64"),
            ("partner_code",    "INT64"),
            ("partner_type",    "STRING"),
            ("partner_name",    "STRING"),
            ("legal_name",      "STRING"),
            ("tax_id",          "STRING"),
            ("activity_type",   "STRING"),
            ("status",          "STRING"),
            ("city",            "STRING"),
            ("state",           "STRING"),
            ("country",         "STRING"),
            ("email",           "STRING"),
            ("phone",           "STRING"),
            ("is_active",       "BOOL"),
            ("excluded_at",     "TIMESTAMP"),
            ("loaded_at",       "TIMESTAMP"),
            ("updated_at",      "TIMESTAMP"),
        ],
    },

    "dim_carrier": {
        "domain": "PARTNERS",
        "entity_type": "DIM",
        "query_file": "dim_carrier.sql",
        "bq_table": "dim_carrier",
        "sk_column": "sk_carrier",
        "load_order": 3,
        "bq_schema": [
            ("sk_carrier",      "INT64"),
            ("carrier_code",    "INT64"),
            ("carrier_name",    "STRING"),
            ("tax_id",          "STRING"),
            ("city",            "STRING"),
            ("state",           "STRING"),
            ("is_active",       "BOOL"),
            ("excluded_at",     "TIMESTAMP"),
            ("loaded_at",       "TIMESTAMP"),
        ],
    },

    # ══════════════════════════════════════════════════════
    # 2. PRODUCTS — Catálogo de Itens e BOM
    # ══════════════════════════════════════════════════════

    "dim_family": {
        "domain": "PRODUCTS",
        "entity_type": "DIM",
        "query_file": "dim_family.sql",
        "bq_table": "dim_family",
        "sk_column": "sk_family",
        "load_order": 1,
        "bq_schema": [
            ("sk_family",       "INT64"),
            ("family_code",     "INT64"),
            ("family_name",     "STRING"),
            ("is_active",       "BOOL"),
            ("excluded_at",     "TIMESTAMP"),
            ("loaded_at",       "TIMESTAMP"),
        ],
    },

    "dim_group": {
        "domain": "PRODUCTS",
        "entity_type": "DIM",
        "query_file": "dim_group.sql",
        "bq_table": "dim_group",
        "sk_column": "sk_group",
        "load_order": 2,
        "bq_schema": [
            ("sk_group",        "INT64"),
            ("group_code",      "INT64"),
            ("group_name",      "STRING"),
            ("is_active",       "BOOL"),
            ("excluded_at",     "TIMESTAMP"),
            ("loaded_at",       "TIMESTAMP"),
        ],
    },

    "dim_tax_classification": {
        "domain": "PRODUCTS",
        "entity_type": "DIM",
        "enabled": False,
        "query_file": "dim_tax_classification.sql",
        "bq_table": "dim_tax_classification",
        "sk_column": "sk_tax_class",
        "load_order": 3,
        "bq_schema": [
            ("sk_tax_class",        "INT64"),
            ("tax_class_code",      "STRING"),
            ("tax_class_name",      "STRING"),
            ("ncm_code",            "STRING"),
            ("is_active",           "BOOL"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "dim_item": {
        "domain": "PRODUCTS",
        "entity_type": "DIM",
        "query_file": "dim_item.sql",
        "bq_table": "dim_item",
        "sk_column": "sk_item",
        "load_order": 4,
        "bq_schema": [
            ("sk_item",             "INT64"),
            ("item_code",           "STRING"),
            ("item_name",           "STRING"),
            ("item_description",    "STRING"),
            ("unit_code",           "INT64"),
            ("family_code",         "INT64"),
            ("group_code",          "INT64"),
            ("tax_class_code",      "STRING"),
            ("net_weight",          "NUMERIC"),
            ("gross_weight",        "NUMERIC"),
            ("is_active",           "BOOL"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "bridge_item_bom": {
        "domain": "PRODUCTS",
        "entity_type": "BRIDGE",
        "query_file": "bridge_item_bom.sql",
        "bq_table": "bridge_item_bom",
        "sk_column": "sk_bom_link",
        "load_order": 5,
        "bq_schema": [
            ("sk_bom_link",         "INT64"),
            ("parent_item_code",    "STRING"),
            ("child_item_code",     "STRING"),
            ("quantity",            "NUMERIC"),
            ("link_type",           "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_serial_number": {
        "domain": "PRODUCTS",
        "entity_type": "FACT",
        "query_file": "fact_serial_number.sql",
        "bq_table": "fact_serial_number",
        "sk_column": "sk_serial",
        "load_order": 6,
        "bq_schema": [
            ("sk_serial",           "INT64"),
            ("item_code",           "STRING"),
            ("serial_number",       "STRING"),
            ("batch_number",        "INT64"),
            ("is_in_use",           "STRING"),
            ("inspection_batch",    "STRING"),
            ("inspection_status",   "INT64"),
            ("inspection_weight",   "NUMERIC"),
            ("inspection_result",   "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_serial_history": {
        "domain": "PRODUCTS",
        "entity_type": "FACT",
        "query_file": "fact_serial_history.sql",
        "bq_table": "fact_serial_history",
        "sk_column": "sk_serial_hist",
        "load_order": 7,
        "bq_schema": [
            ("sk_serial_hist",      "INT64"),
            ("item_code",           "STRING"),
            ("serial_number",       "STRING"),
            ("document_number",     "STRING"),
            ("serial_status",       "STRING"),
            ("quantity",            "INT64"),
            ("notes",               "STRING"),
            ("created_at_erp",      "TIMESTAMP"),
            ("created_by_erp",      "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    # ══════════════════════════════════════════════════════
    # 3. QUOTES — Orçamentos / Cotações
    # ══════════════════════════════════════════════════════

    "fact_quote": {
        "domain": "QUOTES",
        "entity_type": "FACT",
        "query_file": "fact_quote.sql",
        "bq_table": "fact_quote",
        "sk_column": "sk_quote",
        "load_order": 1,
        "bq_schema": [
            ("sk_quote",            "INT64"),
            ("quote_number",        "NUMERIC"),
            ("quote_type",          "STRING"),
            ("quote_status",        "STRING"),
            ("detailed_status",     "INT64"),
            ("partner_code",        "INT64"),
            ("company_code",        "INT64"),
            ("carrier_code",        "INT64"),
            ("quote_date",          "DATE"),
            ("delivery_date",       "DATE"),
            ("nature_code",         "STRING"),
            ("payment_cond_code",   "INT64"),
            ("requester",           "STRING"),
            ("product_amount",      "NUMERIC"),
            ("freight_amount",      "NUMERIC"),
            ("total_amount",        "NUMERIC"),
            ("sent_date_1",         "DATE"),
            ("sent_date_2",         "DATE"),
            ("incoterm",            "STRING"),
            ("payment_method",      "STRING"),
            ("created_at_erp",      "TIMESTAMP"),
            ("created_by_erp",      "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_quote_item": {
        "domain": "QUOTES",
        "entity_type": "FACT",
        "query_file": "fact_quote_item.sql",
        "bq_table": "fact_quote_item",
        "sk_column": "sk_quote_item",
        "load_order": 2,
        "bq_schema": [
            ("sk_quote_item",       "INT64"),
            ("quote_number",        "NUMERIC"),
            ("item_code",           "STRING"),
            ("quantity",            "NUMERIC"),
            ("unit_price",          "NUMERIC"),
            ("ipi_rate",            "NUMERIC"),
            ("item_delivery_date",  "DATE"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    # ══════════════════════════════════════════════════════
    # 4. ORDERS — Pedidos de Compra e Venda
    # ══════════════════════════════════════════════════════

    "dim_operation_nature": {
        "domain": "ORDERS",
        "entity_type": "DIM",
        "query_file": "dim_operation_nature.sql",
        "bq_table": "dim_operation_nature",
        "sk_column": "sk_nature",
        "load_order": 1,
        "bq_schema": [
            ("sk_nature",               "INT64"),
            ("nature_code",             "STRING"),
            ("nature_name",             "STRING"),
            ("direction",               "STRING"),
            ("sale_or_service",         "STRING"),
            ("financial_flag",          "STRING"),
            ("is_return",               "STRING"),
            ("stock_movement_type",     "STRING"),
            ("is_active",               "BOOL"),
            ("excluded_at",             "TIMESTAMP"),
            ("loaded_at",               "TIMESTAMP"),
        ],
    },

    "dim_payment_condition": {
        "domain": "ORDERS",
        "entity_type": "DIM",
        "query_file": "dim_payment_condition.sql",
        "bq_table": "dim_payment_condition",
        "sk_column": "sk_payment_cond",
        "load_order": 2,
        "bq_schema": [
            ("sk_payment_cond",     "INT64"),
            ("payment_cond_code",   "INT64"),
            ("payment_cond_name",   "STRING"),
            ("is_active",           "BOOL"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_purchase_order": {
        "domain": "ORDERS",
        "entity_type": "FACT",
        "query_file": "fact_purchase_order.sql",
        "bq_table": "fact_purchase_order",
        "sk_column": "sk_purchase_order",
        # Incremental ADIADO: a chave composta order_number+invoice_number fica instável
        # (invoice_number vai de NULL->valor quando a nota chega, mudando o sk e duplicando
        # no MERGE). Religar quando houver chave estável. Full por ora.
        "load_order": 3,
        "bq_schema": [
            ("sk_purchase_order",   "INT64"),
            ("order_number",        "STRING"),
            ("quote_number",        "NUMERIC"),
            ("partner_code",        "INT64"),
            ("company_code",        "INT64"),
            ("nature_code",         "STRING"),
            ("payment_cond_code",   "INT64"),
            ("carrier_code",        "INT64"),
            ("order_date",          "DATE"),
            ("delivery_date",       "DATE"),
            ("invoice_date",        "DATE"),
            ("order_status",        "INT64"),
            ("reconciliation_flag", "INT64"),
            ("invoice_number",      "NUMERIC"),
            ("invoice_series",      "STRING"),
            ("nfe_key",             "STRING"),
            ("supplier_order_ref",  "STRING"),
            ("product_amount",      "NUMERIC"),
            ("icms_amount",         "NUMERIC"),
            ("ipi_amount",          "NUMERIC"),
            ("freight_amount",      "NUMERIC"),
            ("total_amount",        "NUMERIC"),
            ("created_at_erp",      "TIMESTAMP"),
            ("created_by_erp",      "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_sales_order": {
        "domain": "ORDERS",
        "entity_type": "FACT",
        "query_file": "fact_sales_order.sql",
        "bq_table": "fact_sales_order",
        "sk_column": "sk_sales_order",
        # Carga incremental (25/06): chave natural order_number -> sk vira hash estável;
        # watermark = invoice_date (YDATEMI), que é o gatilho do faturamento e pega o
        # faturamento de um pedido antigo (order_date ficaria velho e escaparia); o
        # cancelamento entra por excluded_at; o full noturno reconcilia o resto.
        "load_mode": "incremental",
        "natural_key": ["order_number"],
        "watermark_column": "invoice_date",
        "exclusion_column": "excluded_at",
        "overlap_days": 7,
        "load_order": 4,
        "bq_schema": [
            ("sk_sales_order",      "INT64"),
            ("order_number",        "STRING"),
            ("quote_number",        "NUMERIC"),
            ("partner_code",        "INT64"),
            ("company_code",        "INT64"),
            ("nature_code",         "STRING"),
            ("payment_cond_code",   "INT64"),
            ("channel_code",        "STRING"),
            ("channel_name",        "STRING"),
            ("salesperson_code",    "STRING"),
            ("salesperson_name",    "STRING"),
            ("salesperson_group_code", "STRING"),
            ("order_date",          "DATE"),
            ("invoice_date",        "DATE"),
            ("order_status",        "INT64"),
            ("product_amount",      "NUMERIC"),
            ("icms_amount",         "NUMERIC"),
            ("ipi_amount",          "NUMERIC"),
            ("freight_amount",      "NUMERIC"),
            ("total_amount",        "NUMERIC"),
            ("invoice_number",      "NUMERIC"),
            ("nfe_key",             "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_order_item": {
        "domain": "ORDERS",
        "entity_type": "FACT",
        "query_file": "fact_order_item.sql",
        "bq_table": "fact_order_item",
        "sk_column": "sk_order_item",
        "load_order": 5,
        "bq_schema": [
            ("sk_order_item",       "INT64"),
            ("order_number",        "STRING"),
            ("operation_type",      "STRING"),
            ("item_code",           "STRING"),
            ("quantity",            "NUMERIC"),
            ("unit_price",          "NUMERIC"),
            ("ipi_amount",          "NUMERIC"),
            ("icms_amount",         "NUMERIC"),
            ("inspection_flag",     "STRING"),
            ("inspected_qty",       "NUMERIC"),
            ("approved_qty",        "NUMERIC"),
            ("rejected_qty",        "NUMERIC"),
            ("is_approved",         "STRING"),
            ("is_deviation",        "STRING"),
            ("is_rejected",         "STRING"),
            ("is_canceled",         "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "dim_salesperson_group": {
        "domain": "ORDERS",
        "entity_type": "DIM",
        "query_file": "dim_salesperson_group.sql",
        "bq_table": "dim_salesperson_group",
        "sk_column": "sk_salesperson_group",
        "load_order": 7,
        "bq_schema": [
            ("sk_salesperson_group",    "INT64"),
            ("salesperson_group_code",  "STRING"),
            ("group_name",              "STRING"),
            ("updated_at_erp",          "TIMESTAMP"),
            ("is_active",               "BOOL"),
            ("excluded_at",             "TIMESTAMP"),
            ("loaded_at",               "TIMESTAMP"),
        ],
    },

    "dim_salesperson": {
        "domain": "ORDERS",
        "entity_type": "DIM",
        "query_file": "dim_salesperson.sql",
        "bq_table": "dim_salesperson",
        "sk_column": "sk_salesperson",
        "load_order": 8,
        "bq_schema": [
            ("sk_salesperson",          "INT64"),
            ("salesperson_code",        "STRING"),
            ("salesperson_name",        "STRING"),
            ("salesperson_group_code",  "STRING"),
            ("is_active",               "BOOL"),
            ("updated_at_erp",          "TIMESTAMP"),
            ("excluded_at",             "TIMESTAMP"),
            ("loaded_at",               "TIMESTAMP"),
        ],
    },

    "fact_tax_ledger": {
        "domain": "ORDERS",
        "entity_type": "FACT",
        "query_file": "fact_tax_ledger.sql",
        "bq_table": "fact_tax_ledger",
        "sk_column": "sk_tax_ledger",
        "load_order": 6,
        "bq_schema": [
            ("sk_tax_ledger",       "INT64"),
            ("ledger_number",       "NUMERIC"),
            ("order_number",        "STRING"),
            ("invoice_number",      "NUMERIC"),
            ("operation_type",      "STRING"),
            ("nature_code",         "STRING"),
            ("product_amount",      "NUMERIC"),
            ("icms_amount",         "NUMERIC"),
            ("ipi_amount",          "NUMERIC"),
            ("total_amount",        "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    # ══════════════════════════════════════════════════════
    # 5. PRODUCTION — Ordens de Produção
    # ══════════════════════════════════════════════════════

    "fact_production_order": {
        "domain": "PRODUCTION",
        "entity_type": "FACT",
        "query_file": "fact_production_order.sql",
        "bq_table": "fact_production_order",
        "sk_column": "sk_prod_order",
        "load_order": 1,
        "bq_schema": [
            ("sk_prod_order",       "INT64"),
            ("prod_order_number",   "STRING"),
            ("order_number",        "STRING"),
            ("company_code",        "INT64"),
            ("order_date",          "DATE"),
            ("forecast_date",       "DATE"),
            ("prod_status",         "INT64"),
            ("is_urgent",           "INT64"),
            ("completed_at",        "DATE"),
            ("requested_by",        "STRING"),
            ("notes",               "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_production_item": {
        "domain": "PRODUCTION",
        "entity_type": "FACT",
        "query_file": "fact_production_item.sql",
        "bq_table": "fact_production_item",
        "sk_column": "sk_prod_item",
        "load_order": 2,
        "bq_schema": [
            ("sk_prod_item",        "INT64"),
            ("prod_order_number",   "STRING"),
            ("item_code",           "STRING"),
            ("planned_qty",         "NUMERIC"),
            ("actual_qty",          "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_production_comp_item": {
        "domain": "PRODUCTION",
        "entity_type": "FACT",
        "query_file": "fact_production_comp_item.sql",
        "bq_table": "fact_production_comp_item",
        "sk_column": "sk_prod_comp",
        "load_order": 3,
        "bq_schema": [
            ("sk_prod_comp",        "INT64"),
            ("prod_order_number",   "STRING"),
            ("item_code",           "STRING"),
            ("planned_qty",         "NUMERIC"),
            ("actual_qty",          "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    # ══════════════════════════════════════════════════════
    # 6. INVENTORY — Gestão de Estoque
    # ══════════════════════════════════════════════════════

    "fact_inventory_movement": {
        "domain": "INVENTORY",
        "entity_type": "FACT",
        "query_file": "fact_inventory_movement.sql",
        "bq_table": "fact_inventory_movement",
        "sk_column": "sk_movement",
        "load_order": 1,
        "bq_schema": [
            ("sk_movement",         "INT64"),
            ("movement_number",     "NUMERIC"),
            ("order_number",        "STRING"),
            ("operation_type",      "STRING"),
            ("nature_code",         "STRING"),
            ("item_code",           "STRING"),
            ("company_code",        "INT64"),
            ("movement_date",       "DATE"),
            ("quantity",            "NUMERIC"),
            ("unit_price",          "NUMERIC"),
            ("batch_number",        "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "snapshot_inventory_balance": {
        "domain": "INVENTORY",
        "entity_type": "SNAPSHOT",
        "query_file": "snapshot_inventory_balance.sql",
        "bq_table": "snapshot_inventory_balance",
        "sk_column": "sk_balance",
        "load_order": 2,
        "bq_schema": [
            ("sk_balance",          "INT64"),
            ("company_code",        "INT64"),
            ("item_code",           "STRING"),
            ("snapshot_date",       "DATE"),
            ("general_balance",     "NUMERIC"),
            ("purchase_balance",    "NUMERIC"),
            ("sales_balance",       "NUMERIC"),
            ("available_balance",   "NUMERIC"),
            ("in_transit_balance",  "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "dim_batch": {
        "domain": "INVENTORY",
        "entity_type": "DIM",
        "query_file": "dim_batch.sql",
        "bq_table": "dim_batch",
        "sk_column": "sk_batch",
        "load_order": 3,
        "bq_schema": [
            ("sk_batch",            "INT64"),
            ("company_code",        "INT64"),
            ("item_code",           "STRING"),
            ("batch_number",        "STRING"),
            ("batch_date",          "DATE"),
            ("expiration_date",     "DATE"),
            ("batch_balance",       "NUMERIC"),
            ("is_active",           "BOOL"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "bridge_order_batch": {
        "domain": "INVENTORY",
        "entity_type": "BRIDGE",
        "query_file": "bridge_order_batch.sql",
        "bq_table": "bridge_order_batch",
        "sk_column": "sk_order_batch",
        "load_order": 4,
        "bq_schema": [
            ("sk_order_batch",      "INT64"),
            ("order_number",        "STRING"),
            ("item_code",           "STRING"),
            ("batch_number",        "STRING"),
            ("quantity",            "NUMERIC"),
            ("batch_date",          "DATE"),
            ("expiration_date",     "DATE"),
            ("created_at_erp",      "TIMESTAMP"),
            ("created_by_erp",      "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    # ══════════════════════════════════════════════════════
    # 7. IMPORTS — Processos de Importação
    # ══════════════════════════════════════════════════════

    "fact_import_process": {
        "domain": "IMPORTS",
        "entity_type": "FACT",
        "query_file": "fact_import_process.sql",
        "bq_table": "fact_import_process",
        "sk_column": "sk_import",
        "load_order": 1,
        "bq_schema": [
            ("sk_import",           "INT64"),
            ("import_number",       "NUMERIC"),
            ("di_number",           "STRING"),
            ("di_date",             "DATE"),
            ("di_exchange_rate",    "NUMERIC"),
            ("storage_cost",        "NUMERIC"),
            ("afrmm_cost",          "NUMERIC"),
            ("anvisa_cost",         "NUMERIC"),
            ("siscomex_cost",       "NUMERIC"),
            ("intl_freight",        "NUMERIC"),
            ("domestic_freight",    "NUMERIC"),
            ("total_freight",       "NUMERIC"),
            ("total_usd",           "NUMERIC"),
            ("total_brl",           "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_import_order": {
        "domain": "IMPORTS",
        "entity_type": "FACT",
        "query_file": "fact_import_order.sql",
        "bq_table": "fact_import_order",
        "sk_column": "sk_import_order",
        "load_order": 2,
        "bq_schema": [
            ("sk_import_order",     "INT64"),
            ("import_number",       "NUMERIC"),
            ("order_number",        "STRING"),
            ("supplier_name",       "STRING"),
            ("total_usd",           "NUMERIC"),
            ("total_brl",           "NUMERIC"),
            ("ii_amount",           "NUMERIC"),
            ("pis_amount",          "NUMERIC"),
            ("cofins_amount",       "NUMERIC"),
            ("icms_amount",         "NUMERIC"),
            ("ipi_amount",          "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_import_item": {
        "domain": "IMPORTS",
        "entity_type": "FACT",
        "query_file": "fact_import_item.sql",
        "bq_table": "fact_import_item",
        "sk_column": "sk_import_item",
        "load_order": 3,
        "bq_schema": [
            ("sk_import_item",      "INT64"),
            ("import_number",       "NUMERIC"),
            ("order_number",        "STRING"),
            ("item_code",           "STRING"),
            ("quantity",            "NUMERIC"),
            ("unit_price",          "NUMERIC"),
            ("total_usd",           "NUMERIC"),
            ("total_brl",           "NUMERIC"),
            ("ii_amount",           "NUMERIC"),
            ("pis_amount",          "NUMERIC"),
            ("cofins_amount",       "NUMERIC"),
            ("icms_amount",         "NUMERIC"),
            ("ipi_amount",          "NUMERIC"),
            ("landed_cost_brl",     "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_import_installment": {
        "domain": "IMPORTS",
        "entity_type": "FACT",
        "query_file": "fact_import_installment.sql",
        "bq_table": "fact_import_installment",
        "sk_column": "sk_installment",
        "load_order": 4,
        "bq_schema": [
            ("sk_installment",      "INT64"),
            ("import_number",       "NUMERIC"),
            ("order_number",        "STRING"),
            ("installment_name",    "STRING"),
            ("installment_pct",     "NUMERIC"),
            ("installment_date",    "DATE"),
            ("installment_amount",  "NUMERIC"),
            ("total_usd",           "NUMERIC"),
            ("total_brl",           "NUMERIC"),
            ("spread",              "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    # ══════════════════════════════════════════════════════
    # 8. PAYMENTS — Contas a Pagar e Receber
    # ══════════════════════════════════════════════════════

    "dim_bank": {
        "domain": "PAYMENTS",
        "entity_type": "DIM",
        "query_file": "dim_bank.sql",
        "bq_table": "dim_bank",
        "sk_column": "sk_bank",
        "load_order": 1,
        "bq_schema": [
            ("sk_bank",             "INT64"),
            ("bank_code",           "INT64"),
            ("bank_name",           "STRING"),
            ("febraban_code",       "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "dim_department": {
        "domain": "PAYMENTS",
        "entity_type": "DIM",
        "query_file": "dim_department.sql",
        "bq_table": "dim_department",
        "sk_column": "sk_department",
        "load_order": 2,
        "bq_schema": [
            ("sk_department",       "INT64"),
            ("department_code",     "INT64"),
            ("department_name",     "STRING"),
            ("is_active",           "BOOL"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "dim_financial_item": {
        "domain": "PAYMENTS",
        "entity_type": "DIM",
        "query_file": "dim_financial_item.sql",
        "bq_table": "dim_financial_item",
        "sk_column": "sk_financial_item",
        "load_order": 3,
        "bq_schema": [
            ("sk_financial_item",       "INT64"),
            ("financial_item_code",     "STRING"),
            ("financial_item_name",     "STRING"),
            ("is_active",               "BOOL"),
            ("excluded_at",             "TIMESTAMP"),
            ("loaded_at",               "TIMESTAMP"),
        ],
    },

    "dim_surcharge_type": {
        "domain": "PAYMENTS",
        "entity_type": "DIM",
        "query_file": "dim_surcharge_type.sql",
        "bq_table": "dim_surcharge_type",
        "sk_column": "sk_surcharge",
        "load_order": 4,
        "bq_schema": [
            ("sk_surcharge",        "INT64"),
            ("surcharge_code",      "STRING"),
            ("surcharge_name",      "STRING"),
            ("sign",                "STRING"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_payable": {
        "domain": "PAYMENTS",
        "entity_type": "FACT",
        "query_file": "fact_payable.sql",
        "bq_table": "fact_payable",
        "sk_column": "sk_payable",
        # Incremental ADIADO: confirmar se title_number é único GLOBAL (PAGAR E RECEBER é
        # multi-empresa; YNUMERO costuma ser único por empresa). Full por ora.
        "load_order": 5,
        "bq_schema": [
            ("sk_payable",          "INT64"),
            ("title_number",        "NUMERIC"),
            ("order_number",        "STRING"),
            ("partner_code",        "INT64"),
            ("company_code",        "INT64"),
            ("bank_code",           "INT64"),
            ("department_code",     "INT64"),
            ("issue_date",          "DATE"),
            ("due_date",            "DATE"),
            ("document_amount",     "NUMERIC"),
            ("net_amount",          "NUMERIC"),
            ("surcharge_code_1",    "STRING"),
            ("surcharge_amount_1",  "NUMERIC"),
            ("surcharge_code_2",    "STRING"),
            ("surcharge_amount_2",  "NUMERIC"),
            ("surcharge_code_3",    "STRING"),
            ("surcharge_amount_3",  "NUMERIC"),
            ("created_at_erp",      "TIMESTAMP"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_receivable": {
        "domain": "PAYMENTS",
        "entity_type": "FACT",
        "query_file": "fact_receivable.sql",
        "bq_table": "fact_receivable",
        "sk_column": "sk_receivable",
        # Incremental ADIADO: issue_date tem datas FUTURAS (até 2029) que travariam o
        # watermark, e title_number é multi-empresa. Volume baixo (1.609), ganho irrelevante.
        # Full por ora.
        "load_order": 6,
        "bq_schema": [
            ("sk_receivable",       "INT64"),
            ("title_number",        "NUMERIC"),
            ("order_number",        "STRING"),
            ("partner_code",        "INT64"),
            ("company_code",        "INT64"),
            ("bank_code",           "INT64"),
            ("issue_date",          "DATE"),
            ("due_date",            "DATE"),
            ("document_amount",     "NUMERIC"),
            ("net_amount",          "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },

    "fact_settled_title": {
        "domain": "PAYMENTS",
        "entity_type": "FACT",
        "query_file": "fact_settled_title.sql",
        "bq_table": "fact_settled_title",
        "sk_column": "sk_settled",
        "load_order": 7,
        "bq_schema": [
            ("sk_settled",          "INT64"),
            ("title_number",        "NUMERIC"),
            ("order_number",        "STRING"),
            ("settlement_type",     "STRING"),
            ("partner_code",        "INT64"),
            ("company_code",        "INT64"),
            ("bank_code",           "INT64"),
            ("issue_date",          "DATE"),
            ("due_date",            "DATE"),
            ("payment_date",        "DATE"),
            ("document_amount",     "NUMERIC"),
            ("paid_amount",         "NUMERIC"),
            ("excluded_at",         "TIMESTAMP"),
            ("loaded_at",           "TIMESTAMP"),
        ],
    },
}



# HELPERS


def get_entities_by_domain(domain: str) -> list[dict]:
    """Retorna entidades de um domínio, ordenadas por load_order."""
    entities = [
        {"name": name, **cfg}
        for name, cfg in ENTITIES.items()
        if cfg["domain"] == domain
    ]
    return sorted(entities, key=lambda e: e["load_order"])


def get_all_entities_ordered() -> list[dict]:
    """Retorna TODAS as entidades na ordem correta de carga."""
    result = []
    for domain in DOMAIN_LOAD_ORDER:
        result.extend(get_entities_by_domain(domain))
    return result

def get_full_table_id(entity_name: str) -> str:
    """Retorna o table_id completo: projeto.dataset.tabela"""
    cfg = ENTITIES[entity_name]
    dataset = DOMAIN_DATASET_MAP[cfg["domain"]]
    return f"{BQ_PROJECT}.{dataset}.{cfg['bq_table']}"