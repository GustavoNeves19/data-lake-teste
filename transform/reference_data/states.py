"""
Estados brasileiros — Lista fixa de 27 UFs.
Nunca muda, não precisa de API.
"""

BRAZILIAN_STATES = {
    "AC": "ACRE",
    "AL": "ALAGOAS",
    "AM": "AMAZONAS",
    "AP": "AMAPÁ",
    "BA": "BAHIA",
    "CE": "CEARÁ",
    "DF": "DISTRITO FEDERAL",
    "ES": "ESPÍRITO SANTO",
    "GO": "GOIÁS",
    "MA": "MARANHÃO",
    "MG": "MINAS GERAIS",
    "MS": "MATO GROSSO DO SUL",
    "MT": "MATO GROSSO",
    "PA": "PARÁ",
    "PB": "PARAÍBA",
    "PE": "PERNAMBUCO",
    "PI": "PIAUÍ",
    "PR": "PARANÁ",
    "RJ": "RIO DE JANEIRO",
    "RN": "RIO GRANDE DO NORTE",
    "RO": "RONDÔNIA",
    "RR": "RORAIMA",
    "RS": "RIO GRANDE DO SUL",
    "SC": "SANTA CATARINA",
    "SE": "SERGIPE",
    "SP": "SÃO PAULO",
    "TO": "TOCANTINS",
}

# Set de siglas válidas pra validação rápida
VALID_STATE_CODES = set(BRAZILIAN_STATES.keys())

# Mapeamento de nomes corrompidos → sigla correta
STATE_FIXES = {
    "PAR?": "PA",
    "PARAN?": "PR",
    "CEAR?": "CE",
    "MARANH?O": "MA",
    "GOI?S": "GO",
    "AMAP?": "AP",
    "PIAU?": "PI",
    "PARA?BA": "PB",
    "ROND?NIA": "RO",
    "S?O PAULO": "SP",
    "ESP?RITO SANTO": "ES",
    "PAR?": "PA",
}
