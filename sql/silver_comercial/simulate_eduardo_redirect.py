"""
Simulação read-only — impacto de redirecionar os 81 clientes do Eduardo Marques
para outro(s) vendedor(es). NÃO grava nada em BQ.

Uso:
  py -3 sql/silver_comercial/simulate_eduardo_redirect.py
  py -3 sql/silver_comercial/simulate_eduardo_redirect.py --para "Guilherme Aquino"
  py -3 sql/silver_comercial/simulate_eduardo_redirect.py --periodo 2026-04-30 --csv

Por padrão usa o snapshot mais recente em silver_com_rfv_score e simula que TODOS
os clientes do Eduardo vão para o `--para` (default: "Guilherme Aquino").

Para apresentar pro Alves: rodar 1× por candidato e comparar.
"""
import argparse
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')

import pandas as pd
from google.cloud import bigquery

PROJ     = 'sapient-metrics-492914-m7'
LOCATION = 'us-east1'
EDUARDO  = 'Eduardo Marques'
FAMILIA  = 'HOSPITALAR'


def fetch_snapshot(client: bigquery.Client, periodo: str | None) -> tuple[pd.DataFrame, str]:
    """Retorna o snapshot da silver_com_rfv_score para o período pedido (ou o mais recente)."""
    if periodo:
        ref_clause = f"DATE(data_referencia) = DATE '{periodo}'"
    else:
        ref_clause = (
            "DATE(data_referencia) = ("
            f"  SELECT MAX(DATE(data_referencia)) FROM `{PROJ}.silver_comercial.silver_com_rfv_score`"
            ")"
        )

    df = client.query(f"""
        SELECT
            partner_name,
            COALESCE(rfv_salesperson, 'Sem Vendedor') AS rfv_salesperson,
            recencia_dias,
            frequencia,
            valor_total,
            classificacao_2,
            classificacao_3,
            DATE(data_referencia) AS data_referencia
        FROM `{PROJ}.silver_comercial.silver_com_rfv_score`
        WHERE rfv_familia = '{FAMILIA}'
          AND {ref_clause}
    """).to_dataframe()
    periodo_real = str(df['data_referencia'].iloc[0]) if not df.empty else '(vazio)'
    return df, periodo_real


def resumo_por_vendedor(df: pd.DataFrame) -> pd.DataFrame:
    # Mesma lógica de KPIs do dashboard (pages/02_Comercial_e_Compras.py:621)
    return (df
        .groupby('rfv_salesperson', dropna=False)
        .agg(
            clientes      = ('partner_name', 'nunique'),
            campeoes      = ('classificacao_3', lambda s: int((s == 1).sum())),
            fieis         = ('classificacao_3', lambda s: int((s == 2).sum())),
            fp            = ('classificacao_3', lambda s: int((s == 3).sum())),
            nao_perder    = ('classificacao_3', lambda s: int((s == 8).sum())),
            risco_hib     = ('classificacao_3', lambda s: int(s.isin([9, 10]).sum())),
            perdidos      = ('classificacao_3', lambda s: int((s == 11).sum())),
            faturamento   = ('valor_total', 'sum'),
        )
        .reset_index()
        .sort_values('clientes', ascending=False)
    )


def fmt_brl(v: float) -> str:
    if pd.isna(v):
        return 'R$ -'
    return f"R$ {v:>14,.0f}".replace(',', '.')


