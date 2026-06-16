"""
Diagnóstico dos clientes Hospitalar que aparecem na planilha do Alves
mas NÃO aparecem na carteira BQ-HOSPITALAR-ativa.

Estratégia:
  1. Ler 786 nomes da planilha (aba 'Sem fórmula Geral')
  2. Carregar carteira ativa HOSPITALAR do BQ + dim_partner (nome ↔ código)
  3. Normalizar nomes (uppercase, sem acentos, sem espaços extras)
  4. Achar quem está na planilha mas NÃO na carteira-HOSPITALAR
  5. Para os faltantes, buscar partner_code via dim_partner pelo nome normalizado
  6. Para cada partner_code achado: somar pedidos/valor/natureza no período
"""
import io, os, sys, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')

import pandas as pd
from google.cloud import bigquery

PROJ = 'sapient-metrics-492914-m7'
client = bigquery.Client(project=PROJ, location='us-east1')

def norm(s: str) -> str:
    if s is None or pd.isna(s): return ''
    s = str(s).upper().strip()
    s = ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')
    s = re.sub(r'\s+', ' ', s)
    return s

# ── 1. Planilha Alves ─────────────────────────────────────────────────────────
xlsx = r'C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026.xlsx'
plan = pd.read_excel(xlsx, sheet_name='Sem fórmula Geral')
plan['nome_norm'] = plan['ID - CLIENTE'].apply(norm)
nomes_alves = set(plan['nome_norm'].dropna())
print(f'Planilha Alves: {len(plan)} linhas, {len(nomes_alves)} nomes únicos normalizados')

# ── 2. Carteira ativa HOSPITALAR do BQ ────────────────────────────────────────
sql_cart = f"""
SELECT partner_code, partner_name
FROM `{PROJ}.silver_comercial.param_com_rfv_carteira`
WHERE is_active = TRUE
  AND rfv_familia = 'HOSPITALAR'
"""
cart = client.query(sql_cart).to_dataframe()
cart['nome_norm'] = cart['partner_name'].apply(norm)
nomes_cart = set(cart['nome_norm'])
print(f'Carteira BQ HOSPITALAR ativa: {len(cart)} clientes, {len(nomes_cart)} nomes únicos')

# ── 3. Quem está na Alves mas NÃO na carteira ─────────────────────────────────
faltantes = nomes_alves - nomes_cart
print(f'>>> Clientes na planilha mas NÃO na carteira HOSPITALAR: {len(faltantes)}')

# ── 4. Buscar partner_code via dim_partner pelo nome ──────────────────────────
sql_dim = f"""
SELECT partner_code, partner_name
FROM `{PROJ}.dm_partners.dim_partner`
"""
dim = client.query(sql_dim).to_dataframe()
dim['nome_norm'] = dim['partner_name'].apply(norm)

# map nome_norm -> lista de (partner_code, partner_name)
from collections import defaultdict
idx_dim = defaultdict(list)
for _, r in dim.iterrows():
    idx_dim[r['nome_norm']].append((r['partner_code'], r['partner_name']))

resolvidos = []
nao_resolvidos = []
for nf in faltantes:
    if nf in idx_dim:
        matches = idx_dim[nf]
        for code, name in matches:
            resolvidos.append({'nome_norm': nf, 'partner_code': code, 'partner_name': name})
    else:
        nao_resolvidos.append(nf)

print(f'Resolvidos via dim_partner: {len(resolvidos)} matches ({len(set(r["nome_norm"] for r in resolvidos))} nomes distintos)')
print(f'Não resolvidos (sem match exato no dim_partner): {len(nao_resolvidos)}')
if nao_resolvidos:
    print('Exemplos não-resolvidos (até 5):')
    for n in list(nao_resolvidos)[:5]:
        print(f'  - {n}')

# ── 5. Buscar carteira para esses partner_codes (qual rfv_familia eles têm?) ──
codes = sorted({r['partner_code'] for r in resolvidos})
if codes:
    codes_sql = ", ".join(f"'{c}'" for c in codes)
    sql_classif = f"""
    SELECT partner_code, partner_name, salesperson_name, rfv_familia, planilha_nome, is_active
    FROM `{PROJ}.silver_comercial.param_com_rfv_carteira`
    WHERE partner_code IN ({codes_sql})
    """
    classif = client.query(sql_classif).to_dataframe()
    print()
    print('=== Onde estão classificados na carteira BQ os clientes "faltantes":')
    print(classif.groupby(['rfv_familia', 'is_active'], dropna=False).size().reset_index(name='n').to_string())
    print()
    # Pega os que NÃO estão na carteira de jeito nenhum
    classif_codes = set(classif['partner_code'])
    sem_carteira = [c for c in codes if c not in classif_codes]
    print(f'Faltantes que NÃO aparecem em NENHUMA linha da carteira: {len(sem_carteira)}')

    # Salva detalhe
    out = pd.DataFrame(resolvidos).merge(classif, on='partner_code', how='left', suffixes=('','_b'))
    out_path = r'C:\Users\gusta\Downloads\hospitalar_108_faltantes_diag.xlsx'
    out.to_excel(out_path, index=False)
    print(f'>>> Salvo detalhado em: {out_path}')

    # Lista compacta de codigos pra próxima query
    with open(r'C:\Users\gusta\OneDrive\Documentos\Data-Lake\data_lake_nevoni\tmp_codes_faltantes.txt','w',encoding='utf-8') as f:
        f.write('\n'.join(codes))
    print(f'Códigos ERP salvos em tmp_codes_faltantes.txt ({len(codes)} códigos)')
