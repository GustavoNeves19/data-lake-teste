# Data Lake Nevoni — Guia rápido pra começar a usar

> **Para:** Albert Macedo (BI / Nevoni)
> **Objetivo:** te dar autonomia pra montar relatórios e dashboards consultando o nosso Data Lake direto, sem depender de planilha intermediária.
> Atualizado em 25/05/2026.

---

## 1. Visão geral em 30 segundos

A gente tem 3 camadas no BigQuery, em ordem de "qualidade":

| Camada | Para que serve | Você consulta? |
|---|---|---|
| **Bronze** (datasets `dm_*`, `crm_raw`, `goto_raw`…) | Dados brutos extraídos do ERP, CRM, telefonia. Mesmo schema da origem. | **Não.** Cheio de NULL, sem joins, campos crus. |
| **Silver** (`silver_comercial`, `silver_financeiro`…) | Dados limpos, tipados, com regras de negócio aplicadas. | Em casos específicos, quando a Gold não cobre o que você precisa. |
| **Gold** (`gold_comercial`, `gold_financeiro`…) | Pronto para consumo: agregações, KPIs, grãos definidos. | **Sim, sempre comece aqui.** |

**Regra de ouro:** *consulte sempre a Gold primeiro.* Se faltar alguma métrica, me chame que a gente cria a tabela Gold.

---

## 2. Onde ficam as tabelas Gold (mapa rápido)

Projeto BQ: `sapient-metrics-492914-m7`

### Comercial e Compras — `gold_comercial`

| Tabela | Grão (o que cada linha representa) |
|---|---|
| `vendas_mensais` | mês × empresa (faturamento, pedidos) |
| `compras_mensais` | mês × empresa |
| `orcamentos_mensais` | mês × status |
| `ranking_clientes` | cliente × mês (top N) |
| `funil_crm` | pipeline × estágio × mês (CRM Pipedrive) |
| `conversao_orcamento` | mês (taxa orçamento → pedido) |
| `gold_com_cliente_360` | cliente (RFV + CRM + alertas em uma visão única) |
| `gold_com_alerta_comercial` | cliente × tipo de alerta (oportunidade, churn, etc.) |
| `gold_com_vendedor_painel` | vendedor × família RFV (KPIs do vendedor) |
| `gold_com_pipeline_crm` | pipeline × stage × status |

### Financeiro — `gold_financeiro`

| Tabela | Grão |
|---|---|
| `gold_fin_dre_mensal` | regime (caixa/competência) × grupo DRE × mês |
| `gold_fin_kpis_mensais` | mês (KPIs consolidados) |
| `contas_receber` | título × vencimento |
| `contas_pagar` | título × vencimento |
| `fluxo_caixa` | categoria × mês |
| `liquidacoes_mensais` | mês × tipo |
| `param_metas_mensais` | indicador × mês (metas do Diego) |

### Outros setores (em construção)

`gold_operacional`, `gold_sac`, `gold_juridico`, `gold_engenharia`, `gold_fiscal` — alguns vazios por enquanto. Use o que já está consolidado em Comercial e Financeiro.

> Mapa completo e canônico no arquivo `dashboard/utils/gold_tables.py` — quando duvidar do nome de uma tabela, abra esse arquivo (é a fonte da verdade).

---

## 3. Consultando direto pelo BigQuery (SQL puro)

Abre o console: <https://console.cloud.google.com/bigquery?project=sapient-metrics-492914-m7>

Exemplo — top 10 clientes do mês:

```sql
SELECT
  partner_name,
  ROUND(SUM(faturamento), 2) AS faturamento_mes
FROM `sapient-metrics-492914-m7.gold_comercial.ranking_clientes`
WHERE mes = DATE_TRUNC(CURRENT_DATE(), MONTH)
GROUP BY 1
ORDER BY faturamento_mes DESC
LIMIT 10
```

Tudo na região `us-east1`. Use `DATE_TRUNC(...)`, `DATE_DIFF(...)`, `SAFE_DIVIDE(...)` à vontade — é BigQuery padrão.

---

## 4. Construindo um dashboard Streamlit

A gente padronizou Streamlit como camada de visualização. Para começar:

### 4.1. Setup mínimo

```bash
pip install streamlit google-cloud-bigquery google-auth pandas plotly
```

