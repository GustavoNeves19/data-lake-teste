import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\teste\sapient-metrics.json'
from google.cloud import bigquery
c = bigquery.Client(project='sapient-metrics-492914-m7', location='us-east1')

print('=' * 72)
print('INTELIGENCIA COMERCIAL — gold_comercial')
print('=' * 72)

# 1. Sumário executivo
print('\n[1] SUMARIO EXECUTIVO — gold_com_cliente_360')
r = c.query('''
    SELECT
        COUNT(*) AS total,
        COUNTIF(segmento_num <= 3) AS topo_tier,
        COUNTIF(segmento_num IN (7,8)) AS em_risco_adormecido,
        COUNTIF(segmento_num = 9) AS perdidos,
        COUNTIF(flag_oportunidade_sem_crm) AS oportunidade_sem_crm,
        COUNTIF(flag_churn_silencioso) AS churn_silencioso,
        COUNTIF(flag_recuperacao_em_andamento) AS recuperacao,
        COUNTIF(flag_sem_crm) AS fora_radar,
        ROUND(SUM(faturamento_periodo), 0) AS fat_total,
        ROUND(SUM(CASE WHEN segmento_num <= 3 THEN faturamento_periodo ELSE 0 END), 0) AS fat_topo
    FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_cliente_360`
''').to_dataframe()
row = r.iloc[0]
print(f'  Total carteira:             {int(row["total"]):>6,} clientes')
print(f'  Topo (Diamante/Ouro/Prata): {int(row["topo_tier"]):>6,} | Fat: R$ {row["fat_topo"]:>12,.0f}')
print(f'  Em Risco + Adormecido:      {int(row["em_risco_adormecido"]):>6,} clientes')
print(f'  Perdidos:                   {int(row["perdidos"]):>6,} clientes')
print(f'  Faturamento total periodo:  R$ {row["fat_total"]:>12,.0f}')
print()
print(f'  ALERTAS DE INTELIGENCIA:')
print(f'  Oportunidade sem CRM:  {int(row["oportunidade_sem_crm"]):>4} clientes topo sem deal ativo')
print(f'  Churn Silencioso:      {int(row["churn_silencioso"]):>4} em risco sem contato CRM 60d+')
print(f'  Recuperacao andamento: {int(row["recuperacao"]):>4} em risco COM deal aberto')
print(f'  Fora do radar CRM:     {int(row["fora_radar"]):>4} sem match no Pipedrive')

# 2. Alertas por tipo e familia
print('\n[2] ALERTAS POR TIPO x FAMILIA')
r = c.query('''
    SELECT tipo_alerta, rfv_familia,
           COUNT(*) AS qtd,
           ROUND(SUM(faturamento_periodo), 0) AS fat_total
    FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_alerta_comercial`
    GROUP BY 1, 2
    ORDER BY 1, 2
''').to_dataframe()
for _, row in r.iterrows():
    print(f'  {str(row["tipo_alerta"]):<30} {str(row["rfv_familia"]):<12} '
          f'{int(row["qtd"]):>4} clientes | R$ {row["fat_total"]:>12,.0f}')

# 3. Painel por vendedor
print('\n[3] PAINEL POR VENDEDOR')
r = c.query('''
    SELECT rfv_salesperson, rfv_familia,
           qtd_clientes_carteira, qtd_campeoes, qtd_fieis, qtd_fieis_potencial,
           qtd_nao_pode_perder, qtd_em_risco_hibernando, qtd_perdidos,
           pct_topo_carteira, faturamento_erp_periodo, ticket_medio_cliente,
           crm_deals_open, crm_valor_pipeline,
           goto_ligacoes, goto_pct_sentimento_positivo,
           alertas_oportunidade, alertas_churn, clientes_fora_radar
    FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_vendedor_painel`
    ORDER BY faturamento_erp_periodo DESC
''').to_dataframe()
for _, row in r.iterrows():
    print(f'  {str(row["rfv_salesperson"]):<20} {str(row["rfv_familia"]):<12} '
          f'cart={int(row["qtd_clientes_carteira"]):>4} | '
          f'C={int(row["qtd_campeoes"]):>3} F={int(row["qtd_fieis"]):>3} '
          f'FP={int(row["qtd_fieis_potencial"]):>3} NPP={int(row["qtd_nao_pode_perder"]):>3} '
          f'Risco={int(row["qtd_em_risco_hibernando"]):>3} Perd={int(row["qtd_perdidos"]):>3} | '
          f'topo={row["pct_topo_carteira"]:.0%} | '
          f'fat=R${row["faturamento_erp_periodo"]:>12,.0f} tick=R${row["ticket_medio_cliente"]:>8,.0f} | '
          f'deals={int(row["crm_deals_open"]):>4} pipe=R${row["crm_valor_pipeline"]:>10,.0f} | '
          f'calls={int(row["goto_ligacoes"]):>4} sent+={row["goto_pct_sentimento_positivo"]:.0%} | '
          f'op={int(row["alertas_oportunidade"]):>3} churn={int(row["alertas_churn"]):>3} radar={int(row["clientes_fora_radar"]):>3}')

# 4. Pipeline CRM - deals abertos por estagio
print('\n[4] FUNIL CRM — DEALS ABERTOS POR ESTAGIO')
r = c.query('''
    SELECT pipeline_name, stage_name, order_nr, qtd_deals, valor_total,
           valor_medio, dias_medio_no_estagio
    FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_pipeline_crm`
    WHERE status = 'open'
    ORDER BY pipeline_name, order_nr
''').to_dataframe()
cur_pipe = None
for _, row in r.iterrows():
    if row["pipeline_name"] != cur_pipe:
        cur_pipe = row["pipeline_name"]
        print(f'\n  === {cur_pipe} ===')
    print(f'    [{int(row["order_nr"])}] {str(row["stage_name"]):<35} '
          f'{int(row["qtd_deals"]):>4} deals | '
          f'R$ {row["valor_total"]:>10,.0f} | '
          f'avg R$ {row["valor_medio"]:>8,.0f} | '
          f'{row["dias_medio_no_estagio"]:.0f}d no estagio')
