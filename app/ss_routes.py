
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from .models import db, SolicitacaoServico, Placa, Usuario
from .extensions import csrf  # Importa o objeto csrf
from datetime import datetime
import requests
import os
from .permissoes import requer_tipo
from sqlalchemy.orm import joinedload
import logging

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)

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
        # ... (a lógica do POST para criar uma nova solicitação permanece a mesma) ...
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

        dados_para_api = {
            'id_local': nova_ss.id,
            'placa': nova_ss.placa,
            'descricao': nova_ss.descricao,
            'solicitante': current_user.nome
        }
        resultado_api = enviar_para_outra_app(dados_para_api)

        if resultado_api and resultado_api.get('status') == 'sucesso' and 'id_interno' in resultado_api:
            nova_ss.id_externo = str(resultado_api['id_interno'])
            nova_ss.status = 'Em Análise'
            flash('Solicitação de serviço enviada e registrada com sucesso no sistema de checklist!', 'success')
        else:
            nova_ss.status = 'Erro no Envio'
            msg_erro_api = resultado_api.get('mensagem') if resultado_api else 'Falha na comunicação.'
            flash(f'A solicitação foi salva localmente, mas falhou ao enviar: {msg_erro_api}', 'danger')
        
        db.session.commit()
        return redirect(url_for('ss.solicitar_servico'))

    # --- LÓGICA DE FILTRO ATUALIZADA PARA GET ---
    filial_filtro = request.args.get('filial', '')
    unidade_filtro = request.args.get('unidade', '')

    query_placas = Placa.query
    query_solicitacoes = SolicitacaoServico.query.options(joinedload(SolicitacaoServico.usuario))

    if current_user.tipo == 'adm':
        if filial_filtro:
            query_placas = query_placas.filter(Placa.filial == filial_filtro)
            query_solicitacoes = query_solicitacoes.join(Placa, SolicitacaoServico.placa == Placa.placa).filter(Placa.filial == filial_filtro)
        if unidade_filtro:
            query_placas = query_placas.filter(Placa.unidade == unidade_filtro)
            if not filial_filtro:
                 query_solicitacoes = query_solicitacoes.join(Placa, SolicitacaoServico.placa == Placa.placa)
            query_solicitacoes = query_solicitacoes.filter(Placa.unidade == unidade_filtro)
    else:
        if current_user.filial:
            query_placas = query_placas.filter(Placa.filial == current_user.filial)
            query_solicitacoes = query_solicitacoes.join(Placa, SolicitacaoServico.placa == Placa.placa).filter(Placa.filial == current_user.filial)
        if current_user.unidade:
            query_placas = query_placas.filter(Placa.unidade == current_user.unidade)
            if not current_user.filial:
                 query_solicitacoes = query_solicitacoes.join(Placa, SolicitacaoServico.placa == Placa.placa)
            query_solicitacoes = query_solicitacoes.filter(Placa.unidade == current_user.unidade)

    filiais_disponiveis = []
    unidades_disponiveis = []
    if current_user.tipo == 'adm':
        filiais_disponiveis = [f[0] for f in db.session.query(Placa.filial).distinct().order_by(Placa.filial).all() if f[0]]
        unidades_disponiveis = [u[0] for u in db.session.query(Placa.unidade).distinct().order_by(Placa.unidade).all() if u[0]]

    placas = query_placas.order_by(Placa.placa).all()
    solicitacoes = query_solicitacoes.order_by(SolicitacaoServico.data_solicitacao.desc()).all()

    return render_template('solicitacao_servico.html', 
                           solicitacoes=solicitacoes, 
                           placas=placas,
                           filiais_disponiveis=filiais_disponiveis,
                           unidades_disponiveis=unidades_disponiveis,
                           filial_selecionada=filial_filtro,
                           unidade_selecionada=unidade_filtro)

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

