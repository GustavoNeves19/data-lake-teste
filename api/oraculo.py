"""
Oráculo IA (backend FastAPI) — assistente analítico sobre o Data Lake Nevoni.

Port desacoplado do Streamlit de dashboard/utils/oracle.py, com GUARDRAILS de SQL
que o módulo original NÃO tinha (o Streamlit executava o SQL cru do LLM direto no BQ).

Dependências:
- pacote `openai` (pip install openai) — SDK novo (from openai import OpenAI).
  Import tolerante: se a lib não estiver instalada, o módulo ainda importa
  (ready() retorna False e oraculo_chat devolve mensagem de indisponível).
- env OPENAI_API_KEY — no dashboard atual mora em .streamlit/secrets.toml;
  no backend deve migrar para o .env do serviço FastAPI. O valor NUNCA é logado.
- env OPENAI_MODEL (opcional, default gpt-4o-mini).

Notas de custo/segurança:
- Toda query passa por validate_sql() (allowlist de tabelas + bloqueio de DML/DDL
  + statement único) antes de tocar o BigQuery.
- A execução usa maximum_bytes_billed=2 GB e LIMIT forçado (teto de custo por pergunta).
"""

from __future__ import annotations

import os
import re
import math

from google.cloud import bigquery

from .bq import get_client, PROJECT_PROD

# ── Import tolerante do SDK OpenAI ────────────────────────────────────────────
try:
    from openai import OpenAI  # SDK novo (openai>=1.0)
    _OPENAI_OK = True
except Exception:  # ImportError ou qualquer falha de import da lib
    OpenAI = None  # type: ignore
    _OPENAI_OK = False


# ── Config ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Default gpt-4o-mini (barato). A narração é blindada: totais e contagens são
# calculados em Python (_resumo_calculado) e entregues prontos pro modelo, então
# o mini não erra soma/contagem — ele só lê e interpreta, nunca faz conta.
# Dá pra subir pra gpt-4o via env OPENAI_MODEL se quiser narração mais fluida.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

PROJECT = PROJECT_PROD  # "sapient-metrics-492914-m7"

# Teto de bytes faturados por consulta (2 GB) — trava dura de custo no BigQuery.
MAX_BYTES_BILLED = 2_000_000_000
# Timeout curto: o Oráculo é interativo; query lenta = pergunta mal formada.
QUERY_TIMEOUT_S = 30
# LIMIT forçado quando o LLM não põe um.
FORCED_LIMIT = 100


def ready() -> bool:
    """True se o backend pode chamar a OpenAI: SDK instalado + chave 'sk-...'.

    Nunca loga nem expõe o valor da chave — só valida o prefixo.
    """
    key = OPENAI_API_KEY or ""
    return bool(_OPENAI_OK and key.startswith("sk-"))


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM_PROMPT — copiado VERBATIM de dashboard/utils/oracle.py
# (é o coração: injeta schema, regras RFV, filtros canônicos e exemplos).
# ══════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = f"""Você é o **Oráculo da Nevoni** — guardião dos dados do Data Lake, assistente analítico com personalidade sábia, direta e um leve toque de misterioso.

## Sua Personalidade
- Fala em **português brasileiro**, de forma clara, assertiva e sem rodeios
- Age como um consultor sênior que conhece cada detalhe dos dados da Nevoni
- Usa frases de oráculo naturalmente: "Os dados revelam...", "A análise aponta...", "Vejo nos números..."
- É conciso — entrega o insight principal primeiro, detalhes depois
- Quando identifica risco, alerta com clareza. Quando há oportunidade, aponta o próximo passo concreto
- Nunca inventa dados — se não tem certeza, verifica antes de afirmar

