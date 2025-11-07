
# app/api_routes.py

from flask import Blueprint, request, jsonify, current_app
from .models import db, Placa, Veiculo, Motorista, SolicitacaoServico, registrar_log_api
from datetime import datetime
import traceback
import sys

# Cria um novo Blueprint para as rotas da API externa
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/webhook/checklist', methods=['POST'])
def receive_checklist_data():
    """
    Endpoint para receber uma Solicitação de Serviço (via JSON) do sistema de checklist.
    Exige uma chave de API no cabeçalho 'X-API-KEY' para autenticação.
    """
    # 1. Segurança: Verifica se a chave da API foi enviada no cabeçalho
    api_key = request.headers.get('X-API-KEY')
    if not api_key or api_key != current_app.config.get('CHECKLIST_API_KEY'):
        return jsonify({'status': 'erro', 'mensagem': 'Chave de API inválida ou ausente.'}), 401

    # 2. Pega os dados JSON enviados pelo sistema de checklist
    data = request.get_json()
    if not data:
        return jsonify({'status': 'erro', 'mensagem': 'Nenhum dado JSON recebido.'}), 400

    # 3. Validação dos campos obrigatórios do payload
    placa_str = data.get('placa_veiculo')
    item_checklist = data.get('item_checklist')
    nome_solicitante = data.get('nome_solicitante')

    if not all([placa_str, item_checklist, nome_solicitante]):
        return jsonify({'status': 'erro', 'mensagem': 'Dados incompletos. "placa_veiculo", "item_checklist" e "nome_solicitante" são obrigatórios.'}), 400

    try:
        # 4. Busca os objetos no banco de dados
        veiculo = Veiculo.query.join(Placa).filter(Placa.placa == placa_str.upper()).first()
        if not veiculo:
            return jsonify({'status': 'erro', 'mensagem': f'Veículo com placa {placa_str} não encontrado no sistema.'}), 404

        motorista = Motorista.query.filter(Motorista.nome == nome_solicitante.upper()).first()
        if not motorista:
            return jsonify({'status': 'erro', 'mensagem': f'Motorista "{nome_solicitante}" não encontrado no sistema.'}), 404

        # 5. Cria a nova Solicitação de Serviço
        nova_ss = SolicitacaoServico(
            veiculo_id=veiculo.id, # Associa ao Veiculo (conjunto)
            motorista_id=motorista.id,
            item_servico=item_checklist,
            descricao=data.get('observacao_motorista', ''),
            data_solicitacao=datetime.utcnow(),
            status='PENDENTE', # Status inicial padrão
            origem='Checklist Externo',
            id_origem_checklist=data.get('id_origem_checklist')
        )

        db.session.add(nova_ss)
        db.session.commit()

        # 6. Registra a ação no log do sistema
        registrar_log_api(
            acao=f"SS Criada via Webhook: {item_checklist}", 
            info_adicional=f"Placa: {placa_str}, Motorista: {nome_solicitante}, ID Externo: {data.get('id_origem_checklist')}"
        )

        return jsonify({'status': 'sucesso', 'mensagem': f'Solicitação de serviço para "{item_checklist}" da placa {placa_str} criada com sucesso.', 'ss_id': nova_ss.id}), 201

    except Exception as e:
        db.session.rollback()
        traceback.print_exc(file=sys.stderr)
        return jsonify({'status': 'erro', 'mensagem': f'Erro interno no servidor: {str(e)}'}), 500