# --- ROTA DE GERENCIAMENTO COM FILTROS ---
@ss_bp.route('/gerenciar')
@login_required
@requer_tipo("master", "comum", "adm") # Protege a rota para perfis de gestão
def gerenciar_solicitacoes():
    """
    Página para o gestor de manutenção visualizar e gerenciar as SS.
    Filtra por filial/unidade do usuário, exceto para o tipo 'master'.
    """
    query_solicitacoes = SolicitacaoServico.query.options(joinedload(SolicitacaoServico.usuario))

    # Usuários 'master' veem tudo. Outros tipos são filtrados.
    if current_user.tipo != 'adm':
        if current_user.filial:
            placas_da_filial = [p.placa for p in Placa.query.filter_by(filial=current_user.filial).all()]
            query_solicitacoes = query_solicitacoes.filter(SolicitacaoServico.placa.in_(placas_da_filial))
        
        if current_user.unidade:
            placas_da_unidade = [p.placa for p in Placa.query.filter_by(unidade=current_user.unidade).all()]
            query_solicitacoes = query_solicitacoes.filter(SolicitacaoServico.placa.in_(placas_da_unidade))

    solicitacoes = query_solicitacoes.order_by(SolicitacaoServico.data_solicitacao.desc()).all()
    
    return render_template('gerenciar_solicitacoes.html', solicitacoes=solicitacoes)


# --- ROTA DE API ATUALIZADA PARA RECEBER SS DO CHECKLIST ---
@ss_bp.route('/api/ss/nova', methods=['POST'])
@csrf.exempt
def api_nova_ss():
    """
    Endpoint de API para criar uma nova Solicitação de Serviço a partir do sistema de Checklist.
    Requer autenticação via chave de API no cabeçalho X-API-KEY.
    """
    logging.info(f"API /api/ss/nova chamada com dados: {request.get_data()}")
    secret_key = os.environ.get('SECRET_API_KEY')
    if not secret_key:
        logging.error("FATAL: SECRET_API_KEY não está configurada no ambiente.")
        return jsonify({"status": "erro", "mensagem": "Serviço de API não configurado."}), 500

    api_key = request.headers.get('X-API-KEY')
    if not api_key or api_key != secret_key:
        logging.warning(f"API Key inválida ou ausente: {api_key}")
        return jsonify({"status": "erro", "mensagem": "Chave de API inválida ou ausente."}), 401

    dados = request.get_json()
    if not dados:
        logging.warning("API chamada sem corpo JSON.")
        return jsonify({"status": "erro", "mensagem": "Corpo da requisição deve ser JSON."}), 400

    placa_str = dados.get('placa')
    descricao_original = dados.get('descricao')
    if not placa_str or not descricao_original:
        return jsonify({"status": "erro", "mensagem": "'placa' e 'descricao' são obrigatórios."}), 400

    try:
        sistema_user = Usuario.query.filter_by(nome="Sistema").first()
        if not sistema_user:
            logging.error("CRÍTICO: Usuário 'Sistema' não encontrado no banco de dados.")
            return jsonify({"status": "erro", "mensagem": "Configuração interna: Usuário 'Sistema' não encontrado."}), 500

        # --- LÓGICA DE ATUALIZAÇÃO DA PLACA (CORRIGIDA) ---
        api_filial = dados.get('unidade_solicitante') # CORRIGIDO
        api_unidade = dados.get('operacao_solicitante') # CORRIGIDO

        placa_obj = Placa.query.filter_by(placa=placa_str).first()
        if placa_obj:
            if api_filial:
                placa_obj.filial = api_filial
                logging.info(f"Atualizando filial da placa {placa_str} para {api_filial}")
            if api_unidade:
                placa_obj.unidade = api_unidade
                logging.info(f"Atualizando unidade da placa {placa_str} para {api_unidade}")
        else:
            logging.warning(f"Placa {placa_str} recebida via API não foi encontrada no cadastro de placas.")

        # Monta a descrição para a SS
        solicitante_externo = dados.get('solicitante_externo')
        descricao_final = descricao_original
        if solicitante_externo:
            info_header = f"Enviado por: {solicitante_externo}"
            if api_filial:
                info_header += f" (Filial: {api_filial})"
            descricao_final = f"{info_header}\n--------------------\n{descricao_original}"

        nova_ss = SolicitacaoServico(
            placa=placa_str,            
            descricao=descricao_final,
            usuario_id=sistema_user.id,
            status='Recebido via API',
            data_previsao_parada=None
        )
        db.session.add(nova_ss)
        db.session.commit()
        logging.info(f"SS {nova_ss.id} para a placa {placa_str} criada com sucesso via API.")

        return jsonify({
            "status": "sucesso",
            "mensagem": "Solicitação de Serviço criada com sucesso.",
            "id_solicitacao": nova_ss.id
        }), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"EXCEÇÃO INESPERADA ao criar SS via API: {e}", exc_info=True)
        return jsonify({"status": "erro", "mensagem": "Erro interno no servidor ao processar a solicitação."}), 500