Tenha um service account JSON do GCP em `C:\teste\sapient-metrics.json` (se não tiver, me pede).

### 4.2. Cliente BigQuery (copie da nossa lib)

A gente já tem um helper pronto em `dashboard/utils/bq_client.py`. Copie esse padrão:

```python
import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT = "sapient-metrics-492914-m7"
CREDS   = r"C:\teste\sapient-metrics.json"

@st.cache_resource(show_spinner=False)
def get_client():
    creds = service_account.Credentials.from_service_account_file(
        CREDS,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(credentials=creds, project=PROJECT)

@st.cache_data(ttl=3600, show_spinner=False)
def query(sql: str) -> pd.DataFrame:
    """Executa SQL no BQ e cacheia por 1 hora."""
    return get_client().query(sql).to_dataframe()
```

O `@st.cache_data(ttl=3600)` evita chamar o BQ a cada interação — segura por 1 hora.

### 4.3. Formatadores BRL/Pct (úteis no dia a dia)

```python
def fmt_brl(v: float) -> str:
    if v is None: return "—"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(v: float) -> str:
    if v is None: return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"
```

### 4.4. Exemplo end-to-end — uma página inteira

`meu_dashboard.py`:

```python
import streamlit as st
import pandas as pd
import plotly.express as px
from google.cloud import bigquery
from google.oauth2 import service_account

# --- conexão (copiar da seção 4.2) ---
PROJECT = "sapient-metrics-492914-m7"
CREDS   = r"C:\teste\sapient-metrics.json"

@st.cache_resource
def get_client():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return bigquery.Client(credentials=creds, project=PROJECT)

@st.cache_data(ttl=3600)
def query(sql):
    return get_client().query(sql).to_dataframe()

def fmt_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- página ---
st.set_page_config(page_title="Meu primeiro dash", layout="wide")
st.title("Vendas dos últimos 12 meses")

df = query("""
  SELECT mes, SUM(faturamento) AS faturamento
  FROM `sapient-metrics-492914-m7.gold_comercial.vendas_mensais`
  WHERE mes >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
  GROUP BY mes ORDER BY mes
""")

# KPI
c1, c2 = st.columns(2)
with c1:
    st.metric("Faturamento total (12m)", fmt_brl(df['faturamento'].sum()))
with c2:
    st.metric("Média mensal", fmt_brl(df['faturamento'].mean()))

# Gráfico
fig = px.bar(df, x="mes", y="faturamento", title="Faturamento mensal")
st.plotly_chart(fig, use_container_width=True)

# Tabela
df['faturamento'] = df['faturamento'].apply(fmt_brl)
st.dataframe(df, use_container_width=True, hide_index=True)
```

Rodar:

```bash
streamlit run meu_dashboard.py
```

Abre em `http://localhost:8501`. Pronto.

---

## 5. Próximos passos / o que evitar

- **Sempre** comece a query escrevendo `FROM \`sapient-metrics-492914-m7.gold_...\`** — se for `silver_` ou `dm_`, repense.
- **Cache do Streamlit:** `@st.cache_data(ttl=...)` evita BQ desnecessário. Coloca em tudo que é query.
- **Datas:** o BQ aceita `DATE '2026-05-01'` ou `CURRENT_DATE()`. Evite passar string solta.
- **Não rode `SELECT *`** em tabelas grandes — escolha as colunas que precisa.
- **Se precisar de algo que não está na Gold:** me chame. Não saia consumindo silver/bronze direto — virou hábito, vira dívida técnica.

---

## 6. Onde estão as coisas neste repo (referência)

| Caminho | O que tem |
|---|---|
| `dashboard/utils/gold_tables.py` | Mapa canônico de todas as tabelas Gold (fonte da verdade) |
| `dashboard/utils/bq_client.py` | Helper de conexão + cache + formatadores |
| `dashboard/utils/components.py` | KPI cards, headers, sidebar — peça pra eu replicar pro seu dash |
| `dashboard/pages/` | Páginas Streamlit em produção (Financeiro, Comercial, etc.) |
| `sql/gold_comercial/build_gold_comercial.sql` | SQL que constrói as tabelas Gold de Comercial |
| `docs/` | Documentação técnica do projeto |

---

## 7. Dúvidas

Me chama no WhatsApp ou no grupo — qualquer dúvida de schema, query lenta ou Gold faltando, é só falar.

— Gustavo
