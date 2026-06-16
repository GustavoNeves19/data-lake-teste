"""
Dicionários de correção de encoding para termos de domínio.
Cidades NÃO ficam aqui — são resolvidas via IBGE (reference_data/).
"""

from transform.mappings.products import PRODUCT_FIXES
from transform.mappings.companies import COMPANY_FIXES
from transform.mappings.common import COMMON_FIXES

DOMAIN_ENCODING_PATTERNS = {
    **COMMON_FIXES,
    **PRODUCT_FIXES,
    **COMPANY_FIXES,
}

# DOMAIN_ENCODING_PRODUCTS = {
    
# }