# app/veiculos_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from datetime import datetime
from .permissoes import filtrar_query_por_usuario
from .models import db, Veiculo, Placa, Usuario, VeiculoIndisponibilidade, registrar_log
from .permissoes import requer_tipo

veiculos_bp = Blueprint('veiculos', __name__)

# =================================================================================
# ROTA PRINCIPAL DE GERENCIAMENTO
# =================================================================================

# app/veiculos_routes.py

@veiculos_bp.route('/veiculos')
@login_required
@requer_tipo("master", "adm")
def gerenciar_veiculos():
    # Captura os parâmetros de filtro da URL
    filial_filtro = request.args.get('filial', '').upper()
    unidade_filtro = request.args.get('unidade', '').upper()
    
    # Inicia as queries básicas que serão filtradas
    veiculos_query = Veiculo.query
    placas_query = Placa.query

    # 1. Aplica o filtro de permissão padrão (usuário master vê apenas sua unidade)
    veiculos_query = filtrar_query_por_usuario(veiculos_query, Veiculo)
    placas_query = filtrar_query_por_usuario(placas_query, Placa)

    # 2. Aplica os filtros selecionados pelo usuário (se houver)
    if filial_filtro:
        veiculos_query = veiculos_query.filter(Veiculo.filial == filial_filtro)
        placas_query = placas_query.filter(Placa.filial == filial_filtro)
    
    if unidade_filtro:
        veiculos_query = veiculos_query.filter(Veiculo.unidade == unidade_filtro)
        placas_query = placas_query.filter(Placa.unidade == unidade_filtro)
        
    # Executa as queries filtradas
    lista_veiculos = veiculos_query.order_by(Veiculo.nome_conjunto).all()
    todas_as_placas = placas_query.order_by(Placa.placa).all()
    
    # --- Lógica para placas disponíveis ---
    placas_em_uso_ids = set()
    veiculos_ativos_placas = db.session.query(
        Veiculo.placa_cavalo_id, 
        Veiculo.placa_carreta1_id, 
        Veiculo.placa_carreta2_id
    ).filter(Veiculo.ativo == True).all()

    for p_ids in veiculos_ativos_placas:
        if p_ids[0]: placas_em_uso_ids.add(p_ids[0])
        if p_ids[1]: placas_em_uso_ids.add(p_ids[1])
        if p_ids[2]: placas_em_uso_ids.add(p_ids[2])

    placas_cavalo_disponiveis = [p for p in todas_as_placas if p.tipo in ['CAVALO', 'BITRUCK'] and p.id not in placas_em_uso_ids]
    placas_carreta_disponiveis = [p for p in todas_as_placas if p.tipo == 'CARRETA' and p.id not in placas_em_uso_ids]

    # 3. Prepara as listas para os menus de filtro e modais
    filiais_disponiveis = []
    unidades_disponiveis_geral = [] # Para modais
    unidades_disponiveis_filtro = [] # Para o filtro principal
    
    if current_user.tipo == 'adm':
        filiais_db = db.session.query(Placa.filial).distinct().order_by(Placa.filial).all()
        filiais_disponiveis = sorted([f[0] for f in filiais_db if f[0]])
        
        unidades_q = db.session.query(Placa.unidade).distinct()
        if filial_filtro:
            unidades_q = unidades_q.filter(Placa.filial == filial_filtro)
        unidades_db = unidades_q.order_by(Placa.unidade).all()
        unidades_disponiveis_filtro = sorted([u[0] for u in unidades_db if u[0]])
    
    # Lista de unidades para os modais deve ser sempre completa para o ADM
    unidades_geral_db = db.session.query(Placa.unidade).distinct().order_by(Placa.unidade).all()
    unidades_disponiveis_geral = sorted([u[0] for u in unidades_geral_db if u[0]])
        
    if current_user.tipo == 'master' and not current_user.unidade:
        unidades_disponiveis_filtro = unidades_disponiveis_geral

    return render_template(
        'veiculos.html', # CORRIGIDO AQUI
        veiculos=lista_veiculos,
        placas=todas_as_placas,
        placas_cavalo_disponiveis=placas_cavalo_disponiveis,
        placas_carreta_disponiveis=placas_carreta_disponiveis,
        filiais_disponiveis=filiais_disponiveis, # Para o filtro
        unidades_disponiveis=unidades_disponiveis_filtro, # Para o filtro
        unidades_gerais=unidades_disponiveis_geral, # Para os modais
        filial_selecionada=filial_filtro,
        unidade_selecionada=unidade_filtro,
        placas_em_uso_ids=placas_em_uso_ids
    )