def print_resumo(titulo: str, df: pd.DataFrame) -> None:
    print(f"\n{titulo}")
    print("-" * 110)
    print(f"  {'Vendedor':<22} {'Cli':>5}  {'Camp':>5} {'Fié':>5} {'F.Pot':>5} "
          f"{'!Perd':>5} {'Risco':>5} {'Perd':>5}   {'Faturamento':>17}")
    print("-" * 110)
    for _, r in df.iterrows():
        print(f"  {r['rfv_salesperson']:<22} {int(r['clientes']):>5}  "
              f"{int(r['campeoes']):>5} {int(r['fieis']):>5} {int(r['fp']):>5} "
              f"{int(r['nao_perder']):>5} {int(r['risco_hib']):>5} {int(r['perdidos']):>5}   "
              f"{fmt_brl(r['faturamento']):>17}")
    print("-" * 110)
    cols_num = ['clientes', 'campeoes', 'fieis', 'fp', 'nao_perder', 'risco_hib', 'perdidos', 'faturamento']
    tot = df[cols_num].apply(pd.to_numeric, errors='coerce').sum()
    print(f"  {'TOTAL ' + FAMILIA:<22} {int(tot['clientes']):>5}  "
          f"{int(tot['campeoes']):>5} {int(tot['fieis']):>5} {int(tot['fp']):>5} "
          f"{int(tot['nao_perder']):>5} {int(tot['risco_hib']):>5} {int(tot['perdidos']):>5}   "
          f"{fmt_brl(float(tot['faturamento'])):>17}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--para',     default='Guilherme Aquino',
                   help='Vendedor que receberá os clientes do Eduardo (default: Guilherme Aquino).')
    p.add_argument('--periodo',  default=None,
                   help='Data do snapshot (YYYY-MM-DD). Default: mais recente em silver_com_rfv_score.')
    p.add_argument('--csv',      action='store_true',
                   help='Exporta lista detalhada dos 81 clientes do Eduardo para CSV.')
    args = p.parse_args()

    client = bigquery.Client(project=PROJ, location=LOCATION)

    print('=' * 100)
    print(f'  SIMULAÇÃO — Eduardo Marques → "{args.para}"   (HOSPITALAR)')
    print('=' * 100)

    df, periodo_real = fetch_snapshot(client, args.periodo)
    print(f"  Snapshot: {periodo_real}   |   linhas: {len(df)}   |   clientes únicos: {df['partner_name'].nunique()}")

    if df.empty:
        print("  ⚠ Snapshot vazio — verifique o período.")
        return 1

    if EDUARDO not in df['rfv_salesperson'].values:
        print(f"  ⚠ Nenhum cliente atribuído a '{EDUARDO}' nesse snapshot.")
        print(f"  Vendedores no snapshot: {sorted(df['rfv_salesperson'].unique())}")
        return 1

    antes  = resumo_por_vendedor(df)

    df_pos = df.copy()
    df_pos.loc[df_pos['rfv_salesperson'] == EDUARDO, 'rfv_salesperson'] = args.para
    depois = resumo_por_vendedor(df_pos)

    print_resumo("ANTES (estado atual no BQ):", antes)
    print_resumo(f'DEPOIS (hipótese: todos do Eduardo → "{args.para}"):', depois)

    eduardo_df = df[df['rfv_salesperson'] == EDUARDO]
    impacto_fat = eduardo_df['valor_total'].sum()
    print()
    print('=' * 100)
    print(f"  IMPACTO em '{args.para}':")
    print(f"    +{eduardo_df['partner_name'].nunique()} clientes")
    print(f"    +{fmt_brl(impacto_fat).strip()} de faturamento (12m rolling)")
    seg = eduardo_df['classificacao_2'].value_counts()
    if not seg.empty:
        print("    Segmentos que migram:")
        for s, n in seg.items():
            print(f"      {s:<25} {int(n):>3}")
    print('=' * 100)

    if args.csv:
        out = (eduardo_df
            .sort_values('valor_total', ascending=False)
            [['partner_name', 'classificacao_2', 'recencia_dias', 'frequencia', 'valor_total']]
            .rename(columns={
                'partner_name':    'Cliente',
                'classificacao_2': 'Segmento',
                'recencia_dias':   'Recência (dias)',
                'frequencia':      'Frequência (12m)',
                'valor_total':     'Receita (12m)',
            })
        )
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"simulacao_eduardo_{periodo_real}.csv")
        out.to_csv(path, index=False, encoding='utf-8-sig')
        print(f"\n  CSV detalhado: {path}")

    print("\n  Nada gravado em BQ — esta é apenas uma simulação.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
