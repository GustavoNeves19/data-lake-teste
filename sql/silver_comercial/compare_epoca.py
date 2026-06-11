"""
Compara matriz RFV do BQ na mesma época da planilha Alves.

Problema: silver_com_rfv_score usa CURRENT_DATE() para recencia — nunca
comparamos os buckets F/R com a data de referência igual à da planilha.

Este script recalcula a matriz com ref_date = 2026-03-31 (fim do período
Hospitalar) e compara célula a célula com os números do Alves.

Executar: py -3 sql/silver_comercial/compare_epoca.py
"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import pandas as pd
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\teste\sapient-metrics.json'
from google.cloud import bigquery

client = bigquery.Client(project='sapient-metrics-492914-m7', location='us-east1')

REF_HOSP = '2026-03-31'
REF_FARM = '2026-02-28'

SQL = """
WITH base AS (
    SELECT
        partner_name,
        rfv_familia,
        rfv_salesperson,
        MAX(order_date)                                              AS ultima_compra,
        DATE_DIFF(DATE '{ref}', MAX(order_date), DAY)               AS recencia_dias,
        COUNT(DISTINCT order_number)                                 AS frequencia,
        ROUND(SUM(total_amount), 2)                                  AS valor_total,
        ROUND(SUM(CASE WHEN nature_code IN ('5101  A','6101  A')
                       THEN total_amount ELSE 0 END), 0)             AS valor_A
    FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_vendas`
    WHERE order_date <= DATE '{ref}'
      AND rfv_familia = '{familia}'
    GROUP BY partner_name, rfv_familia, rfv_salesperson
),
scored AS (
    SELECT b.*,
        CASE
            WHEN b.rfv_familia IN ('HOSPITALAR','SAC') THEN
                CASE WHEN b.frequencia >= 5 THEN 'F1'
                     WHEN b.frequencia  = 4 THEN 'F2'
                     WHEN b.frequencia  = 3 THEN 'F3'
                     WHEN b.frequencia  = 2 THEN 'F4'
                     ELSE 'F5' END
            ELSE
                CASE WHEN b.frequencia >= 7 THEN 'F1'
                     WHEN b.frequencia >= 5 THEN 'F2'
                     WHEN b.frequencia >= 3 THEN 'F3'
                     WHEN b.frequencia  = 2 THEN 'F4'
                     ELSE 'F5' END
        END AS freq_bucket,
        CASE
            WHEN b.rfv_familia IN ('HOSPITALAR','SAC') THEN
                CASE WHEN b.recencia_dias <=  30 THEN 'R1'
                     WHEN b.recencia_dias <=  60 THEN 'R2'
                     WHEN b.recencia_dias <=  90 THEN 'R3'
                     WHEN b.recencia_dias <  150 THEN 'R4'
                     ELSE 'R5' END
            ELSE
                CASE WHEN b.recencia_dias <=  30 THEN 'R1'
                     WHEN b.recencia_dias <=  60 THEN 'R2'
                     WHEN b.recencia_dias <= 120 THEN 'R3'
                     WHEN b.recencia_dias <= 180 THEN 'R4'
                     ELSE 'R5' END
        END AS rec_bucket
    FROM base b
),
segmented AS (
    SELECT s.*,
        CONCAT(freq_bucket, rec_bucket) AS fr,
        CASE CONCAT(freq_bucket, rec_bucket)
            WHEN 'F1R1' THEN 'DIAMANTE'   WHEN 'F1R2' THEN 'DIAMANTE'   WHEN 'F2R1' THEN 'DIAMANTE'
            WHEN 'F1R3' THEN 'OURO'       WHEN 'F2R2' THEN 'OURO'       WHEN 'F3R1' THEN 'OURO'
            WHEN 'F1R4' THEN 'PRATA'      WHEN 'F2R3' THEN 'PRATA'      WHEN 'F3R2' THEN 'PRATA'      WHEN 'F4R1' THEN 'PRATA'
            WHEN 'F3R3' THEN 'BRONZE'     WHEN 'F4R2' THEN 'BRONZE'     WHEN 'F4R3' THEN 'BRONZE'
            WHEN 'F5R1' THEN 'NOVO'       WHEN 'F5R2' THEN 'NOVO'
            WHEN 'F5R3' THEN 'POTENCIAL'  WHEN 'F5R4' THEN 'POTENCIAL'
            WHEN 'F2R4' THEN 'EM RISCO'   WHEN 'F3R4' THEN 'EM RISCO'   WHEN 'F4R4' THEN 'EM RISCO'
            WHEN 'F1R5' THEN 'ADORMECIDO' WHEN 'F2R5' THEN 'ADORMECIDO' WHEN 'F3R5' THEN 'ADORMECIDO' WHEN 'F4R5' THEN 'ADORMECIDO'
            WHEN 'F5R5' THEN 'PERDIDO'
            ELSE 'OUTROS'
        END AS segmento
    FROM scored s
)
SELECT freq_bucket, rec_bucket, fr, segmento,
       COUNT(DISTINCT partner_name)         AS clientes,
       ROUND(SUM(valor_A), 0)               AS fat_A
FROM segmented
GROUP BY freq_bucket, rec_bucket, fr, segmento
ORDER BY freq_bucket, rec_bucket
"""

# ── HOSPITALAR ────────────────────────────────────────────────────────────────
print('=' * 72)
print(f'HOSPITALAR — ref_date = {REF_HOSP}  (igual planilha Alves)')
print('=' * 72)

hosp = client.query(SQL.format(ref=REF_HOSP, familia='HOSPITALAR')).to_dataframe()

pivot_cli = hosp.pivot_table(index='freq_bucket', columns='rec_bucket',
                              values='clientes', fill_value=0, aggfunc='sum')
pivot_fat = hosp.pivot_table(index='freq_bucket', columns='rec_bucket',
                              values='fat_A', fill_value=0, aggfunc='sum')

print('\nClientes por célula F×R:')
print(pivot_cli.to_string())
print(f'\nTotal clientes: {hosp["clientes"].sum()}')
print(f'Total fat (A):  R$ {hosp["fat_A"].sum():,.0f}')

print('\nPor segmento:')
seg = hosp.groupby('segmento').agg(clientes=('clientes','sum'),
                                    fat_A=('fat_A','sum')).reset_index()
seg = seg.sort_values('clientes', ascending=False)
for _, r in seg.iterrows():
    print(f'  {r["segmento"]:<14}: {int(r["clientes"]):>4} clientes | R$ {r["fat_A"]:>12,.0f}')

print()
print('PLANILHA ALVES — Resultado Geral (635 clientes | R$ 7.645.854):')
planilha = {
    'F1R1 (Campeões)':       26,
    'F1R2 (Fiéis)':          20,
    'F1R4 (N-pode-perder)':   5,
    'F5R1 (Novos)':          40,
    'F5R2 (Promessas)':      32,
    'F5R4+R5 (Perdidos)':   341,
}
for k, v in planilha.items():
    print(f'  {k:<24}: {v}')

print()
print('COMPARAÇÃO célula a célula (BQ vs Planilha):')
comp = {
    'F1R1': 26, 'F1R2': 20, 'F1R4': 5,
    'F5R1': 40, 'F5R2': 32,
}
for fr, plan_val in comp.items():
    bq_row = hosp[hosp['fr'] == fr]
    bq_val = int(bq_row['clientes'].sum()) if len(bq_row) > 0 else 0
    delta = bq_val - plan_val
    flag = '✅' if abs(delta) <= 3 else ('⚠️' if abs(delta) <= 10 else '❌')
    print(f'  {fr}: BQ={bq_val:>3}  Planilha={plan_val:>3}  Δ={delta:+d}  {flag}')

# ── FARMÁCIAS ─────────────────────────────────────────────────────────────────
print()
print('=' * 72)
print(f'FARMÁCIAS — ref_date = {REF_FARM}')
print('=' * 72)

farm = client.query(SQL.format(ref=REF_FARM, familia='FARMACIAS')).to_dataframe()
pivot_f = farm.pivot_table(index='freq_bucket', columns='rec_bucket',
                            values='clientes', fill_value=0, aggfunc='sum')
print('\nClientes por célula F×R:')
print(pivot_f.to_string())
print(f'\nTotal clientes: {farm["clientes"].sum()}')
print(f'Total fat (A):  R$ {farm["fat_A"].sum():,.0f}')
