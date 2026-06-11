"""
Nomes próprios brasileiros com encoding corrompido ('?').
Prenomes, sobrenomes e partículas comuns no Brasil.

Ordenar do maior para o menor (garantido pelo __init__.py ao mesclar).
"""

NAMES_FIXES = {
    # ══════════════════════════════════════════════════════════════════
    # Padrões duplos (??) — processar ANTES dos simples
    # ══════════════════════════════════════════════════════════════════

    # CONCEIÇÃO — 18x — mais frequente com ??
    "CONCEI??O": "CONCEIÇÃO",
    "CONCEI??ES": "CONCEIÇÕES",
    # COCEI??O — typo do ERP para CONCEIÇÃO
    "COCEI??O": "CONCEIÇÃO",

    # ASSUNÇÃO
    "ASSUN??O": "ASSUNÇÃO",
    "ASSUN??ES": "ASSUNÇÕES",

    # ══════════════════════════════════════════════════════════════════
    # Sobrenomes — maiores primeiro (evitar substituição parcial)
    # ══════════════════════════════════════════════════════════════════

    # GON?ALVES — 49x
    "GON?ALVES": "GONÇALVES",

    # ARA?JO — 43x
    "ARA?JO": "ARAÚJO",

    # GUIMAR?ES — 15x
    "GUIMAR?ES": "GUIMARÃES",

    # MENDON?A — 8x
    "MENDON?A": "MENDONÇA",

    # MAGALH?ES — 7x
    "MAGALH?ES": "MAGALHÃES",

    # BRAND?O — 6x (Brandão)
    "BRAND?O": "BRANDÃO",

    # CORR?A — 10x (Corrêa)
    "CORR?A": "CORRÊA",

    # FRAN?A — 12x (França)
    "FRAN?A": "FRANÇA",

    # SIM?ES — 4x (Simões)
    "SIM?ES": "SIMÕES",

    # BONIF?CIO — 4x (Bonifácio)
    "BONIF?CIO": "BONIFÁCIO",

    # MISERIC?RDIA — 4x (Misericórdia)
    "MISERIC?RDIA": "MISERICÓRDIA",

    # N?BREGA — (Nóbrega)
    "N?BREGA": "NÓBREGA",

    # OS?RIO — (Osório)
    "OS?RIO": "OSÓRIO",

    # GATT?S — (Gattás)
    "GATT?S": "GATTÁS",

    # PODEST? — (Podestá)
    "PODEST?": "PODESTÁ",

    # ?VILA — (Ávila)
    "?VILA": "ÁVILA",

    # SEBASTI?O — (Sebastião)
    "SEBASTI?O": "SEBASTIÃO",

    # GALV?O — (Galvão) — já em common.py; repetido aqui p/ segurança
    # "GALV?O": "GALVÃO",  # já coberto

    # TOM? — sobrenome Tomé / Tomá
    "TOM?": "TOMÉ",

    # L?SARO / L?ZARO
    "L?ZARO": "LÁZARO",
    "L?SARO": "LÁSARO",

    # ACR?ZIA / T?NEA — raros mas presentes
    "ACR?ZIA": "ACRÁZIA",
    "T?NEA": "TÂNEA",

    # ?RSIA — (Érsia / Ársia)
    "?RSIA": "ÉRSIA",

    # ANA? — nome Anaí
    "ANA?": "ANAÍ",

    # Outros sobrenomes comuns
    "CUST?DIO": "CUSTÓDIO",
    "FAGUN?ES": "FAGUNDES",
    "FRANC?S": "FRANCÊS",
    "MARC?O": "MARCÃO",
    "PINT?O": "PINTÃO",
    "QUEIROZ": "QUEIROZ",          # já correto — skip
    "QUEIRÓS": "QUEIRÓS",          # já correto
    "SANTAN?": "SANTANÁ",
    "TRAMONT?NA": "TRAMONTINA",    # marca, mas aparece em nomes
    "PEREI?RA": "PEREIRA",         # improvável mas defensivo
    "FRAGOS?": "FRAGOSO",
    "CARN?IRO": "CARNEIRO",
    "OLIV?RIA": "OLIVÁRIA",
    "TAVAR?S": "TAVARES",           # sem acento — já correto

    # ══════════════════════════════════════════════════════════════════
    # Prenomes femininos
    # ══════════════════════════════════════════════════════════════════

    # ELISÂNGELA
    "ELIS?NGELA": "ELISÂNGELA",

    # EUGÊNIA
    "EUG?NIA": "EUGÊNIA",

    # ÂNGELA / ÂNGELO
    "?NGELA": "ÂNGELA",
    "?NGELO": "ÂNGELO",

    # AMÉLIA
    "AM?LIA": "AMÉLIA",

    # ANDRÉA — antes de ANDRÉ (maior primeiro)
    "ANDR?A": "ANDRÉA",

    # J?SSICA — 12x
    "J?SSICA": "JÉSSICA",

    # PATR?CIA — 11x
    "PATR?CIA": "PATRÍCIA",

    # LET?CIA — 10x
    "LET?CIA": "LETÍCIA",

    # B?RBARA — 8x
    "B?RBARA": "BÁRBARA",

    # D?BORA — 8x
    "D?BORA": "DÉBORA",

    # VIT?RIA — 7x
    "VIT?RIA": "VITÓRIA",

    # C?LIA — 7x
    "C?LIA": "CÉLIA",

    # CL?UDIA — 6x
    "CL?UDIA": "CLÁUDIA",

    # L?CIA — 6x
    "L?CIA": "LÚCIA",

    # NAT?LIA — 6x
    "NAT?LIA": "NATÁLIA",

    # M?RCIA — 5x
    "M?RCIA": "MÁRCIA",

    # THA?S — 5x
    "THA?S": "THAÍS",

    # VAL?RIA — 5x
    "VAL?RIA": "VALÉRIA",

    # VER?NICA — 5x
    "VER?NICA": "VERÔNICA",

    # F?TIMA — 4x
    "F?TIMA": "FÁTIMA",

    # J?LIA — 4x
    "J?LIA": "JÚLIA",

    # C?SSIA — 4x
    "C?SSIA": "CÁSSIA",

    # FL?VIA — 4x
    "FL?VIA": "FLÁVIA",

    # K?TIA — 4x
    "K?TIA": "KÁTIA",

    # S?NIA — 4x
    "S?NIA": "SÔNIA",

    # TAIN? — 4x
    "TAIN?": "TAINÁ",

    # ?RICA — 3x
    "?RICA": "ÉRICA",

    # ?GHATA — 1x
    "?GHATA": "ÁGATHA",

    # Outros prenomes femininos frequentes no Brasil
    "?NGELA": "ÂNGELA",
    "?NGELA": "ÂNGELA",
    "S?NIA": "SÔNIA",               # variante grafia
    "CRISTI?NE": "CRISTIANE",       # sem acento — já correto
    "CRISTI?NA": "CRISTINA",        # sem acento — já correto
    "V?NUS": "VÊNUS",
    "M?NICA": "MÔNICA",             # já em common.py; repetido p/ segurança
    "?LIDA": "ÉLIDA",
    "C?NTIA": "CÍNTIA",
    "MARIA ?NGELA": "MARIA ÂNGELA",
    "IS?RIA": "ISÓRIA",
    "LUCR?CIA": "LUCRÉCIA",
    "BENED?TA": "BENEDITA",
    "CONCEI??O": "CONCEIÇÃO",       # já acima — redundância segura
    "H?LIA": "HÉLIA",
    "AN?LIA": "ANÁLIA",
    "DIAN? ": "DIANÁ ",             # nome raro
    "TAM?RES": "TAMIRES",           # variante
    "LOR?NA": "LORENA",             # sem acento — já correto
    "?RSULA": "ÚRSULA",
    "BEATR?Z": "BEATRIZ",           # sem acento na última sílaba em pt-BR
    "MADALENA": "MADALENA",         # já correto
    "R?BECA": "REBECA",             # sem acento em pt-BR
    "ISA?AS": "ISAÍAS",
    "LOR?NZA": "LORENZA",
    "EVEL?SE": "EVELISE",
    "JOSI?NE": "JOSIANE",
    "ELIZAB?TE": "ELIZABETE",
    "EVEL?N": "EVELIN",
    "ROSAN?": "ROSANÁ",
    "IREN?": "IRENÁ",
    "GI?VANA": "GIOVANA",
    "GESI?LDA": "GESILDA",
    "ELIANE ": "ELIANE ",           # já correto
    "TER?SA": "TERESA",             # sem acento em pt-BR

    # ══════════════════════════════════════════════════════════════════
    # Prenomes masculinos
    # ══════════════════════════════════════════════════════════════════

    # JOS? — 41x  (deve vir ANTES de qualquer prefixo menor)
    "JOS?": "JOSÉ",

    # ANDR? — 17x  (deve vir DEPOIS de ANDR?A — já garantido pela ordem)
    "ANDR?": "ANDRÉ",

    # ANT?NIO — 12x
    "ANT?NIO": "ANTÔNIO",

    # J?NIOR — 6x
    "J?NIOR": "JÚNIOR",

    # ROG?RIO — 6x
    "ROG?RIO": "ROGÉRIO",

    # S?RGIO — 6x
    "S?RGIO": "SÉRGIO",

    # M?RCIO — 5x
    "M?RCIO": "MÁRCIO",

    # J?LIO — 5x
    "J?LIO": "JÚLIO",

    # VIN?CIUS — 5x
    "VIN?CIUS": "VINÍCIUS",

    # C?SAR — 4x
    "C?SAR": "CÉSAR",

    # C?NDIDO — 4x
    "C?NDIDO": "CÂNDIDO",

    # LU?S — 4x
    "LU?S": "LUÍS",

    # F?BIO — 4x
    "F?BIO": "FÁBIO",

    # ?LVARO — 1x
    "?LVARO": "ÁLVARO",

    # LÍVIA — nome muito frequente no Brasil
    "L?VIA": "LÍVIA",

    # CÍCERO — nome muito comum no Brasil
    "C?CERO": "CÍCERO",

    # SÍLVIO
    "S?LVIO": "SÍLVIO",

    # HÉLIO
    "H?LIO": "HÉLIO",

    # OTÁVIO
    "OT?VIO": "OTÁVIO",

    # RÔMULO
    "R?MULO": "RÔMULO",

    # TÚLIO
    "T?LIO": "TÚLIO",

    # EUGÊNIO
    "EUG?NIO": "EUGÊNIO",

    # CLÁUDIO
    "CL?UDIO": "CLÁUDIO",

    # MÁRCIO — variante
    "M?RCIO": "MÁRCIO",

    # MAURÍCIO
    "MAUR?CIO": "MAURÍCIO",

    # PATRÍCIO
    "PATR?CIO": "PATRÍCIO",

    # Outros prenomes masculinos frequentes
    "SEBASTI?O": "SEBASTIÃO",       # já acima
    "?DISON": "ÉDISON",
    "?DGAR": "ÉDGAR",
    "?DSON": "ÉDSON",
    "?LVARO": "ÁLVARO",             # já acima
    "D?RIO": "DÁRIO",
    "CL?UDIO": "CLÁUDIO",
    "MAUR?CIO": "MAURÍCIO",
    "PATR?CIO": "PATRÍCIO",
    "AGN?LDO": "AGNALDO",           # sem acento — já correto
    "HER?CLES": "HÉRCULES",
    "T?LIO": "TÚLIO",
    "EUST?QUIO": "EUSTÁQUIO",
    "G?LVÃO": "GÁLVÃO",
    "FAB?OLA": "FABÍOLA",
    "MAUR?LIO": "MAURÍLIO",
    "EUG?NIO": "EUGÊNIO",
    "OSMAR": "OSMAR",               # já correto
    "OZEAS": "OZÉIAS",
    "ISAC": "ISAAC",                # já correto
    "CIRINO": "CIRINO",             # já correto
    "SEBASTI?O": "SEBASTIÃO",
    "DONIZETE": "DONIZETE",         # já correto
    "ALDEC?R": "ALDECIR",
    "ODERC?": "ODERCIR",
    "EDER?CEUS": "EDERCIUS",
    "GENOV?VE": "GENOVEVA",

    # ══════════════════════════════════════════════════════════════════
    # Partículas e artigos em nomes compostos
    # ══════════════════════════════════════════════════════════════════
    # (evitar S? → SÁ pois é substring perigosa; usar apenas se necessário)

    # ══ Sobrenomes/nomes adicionais da 7ª rodada ══
    "VEN?NCIO": "VENÂNCIO",
    "ALC?NTARA": "ALCÂNTARA",
    "HERM?NIO": "HERMÍNIO",
    "VALE?A": "VALENÇA",

    # ══ 8ª rodada — identificados na lista dos 144 ══

    # Sobrenomes com alta frequência
    "JORD?O": "JORDÃO",
    "FALC?O": "FALCÃO",
    "IN?CIO": "INÁCIO",
    "REBOU?AS": "REBOUÇAS",
    "BELTR?O": "BELTRÃO",
    "ESTEV?O": "ESTEVÃO",
    "MONTALV?O": "MONTALVÃO",
    "ARIMAT?IA": "ARIMATÉIA",
    "ASSUMP??O": "ASSUMPÇÃO",
    "MAR?AL": "MARÇAL",
    "UCH?A": "UCHÔA",
    "PERP?TUO": "PERPÉTUO",
    "SILV?RIO": "SILVÉRIO",
    "HON?RIO": "HONÓRIO",
    "BONAF?": "BONAFÉ",
    "BOU?AS": "BOUÇAS",
    "FIGUEIR?": "FIGUEIRÓ",

    # Prenomes femininos da lista
    "T?NIA": "TÂNIA",
    "V?NIA": "VÂNIA",
    "L?GIA": "LÍGIA",
    "ANG?LICA": "ANGÉLICA",
    "IN?S": "INÊS",
    "ANT?NIA": "ANTÔNIA",
    "LEOC?DIA": "LEOCÁDIA",
    "QUIT?RIA": "QUITÉRIA",
    "RA?SA": "RAÍSSA",
    "RA?LA": "RAÍLA",
    "N?DIA": "NÁDIA",
    "L?IA": "LÉIA",
    "N?IA": "NÉIA",
    "N?THALY": "NÁTHALY",
    "ROS?LENE": "ROSÉLENE",
    "VICT?RIA": "VICTÓRIA",
    "ELIN?IA": "ELINÉIA",
    "HINA?": "HINAÍ",
    "THAYN?": "THAYNÃ",
    "T?BITA": "TÁBITA",

    # Prenomes masculinos da lista
    "ROM?RIO": "ROMÁRIO",
    "MOIS?S": "MOISÉS",
    "JOSU?": "JOSUÉ",
    "JESS?": "JESSÉ",
    "AM?RICO": "AMÉRICO",
    "CL?VIS": "CLÓVIS",
    "J?FERSON": "JÉFERSON",
    "ARIST?TELES": "ARISTÓTELES",
    "IZA?AS": "IZAÍAS",
    "EUST?CHIO": "EUSTÁQUIO",
    "H?BER": "HÉBER",
    "AD?O": "ADÃO",
    "CA?QUE": "CAÍQUE",
    "CAU?": "CAUÃ",
    "FABR?CIO": "FABRÍCIO",
    "P?DUA": "PÁDUA",
    "V?TOR": "VÍTOR",
    "INOC?NCIO": "INOCÊNCIO",
    "CEC?LIO": "CECÍLIO",
    "JULI?O": "JULIÃO",
    "EUZ?BIO": "EUZÉBIO",
    "DAMI?O": "DAMIÃO",
    "BRAS?LIO": "BRASÍLIO",
    "F?BIA": "FÁBIA",
    "GESS?": "GESSÉ",
    "K?CIA": "KÁCIA",
    "K?SSIA": "KÁSSIA",
    "KATI?CIA": "KATIÚCIA",
    "FID?NCIO": "FIDÊNCIO",
    "HIL?RIO": "HILÁRIO",
}
