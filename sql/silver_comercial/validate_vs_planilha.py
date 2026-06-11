"""
Validação: silver_com_rfv_score no BQ vs planilha Alves.

Compara:
  - Contagem de clientes por família
  - Faturamento total e por natureza de operação
  - Distribuição de segmentos (F/R buckets)

Executar: py -3 sql/silver_comercial/validate_vs_planilha.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import glob
import pandas as pd
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\teste\sapient-metrics.json'
from google.cloud import bigquery

client = bigquery.Client(project='sapient-metrics-492914-m7', location='us-east1')

print("=" * 78)
print("VALIDAÇÃO: silver_comercial vs planilha Alves")
print("=" * 78)

# ── 1. Totais gerais ───────────────────────────────────────────────────────────
print("\n[1] TOTAIS GERAIS (rolling 13 meses)")
r = client.query("""
    SELECT rfv_familia,
           SUM(qtd_clientes)        AS clientes,
           ROUND(SUM(faturamento_total), 0) AS fat_total_amount
    FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_resumo`
    GROUP BY rfv_familia ORDER BY rfv_familia
""").to_dataframe()
print(r.to_string(index=False))

# Período fixo hospitalar (para comparação com planilha)
print("\n[2] HOSPITALAR — período FIXO 2025-03-01 a 2026-03-31 (igual planilha)")
r2 = client.query("""
    SELECT
        COUNT(DISTINCT partner_name)          AS clientes_dedup,
        ROUND(SUM(total_amount), 0)           AS fat_total_amount,
        ROUND(SUM(product_amount), 0)         AS fat_product_amount,
        -- Apenas CFOP 5101 e 6101 (sem substituição tributária)
        ROUND(SUM(CASE WHEN nature_code IN ('5101  A','6101  A') THEN total_amount ELSE 0 END), 0)
                                              AS fat_5101_6101_A,
        COUNT(*) AS pedidos
    FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_vendas`
    WHERE rfv_familia = 'HOSPITALAR'
      AND order_date BETWEEN '2025-03-01' AND '2026-03-31'
""").to_dataframe()
print(r2.to_string(index=False))
print()
print("  PLANILHA ALVES:  635 clientes | R$ 7.645.854 faturamento")
print(f"  BQ fat_5101_6101_A: compare com planilha (diferença esperada <5%)")

# ── 3. Distribuição F/R buckets ───────────────────────────────────────────────
print("\n[3] HOSPITALAR — distribuição F × R buckets (BQ)")
r3 = client.query("""
    SELECT freq_bucket, rec_bucket,
           COUNT(DISTINCT partner_name)   AS clientes,
           ROUND(SUM(valor_total), 0)     AS faturamento
    FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
    WHERE rfv_familia = 'HOSPITALAR'
    GROUP BY freq_bucket, rec_bucket
    ORDER BY freq_bucket, rec_bucket
""").to_dataframe()
# Pivotear para matriz F×R
pivot = r3.pivot_table(index='freq_bucket', columns='rec_bucket', values='clientes', fill_value=0)
print("Clientes por célula F×R:")
print(pivot.to_string())
print(f"TOTAL: {r3['clientes'].sum()} clientes (com duplicatas por vendedor)")

# De-duplicado
r4 = client.query("""
    SELECT
        COUNT(DISTINCT partner_name) AS clientes_geral
    FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
    WHERE rfv_familia = 'HOSPITALAR'
""").to_dataframe()
print(f"De-duplicado (Geral): {r4['clientes_geral'].iloc[0]} clientes")
print()
print("PLANILHA ALVES (Resultado Geral):")
print("  Campeoes (F1R1): 26  | Fieis (F1R2): 20  | Nao-pode-perder (F1R4): 5")
print("  Novos (F5R1): 40     | Promessas (F5R2): 32")
print("  Perdidos (F5R4+R5): 341")
print("  TOTAL: 635 clientes | R$ 7.645.854")

# ── 4. Segmentos BQ vs planilha ───────────────────────────────────────────────
print("\n[4] HOSPITALAR — segmentos BQ (de-duplicado por nome)")
r5 = client.query("""
    SELECT classificacao_2 AS segmento, classificacao_3 AS seg_num,
           COUNT(DISTINCT partner_name)   AS clientes,
           ROUND(SUM(valor_total), 0)     AS faturamento
    FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
    WHERE rfv_familia = 'HOSPITALAR'
    GROUP BY classificacao_2, classificacao_3
    ORDER BY classificacao_3
""").to_dataframe()
print(r5.to_string(index=False))
print(f"TOTAL: {r5['clientes'].sum()} clientes (inclui dupl. por vendedor)")

print()
print("=" * 78)
print("NOTA: Diferenças esperadas vs planilha:")
print("  1. Período: BQ usa mesma data de início (Mar/25 Hosp, Fev/25 Farm) mas estende até hoje")
print("     → faturamento BQ > planilha em ~3% por incluir Abr-Mai/2026")
print("  2. Faturamento: BQ inclui ST (sufixo K) — planilha usa apenas A (5101/6101)")
print("  3. Recência: BQ calcula vs CURRENT_DATE() (estado atual) — planilha vs Mar/2026")
print("     → buckets R1/R2 diferem mas reflete realidade de hoje")
print("  4. Filiais: LOCMED 9 códigos = 9 pedidos distintos no BQ vs 1 na planilha")
print("  5. 12 clientes rejeitados no populate_carteira (joalheria/relógio)")
print("=" * 78)
