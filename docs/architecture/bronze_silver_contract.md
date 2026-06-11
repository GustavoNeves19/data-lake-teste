# Contrato Bronze ↔ Silver — Data Lake Nevoni

> Documento criado em 28/05/2026 após reflexão arquitetural com o time.
> Origem: descoberta de que o `dim_partner` perdia 73% dos clientes (12.445 de
> 17.124) por aplicar `WHERE YDATEXC IS NULL` no extract.

## Princípio

Seguimos **Medallion Architecture** (Bronze → Silver → Gold).

| Camada | Função | Filtros permitidos | Filtros proibidos |
|---|---|---|---|
| **Bronze** (`dm_*`) | Replicar a fonte com **mínima** transformação | Filtros de **partição/domínio** que definem **o que** a tabela representa (ex: `YTIPOPE='S'` separa vendas de compras) | Filtros de **estado/regra de negócio** (`YDATEXC`, `is_active`, status etc.) |
| **Silver** (`silver_*`) | Aplicar regras de negócio, limpeza, enriquecimento | Tudo que é regra de negócio do domínio (ex: "RFV exclui notas canceladas") | Lógica de apresentação/agregação final |
| **Gold** (`gold_*`) | Agregações para consumo (KPIs, RFV scores) | Lógica de agregação, segmentação, scoring | — |

## O caso YDATEXC

`YDATEXC` é uma coluna padrão do ERP NSR presente em quase todas as tabelas.
Significa "data e hora em que o registro foi marcado como excluído" (soft-delete).

**A interpretação muda por tabela:**

| Tabela | O que `YDATEXC NOT NULL` significa |
|---|---|
| `[CLIENTES OU FORNECEDORES]` | Cadastro do cliente foi desativado |
| `[COMPRAS E VENDAS]` | Nota/pedido foi cancelado |
| `[ATENDENTES]` | Vendedor saiu/foi removido |
| `[NATUREZAS DE OPERAÇÕES]` | Natureza descontinuada |
| `[PAGAR E RECEBER]` | Título cancelado |

Em todos os casos, **o registro continua acessível** — o ERP nativo mostra ele
em consultas históricas. Por isso, o **bronze tem que replicar fielmente**:
trazer o registro junto com a marca de exclusão.

A decisão de filtrar (ou não) `YDATEXC` depende da **regra de negócio do silver**
e pode ser diferente caso a caso:

- **RFV Comercial**: exclui notas canceladas (`YDATEXC IS NULL` em `fact_sales_order`)
- **Auditoria financeira**: inclui canceladas pra reconciliar (`YDATEXC IS NULL OR YDATEXC IS NOT NULL`)
- **Carteira de clientes**: usa todos os cadastros (ativos + excluídos) pra resolver nomes históricos

## Contrato concreto

### Toda query de extract DEVE:

1. **NÃO** filtrar por `YDATEXC`
2. **EXPOR** a coluna como `excluded_at TIMESTAMP` no SELECT
3. Manter coluna `is_active BOOL` derivada (`CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END`) — facilita consumo no silver
4. Pode manter filtros de **partição** (`YTIPOPE`, `YENCDES`) que definem o domínio da tabela

### Todo silver DEVE:

1. Aplicar explicitamente a regra de negócio: `WHERE excluded_at IS NULL` (ou outro critério)
2. Documentar **por que** está filtrando (regra de negócio, fonte da decisão)
3. Quando NÃO filtrar (caso de uso histórico), também documentar o motivo

## Histórico de aplicação

| Data | Tabela | Ação |
|---|---|---|
| 28/05/2026 | `dim_partner` | Removido `WHERE YDATEXC IS NULL`; cobertura subiu de 27% para 100% dos clientes que compraram |
| 28/05/2026 | 37 demais queries do extract | Refator aplicando o contrato |
| 28/05/2026 | `silver_comercial.silver_com_vendas` | Adicionado `excluded_at IS NULL` explícito (notas canceladas continuam fora do RFV) |

## Anti-padrão a evitar

```sql
-- ❌ ERRADO — filtro de regra de negócio no extract (bronze)
SELECT YCODCLI, YNOMCLI
FROM [CLIENTES OU FORNECEDORES]
WHERE YDATEXC IS NULL                 -- regra de negócio no lugar errado
```

```sql
-- ✅ CORRETO — extract puro; filtro só no silver
-- Extract (dim_partner.sql):
SELECT
    YCODCLI AS partner_code,
    YNOMCLI AS partner_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM [CLIENTES OU FORNECEDORES]

-- Silver, quando a regra de negócio pedir:
SELECT * FROM dim_partner WHERE excluded_at IS NULL
```

## Por que o erro aconteceu

Em maio/2026 corrigimos um bug onde o silver_comercial filtrava notas
canceladas inadvertidamente — a "correção" foi mover `YDATEXC IS NULL` pras
queries do extract. Solução foi correta no sintoma (filtrar canceladas), mas
errada na camada (deveria estar no silver). Documento esse erro pra não repetir.
