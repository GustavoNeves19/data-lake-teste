"""Comparativo Excel Alves vs Sistema (regras corrigidas) para abril/2026."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

excel = {
    'HOSPITALAR': {
        'segmentos': {
            'Campeoes': (80, 5433495),
            'Fieis': (47, 913016),
            'Fieis em potencial': (112, 737901),
            'Novos clientes': (38, 90329),
            'Promessas': (28, 65556),
            'Precisando de atencao': (6, 34105),
            'Quase dormentes': (63, 279801),
            'Nao pode perder': (11, 332501),
            'Em risco': (21, 152625),
            'Hibernando': (41, 256045),
            'Perdidos': (339, 908599),
        },
        'total_cli': 786, 'total_fat': 9203974,
    },
    'FARMACIAS': {
        'segmentos': {
            'Campeoes': (0, 0), 'Fieis': (0, 0), 'Fieis em potencial': (0, 0),
            'Novos clientes': (0, 0), 'Promessas': (0, 0), 'Precisando de atencao': (0, 0),
            'Quase dormentes': (0, 0), 'Nao pode perder': (5, 23896),
            'Em risco': (31, 96340), 'Hibernando': (21, 23562), 'Perdidos': (191, 231345),
        },
        'total_cli': 248, 'total_fat': 375144,
    },
    'SAC': {
        'segmentos': {
            'Campeoes': (0, 0), 'Fieis': (0, 0), 'Fieis em potencial': (1, 630),
            'Novos clientes': (0, 0), 'Promessas': (3, 613), 'Precisando de atencao': (0, 0),
            'Quase dormentes': (8, 4664), 'Nao pode perder': (4, 102914),
            'Em risco': (4, 26242), 'Hibernando': (4, 47362), 'Perdidos': (55, 38755),
        },
        'total_cli': 79, 'total_fat': 221180,
    },
}

# Mapa para casar acentos do BQ com a chave sem acento
NORM = {
    'Campeões': 'Campeoes', 'Fiéis': 'Fieis', 'Fiéis em potencial': 'Fieis em potencial',
    'Novos clientes': 'Novos clientes', 'Promessas': 'Promessas',
    'Precisando de atenção': 'Precisando de atencao', 'Quase dormentes': 'Quase dormentes',
    'Não pode perder': 'Nao pode perder', 'Em risco': 'Em risco',
    'Hibernando': 'Hibernando', 'Perdidos': 'Perdidos',
}

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

data_ref = '2026-04-30'
sql = f"""
WITH vendas AS (
  SELECT c.partner_name, c.rfv_familia, o.order_number, o.order_date, o.total_amount
  FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
  JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` c
    ON c.partner_code = o.partner_code AND c.is_active = TRUE
    AND c.salesperson_name NOT IN ('Eduardo', 'Karina')
  JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
    ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
  WHERE o.order_status IN (3,4)
    AND o.order_date BETWEEN '2025-04-01' AND DATE('{data_ref}')
),
base AS (
  SELECT partner_name, rfv_familia,
         DATE_DIFF(DATE('{data_ref}'), MAX(order_date), DAY) AS recencia,
         COUNT(DISTINCT order_number) AS freq,
         SUM(total_amount) AS valor
  FROM vendas GROUP BY 1,2
),
score AS (
  SELECT *,
    CASE WHEN rfv_familia='FARMACIAS' THEN
      CASE WHEN freq>=7 THEN 'F1' WHEN freq>=5 THEN 'F2' WHEN freq>=3 THEN 'F3' WHEN freq=2 THEN 'F4' ELSE 'F5' END
    ELSE
      CASE WHEN freq>=5 THEN 'F1' WHEN freq=4 THEN 'F2' WHEN freq=3 THEN 'F3' WHEN freq=2 THEN 'F4' ELSE 'F5' END
    END AS fb,
    CASE WHEN recencia<=30 THEN 'R1' WHEN recencia<=60 THEN 'R2' WHEN recencia<=120 THEN 'R3'
         WHEN recencia<=180 THEN 'R4' ELSE 'R5' END AS rb
  FROM base
)
SELECT rfv_familia,
  CASE CONCAT(fb,rb)
    WHEN 'F1R1' THEN 'Campeoes'
    WHEN 'F1R2' THEN 'Fieis' WHEN 'F1R3' THEN 'Fieis'
    WHEN 'F1R4' THEN 'Nao pode perder' WHEN 'F1R5' THEN 'Nao pode perder'
    WHEN 'F2R1' THEN 'Fieis' WHEN 'F2R2' THEN 'Fieis' WHEN 'F2R3' THEN 'Fieis'
    WHEN 'F2R4' THEN 'Em risco' WHEN 'F2R5' THEN 'Em risco'
    WHEN 'F3R1' THEN 'Fieis em potencial' WHEN 'F3R2' THEN 'Fieis em potencial'
    WHEN 'F3R3' THEN 'Precisando de atencao'
    WHEN 'F3R4' THEN 'Em risco' WHEN 'F3R5' THEN 'Em risco'
    WHEN 'F4R1' THEN 'Fieis em potencial' WHEN 'F4R2' THEN 'Fieis em potencial'
    WHEN 'F4R3' THEN 'Quase dormentes'
    WHEN 'F4R4' THEN 'Hibernando' WHEN 'F4R5' THEN 'Perdidos'
    WHEN 'F5R1' THEN 'Novos clientes' WHEN 'F5R2' THEN 'Promessas'
    WHEN 'F5R3' THEN 'Quase dormentes' WHEN 'F5R4' THEN 'Perdidos' WHEN 'F5R5' THEN 'Perdidos'
  END AS segmento,
  COUNT(DISTINCT partner_name) AS clientes,
  ROUND(SUM(valor),0) AS faturamento
FROM score
GROUP BY 1, 2
"""
df_sis = client.query(sql).to_dataframe()

ORDEM = ['Campeoes','Fieis','Fieis em potencial','Novos clientes','Promessas',
         'Precisando de atencao','Quase dormentes','Nao pode perder','Em risco','Hibernando','Perdidos']

print('=' * 110)
print('COMPARATIVO: PLANILHAS ALVES (30/04/2026)  x  SISTEMA NOVO (regras corrigidas, mesmo periodo)')
print('=' * 110)

for fam in ['HOSPITALAR','FARMACIAS','SAC']:
    print()
    print(f'--- {fam} ---')
    e = excel[fam]
    sis_fam = df_sis[df_sis['rfv_familia']==fam].set_index('segmento')

    linhas = []
    for seg in ORDEM:
        ex_cli, ex_fat = e['segmentos'].get(seg, (0, 0))
        sis_cli = int(sis_fam.loc[seg, 'clientes']) if seg in sis_fam.index else 0
        sis_fat = int(sis_fam.loc[seg, 'faturamento']) if seg in sis_fam.index else 0
        linhas.append({
            'segmento': seg,
            'EXCEL_cli': ex_cli, 'SIS_cli': sis_cli, 'D_cli': sis_cli - ex_cli,
            'EXCEL_fat': ex_fat, 'SIS_fat': sis_fat, 'D_fat': sis_fat - ex_fat,
        })
    df = pd.DataFrame(linhas)
    print(df.to_string(index=False))

    ex_t_cli = e['total_cli']
    ex_t_fat = e['total_fat']
    sis_t_cli = int(sis_fam['clientes'].sum())
    sis_t_fat = int(sis_fam['faturamento'].sum())
    print(f'TOTAL: EXCEL = {ex_t_cli} cli / R$ {ex_t_fat:,.0f}   |   SISTEMA = {sis_t_cli} cli / R$ {sis_t_fat:,.0f}')
    pct = (sis_t_fat - ex_t_fat) / max(ex_t_fat, 1) * 100
    print(f'  Delta clientes: {sis_t_cli - ex_t_cli:+d}   Delta faturamento: R$ {sis_t_fat - ex_t_fat:+,.0f} ({pct:+.1f}%)')

print()
print('--- GERAL (3 familias) ---')
ex_g_cli = sum(excel[f]['total_cli'] for f in excel)
ex_g_fat = sum(excel[f]['total_fat'] for f in excel)
sis_g_cli = int(df_sis['clientes'].sum())
sis_g_fat = int(df_sis['faturamento'].sum())
print(f'EXCEL ALVES TOTAL:  {ex_g_cli} clientes  /  R$ {ex_g_fat:,.0f}')
print(f'SISTEMA NOVO TOTAL: {sis_g_cli} clientes  /  R$ {sis_g_fat:,.0f}')
print(f'Delta: {sis_g_cli - ex_g_cli:+d} clientes  /  R$ {sis_g_fat - ex_g_fat:+,.0f} ({(sis_g_fat-ex_g_fat)/ex_g_fat*100:+.1f}%)')
