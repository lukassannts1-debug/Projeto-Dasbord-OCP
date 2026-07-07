import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import pandas as pd

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'uma_chave_secreta_qualquer_aqui')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- ROTA 1: PÁGINA INICIAL (LOGIN) ---
@app.route('/')
def home():
    return render_template('index.html')

# --- ROTA 2: DASHBOARD ---
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    nome = request.form.get('nome') if request.method == 'POST' else "Engenheiro"
    # Pega os dados armazenados apenas para a sessão do usuário atual
    dados_dashboard = session.get('dados_dashboard', {})
    return render_template('dashboard.html', nome=nome, dados=dados_dashboard)

# --- FUNÇÕES AUXILIARES ---
def contar_invalido(series):
    if series is None:
        return 0
    serie = series.fillna('').astype(str).str.strip()
    return int((serie == '').sum())


def contar_pendencias_por_etapa(df):
    # Conta pendências em cascata: Regional, COI e Proteção.
    # Coluna I=Regional, J=COI, K=Proteção.
    if df is None or df.empty:
        return [0, 0, 0]

    def coluna_str(index, fallback_name=None):
        if df.shape[1] > index:
            return df.iloc[:, index].fillna('').astype(str).str.strip()
        if fallback_name:
            return df.get(fallback_name, pd.Series([''] * len(df))).fillna('').astype(str).str.strip()
        return pd.Series([''] * len(df))

    regional = coluna_str(8, 'validação regional')
    coi = coluna_str(9, 'validação coi')
    protecao = coluna_str(10, 'validação proteção')

    valor_validado = 'Validado'
    valor_pendente = '0'

    pendencia_regional = int((regional == valor_pendente).sum())
    pendencia_coi = int(((regional == valor_validado) & (coi == valor_pendente)).sum())
    pendencia_protecao = int(((regional == valor_validado) & (coi == valor_validado) & (protecao == valor_pendente)).sum())

    return [pendencia_regional, pendencia_coi, pendencia_protecao]


def extrair_validado_por_mes(df):
    # Retorna labels (dinâmicos) e lista de contagens de validados (coluna L == 'Sim') agrupados por mês
    # Agora usa a Coluna C (índice 2) para identificar o mês e agrupa todos os meses presentes.
    month_names_pt = {
        1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
    }

    if df is None or df.empty:
        return [], []

    # Verifica se há coluna L (índice 11)
    if df.shape[1] <= 11:
        return [], []

    status_series = df.iloc[:, 11].fillna('').astype(str).str.strip().str.upper()
    month_series = df.iloc[:, 2].fillna('').astype(str).str.strip()

    from collections import Counter
    counts = Counter()

    for status, m in zip(status_series, month_series):
        if status == 'SIM':
            mes_num = None
            # tenta interpretar como data
            dt = pd.to_datetime(m, dayfirst=True, errors='coerce')
            if not pd.isna(dt):
                mes_num = int(dt.month)
            else:
                s = str(m).strip()
                # se for número de mês
                if s.isdigit():
                    n = int(s)
                    if 1 <= n <= 12:
                        mes_num = n
                else:
                    key = s.upper()[:3]
                    if key.startswith('JAN') or key.startswith('JANE'):
                        mes_num = 1
                    elif key.startswith('FEV') or key.startswith('FEB'):
                        mes_num = 2
                    elif key.startswith('MAR'):
                        mes_num = 3
                    elif key.startswith('ABR') or key.startswith('APR'):
                        mes_num = 4
                    elif key.startswith('MAI') or key.startswith('MAY'):
                        mes_num = 5
                    elif key.startswith('JUN'):
                        mes_num = 6
                    elif key.startswith('JUL'):
                        mes_num = 7
                    elif key.startswith('AGO') or key.startswith('AUG'):
                        mes_num = 8
                    elif key.startswith('SET') or key.startswith('SEP'):
                        mes_num = 9
                    elif key.startswith('OUT') or key.startswith('OCT'):
                        mes_num = 10
                    elif key.startswith('NOV'):
                        mes_num = 11
                    elif key.startswith('DEZ') or key.startswith('DEC'):
                        mes_num = 12

            if mes_num and 1 <= mes_num <= 12:
                counts[mes_num] += 1

    if not counts:
        return [], []

    # Ordena por mês (1..12) e monta labels/values
    meses_presentes = sorted(counts.keys())
    labels = [month_names_pt[m] for m in meses_presentes]
    values = [int(counts[m]) for m in meses_presentes]

    return labels, values