## Tom para executivos (REGRA — quem lê é DIRETOR/CEO, não analista)
- NUNCA cite no texto da resposta: SQL, query, tabela, coluna, "grain", BigQuery, nome técnico de tabela ou código.
- COMECE pelo número que importa e pelo que ele significa pro negócio; o detalhe vem depois.
- Estrutura: [número/fato] -> [o que significa] -> [próximo passo concreto].
- Linguagem simples: diga "melhores clientes" em vez de "classificacao_3 = 1"; "clientes em risco" em vez de "F2R4".

## ANTI-ALUCINAÇÃO (regra absoluta)
- Os números, tabelas e exemplos DESTE prompt são REFERÊNCIA DE ESQUEMA para você montar a consulta — **NÃO são dados para citar na resposta**. Nunca repita na resposta um valor tirado deste prompt (ex.: "R$ 3.615.785,89" da tabela de carteiras).
- TODO número que você afirmar tem que vir de uma consulta que você mesmo escreveu nesta rodada. Se você não consultou, não afirme.
- Proibido prometer o futuro: NUNCA escreva "vou buscar", "em breve", "vou apresentar", "aguarde", "já retorno". Não existe próximo turno. Ou você emite a consulta AGORA, ou o dado nunca chega ao gestor.

## Empresa
Nevoni: distribuidora de equipamentos hospitalares (Hospitalar), farmácias (Farmácia) e peças/SAC (SAC).
Grupo: Nevoni + Vanguardia Academy.

## Projeto BigQuery
{PROJECT} (região us-east1) — único ambiente ativo (Vanguard está fora de escopo).

## Tabelas Disponíveis

### Silver Comercial (`{PROJECT}.silver_comercial`)

**`silver_com_rfv_base`** — agregado por cliente × família × vendedor titular × período
  Grain: partner_name × rfv_familia × rfv_salesperson × data_referencia
  Colunas:
    - partner_name (razão social via YNOMCLI)
    - rfv_familia: HOSPITALAR | FARMACIAS | SAC | **NOVOS_CLIENTES**
    - rfv_salesperson (titular real ou 'A definir' pra Novos)
    - partner_codes_list (string com códigos de filiais agregadas)
    - ultima_compra_data, recencia_dias, recencia_meses
    - frequencia (nº pedidos únicos), valor_total
    - data_referencia (mês de corte: '2026-04-30', '2026-05-31', etc)

**`silver_com_rfv_score`** — mesmo grain do rfv_base + buckets RFV + segmentação
  Colunas extras: freq_bucket (F1-F5), rec_bucket (R1-R5),
                  classificacao_1 (concat ex 'F1R1'), classificacao_2 (segmento texto),
                  classificacao_3 (1-11 ordenação)

**`silver_com_rfv_resumo`** — sumário por família × vendedor × segmento
  Grain: rfv_familia × rfv_salesperson × segmento × data_referencia
  Colunas: qtd_clientes, faturamento_total, ticket_medio, frequencia_media, recencia_media_dias

**`param_com_rfv_carteira`** — fonte da verdade do titular de cada cliente
  Colunas: partner_code, partner_name, rfv_familia, salesperson_name,
           is_active (FALSE = desativado), salesperson_group_code (FA/FR/PC)

### Gold Comercial (`{PROJECT}.gold_comercial`)
- `gold_com_cliente_360` — visão 360° por cliente
- `gold_com_alerta_comercial` — alertas (oportunidade sem CRM, churn silencioso, etc)
- `gold_com_vendedor_painel` — painel por vendedor
- `gold_com_pipeline_crm` — pipeline Pipedrive

### Bronze ERP (datasets dm_*)
- `dm_orders.fact_sales_order` — vendas brutas (use somente se Silver/Gold não cobrirem)
- `dm_partners.dim_partner` — todos os clientes (incluindo excluídos com YDATEXC NOT NULL)

## Regras de Negócio RFV (Reunião 28/05/2026)

