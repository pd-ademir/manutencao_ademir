
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from .models import db, SolicitacaoServico, Placa
from .extensions import csrf  # Importa o objeto csrf
from datetime import datetime
import requests
import os

ss_bp = Blueprint('ss', __name__, url_prefix='/ss')

def enviar_para_outra_app(dados):
    """
    Envia os dados da solicitação para a API do sistema de checklist.
    """
    url_api_checklist = os.environ.get('URL_API_CHECKLIST', 'URL_DA_OUTRA_APP') 
    
    if url_api_checklist == 'URL_DA_OUTRA_APP':
        print("AVISO: A URL da API de Checklist não está configurada. Usando valor padrão.")

    try:
        # --- AJUSTE NO PAYLOAD PARA CORRESPONDER À API DE DESTINO ---
        payload = {
            'placa': dados.get('placa'),
            'descricao': dados.get('descricao'),
            'solicitante': dados.get('solicitante'), 
            'id_externo': dados.get('id_local')
        }
        
        response = requests.post(url_api_checklist, json=payload)
        response.raise_for_status()
        
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar dados para a API do Checklist: {e}")
        return None

@ss_bp.route('/solicitar', methods=['GET', 'POST'])
@login_required
def solicitar_servico():
    if request.method == 'POST':
        placa = request.form.get('placa')
        descricao = request.form.get('descricao')
        data_previsao_str = request.form.get('data_previsao_parada')

        if not placa or not descricao or not data_previsao_str:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return redirect(url_for('ss.solicitar_servico'))

        try:
            data_previsao_parada = datetime.strptime(data_previsao_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
            return redirect(url_for('ss.solicitar_servico'))

        nova_ss = SolicitacaoServico(
            placa=placa,
            descricao=descricao,
            data_previsao_parada=data_previsao_parada,
            usuario_id=current_user.id,
            status='Enviando...'
        )
        db.session.add(nova_ss)
        db.session.commit()

        # --- AJUSTE NOS DADOS ENVIADOS PARA A API ---
        dados_para_api = {
            'id_local': nova_ss.id,
            'placa': nova_ss.placa,
            'descricao': nova_ss.descricao,
            'solicitante': current_user.nome
        }
        resultado_api = enviar_para_outra_app(dados_para_api)

        # --- AJUSTE NA LEITURA DA RESPOSTA DA API ---
        if resultado_api and resultado_api.get('status') == 'sucesso' and 'id_interno' in resultado_api:
            nova_ss.id_externo = str(resultado_api['id_interno'])
            nova_ss.status = 'Em Análise' # Status inicial após envio com sucesso
            flash('Solicitação de serviço enviada e registrada com sucesso no sistema de checklist!', 'success')
        else:
            nova_ss.status = 'Erro no Envio'
            # Captura a mensagem de erro da API, se disponível
            msg_erro_api = resultado_api.get('mensagem') if resultado_api else 'Falha na comunicação.'
            flash(f'A solicitação foi salva localmente, mas falhou ao enviar: {msg_erro_api}', 'danger')
        
        db.session.commit()

        return redirect(url_for('ss.solicitar_servico'))

    # --- LÓGICA DE FILTRO DE PLACAS E SOLICITAÇÕES ---
    query_placas = Placa.query
    query_solicitacoes = SolicitacaoServico.query

    if current_user.filial:
        placas_filial = [p.placa for p in Placa.query.filter_by(filial=current_user.filial).all()]
        query_placas = query_placas.filter(Placa.filial == current_user.filial)
        query_solicitacoes = query_solicitacoes.filter(SolicitacaoServico.placa.in_(placas_filial))

    if current_user.unidade:
        placas_unidade = [p.placa for p in Placa.query.filter_by(unidade=current_user.unidade).all()]
        query_placas = query_placas.filter(Placa.unidade == current_user.unidade)
        query_solicitacoes = query_solicitacoes.filter(SolicitacaoServico.placa.in_(placas_unidade))

    placas = query_placas.order_by(Placa.placa).all()
    solicitacoes = query_solicitacoes.order_by(SolicitacaoServico.data_solicitacao.desc()).all()

    return render_template('solicitacao_servico.html', solicitacoes=solicitacoes, placas=placas)


@ss_bp.route('/webhook/atualizar_status', methods=['POST'])
@csrf.exempt  # Isenta esta rota da verificação de CSRF
def webhook_atualizar_status():
    """
    Endpoint para receber atualizações de status do sistema de checklist.
    Ele deve enviar o ID que nós fornecemos (nosso id_local).
    """
    dados = request.json
    if not dados or 'id_externo' not in dados:
        return jsonify({"status": "erro", "mensagem": "Dados inválidos ou id_externo (nosso ID local) ausente"}), 400

    # O checklist nos chama de volta usando o ID que enviamos no campo 'id_externo' deles
    nosso_id_local = str(dados.get('id_externo')) 
    solicitacao = SolicitacaoServico.query.filter_by(id=nosso_id_local).first()
    
    if not solicitacao:
        return jsonify({"status": "erro", "mensagem": f"Solicitação com ID local {nosso_id_local} não encontrada"}), 404

    solicitacao.status = dados.get('novo_status', solicitacao.status)
    solicitacao.observacao_externa = dados.get('observacao', solicitacao.observacao_externa)
    solicitacao.data_resposta_externa = datetime.utcnow()
    
    db.session.commit()
    
    print(f"Webhook: Status da SS com ID {solicitacao.id} atualizado para '{solicitacao.status}'")
    
    return jsonify({"status": "recebido"}), 200
