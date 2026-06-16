"""
v2 — matching tolerante para localizar partner_code dos 82 clientes faltantes.

Estratégia:
  1. Normalização agressiva: remove pontuação, sufixos (LTDA, ME, EIRELI, EPP, SA),
     CNPJ-prefix numérico (xx.xxx.xxx/xxxx-xx).
  2. Match exato com nome normalizado em dim_partner E carteira completa.
  3. Para os que falharem, tentar match por "primeira palavra significativa".
  4. Salvar Excel com: nome_planilha | partner_code | partner_name_dim | rfv_familia | ativo | faturamento_abril
"""
import io, os, sys, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')

import pandas as pd
from google.cloud import bigquery
from collections import defaultdict

PROJ = 'sapient-metrics-492914-m7'
client = bigquery.Client(project=PROJ, location='us-east1')

SUFIXOS = re.compile(
    r'\b('
    r'LTDA|LTDA\.|EIRELI|ME|EPP|S/?A|SA|S\.?A\.?|HOSPITAL|EQUIPAMENTOS|HOSPITALAR(?:ES)?|'
    r'COMERCIO|COM|INDUSTRIA|IND|CIA|& CIA|DA|DE|DO|DOS|DAS|E|EM|PARA'
    r')\b', re.IGNORECASE
)
PREFIX_CNPJ = re.compile(r'^\s*[\d\.\-/]+\s+')

def norm(s):
    if s is None or pd.isna(s): return ''
    s = str(s).upper().strip()
    s = ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')
    s = re.sub(r'\s+', ' ', s)
    return s