### Famílias (4)
- **HOSPITALAR** — grupo FA do ERP (5 vendedores titulares)
- **FARMACIAS** — grupo FR (apenas Cauã Ribeiro como titular)
- **SAC** — grupo PC (apenas Geovanna Gomes como titular)
- **NOVOS_CLIENTES** — clientes que tiveram venda mas NÃO estão em carteira; vendedor = 'A definir' (Alves+Vinícius decidem alocação)

### Vendedores titulares por carteira (Abril/2026)
| Família | Carteira | Vendedor | Clientes ativos | Faturamento abr/26 |
|---|---|---|---|---|
| HOSPITALAR | A | Guilherme Aquino | 315 / 129 ativ.| R$ 3.615.785,89 |
| HOSPITALAR | B | Kauã Rodrigues | 295 / 115 | R$ 2.394.372,43 |
| HOSPITALAR | C | Richard Lucas | 435 / 199 | R$ 728.728,97 |
| HOSPITALAR | D | Kauan Ramos | 389 / 180 | R$ 609.953,37 |
| HOSPITALAR | (licitação) | Eduardo Marques | 81 / 49 | R$ 446.313,05 |
| FARMACIAS | — | Cauã Ribeiro | 262 / 248 | R$ 445.047,84 |
| SAC | — | Geovanna Gomes | 158 / 77 | R$ 204.897,51 |
| NOVOS_CLIENTES | — | A definir | — / 697 | R$ 1.780.489,07 |

**Carteira ativa total = 1.935 clientes (1.934 únicos + 1 duplicado MED4)**
**Total no silver Abril/2026 = 1.694 clientes / R$ 10.225.588,13** (bate ERP Δ 0,047%)

### Cobertura da carteira (51,5% geral em abr/26)
938 clientes ativos na carteira NÃO compraram no período — são os **ociosos** (oportunidade de reativação). Pra ver eles: consultar `param_com_rfv_carteira` + LEFT JOIN com `silver_com_rfv_base` (filtrar onde silver é NULL).

### Vendedores excluídos do RFV (decisões Alves)
- **Karina Correia** — distribuidores/rede (não farmácia ponta)
- **Cauã Rodrigues** — migrou de segmento, clientes dele estão hoje com Ribeiro
- **Eduardo Marques** entra na RFV Geral / HOSPITALAR, mas **filtrado fora das 4 carteiras A/B/C/D** (licitação à parte)

## Segmentos RFV (classificacao_3, 1-11)

```
 1 = Campeões          → F1 + R1 (alta freq + recente)
 2 = Fiéis             → F1 + R2-R3
 3 = Fiéis em Potencial → F2-F3 + R1-R2
 4 = Novos clientes    → F5 + R1
 5 = Promessas         → F5 + R2
 6 = Precisando atenção → F3 + R3
 7 = Quase dormentes   → F4-F5 + R3
 8 = Não pode perder   → F1 + R4-R5
 9 = Em risco          → F2-F3 + R4-R5
10 = Hibernando        → F4 + R4
11 = Perdidos          → F4-F5 + R4-R5 ou rec >180d
```

## Thresholds (frequência em 12 meses, recência em dias)

- **HOSPITALAR, SAC, NOVOS_CLIENTES:** F1≥5, F2=4, F3=3, F4=2, F5=1
- **FARMACIAS:** F1≥7, F2=5-6, F3=3-4, F4=2, F5=1
- Recência: R1≤30d | R2≤60d | R3≤120d | R4≤180d | R5>180d

## Janela temporal canônica

`invoice_date` (yDatNot — data da NF) — NÃO usar `order_date` (yDatPed)
Janela: 12 meses pra trás da data_referencia, sempre a partir do início do mês.

Para data_referencia = '2026-04-30':
```
invoice_date BETWEEN '2025-04-01' AND '2026-04-30'
```

## Filtros canônicos no fact_sales_order

```sql
WHERE order_status IN (3, 4)
  AND salesperson_group_code IN ('FA', 'FR', 'PC')   -- exclui EC (e-commerce)
  AND excluded_at IS NULL                              -- só notas ativas (não canceladas)
  AND n.financial_flag <> 'N'                          -- exclui devoluções e similares
```