# =================================================================================
# ROTAS PARA ADICIONAR, EDITAR E ALTERAR STATUS DO CONJUNTO
# =================================================================================

@veiculos_bp.route('/veiculos/add', methods=['POST'])
@login_required
@requer_tipo("master",'adm')
def add_veiculo():
    nome_conjunto = request.form.get('nome_conjunto')
    unidade = request.form.get('unidade')
    filial = request.form.get('filial')
    placa_cavalo_id = request.form.get('placa_cavalo_id')
    placa_carreta1_id = request.form.get('placa_carreta1_id')
    placa_carreta2_id = request.form.get('placa_carreta2_id')

    # --- INÍCIO DA VALIDAÇÃO DE DUPLICIDADE ---
    if placa_carreta1_id and placa_carreta1_id == placa_carreta2_id:
        flash('As placas da Carreta 1 e da Carreta 2 não podem ser iguais.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))
    # --- FIM DA VALIDAÇÃO ---

    if not nome_conjunto or not placa_cavalo_id:
        flash('Nome do conjunto e Placa do Cavalo/Bitruck são obrigatórios.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    # ... (restante da lógica, sem alterações)
    if current_user.tipo != 'adm':
        unidade = current_user.unidade

    if not unidade:
        flash('A unidade é obrigatória.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    if Veiculo.query.filter_by(nome_conjunto=nome_conjunto).first():
        flash(f'Já existe um conjunto com o nome "{nome_conjunto}".', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    placas_selecionadas_ids = {int(p_id) for p_id in [placa_cavalo_id, placa_carreta1_id, placa_carreta2_id] if p_id}
    placa_em_uso = Veiculo.query.filter(
        Veiculo.ativo == True,
        or_(
            Veiculo.placa_cavalo_id.in_(placas_selecionadas_ids),
            Veiculo.placa_carreta1_id.in_(placas_selecionadas_ids),
            Veiculo.placa_carreta2_id.in_(placas_selecionadas_ids)
        )
    ).first()

    if placa_em_uso:
        flash(f'Uma ou mais placas selecionadas já estão em uso no conjunto ativo "{placa_em_uso.nome_conjunto}".', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    novo_veiculo = Veiculo(
        nome_conjunto=nome_conjunto, 
        unidade=unidade,
        filial=filial,
        placa_cavalo_id=int(placa_cavalo_id) if placa_cavalo_id else None,
        placa_carreta1_id=int(placa_carreta1_id) if placa_carreta1_id else None,
        placa_carreta2_id=int(placa_carreta2_id) if placa_carreta2_id else None
    )
    db.session.add(novo_veiculo)
    db.session.commit()
    registrar_log(current_user, f"Adicionou o conjunto '{nome_conjunto}'")
    flash(f'Conjunto "{nome_conjunto}" adicionado com sucesso.', 'success')
    return redirect(url_for('veiculos.gerenciar_veiculos'))


@veiculos_bp.route('/veiculos/edit/<int:veiculo_id>', methods=['POST'])
@login_required
@requer_tipo("master",'adm')
def edit_veiculo(veiculo_id):
    veiculo = Veiculo.query.get_or_404(veiculo_id)

    # Verificação de permissão
    if current_user.tipo != 'adm' and veiculo.unidade != current_user.unidade:
        flash('Você não tem permissão para editar este conjunto.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))
        
    # Obter dados do formulário
    nova_unidade = request.form.get('unidade')
    nova_filial = request.form.get('filial')
    placa_cavalo_id = request.form.get('placa_cavalo_id')
    placa_carreta1_id = request.form.get('placa_carreta1_id')
    placa_carreta2_id = request.form.get('placa_carreta2_id')

    # Validações de placas (sem alteração)
    if placa_carreta1_id and placa_carreta1_id == placa_carreta2_id:
        flash('As placas da Carreta 1 e da Carreta 2 não podem ser iguais.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    placas_selecionadas_ids = {int(p_id) for p_id in [placa_cavalo_id, placa_carreta1_id, placa_carreta2_id] if p_id}
    conflito = Veiculo.query.filter(
        Veiculo.id != veiculo_id,
        Veiculo.ativo == True,
        or_(
            Veiculo.placa_cavalo_id.in_(placas_selecionadas_ids),
            Veiculo.placa_carreta1_id.in_(placas_selecionadas_ids),
            Veiculo.placa_carreta2_id.in_(placas_selecionadas_ids)
        )
    ).first()

    if conflito:
        flash(f'Uma ou mais placas selecionadas já estão em uso no conjunto ativo "{conflito.nome_conjunto}".', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    # Atualiza os dados do conjunto
    veiculo.nome_conjunto = request.form.get('nome_conjunto')
    veiculo.obs = request.form.get('obs')
    veiculo.placa_cavalo_id = int(placa_cavalo_id) if placa_cavalo_id else None
    veiculo.placa_carreta1_id = int(placa_carreta1_id) if placa_carreta1_id else None
    veiculo.placa_carreta2_id = int(placa_carreta2_id) if placa_carreta2_id else None

    # --- INÍCIO DA CORREÇÃO ---
    # Somente usuários 'adm' podem alterar a unidade/filial.
    # Ao alterar, a mudança é propagada para TODAS as placas associadas.
    if current_user.tipo == 'adm':
        veiculo.unidade = nova_unidade
        veiculo.filial = nova_filial
        
        # Propaga a nova unidade e filial para as placas do conjunto
        if veiculo.placa_cavalo:
            veiculo.placa_cavalo.unidade = nova_unidade
            veiculo.placa_cavalo.filial = nova_filial
        if veiculo.placa_carreta1:
            veiculo.placa_carreta1.unidade = nova_unidade
            veiculo.placa_carreta1.filial = nova_filial
        if veiculo.placa_carreta2:
            veiculo.placa_carreta2.unidade = nova_unidade
            veiculo.placa_carreta2.filial = nova_filial
    # --- FIM DA CORREÇÃO ---
    
    db.session.commit()
    registrar_log(current_user, f"Editou o conjunto '{veiculo.nome_conjunto}'")
    flash(f'Conjunto "{veiculo.nome_conjunto}" atualizado com sucesso.', 'success')
    return redirect(url_for('veiculos.gerenciar_veiculos'))



@veiculos_bp.route('/veiculos/toggle_status/<int:veiculo_id>', methods=['POST'])
@login_required
@requer_tipo("master",'adm')
def toggle_veiculo_status(veiculo_id):
    # ... (lógica de ativar/desativar, sem alterações)
    veiculo = Veiculo.query.get_or_404(veiculo_id)

    if current_user.tipo != 'adm' and veiculo.unidade != current_user.unidade:
        flash('Você não tem permissão para alterar este conjunto.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    if veiculo.ativo:
        veiculo.ativo = False
        indisponibilidade = VeiculoIndisponibilidade(
            veiculo_id=veiculo.id,
            motivo="Conjunto desativado pelo usuário.",
            usuario_id=current_user.id
        )
        db.session.add(indisponibilidade)
        
        if veiculo.motorista:
            veiculo.motorista.veiculo_id = None
            flash(f'O motorista {veiculo.motorista.nome} foi desvinculado do conjunto.', 'warning')
        
        db.session.commit()
        registrar_log(current_user, f"Desativou o conjunto '{veiculo.nome_conjunto}'")
        flash(f'Conjunto "{veiculo.nome_conjunto}" foi desativado e arquivado.', 'success')
    
    else:
        placas_do_veiculo_ids = {p_id for p_id in [veiculo.placa_cavalo_id, veiculo.placa_carreta1_id, veiculo.placa_carreta2_id] if p_id}
        conflito = Veiculo.query.filter(
            Veiculo.id != veiculo.id,
            Veiculo.ativo == True,
            or_(
                Veiculo.placa_cavalo_id.in_(placas_do_veiculo_ids),
                Veiculo.placa_carreta1_id.in_(placas_do_veiculo_ids),
                Veiculo.placa_carreta2_id.in_(placas_do_veiculo_ids)
            )
        ).first()

        if conflito:
            flash(f'Não foi possível reativar. Uma ou mais de suas placas já estão em uso no conjunto ativo "{conflito.nome_conjunto}".', 'danger')
            return redirect(url_for('veiculos.gerenciar_veiculos'))

        veiculo.ativo = True
        db.session.commit()
        registrar_log(current_user, f"Reativou o conjunto '{veiculo.nome_conjunto}'")
        flash(f'Conjunto "{veiculo.nome_conjunto}" foi reativado com sucesso.', 'success')

    return redirect(url_for('veiculos.gerenciar_veiculos'))

# =================================================================================
# ROTAS PARA GERENCIAR PLACAS INDIVIDUAIS (ADIÇÃO, EXCLUSÃO, DETALHES)
# =================================================================================

@veiculos_bp.route('/placas/add', methods=['POST'])
@login_required
@requer_tipo("master","adm")
def add_placa():
    # Captura e trata todos os dados do formulário para maiúsculas e sem espaços
    numero_placa = request.form.get('placa', '').strip().upper()
    tipo = request.form.get('tipo')
    fabricante = request.form.get('fabricante', '').strip().upper()
    modelo = request.form.get('modelo', '').strip().upper()
    unidade = request.form.get('unidade', '').strip().upper()
    filial = request.form.get('filial', '').strip().upper()

    # Validações principais
    if not numero_placa or not tipo:
        flash('Número da placa e tipo são obrigatórios.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    # Se o usuário não for ADM, a unidade é a dele (se houver)
    if current_user.tipo != 'adm' and current_user.unidade:
        unidade = current_user.unidade.upper()
    
    # Valida se a unidade foi definida
    if not unidade:
        flash('A unidade é obrigatória para cadastrar a placa.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    # Verifica se a placa já existe
    if Placa.query.filter_by(placa=numero_placa).first():
        flash(f'A placa {numero_placa} já está cadastrada.', 'warning')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    # Cria o novo objeto Placa com todos os campos tratados
    nova_placa = Placa(
        placa=numero_placa,
        tipo=tipo,
        fabricante=fabricante or None,
        modelo=modelo or None,
        unidade=unidade,
        filial=filial or None # Salva como None se a string for vazia
    )
    
    db.session.add(nova_placa)
    db.session.commit()
    
    registrar_log(current_user, f"Adicionou a placa '{nova_placa.placa}' na unidade {unidade}")
    flash(f'Placa {nova_placa.placa} adicionada com sucesso.', 'success')
    return redirect(url_for('veiculos.gerenciar_veiculos'))


@veiculos_bp.route('/placas/delete/<int:placa_id>', methods=['POST'])
@login_required
@requer_tipo("master",'adm')
def delete_placa(placa_id):
    # ... (lógica de deletar placa, sem alterações)
    placa = Placa.query.get_or_404(placa_id)

    if current_user.tipo != 'adm' and placa.unidade != current_user.unidade:
        flash('Você não tem permissão para excluir esta placa.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))
    
    veiculo_usando = Veiculo.query.filter(
        (Veiculo.placa_cavalo_id == placa.id) |
        (Veiculo.placa_carreta1_id == placa.id) |
        (Veiculo.placa_carreta2_id == placa.id)
    ).first()

    if veiculo_usando:
        flash(f'A placa {placa.placa} não pode ser excluída pois está em uso no conjunto "{veiculo_usando.nome_conjunto}".', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    placa_numero = placa.placa
    db.session.delete(placa)
    db.session.commit()
    
    registrar_log(current_user, f"Excluiu a placa '{placa_numero}'")
    flash(f'Placa {placa_numero} excluída com sucesso.', 'info')
    return redirect(url_for('veiculos.gerenciar_veiculos'))


@veiculos_bp.route('/placa/details/<int:placa_id>', methods=['GET'])
@login_required
@requer_tipo("master",'adm')
def get_placa_details(placa_id):
    # ... (lógica de detalhes da placa, sem alterações)
    placa = Placa.query.get_or_404(placa_id)
    
    if current_user.tipo != 'adm' and placa.unidade != current_user.unidade:
        return jsonify({'error': 'Acesso negado'}), 403

    return jsonify({
        'id': placa.id,
        'placa': placa.placa,
        'unidade': placa.unidade,
        'filial': placa.filial,
        'km_atual': placa.km_atual,
        'data_calibragem': placa.data_proxima_calibragem.strftime('%Y-%m-%d') if placa.data_proxima_calibragem else '',
        'km_troca_preventiva': placa.km_troca_preventiva,
        'km_ultima_revisao_preventiva': placa.km_ultima_revisao_preventiva,
        'km_troca_intermediaria': placa.km_troca_intermediaria,
        'km_ultima_revisao_intermediaria': placa.km_ultima_revisao_intermediaria,
        'intervalo_oleo_diferencial': placa.intervalo_oleo_diferencial,
        'troca_oleo_diferencial': placa.troca_oleo_diferencial,
        'intervalo_oleo_cambio': placa.intervalo_oleo_cambio,
        'troca_oleo_cambio': placa.troca_oleo_cambio,
    })


@veiculos_bp.route('/placa/update_details/<int:placa_id>', methods=['POST'])
@login_required
@requer_tipo("master",'adm')
def update_placa_details(placa_id):
    # ... (lógica de atualizar detalhes da placa, sem alterações)
    placa = Placa.query.get_or_404(placa_id)

    if current_user.tipo != 'adm' and placa.unidade != current_user.unidade:
        flash('Você não tem permissão para editar os detalhes desta placa.', 'danger')
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    def to_int_or_none(value):
        if value is None or value == '': return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    placa.unidade = request.form.get('unidade', placa.unidade)
    placa.filial = request.form.get('filial', placa.filial)
    placa.km_atual = to_int_or_none(request.form.get('km_atual'))
    
    data_calibragem_str = request.form.get('data_calibragem')
    if data_calibragem_str:
        placa.data_proxima_calibragem = datetime.strptime(data_calibragem_str, '%Y-%m-%d').date()
    else:
        placa.data_proxima_calibragem = None

    placa.km_troca_preventiva = to_int_or_none(request.form.get('km_troca_preventiva'))
    placa.km_ultima_revisao_preventiva = to_int_or_none(request.form.get('km_ultima_revisao_preventiva'))
    placa.km_troca_intermediaria = to_int_or_none(request.form.get('km_troca_intermediaria'))
    placa.km_ultima_revisao_intermediaria = to_int_or_none(request.form.get('km_ultima_revisao_intermediaria'))
    placa.intervalo_oleo_diferencial = to_int_or_none(request.form.get('intervalo_oleo_diferencial'))
    placa.troca_oleo_diferencial = to_int_or_none(request.form.get('troca_oleo_diferencial'))
    placa.intervalo_oleo_cambio = to_int_or_none(request.form.get('intervalo_oleo_cambio'))
    placa.troca_oleo_cambio = to_int_or_none(request.form.get('troca_oleo_cambio'))

    try:
        db.session.commit()
        registrar_log(current_user, f"Atualizou detalhes de manutenção da placa '{placa.placa}'")
        flash(f'Detalhes da placa {placa.placa} atualizados com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar a placa: {e}', 'danger')
        
    return redirect(url_for('veiculos.gerenciar_veiculos'))


@veiculos_bp.route('/api/unidades_por_filial/<path:filial>')
@login_required
def get_unidades_por_filial(filial):
    """Retorna uma lista JSON de unidades para uma dada filial."""
    if filial == 'nenhuma': # Trata o caso de não ter filial selecionada
        unidades_query = db.session.query(Placa.unidade).distinct().order_by(Placa.unidade)
    else:
        filial_upper = filial.upper()
        unidades_query = db.session.query(Placa.unidade).filter(Placa.filial == filial_upper).distinct().order_by(Placa.unidade)
    
    unidades = [u[0] for u in unidades_query.all() if u[0]]
    return jsonify(unidades)