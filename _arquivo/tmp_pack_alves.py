"""Empacota os 3 CSVs + resumo executivo num único ZIP para o Alves."""
import sys, io, zipfile
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

dl = Path(r'C:\Users\gusta\Downloads')
arquivos = [
    'carteira_so_atual_nao_na_nova.csv',
    'carteira_nova_falta_adicionar.csv',
    'carteira_conflito_vendedor.csv',
]

# README incluso no zip
readme = """\
ANALISE DE CORRELACAO — Carteira Inside Sales (Atualizada) x Sistema atual
Gerado: 25/05/2026 (apos reuniao Gustavo + Albert + Alves)

Fontes cruzadas:
  - PLANILHA: Carteira de Clientes - Inside Sales (Atualizado).xlsx
  - PLANILHA: Farmers Farmacias (version 1).xlsx (aba Ribeiro)
  - BASE BQ:  silver_comercial.param_com_rfv_carteira (clientes ativos)

Chave de cruzamento: ID ERP

================================================================
RESUMO EXECUTIVO
================================================================

CARTEIRA ATUAL (BQ):   1.112 clientes ativos
NOVA CARTEIRA TOTAL:   1.934 clientes (Hosp+SAC: 1.673 + Farmácia: 262)

Match (ID ERP bate):             1.016 (91,4% da carteira atual)
Sô na carteira atual:               96 (decidir: cliente novo OU inativo)
Sô na nova planilha:               982 (adicionar com vendedor da nova)

================================================================
MUDANCAS DE VENDEDOR (do match — 1.016 clientes)
================================================================

Guilherme atual (258)  -> 101 ficam, 157 mudam (57 Richard, 39 Kauan Ramos, 38 Kaua, 21 Eduardo, 2 Geovanna)
Kaua atual (149)       -> 48 ficam, 101 mudam (41 Richard, 34 Kauan Ramos, 20 Eduardo, 4 Guilherme, 2 Geovanna)
Richard atual (83)     -> 82 ficam, 1 vai pra Kauan Ramos
Ramos atual (54)       -> 100% viram Kauan Ramos (rename oficializado)
Ribeiro atual (248)    -> 100% viram Caua Ribeiro (rename oficializado)
Giovanna atual (8)     -> 6 viram Geovanna Gomes, 2 viram Kauan Ramos
Eduardo atual (2)      -> 100% viram Eduardo Marques
Sem Vendedor (214)     -> TODOS GANHAM DONO (129 Geovanna, 40 Kauan Ramos, 22 Kaua,
                          18 Guilherme, 5 Eduardo)

================================================================
NOVOS PARA ADICIONAR (982 clientes da nova planilha)
================================================================

Richard Lucas:      254
Kauan Ramos:        219
Guilherme Aquino:   192
Kaua Rodrigues:     187
Geovanna Gomes:      83
Eduardo Marques:     33
Caua Ribeiro:        14

================================================================
ARQUIVOS NESTE ZIP
================================================================

1) carteira_so_atual_nao_na_nova.csv
   96 clientes da carteira atual que NAO aparecem na nova planilha.
   Alves precisa decidir: descontinuados ou cliente novo a manter?

2) carteira_nova_falta_adicionar.csv
   982 clientes da nova planilha que ainda nao estao na carteira BQ.
   Serao inseridos com vendedor conforme planilha.

3) carteira_conflito_vendedor.csv
   1.016 clientes do match com vendedor atual x novo.
   Filtrar onde vendedor_atual != vendedor_nova para ver mudancas.

================================================================
APROVACAO PENDENTE
================================================================

Apos seu OK, vamos:
  - Substituir param_com_rfv_carteira pela nova base (1.934 clientes)
  - Renomear "Sem Vendedor" -> "Cliente Novo" no dashboard
  - Aplicar regra Giovanna so em SAC (se decisao for manter)
  - Re-rodar RFV historico (Jan-Mai 2026) com nova carteira
"""

zip_path = dl / 'carteira_correlacao_25-05-2026.zip'
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    z.writestr('LEIA-ME.txt', readme)
    for arq in arquivos:
        p = dl / arq
        if p.exists():
            z.write(p, arq)
            print(f'  OK: {arq} ({p.stat().st_size:,} bytes)')
        else:
            print(f'  FALTA: {arq}')

print(f'\nZIP gerado: {zip_path}')
print(f'Tamanho: {zip_path.stat().st_size:,} bytes')
