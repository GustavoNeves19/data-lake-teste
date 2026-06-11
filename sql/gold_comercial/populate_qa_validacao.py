"""Popula gold_qa_validacao com a cascata Nevoni → ERP → BQ → Dash.

Para cada (data_referencia, escopo, metrica):
  1. Lê valor_nevoni (planilha do gestor — hard-coded por mês)
  2. Consulta valor_erp no NSR_ERP (regra canônica validada)
  3. Consulta valor_bq no silver_com_rfv_base
  4. Calcula deltas + status

Roda: py -3 sql/gold_comercial/populate_qa_validacao.py
"""
import io, sys, os
from datetime import datetime, date
from decimal import Decimal
import pandas as pd, pyodbc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.settings import SQL_SERVER_CONFIG
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\teste\sapient-metrics.json'
from google.cloud import bigquery

PROJ = 'sapient-metrics-492914-m7'
bq = bigquery.Client(project=PROJ, location='us-east1')

# ─── Conexão ERP ────────────────────────────────────────────────────────────
cfg = SQL_SERVER_CONFIG
cn = pyodbc.connect(
    f"DRIVER={{{cfg['driver']}}};SERVER={cfg['server']},{cfg['port']};"
    f"DATABASE={cfg['database']};UID={cfg['uid']};PWD={cfg['pwd']};"
    "TrustServerCertificate=yes;Connection Timeout=30;", readonly=True)


# ─── Planilha Nevoni (referência declarada pelo gestor) ──────────────────────
NEVONI_DECLARADO = {
    date(2026, 4, 30): {
        'fonte': 'Planilha Alves RFV Abr/2026 (GERAL filtrado ≤30/04, Hosp 3 vend A/B/C)',
        'janela_ini': '2025-04-01',
        'janela_fim': '2026-04-30',
        'metricas': {
            ('GERAL',      'faturamento'): 10337881.66,   # RFV GERAL.xlsx filtrado ≤30/04/2026
            ('GERAL',      'clientes'):    2075,
            ('GERAL',      'notas'):       4203,
            ('HOSPITALAR', 'faturamento'):  7838472.03,
            ('HOSPITALAR', 'clientes'):     725,
            ('HOSPITALAR', 'notas'):       1613,
            ('FARMACIAS',  'faturamento'):   375144.09,
            ('FARMACIAS',  'clientes'):     248,
            ('FARMACIAS',  'notas'):        584,
            ('SAC',        'faturamento'):   195228.79,
            ('SAC',        'clientes'):      76,
            ('SAC',        'notas'):        145,
        }
    },
    date(2026, 5, 31): {
        'fonte': 'Planilha Alves RFV Mai/2026 entregue 02/06/2026',
        'janela_ini': '2025-05-01',
        'janela_fim': '2026-05-31',
        'metricas': {
            ('GERAL',      'faturamento'): 10095887.48,
            ('GERAL',      'clientes'):    1565,
            ('GERAL',      'notas'):       3480,
            ('HOSPITALAR', 'faturamento'):  8003224.61,
            ('HOSPITALAR', 'clientes'):     616,
            ('HOSPITALAR', 'notas'):       1865,
            ('FARMACIAS',  'faturamento'):   397546.70,
            ('FARMACIAS',  'clientes'):     332,
            ('FARMACIAS',  'notas'):        615,
            ('SAC',        'faturamento'):   189593.63,
            ('SAC',        'clientes'):      73,
            ('SAC',        'notas'):        143,
        }
    }
}

# ─── Filtro canônico ERP (regra final validada 02/06/2026) ─────────────────
# Δ -0,001% vs planilha Alves (R$ 113 residual = encoding/arredondamento)
QUERY_ERP_REF = 'queries_dashboard_vendas_mai2026.sql + sem YDATEXC + sem SITE-LOJA'

