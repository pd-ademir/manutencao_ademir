
# app/mass_update_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_
from markupsafe import Markup
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
    val = str(value).strip().lower()
    if val in ['true', '1', 'sim', 's', 'ativo']:
        return True
    return False

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

# --- ROTA DE UPLOAD DE PLACAS (CORRIGIDA) ---
@mass_update_bp.route('/upload-placas', methods=['POST'])
@login_required
@requer_tipo("master", "comum",'adm')
def upload_placas():
    if 'csv_file' not in request.files or not request.files['csv_file'].filename:
        flash('Nenhum arquivo enviado.', 'danger'); return redirect(url_for('mass_update.index'))
    
    file = request.files['csv_file']
    try:
        stream = io.TextIOWrapper(file.stream, encoding='latin-1')
        # Normaliza o cabeçalho para minúsculas e sem espaços
        header = [h.strip().lower() for h in stream.readline().split(';')]
        stream.seek(0)
        csv_reader = csv.DictReader(stream, delimiter=';', fieldnames=header)
        next(csv_reader) # Pula o cabeçalho que já lemos

        criados, atualizados, ignorados, erros = 0, 0, 0, []

        # Campos permitidos para atualização via CSV
        campos_permitidos = {
            'tipo', 'fabricante', 'modelo', 'ano', 'unidade', 'filial', 'km_atual',
            'data_proxima_calibragem', 'km_troca_preventiva', 'km_ultima_revisao_preventiva',
            'km_troca_intermediaria', 'km_ultima_revisao_intermediaria', 'intervalo_oleo_diferencial',
            'troca_oleo_diferencial', 'intervalo_oleo_cambio', 'troca_oleo_cambio'
        }

        for row_num, row in enumerate(csv_reader, start=2):
            placa_str = row.get('placa', '').strip().upper()
            if not placa_str:
                erros.append(f'Linha {row_num}: Coluna "placa" ausente ou vazia.'); continue

            unidade_linha = row.get('unidade', '').strip().upper()
            filial_linha = row.get('filial', '').strip().upper()
            
            placa_obj = Placa.query.filter_by(placa=placa_str).first()

            if not _verificar_permissao_linha(unidade_linha or (placa_obj.unidade if placa_obj else ''), filial_linha or (placa_obj.filial if placa_obj else '')):
                erros.append(f'Linha {row_num} ({placa_str}): Sem permissão para a filial/unidade.'); continue

            if not placa_obj:
                if not row.get('unidade') or not row.get('tipo'):
                    erros.append(f'Linha {row_num} ({placa_str}): Para criar uma placa, as colunas "unidade" e "tipo" são obrigatórias.'); continue
                placa_obj = Placa(placa=placa_str)
                db.session.add(placa_obj)
                criados += 1
                alterado = True
            else:
                alterado = False

            # Atualiza apenas os campos presentes no CSV e permitidos
            for campo in campos_permitidos:
                if campo in row and row[campo].strip() != '':
                    valor_csv = row[campo].strip()
                    valor_atual = getattr(placa_obj, campo)

                    # Converte para o tipo de dado correto antes de comparar e atribuir
                    novo_valor = None
                    if 'data' in campo:
                        novo_valor = parse_date(valor_csv)
                    elif 'km' in campo or 'intervalo' in campo or 'troca' in campo or 'ano' in campo:
                        novo_valor = to_int_or_none(valor_csv)
                    else:
                        novo_valor = valor_csv.upper()
                    
                    if str(valor_atual or '') != str(novo_valor or ''):
                        setattr(placa_obj, campo, novo_valor)
                        alterado = True
            
            if not alterado and criados == 0:
                ignorados += 1
            elif alterado and criados == 0:
                atualizados +=1

        db.session.commit()
        flash(f'Placas: {criados} criadas, {atualizados} atualizadas, {ignorados} ignoradas.', 'success')
        if erros: flash(Markup('Erros (Placas):<ul>' + ''.join(f'<li>{e}</li>' for e in erros) + '</ul>'), 'danger')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro inesperado no upload de placas: {e}', 'danger')
    return redirect(url_for('mass_update.index'))


