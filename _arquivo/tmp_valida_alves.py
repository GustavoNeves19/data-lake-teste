"""
Validação RFV HOSPITALAR para reunião com Hugo Alves.
Gera dois arquivos Excel:
  1. rfv_hospitalar_ativos.xlsx  — 585 clientes com score RFV
  2. rfv_hospitalar_fora_janela.xlsx — clientes na carteira sem compra nos últimos 13 meses

Executar: py -3 tmp_valida_alves.py
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    r"C:\teste\sapient-metrics.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = bigquery.Client(credentials=creds, project="sapient-metrics-492914-m7")
proj = "sapient-metrics-492914-m7"

OUT = Path(r"C:\Users\gusta\Downloads")

# ── 1. Clientes ativos no RFV (últimos 13 meses, status 3/4) ──────────────────
print("Buscando clientes ativos no RFV...")
sql_ativos = f"""
SELECT
  s.partner_name                          AS Cliente,
  s.rfv_salesperson                       AS Vendedor,
  s.classificacao_2                       AS Segmento,
  s.freq_bucket                           AS Frequencia_Bucket,
  s.rec_bucket                            AS Recencia_Bucket,
  s.frequencia                            AS Qtd_Pedidos,
  s.recencia_dias                         AS Dias_Ultima_Compra,
  s.ultima_compra_data                    AS Ultima_Compra,
  ROUND(s.valor_total, 2)                 AS Faturamento_13m
FROM `{proj}.silver_comercial.silver_com_rfv_score` s
WHERE s.rfv_familia = 'HOSPITALAR'
ORDER BY s.classificacao_3, s.valor_total DESC
"""
df_ativos = client.query(sql_ativos).to_dataframe()
print(f"  Ativos: {len(df_ativos)} clientes")

# ── 2. Clientes na carteira SEM compra nos últimos 13 meses ───────────────────
print("Buscando clientes fora da janela 13m...")
sql_fora = f"""
SELECT
  c.partner_name                          AS Cliente,
  c.salesperson_name                      AS Vendedor,
  MAX(o.order_date)                       AS Ultima_Compra_Historica,
  DATE_DIFF(CURRENT_DATE(), MAX(o.order_date), DAY) AS Dias_Sem_Comprar,
  ROUND(SUM(o.total_amount), 2)           AS Faturamento_Historico_Total,
  COUNT(DISTINCT o.order_number)          AS Total_Pedidos_Historico
FROM `{proj}.silver_comercial.param_com_rfv_carteira` c
-- todos os pedidos históricos (sem filtro de data)
LEFT JOIN `{proj}.dm_orders.fact_sales_order` o
  ON  o.partner_code  = c.partner_code
  AND o.order_status IN (3, 4)
-- join com dim_operation_nature para pegar só vendas financeiras
LEFT JOIN `{proj}.dm_orders.dim_operation_nature` n
  ON  n.nature_code    = o.nature_code
  AND n.financial_flag = 'F'
WHERE c.rfv_familia = 'HOSPITALAR'
  AND c.is_active   = TRUE
  -- excluir quem já está no RFV ativo
  AND c.partner_name NOT IN (
    SELECT partner_name
    FROM `{proj}.silver_comercial.silver_com_rfv_score`
    WHERE rfv_familia = 'HOSPITALAR'
  )
GROUP BY c.partner_name, c.salesperson_name
ORDER BY Faturamento_Historico_Total DESC NULLS LAST
"""
df_fora = client.query(sql_fora).to_dataframe()
print(f"  Fora da janela: {len(df_fora)} clientes")

# ── 3. Exportar Excel ─────────────────────────────────────────────────────────
seg_order = [
    'Campeões','Fiéis','Fiéis em potencial','Novos clientes','Promessas',
    'Precisando de atenção','Quase dormentes','Não pode perder',
    'Em risco','Hibernando','Perdidos'
]

path_ativos = OUT / "rfv_hospitalar_ativos.xlsx"
path_fora   = OUT / "rfv_hospitalar_fora_janela.xlsx"

with pd.ExcelWriter(path_ativos, engine='openpyxl') as writer:
    # Aba resumo por segmento
    resumo = (
        df_ativos
        .groupby('Segmento', sort=False)
        .agg(
            Clientes=('Cliente', 'count'),
            Faturamento_13m=('Faturamento_13m', 'sum'),
            Dias_Medio_Sem_Comprar=('Dias_Ultima_Compra', 'mean'),
        )
        .reset_index()
    )
    resumo['Segmento'] = pd.Categorical(resumo['Segmento'], categories=seg_order, ordered=True)
    resumo = resumo.sort_values('Segmento')
    resumo['Faturamento_13m'] = resumo['Faturamento_13m'].round(2)
    resumo['Dias_Medio_Sem_Comprar'] = resumo['Dias_Medio_Sem_Comprar'].round(0).astype(int)
    resumo.to_excel(writer, sheet_name='Resumo por Segmento', index=False)

    # Aba detalhe completo
    df_ativos.to_excel(writer, sheet_name='Clientes Ativos (585)', index=False)

with pd.ExcelWriter(path_fora, engine='openpyxl') as writer:
    df_fora.to_excel(writer, sheet_name='Fora da Janela 13m', index=False)

print()
print("=" * 60)
print(f"HOSPITALAR ativos (RFV):     {len(df_ativos):4d} clientes")
print(f"HOSPITALAR fora da janela:   {len(df_fora):4d} clientes")
print(f"Total na carteira:           {len(df_ativos)+len(df_fora):4d} clientes")
print()
print(f"Arquivos salvos em:")
print(f"  {path_ativos}")
print(f"  {path_fora}")
print("=" * 60)

# Prévia dos fora da janela (top 10 por faturamento histórico)
print()
print("Top 10 fora da janela por faturamento histórico:")
print(df_fora[['Cliente','Vendedor','Ultima_Compra_Historica','Dias_Sem_Comprar','Faturamento_Historico_Total']].head(10).to_string(index=False))
