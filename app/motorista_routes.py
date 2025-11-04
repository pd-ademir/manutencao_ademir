# app/motorista_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from collections import defaultdict

from .models import db, Motorista, Veiculo, Usuario, registrar_log, Placa
from .permissoes import requer_tipo, filtrar_query_por_usuario


motoristas_bp = Blueprint('motoristas', __name__, url_prefix='/motoristas')

@motoristas_bp.route('/')
@login_required
@requer_tipo("master","adm")
def gerenciar_motoristas():
    # 1. Captura filtros da URL
    filial_filtro = request.args.get('filial', '').upper()
    unidade_filtro = request.args.get('unidade', '').upper()

    # 2. Query base com filtro de permissão
    motoristas_query = filtrar_query_por_usuario(Motorista.query, Motorista)
    veiculos_query = filtrar_query_por_usuario(Veiculo.query, Veiculo)

    # 3. Aplica filtros de filial e unidade se o usuário for ADM
    if current_user.tipo == 'adm':
        if filial_filtro:
            motoristas_query = motoristas_query.filter(Motorista.filial == filial_filtro)
            veiculos_query = veiculos_query.filter(Veiculo.filial == filial_filtro)
        if unidade_filtro:
            motoristas_query = motoristas_query.filter(Motorista.unidade == unidade_filtro)
            veiculos_query = veiculos_query.filter(Veiculo.unidade == unidade_filtro)

    # 4. Executa a query principal
    lista_motoristas = motoristas_query.order_by(Motorista.nome).all()

    # 5. Prepara dados para os formulários/modais
    veiculos_vinculados_ids = {m.veiculo_id for m in motoristas_query.filter(Motorista.veiculo_id.isnot(None)).all()}
    veiculos_disponiveis = veiculos_query.filter(
        Veiculo.ativo == True,
        Veiculo.id.notin_(veiculos_vinculados_ids)
    ).order_by(Veiculo.nome_conjunto).all()

    # 6. Lógica para popular os filtros dinâmicos para o ADM
    filiais_disponiveis = []
    unidades_para_filtro = []
    filial_unidade_map = {}
    todas_as_unidades_gerais = []

    if current_user.tipo == 'adm':
        # Usamos o modelo Placa como fonte da verdade para filiais e unidades
        pares_filial_unidade = db.session.query(Placa.filial, Placa.unidade).distinct().all()
        
        filiais_set = set()
        unidades_set = set()
        
        for filial, unidade in pares_filial_unidade:
            if filial:
                filiais_set.add(filial)
                if unidade:
                    unidades_set.add(unidade)
                    if filial not in filial_unidade_map:
                        filial_unidade_map[filial] = []
                    if unidade not in filial_unidade_map[filial]:
                        filial_unidade_map[filial].append(unidade)

        filiais_disponiveis = sorted(list(filiais_set))
        todas_as_unidades_gerais = sorted(list(unidades_set))
        
        for filial in filial_unidade_map:
            filial_unidade_map[filial].sort()

        if filial_filtro:
            unidades_para_filtro = filial_unidade_map.get(filial_filtro, [])
        else:
            unidades_para_filtro = todas_as_unidades_gerais
    else: # Para outros usuários, pega apenas as unidades deles
        unidades_db = db.session.query(Motorista.unidade).filter(Motorista.unidade.isnot(None)).distinct().all()
        unidades_para_filtro = sorted([u[0] for u in unidades_db])


    return render_template('motoristas.html', 
                           motoristas=lista_motoristas, 
                           veiculos_disponiveis=veiculos_disponiveis,
                           # Itens para os filtros
                           filiais_disponiveis=filiais_disponiveis,
                           unidades_para_filtro=unidades_para_filtro,
                           todas_unidades_json=todas_as_unidades_gerais,
                           filial_selecionada=filial_filtro,
                           unidade_selecionada=unidade_filtro,
                           filial_unidade_map=filial_unidade_map,
                           # Itens para os modais (listas completas)
                           unidades_gerais=todas_as_unidades_gerais,
                           filiais_gerais=filiais_disponiveis)