## Regra Crítica — Grain de silver_com_rfv_*

Tabelas RFV têm grain partner_name × rfv_familia × rfv_salesperson × data_referencia. Um cliente em mais de uma carteira aparece em + de 1 linha.

**Pra contar CLIENTES:**
- Use `COUNT(DISTINCT partner_name)` — NUNCA `COUNT(*)`
- Sempre filtre por `data_referencia` específico (ex: `WHERE data_referencia = DATE '2026-04-30'`)
- Se quiser ver vendedores agrupados: `STRING_AGG(DISTINCT rfv_salesperson, ', ')`

**Exemplo correto:**
```sql
-- Campeões Hospitalar (todas as 4 carteiras + Eduardo)
SELECT
  partner_name,
  STRING_AGG(DISTINCT rfv_salesperson, ', ' ORDER BY rfv_salesperson) AS vendedores,
  MAX(frequencia) AS freq,
  MIN(recencia_dias) AS rec,
  MAX(valor_total) AS valor
FROM `{PROJECT}.silver_comercial.silver_com_rfv_score`
WHERE data_referencia = DATE '2026-04-30'
  AND rfv_familia = 'HOSPITALAR'
  AND classificacao_2 = 'Campeões'
GROUP BY partner_name
ORDER BY valor DESC
LIMIT 20
```

**Filtro especial — "4 carteiras Hospitalar" (sem Eduardo):**
```sql
WHERE rfv_familia = 'HOSPITALAR'
  AND rfv_salesperson IN ('Guilherme Aquino', 'Kauã Rodrigues', 'Richard Lucas', 'Kauan Ramos')
```

## COMO VOCÊ RESPONDE — dois modos

Você trabalha em duas etapas. NESTA etapa você só decide entre dois modos:

**MODO DADOS** — a pergunta pede número, lista, ranking, comparação ou qualquer coisa que dependa dos dados.
- Responda com **APENAS um bloco ```sql ...```** e mais nada. Sem texto antes, sem texto depois.
- Não escreva a análise agora: depois que a consulta rodar, você recebe os números REAIS e escreve a resposta em cima deles. Escrever texto aqui só atrapalha.
- A consulta roda nos bastidores; o gestor nunca vê o SQL.

**MODO CONCEITO** — a pergunta é definição, interpretação ou "como funciona" e NÃO precisa de número novo.
- Responda direto em prosa executiva, em português, sem bloco SQL.

Na dúvida entre os dois, prefira MODO DADOS: é melhor consultar do que chutar.

## Regras da consulta (MODO DADOS)

1. Use SEMPRE o nome completo: `{PROJECT}.dataset.tabela`.
2. Só SELECT/WITH. Nada de INSERT/UPDATE/DELETE/DDL.
3. Para contar clientes use `COUNT(DISTINCT partner_name)` e filtre `data_referencia` específico (nunca CURRENT_DATE() na janela).
4. Traga colunas legíveis e already-agregadas (nomes de cliente/vendedor, valores somados), não IDs crus. Dê apelidos em português nas colunas (ex.: `AS cliente`, `AS faturamento`).
5. Ordene pelo que importa (geralmente `valor_total`/faturamento DESC) e ponha `LIMIT` coerente com a pergunta ("top 5" -> LIMIT 5; "top 10" -> LIMIT 10; senão LIMIT 20).
"""


# ══════════════════════════════════════════════════════════════════════════════
# NARRATOR_PROMPT — segunda passada: escreve a análise executiva SOBRE o dado real
# que voltou do BigQuery. Ele NUNCA inventa número — só interpreta o que recebe.
# ══════════════════════════════════════════════════════════════════════════════
NARRATOR_PROMPT = """Você é o Oráculo da Nevoni escrevendo para um DIRETOR/CEO.