def erp_query(janela_ini, janela_fim, grupo_filter=None):
    """grupo_filter=None  → soma todos (FA+FR+PC)
                  ='FA'    → só Hospitalar
                  ='FR'    → só Farmácias
                  ='PC'    → só SAC
    """
    grupo_clause = f"AND c.YGRUVEN IN ('FA','FR','PC')" if grupo_filter is None \
                   else f"AND c.YGRUVEN = '{grupo_filter}'"
    sql = f"""
    SELECT
        COUNT(*)                                                 AS notas,
        COUNT(DISTINCT UPPER(LTRIM(RTRIM(cli.YNOMCLI))))         AS clientes,
        SUM(a.yValPro)                                           AS faturamento
    FROM [COMPRAS E VENDAS] a
    LEFT JOIN [NATUREZAS DE OPERAÇÕES]   b   ON a.yCodNat=b.yCodNat
    LEFT JOIN [ATENDENTES]               c   ON a.yCodVen2=c.yCodVen
    LEFT JOIN [CLIENTES OU FORNECEDORES] cli ON cli.YCODCLI=a.YCODCLI
    WHERE a.yTipOpe='S' AND b.yFinNat<>'N'
      AND a.yCodVen <> '000054'                          -- exclui SITE-LOJA
      {grupo_clause}
      AND a.yDatNot BETWEEN '{janela_ini}' AND '{janela_fim}'
    """
    return pd.read_sql(sql, cn).iloc[0]


# ─── Consulta BQ silver_com_rfv_base por escopo ────────────────────────────
def bq_query(data_ref, escopo):
    fam_filter = '' if escopo == 'GERAL' else f"AND rfv_familia = '{escopo}'"
    # Regra Alves (confirmada 05/06/2026): Eduardo Marques só entra no GERAL,
    # NÃO no detalhamento das carteiras (Hospitalar/Farmácia/SAC).
    eduardo_filter = '' if escopo == 'GERAL' else "AND rfv_salesperson NOT LIKE 'Eduardo%'"
    sql = f"""
    SELECT
        SUM(frequencia)              AS notas,
        COUNT(DISTINCT partner_name) AS clientes,
        SUM(valor_total)             AS faturamento
    FROM `{PROJ}.silver_comercial.silver_com_rfv_base`
    WHERE data_referencia = DATE('{data_ref}')
      {fam_filter}
      {eduardo_filter}
    """
    df = bq.query(sql).to_dataframe()
    if df.empty:
        return {'notas': 0, 'clientes': 0, 'faturamento': 0}
    return df.iloc[0].to_dict()


# ─── Status ─────────────────────────────────────────────────────────────────
def calc_status(pct_abs):
    if pct_abs < 1.0:    return 'VERDE'
    if pct_abs < 3.0:    return 'AMARELO'
    return 'VERMELHO'


# ─── Populate ───────────────────────────────────────────────────────────────
print('═' * 80)
print('  POPULATE gold_qa_validacao')
print('═' * 80)

grupo_map = {'GERAL': None, 'HOSPITALAR': 'FA', 'FARMACIAS': 'FR', 'SAC': 'PC'}
linhas = []

for data_ref, cfg_ref in NEVONI_DECLARADO.items():
    janela_ini, janela_fim = cfg_ref['janela_ini'], cfg_ref['janela_fim']
    print(f'\n  → data_referencia={data_ref}  janela {janela_ini}→{janela_fim}')

    for escopo in ['GERAL','HOSPITALAR','FARMACIAS','SAC']:
        erp = erp_query(janela_ini, janela_fim, grupo_map[escopo])
        bq_r = bq_query(data_ref, escopo)

        for metrica in ['faturamento','clientes','notas']:
            v_nev = float(cfg_ref['metricas'].get((escopo, metrica)) or 0)
            v_erp = float(erp[metrica] or 0)
            v_bq  = float(bq_r[metrica] or 0)
            d_en  = v_erp - v_nev
            d_be  = v_bq  - v_erp
            d_total_pct = ((v_bq - v_nev) / v_nev * 100) if v_nev else 0
            status = calc_status(abs(d_total_pct))

            D = lambda x: Decimal(str(round(x, 4)))
            linha = dict(
                data_referencia=data_ref, escopo=escopo, metrica=metrica,
                valor_nevoni=D(v_nev), fonte_nevoni=cfg_ref['fonte'],
                valor_erp=D(v_erp), query_erp_ref=QUERY_ERP_REF,
                delta_erp_nevoni=D(d_en),
                pct_erp_nevoni=D((d_en/v_nev*100) if v_nev else 0),
                valor_bq=D(v_bq), tabela_bq_ref=f'silver_com_rfv_base@{data_ref}',
                delta_bq_erp=D(d_be),
                pct_bq_erp=D((d_be/v_erp*100) if v_erp else 0),
                status=status, delta_total_pct=D(d_total_pct),
                validado_em=datetime.utcnow(),
                observacao='Regra: sem YDATEXC, sem SITE-LOJA (000054)',
            )
            linhas.append(linha)
            print(f'    {escopo:<11} {metrica:<12} '
                  f'Nev {v_nev:>12,.2f} | ERP {v_erp:>12,.2f} | BQ {v_bq:>12,.2f} | '
                  f'Δtot {d_total_pct:+6.2f}%  [{status}]')

