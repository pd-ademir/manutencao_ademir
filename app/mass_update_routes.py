# app/mass_update_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from .models import db, Placa, Motorista, Veiculo, clean_cpf
from .permissoes import requer_tipo
import csv
import io
from datetime import datetime

mass_update_bp = Blueprint('mass_update', __name__, url_prefix='/mass-update')

# --- FUNÇÕES AUXILIARES ---
def parse_date(date_string):
    if not date_string or not date_string.strip(): return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try: return datetime.strptime(date_string.strip(), fmt).date()
        except (ValueError, TypeError): pass
    return None

def to_int_or_none(value):
    if value is None or not str(value).strip(): return None
    try: return int(float(str(value).strip()))
    except (ValueError, TypeError): return None

def to_bool(value):
    return str(value).strip().lower() in ['true', '1', 'sim', 's', 'ativo']

# --- FUNÇÃO DE VERIFICAÇÃO DE PERMISSÃO ---
def _verificar_permissao_linha(unidade_linha, filial_linha):
    if current_user.tipo == 'adm':
        return True
    if current_user.filial and filial_linha and current_user.filial.upper() != filial_linha.upper():
        return False
    if current_user.unidade and unidade_linha and current_user.unidade.upper() != unidade_linha.upper():
        return False
    return True

@mass_update_bp.route('/')
@login_required
@requer_tipo("master", "comum",'adm')
def index():
    return render_template('cadastros_em_massa.html')

@mass_update_bp.route('/upload-placas', methods=['POST'])
@login_required
@requer_tipo("master", "comum",'adm')
def upload_placas():
    if 'csv_file' not in request.files or not request.files['csv_file'].filename:
        flash('Nenhum arquivo enviado.', 'danger'); return redirect(url_for('mass_update.index'))
    file = request.files['csv_file']
    try:
        stream = io.TextIOWrapper(file.stream, encoding='utf-8-sig')
        csv_reader = csv.DictReader(stream, delimiter=';')
        criados, atualizados, ignorados, erros = 0, 0, 0, []
        for row_num, row in enumerate(csv_reader, start=2):
            placa_str = row.get('placa', '').strip().upper()
            unidade_linha = row.get('unidade', '').strip().upper()
            filial_linha = row.get('filial', '').strip().upper()
            if not _verificar_permissao_linha(unidade_linha, filial_linha):
                erros.append(f'Linha {row_num} ({placa_str}): Sem permissão para a filial/unidade.'); continue
            if not placa_str: erros.append(f'Linha {row_num}: Coluna "placa" é obrigatória.'); continue
            dados = {k: v.strip() for k, v in row.items()}
            placa_obj = Placa.query.filter_by(placa=placa_str).first()
            if not placa_obj:
                if not dados.get('unidade') or not dados.get('tipo'): erros.append(f'Linha {row_num} ({placa_str}): Para criar, "unidade" e "tipo" são obrigatórios.'); continue
                placa_obj = Placa(placa=placa_str); db.session.add(placa_obj); criados += 1
            else:
                if any(str(getattr(placa_obj, k, '') or '') != v for k, v in dados.items() if k != 'placa'): atualizados += 1
                else: ignorados += 1
            for k, v in dados.items(): setattr(placa_obj, k, v or None)
        db.session.commit()
        flash(f'Placas: {criados} criadas, {atualizados} atualizadas, {ignorados} ignoradas.', 'success')
        if erros: flash('Erros (Placas):<ul>' + ''.join(f'<li>{e}</li>' for e in erros) + '</ul>', 'danger')
    except Exception as e: db.session.rollback(); flash(f'Erro inesperado: {e}', 'danger')
    return redirect(url_for('mass_update.index'))

