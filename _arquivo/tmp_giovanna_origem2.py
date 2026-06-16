"""De onde vem 'Giovanna' na carteira? Listar todas as abas dos 3 xlsx."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

files = {
    'HOSPITALAR': r'C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026 (1).xlsx',
    'FARMACIAS':  r'C:\Users\gusta\Downloads\RFV Farmácias 01-04-2025 até 30-04-2026 (1).xlsx',
    'SAC':        r'C:\Users\gusta\Downloads\RFV SAC 01-04-2025 até 30-04-2026 (1).xlsx',
}

# Os 7 clientes HOSPITALAR Giovanna
codes_hosp = ['51693', '598', '47610', '47901', '914330', '46589', '51689']
nomes_hosp = [
    'ALBB VENDAS E ASSISTENCIA TECNICA HOSPITALAR LTDA',
    'CICAVEL CIRURGICA CASCAVEL LTDA',
    'EMPRESA BRASILEIRA DE SERVICOS HOSPITALARES',
    'EMPRESA BRASILEIRA DE SERVICOS HOSPITALARES - EBSERH',
    'LUMINO ODONTOLOGIA UNIPESSOAL LTDA',
]

for fam, path in files.items():
    print('=' * 80)
    print(f'{fam} — abas em {path.split(chr(92))[-1]}')
    print('=' * 80)
    try:
        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            print(f'  - "{sheet}"')
            # Se for aba com Giovanna no nome, lista clientes
            if 'GIOVAN' in sheet.upper() or 'GEOVAN' in sheet.upper():
                df = pd.read_excel(path, sheet_name=sheet)
                print(f'    >>> {len(df)} linhas')
                if 'ID - CLIENTE' in df.columns:
                    print('    Clientes:')
                    print('    ' + '\n    '.join(df['ID - CLIENTE'].dropna().astype(str).head(20).tolist()))
    except Exception as e:
        print(f'  Erro: {e}')
    print()

# Procura nome exato Giovanna nas abas Hospitalar
print('=' * 80)
print('Procurando "Giovan*" / "Geovan*" em TODAS as abas Hospitalar:')
print('=' * 80)
path = files['HOSPITALAR']
xls = pd.ExcelFile(path)
for sheet in xls.sheet_names:
    try:
        df = pd.read_excel(path, sheet_name=sheet)
        for col in df.columns:
            try:
                ser = df[col].astype(str).str.upper()
                if ser.str.contains('GIOVAN|GEOVAN', na=False).any():
                    matches = df[ser.str.contains('GIOVAN|GEOVAN', na=False)]
                    print(f'\n  Aba "{sheet}", coluna "{col}": {len(matches)} matches')
                    print(matches[[col]].head(10).to_string(index=False))
            except Exception:
                pass
    except Exception:
        pass