# --- ROTA DE UPLOAD DE MOTORISTAS (CORRIGIDA) ---
@mass_update_bp.route('/upload-motoristas', methods=['POST'])
@login_required
@requer_tipo("master", "comum",'adm')
def upload_motoristas():
    if 'csv_file' not in request.files or not request.files['csv_file'].filename:
        flash('Nenhum arquivo enviado.', 'danger'); return redirect(url_for('mass_update.index'))
    
    file = request.files['csv_file']
    try:
        stream = io.TextIOWrapper(file.stream, encoding='latin-1')
        header = [h.strip().lower() for h in stream.readline().split(';')]
        stream.seek(0)
        csv_reader = csv.DictReader(stream, delimiter=';', fieldnames=header)
        next(csv_reader)

        criados, atualizados, ignorados, erros = 0, 0, 0, []
        campos_permitidos = {'nome', 'cnh', 'rg', 'unidade', 'filial', 'ativo'}

        for row_num, row in enumerate(csv_reader, start=2):
            cpf_limpo = clean_cpf(row.get('cpf', ''))
            if not cpf_limpo:
                erros.append(f'Linha {row_num}: CPF inválido ou ausente.'); continue

            unidade_linha = row.get('unidade', '').strip().upper()
            filial_linha = row.get('filial', '').strip().upper()
            motorista = Motorista.query.filter_by(_cpf=cpf_limpo).first()

            if not _verificar_permissao_linha(unidade_linha or (motorista.unidade if motorista else ''), filial_linha or (motorista.filial if motorista else '')):
                erros.append(f'Linha {row_num} (CPF: {cpf_limpo}): Sem permissão para a filial/unidade.'); continue

            if not motorista:
                if not row.get('nome') or not row.get('unidade'):
                    erros.append(f'Linha {row_num} (CPF: {cpf_limpo}): Para criar, "nome" e "unidade" são obrigatórios.'); continue
                motorista = Motorista(cpf=cpf_limpo)
                db.session.add(motorista)
                criados += 1
                alterado = True
            else:
                alterado = False

            for campo in campos_permitidos:
                if campo in row and row[campo].strip() != '':
                    valor_csv = row[campo].strip()
                    valor_atual = getattr(motorista, campo)
                    novo_valor = to_bool(valor_csv) if campo == 'ativo' else valor_csv.upper()

                    if str(valor_atual or '') != str(novo_valor or ''):
                        setattr(motorista, campo, novo_valor)
                        alterado = True
            
            if not alterado and criados == 0:
                ignorados += 1
            elif alterado and criados == 0:
                atualizados +=1

        db.session.commit()
        flash(f'Motoristas: {criados} criados, {atualizados} atualizados, {ignorados} ignoradas.', 'success')
        if erros: flash(Markup('Erros (Motoristas):<ul>' + ''.join(f'<li>{e}</li>' for e in erros) + '</ul>'), 'danger')
    except Exception as e: 
        db.session.rollback()
        flash(f'Erro inesperado no upload de motoristas: {e}', 'danger')
    return redirect(url_for('mass_update.index'))