Você recebe a pergunta do gestor e o RESULTADO REAL de uma consulta ao Data Lake.
Escreva a resposta final, curta e de alto valor, SOMENTE com base nesses dados.

REGRAS:
- Português brasileiro, tom de consultor sênior: direto, seguro, sem enrolação.
- Estrutura: **(1) manchete** com o número/achado principal em negrito -> **(2) o que significa** para o negócio (1-2 frases) -> **(3) um próximo passo concreto**.
- Use SOMENTE os números que estão nos dados recebidos. NUNCA invente, arredonde grosseiro nem cite valores que não estão ali.
- Para QUALQUER total, soma ou quantidade, copie o valor do bloco "RESUMO CALCULADO" — ele já vem somado/contado. NUNCA some nem conte os itens você mesmo (você erra). Se um total não está no RESUMO, não afirme total.
- Valores em reais no formato brasileiro: R$ 1.641.084,31 (ponto no milhar, vírgula no decimal).
- Destaque em **negrito** os números e nomes que importam.
- Se ajudar a leitura, cite os 3-5 primeiros itens em bullets curtos (o gestor vê a tabela completa logo abaixo da sua resposta, então NÃO repita a tabela inteira).
- NUNCA mencione SQL, tabela, coluna, BigQuery ou qualquer termo técnico.
- NUNCA diga "vou buscar", "em breve" ou prometa algo futuro. A resposta é agora.
- Se os dados vierem vazios, diga com clareza que não houve resultado para o filtro pedido e sugira um recorte alternativo.
- 4 a 8 linhas no total. Nada de introdução genérica ("aqui está...", "com base na análise...")."""


# ══════════════════════════════════════════════════════════════════════════════
# GUARDRAILS
# ══════════════════════════════════════════════════════════════════════════════

# Allowlist de tabelas — dataset.tabela (sem o projeto). Qualquer referência em
# FROM/JOIN fora deste set faz a query ser rejeitada.
ALLOWED: set[str] = {
    "silver_comercial.silver_com_rfv_base",
    "silver_comercial.silver_com_rfv_score",
    "silver_comercial.silver_com_rfv_resumo",
    "silver_comercial.param_com_rfv_carteira",
    "silver_comercial.param_com_entity_bridge",
    "gold_comercial.gold_com_cliente_360",
    "gold_comercial.gold_com_alerta_comercial",
    "gold_comercial.gold_com_vendedor_painel",
    "gold_comercial.gold_com_pipeline_crm",
    "gold_comercial.gold_qa_validacao",
    "dm_orders.fact_sales_order",
    "dm_orders.dim_operation_nature",
    "dm_partners.dim_partner",
    "crm_raw.funil_vendas_farmacia",
    "crm_raw.recorrencia_farmacia",
    "crm_raw.recorrencia_distribuidores",
}

# Palavras proibidas (DML/DDL/execução) — checadas como palavra inteira (\b...\b).
_FORBIDDEN_WORDS = [
    "INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "CREATE", "ALTER",
    "TRUNCATE", "GRANT", "REVOKE", "CALL", "EXECUTE",
]
_FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(_FORBIDDEN_WORDS) + r")\b", re.IGNORECASE
)

# Captura `proj.dataset.tabela` ou `dataset.tabela` após FROM/JOIN, com ou sem
# crase (backtick). Aceita nomes com hífen (projeto do BQ) entre as crases.
_TABLE_REF_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+`?"
    r"(?:(?P<proj>[A-Za-z0-9_-]+)\.)?"      # projeto (opcional)
    r"(?P<ds>[A-Za-z0-9_-]+)\."             # dataset
    r"(?P<tbl>[A-Za-z0-9_-]+)"              # tabela
    r"`?",
    re.IGNORECASE,
)


def _strip_comments(sql: str) -> str:
    """Remove comentários -- de linha e /* */ de bloco, para análise limpa."""
    # Blocos /* ... */
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Linha -- ...
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _referenced_tables(sql: str) -> list[str]:
    """Lista de `dataset.tabela` referenciadas em FROM/JOIN.

    Ignora referências onde o "projeto" na verdade é um alias/CTE (sem projeto,
    parte central não é um dataset conhecido) — mas para segurança validamos TODAS
    as ocorrências de padrão dataset.tabela; CTEs (WITH x AS) usam FROM x (sem ponto),
    que não casa este regex e portanto não é validado como tabela.
    """
    refs: list[str] = []
    for m in _TABLE_REF_RE.finditer(sql):
        ds = m.group("ds")
        tbl = m.group("tbl")
        # Se veio com 3 partes (proj.ds.tbl), o group proj é o projeto e ds.tbl é
        # o par a validar. Se veio com 2 partes, o regex casa proj=None, ds, tbl.
        refs.append(f"{ds}.{tbl}")
    return refs


def validate_sql(sql: str) -> tuple[bool, str]:
    """Valida o SQL gerado pelo LLM antes de tocar o BigQuery.

    Regras (todas devem passar):
    - não-vazio;
    - começa (após remover comentários/strip/lower) com SELECT ou WITH;
    - não contém palavra proibida de DML/DDL/execução;
    - statement único (';' só permitido no final);
    - todas as tabelas em FROM/JOIN estão na allowlist.

    Retorna (ok, motivo). motivo é '' quando ok=True.
    """
    if not sql or not sql.strip():
        return False, "Query vazia."

    clean = _strip_comments(sql).strip()
    if not clean:
        return False, "Query vazia após remover comentários."

    lowered = clean.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False, "Apenas consultas SELECT/WITH são permitidas."

    # Palavras proibidas de escrita/DDL/execução.
    m = _FORBIDDEN_RE.search(clean)
    if m:
        return False, f"Comando não permitido detectado: {m.group(1).upper()}."

    # Múltiplos statements: aceita no máximo um ';' e só no fim.
    stripped_semi = clean.rstrip().rstrip(";").rstrip()
    if ";" in stripped_semi:
        return False, "Múltiplos comandos não são permitidos (';' no meio da query)."

    # Allowlist de tabelas.
    refs = _referenced_tables(clean)
    if not refs:
        return False, "Nenhuma tabela reconhecida na consulta."
    for ref in refs:
        if ref.lower() not in {a.lower() for a in ALLOWED}:
            return False, f"Tabela fora da lista permitida: {ref}."

    return True, ""


def _has_limit(sql: str) -> bool:
    """True se o SQL (fora de comentários) já tem uma cláusula LIMIT."""
    clean = _strip_comments(sql)
    return re.search(r"\blimit\b\s+\d+", clean, re.IGNORECASE) is not None


# ══════════════════════════════════════════════════════════════════════════════
# Execução no BigQuery
# ══════════════════════════════════════════════════════════════════════════════
def _run_sql(sql: str):
    """Roda o SQL no BQ com teto de bytes e timeout curto; devolve DataFrame.

    Envelopa em `SELECT * FROM (<sql>) LIMIT n` quando o SQL não tem LIMIT próprio,
    garantindo que nunca voltamos linhas demais para o chat.
    """
    inner = sql.rstrip().rstrip(";").rstrip()
    if _has_limit(inner):
        final_sql = inner
    else:
        final_sql = f"SELECT * FROM (\n{inner}\n) LIMIT {FORCED_LIMIT}"

    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES_BILLED)
    client = get_client()
    job = client.query(final_sql, job_config=job_config)
    return job.result(timeout=QUERY_TIMEOUT_S).to_dataframe()


# ══════════════════════════════════════════════════════════════════════════════
# JSON-safe
# ══════════════════════════════════════════════════════════════════════════════
def _json_safe_value(v):
    """Converte um valor de célula para algo serializável em JSON."""
    if v is None:
        return None
    # NaN / inf de floats
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    # Timestamps / datas / qualquer coisa com isoformat
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    # Tipos numpy / decimais / bytes → normaliza
    if isinstance(v, (int, str, bool)):
        return v
    return str(v)


def _rows_json_safe(df) -> list[dict]:
    """DataFrame -> lista de dicts JSON-safe (nada de NaN, Timestamp cru, etc.)."""
    import pandas as pd  # local: mantém o import de bq/queries como fonte única

    if df is None or df.empty:
        return []
    # Substitui NaN/NaT por None antes de serializar.
    safe = df.where(pd.notnull(df), None)
    records = safe.to_dict(orient="records")
    return [{k: _json_safe_value(v) for k, v in row.items()} for row in records]


# ══════════════════════════════════════════════════════════════════════════════
# Utilitários de texto
# ══════════════════════════════════════════════════════════════════════════════
def _extract_sql(text: str) -> str | None:
    """Extrai a primeira query SQL de um bloco ```sql ...``` (regex verbatim)."""
    m = re.search(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None


def _strip_sql_block(text: str) -> str:
    """Remove o(s) bloco(s) ```sql ...``` do texto exibido ao executivo."""
    return re.sub(r"```sql.*?```", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


# Colunas cujo nome sugere dinheiro — só dessas faz sentido somar (não de recência/freq).
_MONEY_HINTS = ("faturamento", "valor", "receita", "montante", "faturado")


def _fmt_brl(v: float) -> str:
    """Float -> 'R$ 1.234.567,89' (padrão brasileiro)."""
    s = f"{v:,.2f}"  # 1,234,567.89
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _resumo_calculado(df) -> str:
    """Agregados DETERMINÍSTICOS (contagem + somas de colunas monetárias) em Python.

    O modelo (sobretudo o mini) erra soma/contagem quando faz de cabeça. Entregamos
    esses números prontos pra ele só copiar — nunca calcular. Recência/frequência não
    são somadas (não faz sentido); só colunas cujo nome sugere dinheiro.
    """
    import pandas as pd

    if df is None or df.empty:
        return "Total de registros: 0"

    linhas = [f"Total de registros (linhas): {len(df)}"]
    for col in df.columns:
        if any(h in str(col).lower() for h in _MONEY_HINTS):
            serie = pd.to_numeric(df[col], errors="coerce")
            if serie.notna().any():
                linhas.append(f"Soma de '{col}': {_fmt_brl(float(serie.sum()))}")
    return "\n".join(linhas)


def _df_to_markdown(df) -> str:
    """Markdown do df.head(20). Usa to_markdown se disponível, senão fallback simples."""
    head = df.head(20)
    try:
        return head.to_markdown(index=False)
    except Exception:
        # Fallback sem tabulate: pipe-table manual.
        cols = list(head.columns)
        linhas = ["| " + " | ".join(str(c) for c in cols) + " |",
                  "| " + " | ".join("---" for _ in cols) + " |"]
        for _, r in head.iterrows():
            linhas.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
        return "\n".join(linhas)


# ══════════════════════════════════════════════════════════════════════════════
# Chamada à OpenAI (DRY entre as duas passadas)
# ══════════════════════════════════════════════════════════════════════════════
def _chat(messages: list[dict], *, temperature: float, max_tokens: int) -> str:
    """Uma chamada de chat completion. Levanta exceção em falha (o chamador trata)."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def _narrate(question: str, df, history: list[dict] | None) -> str:
    """Segunda passada: escreve a análise executiva SOBRE o dado real retornado.

    Recebe o DataFrame já executado e devolve o texto final. Nunca inventa número —
    o modelo só enxerga os dados que passamos (df.head em markdown).
    """
    data_md = _df_to_markdown(df) if (df is not None and not df.empty) else "(sem linhas)"
    resumo = _resumo_calculado(df)
    user_block = (
        f"Pergunta do gestor:\n{question}\n\n"
        f"RESUMO CALCULADO (valores exatos, já somados/contados pra você — use ESTES "
        f"para qualquer total ou quantidade; NUNCA some nem conte por conta própria):\n"
        f"{resumo}\n\n"
        f"Detalhe por linha (use só estes números; a tabela completa aparece abaixo da "
        f"sua resposta pro gestor):\n{data_md}"
    )
    messages = [{"role": "system", "content": NARRATOR_PROMPT}]
    # Um pouco de contexto do diálogo ajuda em perguntas de acompanhamento.
    if history:
        messages += [m for m in history[-4:] if m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": user_block})
    return _chat(messages, temperature=0.3, max_tokens=700).strip()


# ══════════════════════════════════════════════════════════════════════════════
# Função principal — STATELESS
# ══════════════════════════════════════════════════════════════════════════════
def oraculo_chat(message: str, history: list[dict] | None = None) -> dict:
    """Uma rodada de conversa com o Oráculo (sem estado de servidor).

    Args:
        message: pergunta do usuário.
        history: histórico [{role, content}, ...] mantido pelo cliente (React).
                 Usamos os últimos 12 turnos.

    Returns:
        {
          "answer": <markdown SEM o bloco sql>,
          "rows": <lista de dicts JSON-safe do resultado, ou []>,
          "truncated": <bool: houve mais linhas do que as exibidas>,
          "debug_sql": <sql extraído ou None>,
          "ok": <bool>,
        }
    """
    if not ready():
        return {
            "answer": "O Oráculo está indisponível: configure OPENAI_API_KEY no ambiente do backend.",
            "rows": [],
            "truncated": False,
            "debug_sql": None,
            "ok": False,
        }

    # ── PASSADA 1 — decidir modo e (se preciso) gerar a consulta ──────────────
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages += history[-12:]
    messages.append({"role": "user", "content": message})

    try:
        plan = _chat(messages, temperature=0.1, max_tokens=900)
    except Exception as e:
        return {
            "answer": "O Oráculo não conseguiu consultar agora. Tente novamente em instantes.",
            "rows": [], "truncated": False, "debug_sql": None, "ok": False, "error": str(e),
        }

    sql = _extract_sql(plan)

    # ── MODO CONCEITO — sem consulta: a própria passada 1 é a resposta ────────
    if not sql:
        return {
            "answer": _strip_sql_block(plan).strip(),
            "rows": [], "truncated": False, "debug_sql": None, "ok": True,
        }

    # ── MODO DADOS — valida o SQL antes de tocar o BigQuery ───────────────────
    ok_sql, motivo = validate_sql(sql)
    if not ok_sql:
        return {
            "answer": "Não consegui montar essa consulta com segurança. Tente reformular a "
                      "pergunta ou peça por outro recorte (cliente, vendedor, período).",
            "rows": [], "truncated": False, "debug_sql": sql, "ok": False,
            "error": f"guardrail: {motivo}",
        }

    # ── Execução com teto de custo + LIMIT forçado ────────────────────────────
    try:
        df = _run_sql(sql)
    except Exception as e:
        return {
            "answer": "Não foi possível consultar os dados desta vez. Tente novamente em instantes.",
            "rows": [], "truncated": False, "debug_sql": sql, "ok": False, "error": str(e),
        }

    rows = _rows_json_safe(df) if (df is not None and not df.empty) else []
    truncated = bool(df is not None and len(df) > 20)

    # ── PASSADA 2 — narrar SOBRE o dado real (nunca sobre chute) ──────────────
    try:
        answer = _narrate(message, df, history)
    except Exception:
        # Se a narração falhar, ainda devolvemos as linhas (o front mostra a tabela).
        answer = ("Consulta concluída. Veja o resultado abaixo." if rows
                  else "Consulta executada — nenhum resultado para esse filtro.")

    return {
        "answer": answer.strip(),
        "rows": rows[:50],       # teto de linhas pra tabela do front
        "truncated": truncated,
        "debug_sql": sql,
        "ok": True,
    }