def extrair_aderencia_por_regional(df):
    regionais = ['CENTRO', 'LESTE', 'NOROESTE', 'NORTE', 'SUL']
    if df is None or df.empty:
        return regionais, [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]

    # Coluna B: Regional
    if df.shape[1] > 1:
        regional_series = df.iloc[:, 1].fillna('').astype(str).str.strip().str.upper()
    else:
        regional_series = pd.Series([''] * len(df))

    # Coluna O: Meta
    meta_series = pd.Series(0, index=df.index)
    if df.shape[1] > 14:
        meta_series = pd.to_numeric(df.iloc[:, 14], errors='coerce').fillna(0)

    # Coluna P: Pontos Validados
    validado_series = pd.Series(0, index=df.index)
    if df.shape[1] > 15:
        validado_series = pd.to_numeric(df.iloc[:, 15], errors='coerce').fillna(0)

    metas_por_regional = []
    validados_por_regional = []

    for reg in regionais:
        filtro = regional_series == reg
        metas_por_regional.append(int(meta_series[filtro].sum()))
        validados_por_regional.append(int(validado_series[filtro].sum()))

    return regionais, metas_por_regional, validados_por_regional


# --- ROTA 3: UPLOAD E PROCESSAMENTO DA PLANILHA ---
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'documento' not in request.files:
            return "Nenhum arquivo enviado", 400

        arquivo = request.files['documento']
        if arquivo.filename == '':
            return "Nenhum arquivo selecionado", 400

        nome_seguro = secure_filename(arquivo.filename)
        caminho_salvamento = os.path.join(app.config['UPLOAD_FOLDER'], nome_seguro)
        arquivo.save(caminho_salvamento)

        try:
            if nome_seguro.lower().endswith('.csv'):
                df = pd.read_csv(caminho_salvamento)
            else:
                df = pd.read_excel(caminho_salvamento)

            df.columns = df.columns.str.strip().str.lower()

            # --- LÓGICA DE CÁLCULO DOS KPIs ---
            # Verifica se a planilha tem pelo menos 12 colunas (até a coluna L)
            if df.shape[1] >= 12:
                # Coluna C (Índice 2): Contar linhas com valor preenchido ignorando vazios
                col_c = df.iloc[:, 2].fillna('').astype(str).str.strip()
                total_equip = int((col_c != '').sum())
                
                # Coluna L (Índice 11): Tratar strings e contar 'SIM' e 'PENDENTE'
                df['validado'] = df.iloc[:, 11].fillna('').astype(str).str.strip().str.upper()
                validados_sim = int((df['validado'] == 'SIM').sum())
                nao_validados = int((df['validado'] == 'PENDENTE').sum())
            else:
                total_equip = validados_sim = nao_validados = 0
                df['validado'] = ''

            avanco_global = round((validados_sim / total_equip) * 100, 1) if total_equip > 0 else 0

            regionais = ['NORTE', 'CENTRO', 'NOROESTE', 'LESTE', 'SUL']
            regional_series = df.get('regional', pd.Series('', index=df.index)).fillna('').astype(str).str.strip().str.upper()
            detalhe_regional = []

            for r in regionais:
                df_r = df[regional_series == r]
                t_r = int(df_r.shape[0])
                v_s = int(df_r[df_r['validado'] == 'SIM'].shape[0])
                n_v = int(df_r[df_r['validado'] == 'PENDENTE'].shape[0])
                pct = round((v_s / t_r) * 100) if t_r > 0 else 0

                detalhe_regional.append({
                    'nome': r,
                    'total': t_r,
                    'sim': v_s,
                    'nao': n_v,
                    'pct': pct
                })

            fluxo_pendencias = contar_pendencias_por_etapa(df)
            regioes_aderencia, metas_aderencia, pontos_validados = extrair_aderencia_por_regional(df)

            # Extração de validados por mês (Janeiro a Junho)
            grafico_mensal_labels, grafico_mensal_validado = extrair_validado_por_mes(df)

            session['dados_dashboard'] = {
                'total': total_equip,
                'validados': validados_sim,
                'nao_validados': nao_validados,
                'avanco': avanco_global,
                'regionais': detalhe_regional,
                'grafico_fluxo': fluxo_pendencias,
                'aderencia_regional_labels': regioes_aderencia,
                'aderencia_regional_meta': metas_aderencia,
                'aderencia_regional_validados': pontos_validados
                ,
                'grafico_mensal_labels': grafico_mensal_labels,
                'grafico_mensal_validado': grafico_mensal_validado
            }

            os.remove(caminho_salvamento)
            flash('Planilha importada com sucesso!', 'success')

        except Exception as e:
            return f"Erro ao processar a planilha. Verifique os dados e colunas. Detalhe: {e}", 500

        return redirect(url_for('dashboard'))

    return render_template('upload.html')

# --- INICIALIZAÇÃO DO SERVIDOR ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)