# --- ROTA DE UPLOAD DE CONJUNTOS (FINAL) ---
@mass_update_bp.route('/upload-conjuntos', methods=['POST'])
@login_required
@requer_tipo("master", "comum", 'adm')
def upload_conjuntos():
    if 'csv_file' not in request.files or not request.files['csv_file'].filename:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('mass_update.index'))

    file = request.files['csv_file']
    try:
        stream = io.TextIOWrapper(file.stream, encoding='latin-1')
        csv_reader = csv.DictReader(stream, delimiter=';')
        
        criados, atualizados, ignorados, erros = 0, 0, 0, []

        linhas_csv = list(csv_reader)
        placas_no_csv = set()
        cpfs_no_csv = set()
        for row in linhas_csv:
            for col in ['placa_cavalo', 'placa_carreta1', 'placa_carreta2']:
                if row.get(col) and row[col].strip(): placas_no_csv.add(row[col].strip().upper())
            if row.get('motorista_cpf') and row['motorista_cpf'].strip(): cpfs_no_csv.add(clean_cpf(row['motorista_cpf']))

        placas_db = {p.placa: p for p in Placa.query.filter(Placa.placa.in_(placas_no_csv)).all()}
        motoristas_db = {m._cpf: m for m in Motorista.query.filter(Motorista._cpf.in_(cpfs_no_csv)).all()}
        
        placas_em_uso_query = db.session.query(Veiculo.placa_cavalo_id, Veiculo.placa_carreta1_id, Veiculo.placa_carreta2_id).filter(Veiculo.ativo == True).all()
        placas_em_uso_ids = {id for tpl in placas_em_uso_query for id in tpl if id}

        for row_num, row in enumerate(linhas_csv, start=2):
            nome_conjunto = row.get('nome_conjunto', '').strip().upper()
            if not nome_conjunto:
                erros.append(f'Linha {row_num}: A coluna "nome_conjunto" é obrigatória.'); continue

            unidade_linha = row.get('unidade', '').strip().upper()
            filial_linha = row.get('filial', '').strip().upper()

            veiculo = Veiculo.query.filter_by(nome_conjunto=nome_conjunto).first()

            if not _verificar_permissao_linha(unidade_linha or (veiculo.unidade if veiculo else ''), filial_linha or (veiculo.filial if veiculo else '')):
                erros.append(f'Linha {row_num} ({nome_conjunto}): Sem permissão para a filial/unidade especificada.'); continue

            placa_cavalo_str = row.get('placa_cavalo', '').strip().upper()
            placa_c1_str = row.get('placa_carreta1', '').strip().upper()
            placa_c2_str = row.get('placa_carreta2', '').strip().upper()
            
            placa_cavalo = placas_db.get(placa_cavalo_str) if placa_cavalo_str else None
            placa_c1 = placas_db.get(placa_c1_str) if placa_c1_str else None
            placa_c2 = placas_db.get(placa_c2_str) if placa_c2_str else None
            motorista = motoristas_db.get(clean_cpf(row.get('motorista_cpf',''))) if row.get('motorista_cpf') else None

            if placa_cavalo_str and not placa_cavalo:
                erros.append(f'Linha {row_num} ({nome_conjunto}): Placa do cavalo "{placa_cavalo_str}" não encontrada.'); continue
            if placa_c1_str and not placa_c1:
                erros.append(f'Linha {row_num} ({nome_conjunto}): Placa da carreta 1 "{placa_c1_str}" não encontrada.'); continue
            if placa_c2_str and not placa_c2:
                erros.append(f'Linha {row_num} ({nome_conjunto}): Placa da carreta 2 "{placa_c2_str}" não encontrada.'); continue
            
            dados = {
                'unidade': unidade_linha,
                'filial': filial_linha,
                'placa_cavalo': placa_cavalo,
                'placa_carreta1': placa_c1,
                'placa_carreta2': placa_c2,
                'motorista': motorista,
                'ativo': to_bool(row.get('ativo', 'true')),
                'obs': row.get('obs', '').strip() or None
            }
            
            if not veiculo:
                if not dados['unidade'] or not dados['placa_cavalo']:
                    erros.append(f'Linha {row_num} ({nome_conjunto}): Para criar, "unidade" e "placa_cavalo" são obrigatórios.'); continue
                
                ids_para_checar = {p.id for p in [placa_cavalo, placa_c1, placa_c2] if p}
                if any(pid in placas_em_uso_ids for pid in ids_para_checar):
                    erros.append(f'Linha {row_num} ({nome_conjunto}): Uma ou mais placas já em uso. Criação ignorada.'); continue
                
                veiculo = Veiculo(nome_conjunto=nome_conjunto)
                for k, v in dados.items(): setattr(veiculo, k, v)
                db.session.add(veiculo)
                criados += 1
                placas_em_uso_ids.update(ids_para_checar)
            else:
                alterado = False
                for k, v in dados.items():
                    # Compara objetos da relação pelo ID para evitar lazy loading desnecessário
                    valor_atual = getattr(veiculo, k)
                    if k in ['placa_cavalo', 'placa_carreta1', 'placa_carreta2', 'motorista']:
                        if (valor_atual.id if valor_atual else None) != (v.id if v else None):
                            setattr(veiculo, k, v); alterado = True
                    elif valor_atual != v:
                        setattr(veiculo, k, v); alterado = True
                
                if alterado:
                    atualizados += 1
                else:
                    ignorados += 1
        
        db.session.commit()
        flash(f'Importação de Conjuntos concluída: {criados} criados, {atualizados} atualizados, {ignorados} ignorados.', 'success')
        if erros:
            msg_erro_html = '<strong>Erros na importação de Conjuntos:</strong><ul>' + ''.join(f'<li>{e}</li>' for e in erros) + '</ul>'
            flash(Markup(msg_erro_html), 'danger')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro inesperado ao processar o arquivo de conjuntos: {e}', 'danger')
    
    return redirect(url_for('mass_update.index'))
