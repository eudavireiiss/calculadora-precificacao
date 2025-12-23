from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import pandas as pd
import numpy as np
import os
from io import BytesIO
import json
from datetime import datetime
import uuid
import functools
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Mude para produção!
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Criar pasta de uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Dados em memória (em produção use um banco de dados)
produtos_data = []

# ID da sua planilha pública
SHEET_ID = "1gwu2QVQPCBBYdVJIIELcC3hj68h0p4yAwFjF6jsr3bE"

# Sistema de cache simples
cache_data = {}
cache_time = {}

# ========== FUNÇÕES DE CACHE ==========
def cache_result(minutes=5):
    """Decorador para cache de dados do Google Sheets"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}_{str(kwargs)}"
            
            # Verifica se está em cache e ainda válido
            if cache_key in cache_data:
                if datetime.now() - cache_time[cache_key] < timedelta(minutes=minutes):
                    print(f"Usando cache para {cache_key}")
                    return cache_data[cache_key]
            
            # Executa função e armazena em cache
            result = func(*args, **kwargs)
            cache_data[cache_key] = result
            cache_time[cache_key] = datetime.now()
            print(f"Cache atualizado para {cache_key}")
            
            return result
        return wrapper
    return decorator

# ========== FUNÇÕES PARA GOOGLE SHEETS ==========
@cache_result(minutes=10)  # Cache de 10 minutos para Google Sheets
def carregar_aba_sheets(aba_nome):
    """Carrega uma aba específica da sua planilha do Google Sheets"""
    try:
        # Formata a URL para CSV (forma mais simples)
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        
        # Carrega os dados
        df = pd.read_csv(url, encoding='utf-8')
        print(f"Aba '{aba_nome}' carregada: {df.shape[0]} linhas, {df.shape[1]} colunas")
        
        # Log das primeiras colunas para debug
        print(f"Colunas encontradas: {list(df.columns[:5])}...")
        
        return df
        
    except Exception as e:
        print(f"Erro ao carregar aba '{aba_nome}': {e}")
        return pd.DataFrame()

def carregar_todos_dados():
    """Carrega todas as abas relevantes da planilha"""
    # Adapte os nomes das abas conforme sua planilha
    abas = {
        'produtos': 'PRODUTOS',
        'tabela1': 'TABELA 1', 
        'tabela2': 'TABELA 2',
        'vendas': 'VENDAS'  # Adicione outras abas conforme necessário
    }
    
    dados = {}
    for key, aba_nome in abas.items():
        dados[key] = carregar_aba_sheets(aba_nome)
    
    return dados

def analisar_dados_vendas():
    """Análise específica para dashboard de vendas"""
    try:
        # Carrega dados da planilha
        dados = carregar_todos_dados()
        
        # Verifica quais abas foram carregadas com sucesso
        abas_carregadas = {k: v for k, v in dados.items() if not v.empty}
        print(f"Abas carregadas com sucesso: {list(abas_carregadas.keys())}")
        
        # Exemplo de análise com a aba PRODUTOS
        if 'produtos' in abas_carregadas:
            df_produtos = dados['produtos']
            
            # Tenta identificar colunas automaticamente
            colunas = df_produtos.columns.tolist()
            print(f"Colunas na aba PRODUTOS: {colunas}")
            
            # Processamento básico dos dados
            analise = {
                'total_registros': len(df_produtos),
                'colunas_disponiveis': colunas,
                'primeiros_registros': df_produtos.head().to_dict('records'),
                'estatisticas': {}
            }
            
            # Tenta calcular estatísticas para colunas numéricas
            for col in df_produtos.select_dtypes(include=[np.number]).columns:
                analise['estatisticas'][col] = {
                    'media': float(df_produtos[col].mean()),
                    'mediana': float(df_produtos[col].median()),
                    'min': float(df_produtos[col].min()),
                    'max': float(df_produtos[col].max()),
                    'soma': float(df_produtos[col].sum())
                }
            
            return analise
        
        return {'erro': 'Nenhuma aba relevante encontrada'}
        
    except Exception as e:
        print(f"Erro na análise: {e}")
        return {'erro': str(e)}

# ========== FUNÇÕES DE CÁLCULO EXISTENTES ==========
def calcular_precificacao(mercado, preco_nf, imposto_perc):
    """Calcula toda a cadeia de precificação"""
    # Seu código existente aqui (mantido igual)
    pc_nf_imposto = preco_nf * (1 + imposto_perc/100)
    pmz_cd = pc_nf_imposto * 1.101 * 1.03
    pmz_loja = pmz_cd
    pc_dist = pmz_loja * 1.087
    pc_piso = pmz_loja * 1.15
    
    # Percentuais vs Mercado
    perc_nf_mercado = (mercado / pc_nf_imposto - 1) * 100
    perc_pmz_mercado = (mercado / pmz_loja - 1) * 100
    perc_dist_mercado = (mercado / pc_dist - 1) * 100
    perc_piso_mercado = (mercado / pc_piso - 1) * 100
    
    # Novo custo necessário
    novo_custo = mercado / 1.15 / 1.03 / 1.101 / (1 + imposto_perc/100)
    dif_nf = novo_custo - preco_nf
    
    # Determinar situação
    if perc_piso_mercado >= 0:
        situacao = "success"
        situacao_texto = "Competitivo"
    elif perc_piso_mercado > -20:
        situacao = "warning"
        situacao_texto = "Atenção"
    else:
        situacao = "danger"
        situacao_texto = "Crítico"
    
    return {
        'pc_nf_imposto': round(pc_nf_imposto, 2),
        'pmz_cd': round(pmz_cd, 2),
        'pmz_loja': round(pmz_loja, 2),
        'pc_dist': round(pc_dist, 2),
        'pc_piso': round(pc_piso, 2),
        'perc_nf_mercado': round(perc_nf_mercado, 2),
        'perc_pmz_mercado': round(perc_pmz_mercado, 2),
        'perc_dist_mercado': round(perc_dist_mercado, 2),
        'perc_piso_mercado': round(perc_piso_mercado, 2),
        'novo_custo': round(novo_custo, 2),
        'dif_nf': round(dif_nf, 2),
        'situacao': situacao,
        'situacao_texto': situacao_texto
    }

# ========== NOVAS ROTAS PARA DASHBOARD ==========
@app.route('/dashboard')
def dashboard():
    """Página principal do dashboard"""
    # Carrega dados da planilha
    dados_sheets = analisar_dados_vendas()
    
    # Seu dashboard terá duas fontes de dados:
    # 1. Dados da planilha do Google Sheets
    # 2. Dados dos produtos calculados no app
    
    return render_template('dashboard.html', 
                         dados_sheets=dados_sheets,
                         produtos=produtos_data,
                         total_produtos=len(produtos_data))

@app.route('/api/dashboard/dados')
@cache_result(minutes=5)  # Cache de 5 minutos para API
def api_dashboard_dados():
    """API para dados do dashboard (usada por AJAX)"""
    dados_sheets = analisar_dados_vendas()
    
    return jsonify({
        'success': True,
        'dados_sheets': dados_sheets,
        'produtos_calculados': {
            'total': len(produtos_data),
            'criticos': sum(1 for p in produtos_data if p['situacao'] == 'danger'),
            'atencao': sum(1 for p in produtos_data if p['situacao'] == 'warning'),
            'competitivos': sum(1 for p in produtos_data if p['situacao'] == 'success'),
            'economia_total': round(sum(p['dif_nf'] for p in produtos_data), 2)
        },
        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    })

@app.route('/api/sheets/preview')
def api_sheets_preview():
    """API para visualizar dados da planilha"""
    aba = request.args.get('aba', 'PRODUTOS')
    limite = int(request.args.get('limite', 10))
    
    df = carregar_aba_sheets(aba)
    
    if df.empty:
        return jsonify({'success': False, 'message': 'Aba não encontrada ou vazia'})
    
    preview = df.head(limite).to_dict('records')
    colunas = df.columns.tolist()
    
    return jsonify({
        'success': True,
        'aba': aba,
        'colunas': colunas,
        'total_registros': len(df),
        'preview': preview
    })

# ========== ROTAS EXISTENTES (MANTIDAS) ==========
@app.route('/')
def index():
    return render_template('index.html', produtos=produtos_data)

@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar():
    if request.method == 'POST':
        try:
            produto = request.form.get('produto')
            mercado = float(request.form.get('mercado', 0))
            preco_nf = float(request.form.get('preco_nf', 0))
            imposto_perc = float(request.form.get('imposto_perc', 0))
            codigo_nf = request.form.get('codigo_nf', '')
            
            # Calcular
            resultados = calcular_precificacao(mercado, preco_nf, imposto_perc)
            
            # Criar produto
            novo_produto = {
                'id': str(uuid.uuid4()),
                'produto': produto,
                'mercado': mercado,
                'preco_nf': preco_nf,
                'imposto_perc': imposto_perc,
                'codigo_nf': codigo_nf,
                'data_cadastro': datetime.now().strftime('%d/%m/%Y %H:%M'),
                **resultados
            }
            
            produtos_data.append(novo_produto)
            
            return jsonify({
                'success': True,
                'message': 'Produto adicionado com sucesso!',
                'produto': novo_produto
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    return render_template('adicionar.html')

@app.route('/lista')
def lista():
    return render_template('lista.html', produtos=produtos_data)

@app.route('/analise')
def analise():
    return render_template('analise.html', produtos=produtos_data)

# ... (mantenha todas as outras rotas existentes)

if __name__ == '__main__':
    app.run(debug=True, port=5000)  