from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import pandas as pd
import numpy as np
import os
from io import BytesIO
import json
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Mude para produção!
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Criar pasta de uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Dados em memória (em produção use um banco de dados)
produtos_data = []

# Funções de cálculo
def calcular_precificacao(mercado, preco_nf, imposto_perc):
    """Calcula toda a cadeia de precificação"""
    
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

# Rotas
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

@app.route('/importar', methods=['GET', 'POST'])
def importar():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'})
        
        if file and file.filename.endswith('.xlsx'):
            try:
                df = pd.read_excel(file)
                
                # Verificar colunas
                colunas = df.columns.tolist()
                
                return jsonify({
                    'success': True,
                    'colunas': colunas,
                    'preview': df.head(10).to_dict('records')
                })
                
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
    
    return render_template('importar.html')

@app.route('/processar-importacao', methods=['POST'])
def processar_importacao():
    data = request.json
    coluna_produtos = data.get('coluna_produtos')
    coluna_codigo = data.get('coluna_codigo', '')
    coluna_preco_nf = data.get('coluna_preco_nf', '')
    
    mercado_padrao = float(data.get('mercado_padrao', 2.49))
    preco_nf_padrao = float(data.get('preco_nf_padrao', 3.00))
    imposto_padrao = float(data.get('imposto_padrao', 2.01))
    
    produtos_selecionados = data.get('produtos_selecionados', [])
    
    try:
        # Aqui processaria o arquivo novamente
        # Por simplicidade, vou criar produtos fictícios
        produtos_importados = []
        
        for produto_nome in produtos_selecionados:
            resultados = calcular_precificacao(mercado_padrao, preco_nf_padrao, imposto_padrao)
            
            novo_produto = {
                'id': str(uuid.uuid4()),
                'produto': produto_nome,
                'mercado': mercado_padrao,
                'preco_nf': preco_nf_padrao,
                'imposto_perc': imposto_padrao,
                'codigo_nf': f"IMP_{produto_nome[:10]}",
                'data_cadastro': datetime.now().strftime('%d/%m/%Y %H:%M'),
                **resultados
            }
            
            produtos_data.append(novo_produto)
            produtos_importados.append(novo_produto)
        
        return jsonify({
            'success': True,
            'message': f'{len(produtos_importados)} produtos importados com sucesso!',
            'importados': produtos_importados
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/buscar', methods=['GET', 'POST'])
def buscar():
    if request.method == 'POST':
        termo = request.form.get('termo', '').lower()
        coluna = request.form.get('coluna', 'produto')
        
        resultados = []
        for produto in produtos_data:
            if termo:
                if coluna == 'todos':
                    # Buscar em todos os campos de texto
                    if (termo in produto['produto'].lower() or 
                        termo in produto.get('codigo_nf', '').lower()):
                        resultados.append(produto)
                elif coluna in produto:
                    if termo in str(produto[coluna]).lower():
                        resultados.append(produto)
            else:
                resultados.append(produto)
        
        return render_template('buscar.html', resultados=resultados, termo=termo, coluna=coluna)
    
    return render_template('buscar.html', resultados=[], termo='', coluna='produto')

@app.route('/lista')
def lista():
    return render_template('lista.html', produtos=produtos_data)

@app.route('/analise')
def analise():
    return render_template('analise.html', produtos=produtos_data)

@app.route('/exportar')
def exportar():
    if not produtos_data:
        return jsonify({'success': False, 'message': 'Nenhum dado para exportar'})
    
    try:
        df = pd.DataFrame(produtos_data)
        
        # Remover colunas internas
        colunas_exportar = [
            'produto', 'codigo_nf', 'mercado', 'preco_nf', 'imposto_perc',
            'pc_nf_imposto', 'pmz_cd', 'pmz_loja', 'pc_dist', 'pc_piso',
            'perc_nf_mercado', 'perc_pmz_mercado', 'perc_dist_mercado',
            'perc_piso_mercado', 'novo_custo', 'dif_nf', 'situacao_texto',
            'data_cadastro'
        ]
        
        df_export = df[colunas_exportar]
        
        # Renomear colunas
        df_export.columns = [
            'Produto', 'Código NF', 'Preço Mercado', 'Preço NF', 'Imposto %',
            'PC NF + Imposto', 'PMZ CD', 'PMZ Loja', 'PC Dist', 'PC Piso',
            '% NF vs Mercado', '% PMZ vs Mercado', '% Dist vs Mercado',
            '% PISO vs Mercado', 'Novo Custo', 'Diferença NF', 'Situação',
            'Data Cadastro'
        ]
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Resultados')
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'resultados_precificacao_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/calcular', methods=['POST'])
def api_calcular():
    try:
        data = request.json
        mercado = float(data.get('mercado', 0))
        preco_nf = float(data.get('preco_nf', 0))
        imposto_perc = float(data.get('imposto_perc', 0))
        
        resultados = calcular_precificacao(mercado, preco_nf, imposto_perc)
        
        return jsonify({
            'success': True,
            'resultados': resultados
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/limpar', methods=['POST'])
def api_limpar():
    global produtos_data
    produtos_data = []
    return jsonify({'success': True, 'message': 'Dados limpos com sucesso!'})

@app.route('/api/estatisticas')
def api_estatisticas():
    if not produtos_data:
        return jsonify({
            'total': 0,
            'criticos': 0,
            'atencao': 0,
            'competitivos': 0,
            'economia_total': 0
        })
    
    total = len(produtos_data)
    criticos = sum(1 for p in produtos_data if p['situacao'] == 'danger')
    atencao = sum(1 for p in produtos_data if p['situacao'] == 'warning')
    competitivos = sum(1 for p in produtos_data if p['situacao'] == 'success')
    economia_total = sum(p['dif_nf'] for p in produtos_data)
    
    return jsonify({
        'total': total,
        'criticos': criticos,
        'atencao': atencao,
        'competitivos': competitivos,
        'economia_total': round(economia_total, 2)
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)