def norm_hard(s):
    """normalização agressiva — remove sufixos, pontuação, CNPJ no início."""
    s = norm(s)
    s = PREFIX_CNPJ.sub('', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    s = SUFIXOS.sub(' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ── 1. Planilha Alves ────────────────────────────────────────────────────────
xlsx = r'C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026.xlsx'
plan = pd.read_excel(xlsx, sheet_name='Sem fórmula Geral')
plan['nome_norm'] = plan['ID - CLIENTE'].apply(norm)
plan['nome_hard'] = plan['ID - CLIENTE'].apply(norm_hard)

# ── 2. Carteira HOSPITALAR ativa ─────────────────────────────────────────────
sql_cart_hosp = f"""
SELECT partner_code, partner_name
FROM `{PROJ}.silver_comercial.param_com_rfv_carteira`
WHERE is_active = TRUE AND rfv_familia = 'HOSPITALAR'
"""
cart = client.query(sql_cart_hosp).to_dataframe()
cart['nome_norm'] = cart['partner_name'].apply(norm)
nomes_cart = set(cart['nome_norm'])

faltantes = plan[~plan['nome_norm'].isin(nomes_cart)].copy()
print(f'Total planilha Alves: {len(plan)}')
print(f'Total carteira BQ HOSPITALAR ativa: {len(cart)}')
print(f'Faltantes (planilha mas não em HOSPITALAR-ativo): {len(faltantes)}')

# ── 3. dim_partner inteiro ───────────────────────────────────────────────────
sql_dim = f"""
SELECT partner_code, partner_name, legal_name, tax_id, city, state, status, is_active
FROM `{PROJ}.dm_partners.dim_partner`
"""
dim = client.query(sql_dim).to_dataframe()
dim['nome_norm'] = dim['partner_name'].apply(norm)
dim['legal_norm'] = dim['legal_name'].apply(norm)
dim['nome_hard'] = dim['partner_name'].apply(norm_hard)
dim['legal_hard'] = dim['legal_name'].apply(norm_hard)
print(f'dim_partner: {len(dim)} linhas')

# índices
ix_nome_exact = defaultdict(list)
ix_legal_exact = defaultdict(list)
ix_nome_hard = defaultdict(list)
for _, r in dim.iterrows():
    ix_nome_exact[r['nome_norm']].append(r['partner_code'])
    ix_legal_exact[r['legal_norm']].append(r['partner_code'])
    ix_nome_hard[r['nome_hard']].append(r['partner_code'])

# ── 4. Resolver os faltantes ─────────────────────────────────────────────────
def resolve(row):
    candidatos = []
    n_exact, n_hard = row['nome_norm'], row['nome_hard']
    if n_exact in ix_nome_exact:
        candidatos = ix_nome_exact[n_exact]
    elif n_exact in ix_legal_exact:
        candidatos = ix_legal_exact[n_exact]
    elif n_hard and n_hard in ix_nome_hard:
        candidatos = ix_nome_hard[n_hard]
    return candidatos

faltantes['matches'] = faltantes.apply(resolve, axis=1)
faltantes['n_matches'] = faltantes['matches'].apply(len)

resolvidos = faltantes[faltantes['n_matches'] > 0].copy()
nao_res    = faltantes[faltantes['n_matches'] == 0].copy()
print(f'Resolvidos (>=1 match): {len(resolvidos)}')
print(f'Não resolvidos:         {len(nao_res)}')

# Expandir os multi-match
rows = []
for _, r in resolvidos.iterrows():
    for code in r['matches']:
        rows.append({'planilha_nome': r['ID - CLIENTE'], 'partner_code': code,
                     'n_matches': r['n_matches']})
df_resolved = pd.DataFrame(rows)

# ── 5. Olhar classificação atual desses partner_code na carteira ─────────────
codes = sorted(df_resolved['partner_code'].unique().tolist())
print(f'Partner_codes únicos resolvidos: {len(codes)}')

if codes:
    codes_sql = ", ".join(str(int(c)) for c in codes)
    sql_classif = f"""
    SELECT partner_code, partner_name AS cart_name, salesperson_name,
           rfv_familia, planilha_nome AS cart_planilha, is_active
    FROM `{PROJ}.silver_comercial.param_com_rfv_carteira`
    WHERE partner_code IN ({codes_sql})
    """
    classif = client.query(sql_classif).to_dataframe()
    print()
    print('=== Onde estão na carteira atual (rfv_familia × is_active):')
    print(classif.groupby(['rfv_familia','is_active'], dropna=False).size()
                 .reset_index(name='n').to_string())

    # 6. Faturamento por esses codes em abril/2026 (todas naturezas)
    sql_fat = f"""
    SELECT o.partner_code, o.nature_code, n.financial_flag, n.nature_name,
           COUNT(DISTINCT o.order_number) AS pedidos,
           ROUND(SUM(o.total_amount),2)   AS faturamento
    FROM `{PROJ}.dm_orders.fact_sales_order` o
    LEFT JOIN `{PROJ}.dm_orders.dim_operation_nature` n
        ON n.nature_code = o.nature_code
    WHERE o.partner_code IN ({codes_sql})
      AND o.order_status IN (3, 4)
      AND o.order_date >= DATE '2025-04-01'
      AND o.order_date <= DATE '2026-04-30'
    GROUP BY o.partner_code, o.nature_code, n.financial_flag, n.nature_name
    """
    fat = client.query(sql_fat).to_dataframe()
    print()
    print(f'Pedidos encontrados no BQ para os codes resolvidos: {len(fat)} linhas')
    print(f'Faturamento total (todas naturezas):   R$ {fat["faturamento"].sum():>14,.2f}')
    if not fat.empty:
        ok = fat[fat['financial_flag'] != 'N']
        nn = fat[fat['financial_flag'] == 'N']
        print(f'  - faturamento <> N (conta hoje):   R$ {ok["faturamento"].sum():>14,.2f}')
        print(f'  - faturamento  = N (não conta):    R$ {nn["faturamento"].sum():>14,.2f}')

    # Output Excel
    out_path = r'C:\Users\gusta\Downloads\hospitalar_faltantes_diag.xlsx'
    with pd.ExcelWriter(out_path) as w:
        df_resolved.merge(
            dim[['partner_code','partner_name','legal_name','tax_id','city','state','status']],
            on='partner_code', how='left'
        ).merge(classif, on='partner_code', how='left').to_excel(w, 'Resolvidos', index=False)
        nao_res[['ID - CLIENTE']].rename(columns={'ID - CLIENTE':'nome_planilha'}).to_excel(w, 'Nao_resolvidos', index=False)
        if not fat.empty:
            fat.to_excel(w, 'Faturamento_por_natureza', index=False)
    print(f'>>> Excel salvo: {out_path}')

    # Lista CSV de partner_code pra próxima query SSM
    with open(r'C:\Users\gusta\OneDrive\Documentos\Data-Lake\data_lake_nevoni\tmp_codes_faltantes.txt','w',encoding='utf-8') as f:
        f.write(','.join(str(int(c)) for c in codes))
    print(f'Códigos ERP em tmp_codes_faltantes.txt: {len(codes)} codes')