@mass_update_bp.route('/upload-motoristas', methods=['POST'])
@login_required
@requer_tipo("master", "comum",'adm')
def upload_motoristas():
    if 'csv_file' not in request.files or not request.files['csv_file'].filename:
        flash('Nenhum arquivo enviado.', 'danger'); return redirect(url_for('mass_update.index'))
    file = request.files['csv_file']
    try:
        stream = io.TextIOWrapper(file.stream, encoding='utf-8-sig')
        csv_reader = csv.DictReader(stream, delimiter=';')
        criados, atualizados, ignorados, erros = 0, 0, 0, []
        for row_num, row in enumerate(csv_reader, start=2):
            cpf_limpo = clean_cpf(row.get('cpf', ''))
            unidade_linha = row.get('unidade', '').strip().upper()
            filial_linha = row.get('filial', '').strip().upper()
            if not _verificar_permissao_linha(unidade_linha, filial_linha):
                erros.append(f'Linha {row_num} (CPF: {cpf_limpo}): Sem permissão para a filial/unidade.'); continue
            if not cpf_limpo: erros.append(f'Linha {row_num}: CPF inválido ou ausente.'); continue
            dados = {'nome': row.get('nome'), 'cnh': row.get('cnh'), 'rg': row.get('rg'), 'ativo': to_bool(row.get('ativo')), 'unidade': unidade_linha, 'filial': filial_linha}
            motorista = Motorista.query.filter_by(_cpf=cpf_limpo).first()
            if not motorista:
                if not dados.get('nome') or not dados.get('unidade'): erros.append(f'Linha {row_num} (CPF: {cpf_limpo}): Para criar, "nome" e "unidade" são obrigatórios.'); continue
                motorista = Motorista(cpf=cpf_limpo); db.session.add(motorista); criados += 1
            else:
                if any(getattr(motorista, k) != v for k, v in dados.items()): atualizados += 1
                else: ignorados += 1
            for k, v in dados.items(): setattr(motorista, k, v)
        db.session.commit()
        flash(f'Motoristas: {criados} criados, {atualizados} atualizados, {ignorados} ignoradas.', 'success')
        if erros: flash('Erros (Motoristas):<ul>' + ''.join(f'<li>{e}</li>' for e in erros) + '</ul>', 'danger')
    except Exception as e: db.session.rollback(); flash(f'Erro inesperado: {e}', 'danger')
    return redirect(url_for('mass_update.index'))

@mass_update_bp.route('/upload-conjuntos', methods=['POST'])
@login_required
@requer_tipo("master", "adm")
def upload_conjuntos():
    if 'csv_file' not in request.files or not request.files['csv_file'].filename:
        flash('Nenhum arquivo enviado.', 'danger'); return redirect(url_for('mass_update.index'))
    file = request.files['csv_file']
    try:
        stream = io.TextIOWrapper(file.stream, encoding='utf-8-sig')
        csv_reader = csv.DictReader(stream, delimiter=';')
        criados, atualizados, ignorados, erros = 0, 0, 0, []
        for row_num, row in enumerate(csv_reader, start=2):
            nome_conjunto = row.get('nome_conjunto', '').strip().upper()
            unidade_linha = row.get('unidade', '').strip().upper()
            filial_linha = row.get('filial', '').strip().upper()
            if not _verificar_permissao_linha(unidade_linha, filial_linha):
                erros.append(f'Linha {row_num} ({nome_conjunto}): Sem permissão para a filial/unidade.'); continue
            if not nome_conjunto: erros.append(f'Linha {row_num}: "nome_conjunto" é obrigatório.'); continue
            placa_cavalo = Placa.query.filter_by(placa=row.get('placa_cavalo','').strip().upper()).first()
            motorista = Motorista.query.filter_by(_cpf=clean_cpf(row.get('motorista_cpf',''))).first()
            if row.get('placa_cavalo') and not placa_cavalo: erros.append(f'Linha {row_num} ({nome_conjunto}): Placa cavalo não encontrada.'); continue
            dados = {'unidade': unidade_linha, 'filial': filial_linha, 'placa_cavalo_id': placa_cavalo.id if placa_cavalo else None, 'motorista_id': motorista.id if motorista else None, 'ativo': to_bool(row.get('ativo')), 'obs': row.get('obs')}
            veiculo = Veiculo.query.filter_by(nome_conjunto=nome_conjunto).first()
            if not veiculo:
                if not dados.get('unidade') or not dados.get('placa_cavalo_id'): erros.append(f'Linha {row_num} ({nome_conjunto}): Para criar, "unidade" e "placa_cavalo" são obrigatórios.'); continue
                veiculo = Veiculo(nome_conjunto=nome_conjunto); db.session.add(veiculo); criados += 1
            else:
                if any(getattr(veiculo, k) != v for k, v in dados.items()): atualizados += 1
                else: ignorados += 1
            for k, v in dados.items(): setattr(veiculo, k, v)
        db.session.commit()
        flash(f'Conjuntos: {criados} criados, {atualizados} atualizados, {ignorados} ignorados.', 'success')
        if erros: flash('Erros (Conjuntos):<ul>' + ''.join(f'<li>{e}</li>' for e in erros) + '</ul>', 'danger')
    except Exception as e: db.session.rollback(); flash(f'Erro inesperado: {e}', 'danger')
    return redirect(url_for('mass_update.index'))
