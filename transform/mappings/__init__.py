"""
Dicionários de correção de encoding para termos de domínio.
Cidades NÃO ficam aqui — são resolvidas via IBGE (reference_data/).
"""

from transform.mappings.products import PRODUCT_FIXES
from transform.mappings.companies import COMPANY_FIXES
from transform.mappings.common import COMMON_FIXES
from transform.mappings.names import NAMES_FIXES

# Mescla todos os dicionários; ordena por tamanho decrescente para evitar
# substituições parciais (ex: "ANDR?A" antes de "ANDR?").
_merged = {**COMMON_FIXES, **PRODUCT_FIXES, **COMPANY_FIXES, **NAMES_FIXES}
DOMAIN_ENCODING_PATTERNS = dict(sorted(_merged.items(), key=lambda x: -len(x[0])))

# DOMAIN_ENCODING_PRODUCTS = {
    
# }