@motoristas_bp.route('/add', methods=['POST'])
@login_required
@requer_tipo("master",'adm')
def add_motorista():
    nome = request.form.get('nome')
    cpf = request.form.get('cpf')
    unidade = request.form.get('unidade')
    veiculo_id = request.form.get('veiculo_id')

    if not nome or not cpf:
        flash('Nome e CPF são obrigatórios.', 'danger')
        return redirect(url_for('motoristas.gerenciar_motoristas'))

    # Se o usuário não for ADM, força a unidade dele
    if current_user.tipo != 'adm':
        unidade = current_user.unidade
    
    if not unidade:
        flash('A unidade é obrigatória.', 'danger')
        return redirect(url_for('motoristas.gerenciar_motoristas'))

    novo_motorista = Motorista(
        nome=nome, 
        cpf=cpf,
        rg=request.form.get('rg'), 
        cnh=request.form.get('cnh'), 
        frota=request.form.get('frota'), 
        unidade=unidade,
        filial=request.form.get('filial'),
        veiculo_id=int(veiculo_id) if veiculo_id else None
    )
    
    novo_motorista.set_password(None)
    
    try:
        db.session.add(novo_motorista)
        db.session.commit()
        registrar_log(current_user, f"Adicionou o motorista '{nome}'")
        flash(f'Motorista {nome} adicionado com sucesso!', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Já existe um motorista com este CPF.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao adicionar o motorista: {e}', 'danger')

    return redirect(url_for('motoristas.gerenciar_motoristas'))

@motoristas_bp.route('/edit/<int:motorista_id>', methods=['POST'])
@login_required
@requer_tipo("master",'adm')
def edit_motorista(motorista_id):
    motorista = Motorista.query.get_or_404(motorista_id)
    
    if current_user.tipo != 'adm' and motorista.unidade != current_user.unidade:
        flash('Você não tem permissão para editar este motorista.', 'danger')
        return redirect(url_for('motoristas.gerenciar_motoristas'))

    cpf_antigo = motorista.cpf
    cpf_novo = request.form.get('cpf')

    motorista.nome = request.form.get('nome')
    motorista.rg = request.form.get('rg')
    motorista.cnh = request.form.get('cnh')
    motorista.frota = request.form.get('frota')
    motorista.veiculo_id = int(request.form.get('veiculo_id')) if request.form.get('veiculo_id') else None
    
    # Apenas o ADM pode mudar a filial e unidade livremente
    if current_user.tipo == 'adm':
        motorista.filial = request.form.get('filial')
        motorista.unidade = request.form.get('unidade')
    
    motorista.cpf = cpf_novo

    if cpf_novo != cpf_antigo:
        motorista.set_password(None)
        flash('O CPF foi alterado. A senha do motorista foi redefinida para os 6 primeiros dígitos do novo CPF.', 'info')
    
    try:
        db.session.commit()
        registrar_log(current_user, f"Editou o motorista '{motorista.nome}'")
        flash(f'Dados do motorista {motorista.nome} atualizados com sucesso!', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Já existe um motorista com este novo CPF.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao editar o motorista: {e}', 'danger')

    return redirect(url_for('motoristas.gerenciar_motoristas'))

@motoristas_bp.route('/toggle_status/<int:motorista_id>', methods=['POST'])
@login_required
@requer_tipo("master",'adm')
def toggle_motorista_status(motorista_id):
    motorista = Motorista.query.get_or_404(motorista_id)
    
    if current_user.tipo != 'adm' and motorista.unidade != current_user.unidade:
        flash('Você não tem permissão para alterar o status deste motorista.', 'danger')
        return redirect(url_for('motoristas.gerenciar_motoristas'))

    motorista.ativo = not motorista.ativo
    
    if not motorista.ativo and motorista.veiculo:
        motorista.veiculo_id = None
        
    db.session.commit()
    
    status = "ativado" if motorista.ativo else "desativado"
    registrar_log(current_user, f"{status.capitalize()} o motorista '{motorista.nome}'")
    flash(f'Motorista {motorista.nome} foi {status} com sucesso.', 'success')
    
    return redirect(url_for('motoristas.gerenciar_motoristas'))

@motoristas_bp.route('/desvincular_conjunto/<int:motorista_id>', methods=['POST'])
@login_required
@requer_tipo("master",'adm')
def desvincular_conjunto(motorista_id):
    motorista = Motorista.query.get_or_404(motorista_id)

    if current_user.tipo != 'adm' and motorista.unidade != current_user.unidade:
        flash('Você não tem permissão para modificar este motorista.', 'danger')
        return redirect(url_for('motoristas.gerenciar_motoristas'))

    if motorista.veiculo:
        veiculo_nome = motorista.veiculo.nome_conjunto
        motorista.veiculo_id = None
        db.session.commit()
        registrar_log(current_user, f"Desvinculou o conjunto '{veiculo_nome}' do motorista '{motorista.nome}'")
        flash(f'O conjunto "{veiculo_nome}" foi desvinculado do motorista {motorista.nome}.', 'success')
    else:
        flash(f'O motorista {motorista.nome} já não possui um conjunto vinculado.', 'info')

    return redirect(url_for('motoristas.gerenciar_motoristas'))
