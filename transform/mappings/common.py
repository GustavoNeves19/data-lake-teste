"""
Padrões comuns de encoding que aparecem em múltiplos domínios.
Fragmentos de palavras — aplicados com str.replace (não precisa ser palavra inteira).

REGRA: colocar os padrões MAIORES primeiro (ex: "??O" antes de "?O")
para evitar substituição parcial.
"""

COMMON_FIXES = {
    # ══ Padrões com dois ?? (ÇÃ, ÇÕ) — processar PRIMEIRO ══
    "A??O": "AÇÃO",
    "A??ES": "AÇÕES",
    "FUN??O": "FUNÇÃO",
    "FUN??ES": "FUNÇÕES",
    "SE??O": "SEÇÃO",
    "SE??ES": "SEÇÕES",
    "POSI??O": "POSIÇÃO",
    "POSI??ES": "POSIÇÕES",
    "CONDI??O": "CONDIÇÃO",
    "CONDI??ES": "CONDIÇÕES",
    "EXCE??O": "EXCEÇÃO",
    "EXCE??ES": "EXCEÇÕES",
    "INSTALA??O": "INSTALAÇÃO",
    "INSTALA??ES": "INSTALAÇÕES",
    "OPERA??O": "OPERAÇÃO",
    "OPERA??ES": "OPERAÇÕES",
    "CALIBRA??O": "CALIBRAÇÃO",
    "MANUTEN??O": "MANUTENÇÃO",
    "REDU??O": "REDUÇÃO",
    "FIXA??O": "FIXAÇÃO",
    "PROTE??O": "PROTEÇÃO",
    "AUTOMA??O": "AUTOMAÇÃO",
    "REFRIGERA??O": "REFRIGERAÇÃO",
    "VENTILA??O": "VENTILAÇÃO",
    "DISTRIBUI??O": "DISTRIBUIÇÃO",
    "IMPORTA??O": "IMPORTAÇÃO",
    "EXPORTA??O": "EXPORTAÇÃO",
    "INFORMA??O": "INFORMAÇÃO",
    "INFORMA??ES": "INFORMAÇÕES",
    "EDUCA??O": "EDUCAÇÃO",
    "PRODU??O": "PRODUÇÃO",
    "CONSTRU??O": "CONSTRUÇÃO",
    "SOLU??O": "SOLUÇÃO",
    "SOLU??ES": "SOLUÇÕES",
    "COMUNICA??O": "COMUNICAÇÃO",
    "CLASSIFICA??O": "CLASSIFICAÇÃO",
    "ORGANIZA??O": "ORGANIZAÇÃO",
    "MOVIMENTA??O": "MOVIMENTAÇÃO",
    "DOCUMENTA??O": "DOCUMENTAÇÃO",
    "ADMINISTRA??O": "ADMINISTRAÇÃO",
    "LIQUIDA??O": "LIQUIDAÇÃO",
    "NEGOCIA??O": "NEGOCIAÇÃO",
    "ATUALIZA??O": "ATUALIZAÇÃO",
    "FATURA??O": "FATURAÇÃO",
    "TRIBUTA??O": "TRIBUTAÇÃO",
    "COMPENSA??O": "COMPENSAÇÃO",
    "DEVOLU??O": "DEVOLUÇÃO",
    "INSPE??O": "INSPEÇÃO",
    "RECEP??O": "RECEPÇÃO",
    "CORRE??O": "CORREÇÃO",
    "ALTERA??O": "ALTERAÇÃO",
    "CANCELA??O": "CANCELAÇÃO",
    "APROVA??O": "APROVAÇÃO",

    # ══ Padrões com um ? (Ã, Á, Â, É, Ê, Í, Ó, Ô, Õ, Ú, Ç) ══
    # Ã / Õ
    "S?O": "SÃO",
    "N?O": "NÃO",
    "GR?O": "GRÃO",
    "M?O": "MÃO",
    "ALEM?O": "ALEMÃO",
    "CRIST?O": "CRISTÃO",
    "CAPIT?O": "CAPITÃO",
    "JO?O": "JOÃO",
    "CONEX?O": "CONEXÃO",
    "PRESS?O": "PRESSÃO",
    "DIMENS?O": "DIMENSÃO",
    "EXTENS?O": "EXTENSÃO",
    "TENS?O": "TENSÃO",
    "EXPANS?O": "EXPANSÃO",
    "COLIS?O": "COLISÃO",
    "EMISS?O": "EMISSÃO",
    "PERMISS?O": "PERMISSÃO",
    "COMISS?O": "COMISSÃO",
    "DIVIS?O": "DIVISÃO",
    "REVIS?O": "REVISÃO",
    "PROVIS?O": "PROVISÃO",
    "VIS?O": "VISÃO",

    # Ç
    "PRE?O": "PREÇO",
    "SERVI?O": "SERVIÇO",
    "SERVI?OS": "SERVIÇOS",
    "CABE?A": "CABEÇA",
    "BALAN?A": "BALANÇA",
    "MUDAN?A": "MUDANÇA",
    "SEGURAN?A": "SEGURANÇA",
    "CONFIAN?A": "CONFIANÇA",
    "ALIAN?A": "ALIANÇA",
    "LIDERAN?A": "LIDERANÇA",
    "ESPERAN?A": "ESPERANÇA",
    "PRESEN?A": "PRESENÇA",
    "ISEN??O": "ISENÇÃO",

    # É / Ê
    "COM?RCIO": "COMÉRCIO",
    "NEG?CIOS": "NEGÓCIOS",
    "NEG?CIO": "NEGÓCIO",
    "GER?NCIA": "GERÊNCIA",
    "REFER?NCIA": "REFERÊNCIA",
    "EMERG?NCIA": "EMERGÊNCIA",
    "FREQU?NCIA": "FREQUÊNCIA",
    "EXPERI?NCIA": "EXPERIÊNCIA",
    "CONSIST?NCIA": "CONSISTÊNCIA",

    # Á
    "?GUA": "ÁGUA",
    "?REA": "ÁREA",
    "M?QUINA": "MÁQUINA",
    "V?LVULA": "VÁLVULA",
    "L?MINA": "LÂMINA",
    "C?MARA": "CÂMARA",
    "DIN?MICA": "DINÂMICA",

    # Ó / Ô
    "LOG?STICA": "LOGÍSTICA",
    "MEC?NICA": "MECÂNICA",
    "HIDR?ULICA": "HIDRÁULICA",
    "PNEUM?TICA": "PNEUMÁTICA",
    "EL?TRICA": "ELÉTRICA",
    "ELETR?NICA": "ELETRÔNICA",
    "QU?MICA": "QUÍMICA",
    "T?CNICA": "TÉCNICA",
    "T?CNICO": "TÉCNICO",
    "T?RMICO": "TÉRMICO",
    "T?RMICO": "TÉRMICO",
    "AUT?NOMO": "AUTÔNOMO",
    "TEL?FONE": "TELEFONE",
    "PER?ODO": "PERÍODO",
    "RELAT?RIO": "RELATÓRIO",
    "ESCRIT?RIO": "ESCRITÓRIO",
    "AUDIT?RIO": "AUDITÓRIO",
    "REPOSIT?RIO": "REPOSITÓRIO",
    "TERRIT?RIO": "TERRITÓRIO",
    "TEMPOR?RIO": "TEMPORÁRIO",
    "PROVIS?RIO": "PROVISÓRIO",
    "NECESS?RIO": "NECESSÁRIO",
    "VOLUNT?RIO": "VOLUNTÁRIO",
    "COMENT?RIO": "COMENTÁRIO",
    "INVENT?RIO": "INVENTÁRIO",
    "ARMAZ?M": "ARMAZÉM",

    # Ú
    "?NICO": "ÚNICO",
    "?LTIMO": "ÚLTIMO",
    "N?MERO": "NÚMERO",
    "N?MEROS": "NÚMEROS",
    "P?BLICO": "PÚBLICO",
    "M?SICA": "MÚSICA",
    
# Adicionar ao COMMON_FIXES:
    "ABRA?ADEIRA": "ABRAÇADEIRA",
    "BALAN?A": "BALANÇA",
    "DESCART?VEIS": "DESCARTÁVEIS",
    "DESCART?VEL": "DESCARTÁVEL",
    "M?DICO": "MÉDICO",
    "M?DICA": "MÉDICA",
    "M?DICOS": "MÉDICOS",
    "REABILITA??O": "REABILITAÇÃO",
    "INCLUS?O": "INCLUSÃO",
    "PAIX?O": "PAIXÃO",
    "ACELERA??O": "ACELERAÇÃO",
    "?CULOS": "ÓCULOS",
    "?NIBUS": "ÔNIBUS",
    "RENASCEN?A": "RENASCENÇA",
    "ANHANG?ERA": "ANHANGUERA",

    # ══ Plurais e variantes faltantes ══
    # ÇÕ / ÃO plurais
    "DEVOLU??ES": "DEVOLUÇÕES",
    "RESCIS?ES": "RESCISÕES",
    "REFEI??ES": "REFEIÇÕES",
    "EMISS?ES": "EMISSÕES",
    "CONEX?ES": "CONEXÕES",

    # É / Ê (singular e plural masculino/feminino)
    "EL?TRICOS": "ELÉTRICOS",
    "EL?TRICAS": "ELÉTRICAS",
    "ELETR?NICOS": "ELETRÔNICOS",
    "PERIF?RICOS": "PERIFÉRICOS",
    "EL?TRICO": "ELÉTRICO",
    "MAT?RIA": "MATÉRIA",
    "MAT?RIAS": "MATÉRIAS",
    "ESCRIT?RIOS": "ESCRITÓRIOS",

    # Á / Â
    "AP?S": "APÓS",
    "SAL?RIOS": "SALÁRIOS",
    "SAL?RIO": "SALÁRIO",
    "FUNCION?RIOS": "FUNCIONÁRIOS",
    "FUNCION?RIO": "FUNCIONÁRIO",
    "MOBILI?RIO": "MOBILIÁRIO",
    "MOBILI?RIOS": "MOBILIÁRIOS",
    "OR?AMENTO": "ORÇAMENTO",
    "OR?AMENTOS": "ORÇAMENTOS",
    "COBRAN?A": "COBRANÇA",
    "COBRAN?AS": "COBRANÇAS",
    "EMPRESTIMOS": "EMPRÉSTIMOS",
    "EMPR?STIMOS": "EMPRÉSTIMOS",
    "EMPR?STIMO": "EMPRÉSTIMO",

    # Ç variantes
    "PE?AS": "PEÇAS",
    "PE?A": "PEÇA",
    "VIAC?O": "VIAÇÃO",
    "RODOA?REO": "RODOAÉREO",

    # Transporte / logística
    "RODOFEROVI?RIO": "RODOFERROVIÁRIO",
    "RODOVI?RIO": "RODOVIÁRIO",
    "FERROVI?RIO": "FERROVIÁRIO",
    "AEROPORTO?RIO": "AEROPORTUÁRIO",

    # Elásticos / flexíveis
    "ELAST?MEROS": "ELASTÔMEROS",
    "ELAST?MERO": "ELASTÔMERO",
    "FLEX?VEIS": "FLEXÍVEIS",
    "FLEX?VEL": "FLEXÍVEL",

    # Motor / indústria
    "PIST?O": "PISTÃO",
    "PIST?ES": "PISTÕES",
    "F?CIL": "FÁCIL",
    "F?CEIS": "FÁCEIS",

    # Termos financeiros
    "RETEN??O": "RETENÇÃO",
    "RETEN??ES": "RETENÇÕES",
    "ISEN??O": "ISENÇÃO",
    "ISEN??ES": "ISENÇÕES",
    "AQUISI??O": "AQUISIÇÃO",
    "AQUISI??ES": "AQUISIÇÕES",
    "PRESTA??ES": "PRESTAÇÕES",
    "PRESTA??O": "PRESTAÇÃO",
    "COMISS?ES": "COMISSÕES",
    "COMISS?O": "COMISSÃO",
    "TRIBUTA??ES": "TRIBUTAÇÕES",
    "RATEIO": "RATEIO",

    # Termos RH
    "RESCIS?O": "RESCISÃO",
    "ADMISS?O": "ADMISSÃO",
    "ADMISS?ES": "ADMISSÕES",
    "CARGOS E REMUNERA??O": "CARGOS E REMUNERAÇÃO",

    # Informática / tecnologia
    "PERIF?RICO": "PERIFÉRICO",
    "COMPUTADORES E PERIF?RICOS": "COMPUTADORES E PERIFÉRICOS",
    "M?DIA": "MÍDIA",
    "LICEN?A": "LICENÇA",
    "LICEN?AS": "LICENÇAS",

    # ══ Termos técnicos industriais / produtos ══
    "C?NICA": "CÔNICA",
    "C?NICO": "CÔNICO",
    "C?NICOS": "CÔNICOS",
    "CELUL?IDE": "CELULÓIDE",
    "CAF?": "CAFÉ",
    "PNEUM?TICOS": "PNEUMÁTICOS",
    "PNEUM?TICO": "PNEUMÁTICO",
    "POLIM?RICA": "POLIMÉRICA",
    "POLIM?RICO": "POLIMÉRICO",
    "ACESS?RIOS": "ACESSÓRIOS",
    "ACESS?RIO": "ACESSÓRIO",
    "ROD?ZIOS": "RODÍZIOS",
    "ROD?ZIO": "RODÍZIO",
    "INJE??O": "INJEÇÃO",
    "INJE??ES": "INJEÇÕES",
    "FOR?A": "FORÇA",
    "FOR?AS": "FORÇAS",
    "VACU?METRO": "VACUÔMETRO",
    "VACU?METROS": "VACUÔMETROS",
    "INFORM?TICA": "INFORMÁTICA",
    "LOCOMO??O": "LOCOMOÇÃO",
    "SELE??O": "SELEÇÃO",
    "SELE??ES": "SELEÇÕES",
    "RECRUTAMENTO E SELE??O": "RECRUTAMENTO E SELEÇÃO",
    "ESPECIFICADAS": "ESPECIFICADAS",  # já correto — skip
    "N?O ESPECIFICADAS": "NÃO ESPECIFICADAS",

    # Transportadoras / cidades
    "IGUA?U": "IGUAÇU",
    "A?ORES": "AÇORES",
    "PAJU?ARA": "PAJUÇARA",

    # Financeiro extra
    "VACU?": "VACUÔ",
    "DESPESAS INFORM?TICA": "DESPESAS INFORMÁTICA",
    "FOR?A INALADOR": "FORÇA INALADOR",

    # ══ Últimas adições — termos observados nos dados ══
    "GAL?O": "GALÃO",
    "GAL?ES": "GALÕES",
    "SANIT?RIO": "SANITÁRIO",
    "SANIT?RIOS": "SANITÁRIOS",
    "SANIT?RIA": "SANITÁRIA",
    "GR?FICO": "GRÁFICO",
    "GR?FICOS": "GRÁFICOS",
    "GR?FICA": "GRÁFICA",
    "SUBSTITUI??O": "SUBSTITUIÇÃO",
    "SUBSTITUI??ES": "SUBSTITUIÇÕES",
    "LOG?STICO": "LOGÍSTICO",
    "LOG?STICOS": "LOGÍSTICOS",
    "LOG?STICA": "LOGÍSTICA",
    "OP??O": "OPÇÃO",
    "OP??ES": "OPÇÕES",
    "GALV?NICA": "GALVÂNICA",
    "GALV?NICO": "GALVÂNICO",
    "DESODORANTE": "DESODORANTE",  # já correto
    "DESODORANTE SANIT?RIO": "DESODORANTE SANITÁRIO",
    "DETERGENTE SLOPAN": "DETERGENTE SLOPAN",  # já correto — skip
    "EPI?S": "EPIs",  # Equipamento Proteção Individual (plural)
    "M?NICA": "MÔNICA",  # nome de marca/personagem
    "TURMA DA M?NICA": "TURMA DA MÔNICA",

    # ══ Termos faltantes identificados na 2ª rodada ══

    # Frases verbais / operacionais
    "LIGAC?ES": "LIGAÇÕES",       # "BL CONTROLE DE LIGAÇÕES" — produto
    "LIGA??O": "LIGAÇÃO",
    "OPINI?O": "OPINIÃO",         # entidade bridge

    # Cidades / regiões com acento
    "CORUMB?": "CORUMBÁ",          # Corumbá (MS)
    "OL?MPIA": "OLÍMPIA",          # Olímpia (SP)
    "OL?MPICO": "OLÍMPICO",
    "OL?MPICOS": "OLÍMPICOS",

    # Transportadoras / marcas
    "RA?A": "RAÇA",                # Raça Transportes
    "TCH?": "TCHÉ",                # Rede Tché (expressão gaúcha)
    "MELGA?O": "MELGAÇO",          # sobrenome / cidade

    # Estrangeirismos / nomes espanhóis presentes nos dados
    "M?NDEZ": "MÉNDEZ",
    "MANJ?N": "MANJÓN",

    # Sufixos truncados em campos médicos
    "M?DI": "MÉDI",                # truncamento de MÉDICO/MÉDICA

    # ══ 3ª rodada — termos médicos/hospitalares e gerais ══

    # Assistência / clínica (alta frequência em dim_partner / entity_bridge)
    "ASSIST?NCIA": "ASSISTÊNCIA",
    "ASSIST?NCIAS": "ASSISTÊNCIAS",
    "CL?NICA": "CLÍNICA",
    "CL?NICAS": "CLÍNICAS",
    "ODONTOL?GICA": "ODONTOLÓGICA",
    "ODONTOL?GICO": "ODONTOLÓGICO",
    "ODONTOL?GICAS": "ODONTOLÓGICAS",
    "ODONTOL?GICOS": "ODONTOLÓGICOS",

    # Infância / maternidade
    "INF?NCIA": "INFÂNCIA",

    # Cidades brasileiras frequentes
    "RIBEIR?O": "RIBEIRÃO",        # Ribeirão Preto, Ribeirão das Neves...
    "PARNA?BA": "PARNAÍBA",        # cidade no Piauí
    "POUSO ALEGRE": "POUSO ALEGRE",  # já correto
    "ARARAQUARA": "ARARAQUARA",      # já correto

    # Informática / produtos
    "C?DIGO": "CÓDIGO",
    "C?DIGOS": "CÓDIGOS",
    "MEM?RIA": "MEMÓRIA",
    "MEM?RIAS": "MEMÓRIAS",

    # Logística / transportes
    "R?PIDA": "RÁPIDA",
    "R?PIDAS": "RÁPIDAS",
    "R?PIDO": "RÁPIDO",
    "R?PIDOS": "RÁPIDOS",

    # Operação / natureza — corrigir standalone "? ESPECIFICADAS"
    "ENTRADAS ? ESPECIFICADAS": "ENTRADAS NÃO ESPECIFICADAS",
    "SA?DAS ? ESPECIFICADAS": "SAÍDAS NÃO ESPECIFICADAS",

    # Médico — mais variantes
    "M?DICO": "MÉDICO",            # já em common mas repete para garantia
    "M?DICA": "MÉDICA",
    "M?DICOS": "MÉDICOS",
    "M?DICAS": "MÉDICAS",

    # Sobrenome Sodré (Carina Almeida Sodré)
    "SODR?": "SODRÉ",

    # Crisóstomo (Daniel Crisóstomo)
    "CRIS?STOMO": "CRISÓSTOMO",

    # Osmário (nome masculino)
    "OSM?RIO": "OSMÁRIO",

    # Eloá (nome feminino)
    "ELO?": "ELOÁ",

    # Variantes de separadores em nomes corporativos
    # (NSR?-?REDE, C.T.M.?COMERCIO etc. — não corrígir automaticamente pois
    #  o '?' é separador, não acento)

    # ══ 4ª rodada — termos observados na 3ª execução ══

    # Plástica / Fênix — empresas
    "PL?STICA": "PLÁSTICA",
    "PL?STICAS": "PLÁSTICAS",
    "PL?STICO": "PLÁSTICO",
    "PL?STICOS": "PLÁSTICOS",
    "F?NIX": "FÊNIX",

    # Saída (direção / endereço)
    "SA?DA": "SAÍDA",
    "SA?DAS": "SAÍDAS",
    "ENTRADA": "ENTRADA",          # já correto

    # Fábrica / local
    "F?BRICA": "FÁBRICA",
    "F?BRICAS": "FÁBRICAS",
    "FABRIC?": "FABRICÁ",          # truncamento improvável mas defensivo

    # Elétrica / produtos
    "FUS?VEL": "FUSÍVEL",
    "FUS?VEIS": "FUSÍVEIS",
    "?MPERE": "ÂMPERE",
    "?MPERES": "ÂMPERES",

    # Fármacia e congêneres
    "FARM?CIA": "FARMÁCIA",
    "FARM?CIAS": "FARMÁCIAS",

    # Abreviações médicas
    "M?D.": "MÉD.",
    "M?D ": "MÉD ",                # forma sem ponto

    # Prenome Aurélio (muito comum no Brasil)
    "AUR?LIO": "AURÉLIO",
    "AUR?LIA": "AURÉLIA",

    # Nome Ítalo (italiano-brasileiro)
    "?TALO": "ÍTALO",
    "?TALA": "ÍTALA",

    # Laíla / Layla
    "LA?LA": "LAÍLA",

    # Variante grafias R?pido (mixed-case)
    "R?pido": "Rápido",
    "R?pida": "Rápida",

    # Lóggica (transportadora)
    "L?GGICA": "LÓGGICA",

    # ══ 5ª rodada ══

    # Econômico / catálogo / Suíça
    "ECON?MICO": "ECONÔMICO",
    "ECON?MICA": "ECONÔMICA",
    "ECON?MICOS": "ECONÔMICOS",
    "Econ?mico": "Econômico",      # mixed-case (transportadora)
    "CAT?LOGO": "CATÁLOGO",
    "CAT?LOGOS": "CATÁLOGOS",
    "SUI?A": "SUÍÇA",              # Suíça / transportadora Suíça Brasileira

    # Sobrenome Régis
    "R?GIS": "RÉGIS",

    # Nome Laís (feminino)
    "LA?S": "LAÍS",

    # Sobrenome Spíndola / Espíndola
    "ESP?NDOLA": "ESPÍNDOLA",
    "SP?NDOLA": "SPÍNDOLA",

    # Termos gerais que aparecem em produtos
    "padr?o": "padrão",            # mixed-case (produto)
    "padr?es": "padrões",

    # Régis / registros — common.py por ser termo geral
    "REGISTR?VEL": "REGISTRÁVEL",
    "REGISTR?VEIS": "REGISTRÁVEIS",

    # ══ 6ª rodada ══

    # Nível — ALTA frequência em produtos industriais
    "N?VEL": "NÍVEL",
    "N?VEIS": "NÍVEIS",

    # União (transportadoras, cooperativas)
    "UNI?O": "UNIÃO",
    "UNI?ES": "UNIÕES",

    # Galvão (sobrenome — já temos GALV?NICA → GALVÂNICA)
    "GALV?O": "GALVÃO",
    "GALV?ES": "GALVÕES",

    # Garça (cidade SP — transportadora)
    "GAR?A": "GARÇA",

    # LOGÍSTICA variante de corrupcao (LOGIST?CA vs LOG?STICA)
    "LOGIST?CA": "LOGÍSTICA",
    "LOGIST?CO": "LOGÍSTICO",
    "LOGIST?COS": "LOGÍSTICOS",

    # ASPIRADOR DE PÓ — contexto seguro para P?
    "ASPIRADOR DE P?": "ASPIRADOR DE PÓ",
    "P? P/": "PÓ P/",
    "DE P?": "DE PÓ",              # contexto "aspirador de pó"
    "(P?)": "(PÓ)",                # ex: COLORPLUS (PÓ)

    # Açougueiro / açúcar (produtos alimentares)
    "A?OUGUEIRO": "AÇOUGUEIRO",
    "A?OUGUEIRA": "AÇOUGUEIRA",
    "A??CAR": "AÇÚCAR",

    # Concreto / construção
    "CONCRET?IRA": "CONCRETEIRA",
    "CONCRET?IRAS": "CONCRETEIRAS",

    # Hidráulico — variantes masculinas (feminina já existia)
    "HIDR?ULICO": "HIDRÁULICO",
    "HIDR?ULICOS": "HIDRÁULICOS",

    # Trapézio (móveis de escritório)
    "TRAP?ZIO": "TRAPÉZIO",

    # Rosária / Rosário (nomes)
    "ROS?RIO": "ROSÁRIO",
    "ROS?RIA": "ROSÁRIA",

    # Cantão (sobrenome)
    "CANT?O": "CANTÃO",

    # Tristão (sobrenome)
    "TRIST?O": "TRISTÃO",

    # Gás — alta frequência em produtos industriais
    "G?S": "GÁS",
    "G?SES": "GASES",

    # Oséias (nome bíblico masculino)
    "OS?IAS": "OSÉIAS",

    # Formulário (produto de escritório)
    "FORMUL?RIO": "FORMULÁRIO",
    "FORMUL?RIOS": "FORMULÁRIOS",

    # Sintético/Sintética — standalone (a frase completa está em products.py)
    "SINT?TICOS": "SINTÉTICOS",
    "SINT?TICAS": "SINTÉTICAS",
    "SINT?TICO": "SINTÉTICO",
    "SINT?TICA": "SINTÉTICA",

    # ══ 8ª rodada — termos comuns e cidades ══

    # Espírito Santo (estado + nome)
    "ESP?RITO": "ESPÍRITO",

    # Espaço / terapêutico (empresas)
    "ESPA?O": "ESPAÇO",
    "TERAP?UTICO": "TERAPÊUTICO",
    "TERAP?UTICA": "TERAPÊUTICA",

    # Cartão / veterinário
    "CART?O": "CARTÃO",
    "VETERIN?RIO": "VETERINÁRIO",
    "VETERIN?RIA": "VETERINÁRIA",
    "VETERIN?RIOS": "VETERINÁRIOS",

    # Cidades brasileiras
    "CHAPEC?": "CHAPECÓ",
    "TAUBAT?": "TAUBATÉ",
    "NAZAR?": "NAZARÉ",
    "BRAGAN?A": "BRAGANÇA",
    "PAR?": "PARÁ",

    # Expressões em nomes
    "DO C?U": "DO CÉU",
    "DE NAZAR?": "DE NAZARÉ",

    # Sobrenome Sá — com contexto seguro para evitar falsos positivos
    "DE S?": "DE SÁ",
    " S? ": " SÁ ",
    "THIAGO S?": "THIAGO SÁ",

    # Outros termos da lista
    "FLOREN?A": "FLORENÇA",
    "ARAG?O": "ARAGÃO",
    "VALEN?A": "VALENÇA",
    "CHAC?N": "CHACÓN",
    "FAI?AL": "FAISSAL",
    "PERI??O": "PERIÇÃO",
    "TIM?TEO": "TIMÓTEO",
    "MART?": "MARTÉ",
    "BRAS?LIO": "BRASÍLIO",

    # Nome Laíza (variante de Laís)
    "LA?ZA": "LAÍZA",

    # Outros termos gerais em produtos
    "M?VEL": "MÓVEL",
    "M?VEIS": "MÓVEIS",
    "PROP?SITO": "PROPÓSITO",
    "PROP?SITOS": "PROPÓSITOS",
    "SUSPEN??O": "SUSPENSÃO",
    "VEDAC?O": "VEDAÇÃO",
    "VEDAC?ES": "VEDAÇÕES",
}