cn.close()

# ─── Carrega no BQ via DELETE+INSERT por data_referencia ────────────────────
print(f'\n  → Carregando {len(linhas)} linhas no BQ...')
df = pd.DataFrame(linhas)
df['data_referencia'] = pd.to_datetime(df['data_referencia']).dt.date

# Delete antes pra evitar duplicar em re-run
periodos = ", ".join(f"DATE '{p}'" for p in df['data_referencia'].unique())
del_sql = f"""
DELETE FROM `{PROJ}.gold_comercial.gold_qa_validacao`
WHERE data_referencia IN ({periodos})
"""
bq.query(del_sql).result()

# Insert via load_table_from_dataframe
job_config = bigquery.LoadJobConfig(
    write_disposition='WRITE_APPEND',
    schema=[
        bigquery.SchemaField('data_referencia','DATE', mode='REQUIRED'),
        bigquery.SchemaField('escopo','STRING', mode='REQUIRED'),
        bigquery.SchemaField('metrica','STRING', mode='REQUIRED'),
        bigquery.SchemaField('valor_nevoni','NUMERIC'),
        bigquery.SchemaField('fonte_nevoni','STRING'),
        bigquery.SchemaField('valor_erp','NUMERIC'),
        bigquery.SchemaField('query_erp_ref','STRING'),
        bigquery.SchemaField('delta_erp_nevoni','NUMERIC'),
        bigquery.SchemaField('pct_erp_nevoni','NUMERIC'),
        bigquery.SchemaField('valor_bq','NUMERIC'),
        bigquery.SchemaField('tabela_bq_ref','STRING'),
        bigquery.SchemaField('delta_bq_erp','NUMERIC'),
        bigquery.SchemaField('pct_bq_erp','NUMERIC'),
        bigquery.SchemaField('status','STRING', mode='REQUIRED'),
        bigquery.SchemaField('delta_total_pct','NUMERIC'),
        bigquery.SchemaField('validado_em','TIMESTAMP', mode='REQUIRED'),
        bigquery.SchemaField('observacao','STRING'),
    ],
)
job = bq.load_table_from_dataframe(df, f'{PROJ}.gold_comercial.gold_qa_validacao', job_config=job_config)
job.result()
print(f'  OK: {len(df)} linhas inseridas')

# Sumário final
print('\n' + '═' * 80)
print('  RESUMO POR ESCOPO (faturamento)')
print('═' * 80)
fat = df[df['metrica'] == 'faturamento']
print(f'  {"escopo":<14} {"Nevoni":>14} {"ERP":>14} {"BQ":>14} {"Δ total":>9} {"status":>10}')
print('  ' + '─' * 75)
for _, r in fat.iterrows():
    print(f'  {r["escopo"]:<14} {float(r["valor_nevoni"]):>14,.2f} '
          f'{float(r["valor_erp"]):>14,.2f} {float(r["valor_bq"]):>14,.2f} '
          f'{float(r["delta_total_pct"]):>+8.2f}% {r["status"]:>10}')
print('\nFim.')
