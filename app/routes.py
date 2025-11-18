
from flask import Blueprint, render_template, redirect, url_for, request, flash, make_response, render_template_string, current_app

from collections import defaultdict
from .forms import VehicleForm, ManutencaoForm, PneuAplicadoForm, EstoquePneuForm
from .models import db, Veiculo, Manutencao, Usuario, LogSistema, registrar_log, get_ip_real, PneuAplicado, EstoquePneu, HistoricoBloqueio
from .alertas import gerar_resumo_veiculos, extrair_dados, disparar_alertas_reais
from .permissoes import tem_permissao
from sqlalchemy.orm import aliased
from sqlalchemy import case, func
from markupsafe import Markup
from datetime import datetime, timedelta, date
from xhtml2pdf import pisa
from io import BytesIO
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from flask import abort, session, jsonify, send_file
from zoneinfo import ZoneInfo
from .utils import detectar_alteracoes
from zoneinfo import ZoneInfo
from .models import Placa

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import pytz
from dateutil.relativedelta import relativedelta
import traceback
import sys
import base64
import os
import pdfplumber
import re
from werkzeug.utils import secure_filename
from sqlalchemy import or_, func
from flask_wtf import FlaskForm
import csv
import io
from .permissoes import filtrar_query_por_usuario # Verifique se este import está no topo do seu arquivo
from sqlalchemy.orm import joinedload # Verifique se este import está no topo
import traceback
import sys
from datetime import datetime
import re

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


main = Blueprint('main', __name__)

def requer_tipo(*tipos_autorizados):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_user.is_authenticated and current_user.tipo in tipos_autorizados:
                return f(*args, **kwargs)
            else:
                flash("Acesso não autorizado para este usuário.", "danger")
                return redirect(url_for('main.index'))
        return wrapper
    return decorator


def get_manutencoes_vencidas(veiculo):
    """
    Verifica as manutenções vencidas com base na placa do cavalo de um conjunto.
    Recebe um objeto 'Veiculo' (conjunto).
    """
    tipos = []
    if not veiculo.placa_cavalo:
        return tipos

    cavalo = veiculo.placa_cavalo
    
    if cavalo.km_para_preventiva is not None and cavalo.km_para_preventiva <= 0: tipos.append("Preventiva")
    if cavalo.km_para_intermediaria is not None and cavalo.km_para_intermediaria <= 0: tipos.append("Intermediária")
    if cavalo.km_para_diferencial is not None and cavalo.km_para_diferencial <= 0: tipos.append("Diferencial")
    if cavalo.km_para_cambio is not None and cavalo.km_para_cambio <= 0: tipos.append("Câmbio")
    return tipos

def verificar_e_registrar_bloqueio(veiculo):
    """
    Verifica manutenções vencidas e cria um registro no histórico se for um novo bloqueio.
    """
    if not veiculo.placa_cavalo:
        return

    manutencoes_vencidas = get_manutencoes_vencidas(veiculo)
    
    for tipo_vencido in manutencoes_vencidas:
        bloqueio_existente = HistoricoBloqueio.query.filter_by(
            placa_id=veiculo.placa_cavalo_id,
            tipo_manutencao=tipo_vencido, 
            liberado=False
        ).first()
        
        if not bloqueio_existente:
            # --- CORREÇÃO APLICADA AQUI ---
            # Removido o argumento 'veiculo_id', que não pertence ao modelo HistoricoBloqueio.
            novo_bloqueio = HistoricoBloqueio(
                placa_id=veiculo.placa_cavalo_id,
                tipo_manutencao=tipo_vencido,
                km_bloqueio=veiculo.placa_cavalo.km_atual,
                data_bloqueio=datetime.utcnow()
            )
            db.session.add(novo_bloqueio)
            print(f"NOVO BLOQUEIO REGISTRADO: Placa {veiculo.placa_cavalo.placa}, Tipo: {tipo_vencido}")
            
    db.session.commit()



@main.route('/')
@login_required
def index():
    hoje = date.today()
    
    # APLICA O FILTRO DE PERMISSÃO
    query_base = Veiculo.query.options(joinedload(Veiculo.placa_cavalo), joinedload(Veiculo.placa_carreta1), joinedload(Veiculo.motorista))
    query_filtrada = filtrar_query_por_usuario(query_base, Veiculo)
    todos = query_filtrada.order_by(Veiculo.nome_conjunto).all()

    filtro = request.args.get('filtro')

    for v_check in todos:
        verificar_e_registrar_bloqueio(v_check)

    def manutencao_relevante(v):
        if not v.placa_cavalo:
            return False
        return any([
            v.placa_cavalo.km_para_preventiva and 0 < v.placa_cavalo.km_para_preventiva <= 5000,
            v.placa_cavalo.km_para_intermediaria and 0 < v.placa_cavalo.km_para_intermediaria <= 5000,
            v.placa_cavalo.km_para_diferencial and 0 < v.placa_cavalo.km_para_diferencial <= 5000,
            v.placa_cavalo.km_para_cambio and 0 < v.placa_cavalo.km_para_cambio <= 5000
        ])
    
    veiculos_para_exibir = []
    for v in todos: # Agora itera sobre a lista já filtrada
        if not v.placa_cavalo:
            continue

        calibragem_vencida = v.placa_cavalo.data_proxima_calibragem and v.placa_cavalo.data_proxima_calibragem <= hoje
        
        revisao_carreta_vencida = False
        if v.placa_carreta1 and v.placa_carreta1.data_proxima_revisao_carreta:
            revisao_carreta_vencida = v.placa_carreta1.data_proxima_revisao_carreta <= hoje + timedelta(days=30)

        outras_manutencoes = manutencao_relevante(v)
        v.manutencoes_vencidas = get_manutencoes_vencidas(v)

        if filtro == 'ocultar_somente_calibragem':
            if outras_manutencoes or v.manutencoes_vencidas or revisao_carreta_vencida:
                veiculos_para_exibir.append(v)
        else:
            if outras_manutencoes or v.manutencoes_vencidas or calibragem_vencida or revisao_carreta_vencida:
                veiculos_para_exibir.append(v)

    return render_template('index.html', veiculos=veiculos_para_exibir, current_date=hoje)


# Em app/routes.py

@main.route('/extract_os', methods=['GET', 'POST'])
@login_required
def extract_os():
    if request.method == 'POST':
        if 'pdf_file' not in request.files:
            flash('Nenhum arquivo enviado.', 'danger')
            return redirect(request.url)
        file = request.files['pdf_file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'warning')
            return redirect(request.url)
        
        if file and file.filename.endswith('.pdf'):
            try:
                # Extração de dados do PDF (lógica mantida)
                with pdfplumber.open(file) as pdf:
                    full_text = ''.join(page.extract_text(layout=True) or '' for page in pdf.pages)

                placa_match = re.search(r'([A-Z]{3}\\d[A-Z\\d]\\d{2})', full_text)
                placa_str = placa_match.group(1).strip() if placa_match else None

                km_match = re.search(r'(\\d{1,3}(?:\\.\\d{3})*,\\d{3})', full_text)
                km_final = int(km_match.group(1).split(',')[0].replace('.', '')) if km_match else 0

                data_str = None
                header_date_match = re.search(r'FECHAMENTO(?:.|\\n)*?(\\d{2}/\\d{2}/\\d{4})', full_text)
                if header_date_match:
                    data_str = header_date_match.group(1).strip()
                else:
                    all_dates = re.findall(r'(\\d{2}/\\d{2}/\\d{4})', full_text)
                    if all_dates:
                        latest_date = max([datetime.strptime(d, '%d/%m/%Y') for d in all_dates])
                        data_str = latest_date.strftime('%d/%m/%Y')
                
                tipo_servico = None
                service_detail_match = re.search(r'PREVENTIVA.*?KM\\s*-\\s*(COMPLETA|INTERMEDIARIA)', full_text, re.IGNORECASE)
                if service_detail_match:
                    keyword = service_detail_match.group(1).upper()
                    if 'COMPLETA' in keyword: tipo_servico = 'PREVENTIVA'
                    elif 'INTERMEDIARIA' in keyword: tipo_servico = 'INTERMEDIaria'

                # --- VALIDAÇÃO E CHAMADA DA FUNÇÃO CORE CORRIGIDA ---
                if not all([placa_str, data_str, tipo_servico]):
                    flash(f"Dados insuficientes no PDF: Placa='{placa_str}', Data='{data_str}', Tipo='{tipo_servico}'. Manutenção não registrada.", "danger")
                    return redirect(url_for('main.extract_os'))

                placa_obj = Placa.query.filter_by(placa=placa_str).first()
                if not placa_obj:
                    flash(f"Placa {placa_str} extraída do PDF não encontrada no sistema.", "warning")
                    return redirect(url_for('main.extract_os'))

                data_manutencao = datetime.strptime(data_str, '%d/%m/%Y').date()
                observacoes_pdf = f"Manutenção via PDF. KM: {km_final}"

                # Chamada para a nova função centralizada
                sucesso, mensagem = _registrar_manutencao_core(
                    placa_id=placa_obj.id,
                    tipo_manutencao=tipo_servico,
                    km_manutencao=km_final,
                    data_manutencao=data_manutencao,
                    observacoes=observacoes_pdf,
                    usuario_log=current_user
                )

                if sucesso:
                    flash(mensagem, 'success')
                else:
                    flash(mensagem, 'danger')
                
                return redirect(url_for('veiculos.gerenciar_veiculos'))

            except Exception as e:
                flash(f'Ocorreu um erro crítico durante o processamento do PDF: {e}', 'danger')
                traceback.print_exc(file=sys.stderr)
                return redirect(url_for('main.extract_os'))

    return render_template('extract_os.html')


def format_km(value):
    """Função para formatar números como quilometragem, disponível em Python e registrada como filtro."""
    if isinstance(value, (int, float)):
        return f"{value:,.0f}".replace(',', '.')
    return value
main.app_template_filter('format_km')(format_km) # Registra a função como um filtro de template



@main.route('/plano-manutencao/pdf')
@login_required
def plano_manutencao_pdf():
    """Gera um PDF do plano de manutenção usando ReportLab com layout corrigido."""
    # --- 1. Busca e processamento de dados ---
    unidade_selecionada = request.args.get('unidade', '')
    filial_selecionada = request.args.get('filial', '')

    # =============================== ALTERAÇÃO REALIZADA AQUI ===============================
    # Adicionado filtro para buscar apenas veículos ATIVOS.
    query = filtrar_query_por_usuario(Veiculo.query, Veiculo).filter(Veiculo.ativo == True)
    # =======================================================================================

    if unidade_selecionada:
        query = query.filter(Veiculo.unidade == unidade_selecionada)
    if filial_selecionada and current_user.tipo == 'adm':
        query = query.filter(Veiculo.filial == filial_selecionada)

    query = query.options(joinedload(Veiculo.motorista), joinedload(Veiculo.placa_cavalo), joinedload(Veiculo.placa_carreta1))

    def chave_ordenacao(veiculo):
        if not veiculo.placa_cavalo or veiculo.placa_cavalo.km_atual is None: return float('inf')
        kms = [k for k in [veiculo.placa_cavalo.km_para_preventiva, veiculo.placa_cavalo.km_para_intermediaria, veiculo.placa_cavalo.km_para_diferencial, veiculo.placa_cavalo.km_para_cambio] if k is not None]
        return min(kms) if kms else float('inf')

    veiculos_ordenados = sorted(query.all(), key=chave_ordenacao)
    hoje = date.today()

    # --- 2. Preparação dos dados para a tabela do PDF ---
    table_data = []
    table_data.append(['Veículo', 'Preventiva', 'Intermediária', 'Diferencial', 'Câmbio', 'Rev. Carreta'])

    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle(name='Normal', parent=styles['Normal'], alignment=TA_CENTER, fontSize=7, leading=9)
    style_danger = ParagraphStyle(name='Danger', parent=style_normal, textColor=colors.red)
    style_warning = ParagraphStyle(name='Warning', parent=style_normal, textColor=colors.orange)
    style_muted = ParagraphStyle(name='Muted', parent=style_normal, textColor=colors.grey)
    style_vehicle = ParagraphStyle(name='Vehicle', parent=styles['Normal'], alignment=TA_LEFT, fontSize=8, leading=10)

    for v in veiculos_ordenados:
        row = []
        motorista_str = v.motorista.nome if v.motorista else 'N/D'
        
        info_str = f"<b>{v.nome_conjunto}</b><br/><font size='7' color='grey'>{motorista_str}</font>"
        
        if v.placa_cavalo and v.placa_cavalo.km_atual:
            km_formatado = format_km(v.placa_cavalo.km_atual)
            info_str += f"<br/><font size='7'><b>KM: {km_formatado}</b></font>"
            
        row.append(Paragraph(info_str, style_vehicle))

        if v.placa_cavalo:
            km_atual = v.placa_cavalo.km_atual or 0
            tipos = {
                'preventiva': (v.placa_cavalo.km_ultima_revisao_preventiva, v.placa_cavalo.km_troca_preventiva, 5000),
                'intermediaria': (v.placa_cavalo.km_ultima_revisao_intermediaria, v.placa_cavalo.km_troca_intermediaria, 3000),
                'diferencial': (v.placa_cavalo.troca_oleo_diferencial, v.placa_cavalo.intervalo_oleo_diferencial, 5000),
                'cambio': (v.placa_cavalo.troca_oleo_cambio, v.placa_cavalo.intervalo_oleo_cambio, 5000)
            }
            for nome, (ult_rev, intervalo, warning) in tipos.items():
                if intervalo and intervalo > 0 and ult_rev is not None:
                    km_prox = ult_rev + intervalo; km_rest = km_prox - km_atual
                    cor_style = style_danger if km_rest <= 0 else (style_warning if km_rest <= warning else style_normal)
                    prox_str = format_km(km_prox); rest_str = f"({('+' if km_rest > 0 else '')}{format_km(km_rest)} km)"
                    row.append(Paragraph(f"Próx: <b>{prox_str}</b><br/><font size='6'>{rest_str}</font>", cor_style))
                else:
                    row.append(Paragraph("N/A", style_muted))
        else:
            row.extend([Paragraph("N/A", style_muted)] * 4)

        if v.placa_carreta1 and v.placa_carreta1.data_proxima_revisao_carreta:
            data_rev = v.placa_carreta1.data_proxima_revisao_carreta; dias = (data_rev - hoje).days
            status = "Vencido" if dias < 0 else (f"Vence em {dias}d" if dias <= 7 else f"Faltam {dias}d")
            cor_style = style_danger if dias < 0 else (style_warning if dias <= 7 else style_normal)
            data_str = data_rev.strftime('%d/%m/%Y')
            row.append(Paragraph(f"{status}<br/><font size='6'>{data_str}</font>", cor_style))
        else:
            row.append(Paragraph("N/A", style_muted))
        table_data.append(row)

    # --- 3. Construção do PDF com ReportLab ---
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(A4), leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=4*cm, bottomMargin=2.5*cm)

    logo_path = os.path.join(current_app.root_path, 'static', 'logo.jpg')
    logo = Image(logo_path, width=3*cm, height=1.5*cm) if os.path.exists(logo_path) else Paragraph(" ", style_normal)
    
    header_text = f"""
        <b>Plano de Manutenção - {unidade_selecionada or 'Todas as Unidades'}</b><br/>
        <font size='8'>Filial: {filial_selecionada or 'Todas'} | Unidade: {unidade_selecionada or 'Todas'} | Gerado em: {hoje.strftime('%d/%m/%Y')}</font>
    """
    style_header_text = ParagraphStyle(name='HeaderText', alignment=TA_RIGHT, fontSize=10, leading=12)
    header_paragraph = Paragraph(header_text, style_header_text)

    def header_footer(canvas, doc):
        canvas.saveState()
        header_table = Table([[logo, header_paragraph]], colWidths=[4*cm, doc.width - 4*cm], style=[('VALIGN', (0,0), (-1,-1), 'MIDDLE')])
        
        page_width, page_height = doc.pagesize
        w, h = header_table.wrap(doc.width, doc.topMargin)
        header_table.drawOn(canvas, doc.leftMargin, page_height - 1.5*cm - h)
        
        line_y = page_height - 1.5*cm - h - 0.2*cm
        canvas.setStrokeColorRGB(0.7, 0.7, 0.7)
        canvas.line(doc.leftMargin, line_y, doc.leftMargin + doc.width, line_y)
        
        canvas.setFont('Helvetica', 8)
        canvas.drawString(doc.leftMargin, 1.5*cm, "Sistema de Gestão de Frotas")
        canvas.drawRightString(doc.leftMargin + doc.width, 1.5*cm, f"Página {doc.page}")
        canvas.restoreState()

    table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f2f2f2')), ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 8), ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#cccccc')),
    ])

    manutencao_col_width = 3.2 * cm
    col_widths = [
        doc.width - (manutencao_col_width * 5),
        manutencao_col_width, manutencao_col_width, manutencao_col_width, manutencao_col_width, manutencao_col_width
    ]
    
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(table_style)
    
    story = [t]
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"plano_manutencao_{hoje}.pdf", mimetype='application/pdf')

# --------------------------------------------------------------------------
# ROTA PARA ATUALIZAÇÃO DE KM EM MASSA 
# --------------------------------------------------------------------------

@main.route('/atualizar-km/<int:placa_id>', methods=['POST'])
@login_required
@requer_tipo("master", "comum", 'adm')
def atualizar_km(placa_id):
    placa_obj = Placa.query.get_or_404(placa_id)
    
    # Validação de permissão
    if not tem_permissao('editar_km_geral'):
        unidades_usuario = [u.strip().upper() for u in (current_user.unidade or '').split(',') if u]
        if not unidades_usuario or placa_obj.unidade not in unidades_usuario:
            flash('Você não tem permissão para atualizar o KM desta placa.', 'danger')
            return redirect(url_for('main.lista_placas'))

    km_novo_str = request.form.get('km_atual')

    if not km_novo_str or not km_novo_str.isdigit():
        flash('Valor de KM inválido.', 'danger')
        return redirect(url_for('main.lista_placas'))

    km_novo = int(km_novo_str)
    km_atual_db = placa_obj.km_atual or 0

    if km_novo < km_atual_db:
        flash(f'O novo KM ({format_km(km_novo)}) não pode ser menor que o atual ({format_km(km_atual_db)}).', 'warning')
        return redirect(url_for('main.lista_placas'))
    
    if km_novo != km_atual_db:
        placa_obj.km_atual = km_novo
        placa_obj.data_ultima_atualizacao_km = datetime.now(pytz.timezone("America/Fortaleza"))
        db.session.commit()
        
        registrar_log(current_user, f"Atualizou KM do veículo {placa_obj.placa} para {format_km(km_novo)}")
        flash(f'KM da placa {placa_obj.placa} atualizado para {format_km(km_novo)} com sucesso!', 'success')
    else:
        flash(f'Nenhuma alteração necessária para a placa {placa_obj.placa}.', 'info')

    return redirect(url_for('main.lista_placas'))


@main.route('/atualizar-km-massa', methods=['GET', 'POST'])
@login_required
@requer_tipo("master", "comum",'adm')
def atualizar_km_massa():
    form = FlaskForm() # Proteção CSRF
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('Nenhum arquivo enviado.', 'danger')
            return redirect(request.url)

        file = request.files['csv_file']

        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'warning')
            return redirect(request.url)

        if not file.filename.lower().endswith('.csv'):
            flash('Arquivo inválido. Por favor, envie um arquivo .csv', 'danger')
            return redirect(request.url)
            
        try:
            file.seek(0)
            text_stream = io.TextIOWrapper(file, encoding='utf-8-sig')

            try:
                primeira_linha = text_stream.readline()
                if not primeira_linha:
                    flash("O arquivo CSV está vazio.", "warning")
                    return redirect(url_for('main.lista_placas'))
                
                dialect = csv.Sniffer().sniff(primeira_linha, delimiters=',;')
                text_stream.seek(0)
            except (csv.Error, StopIteration):
                dialect = 'excel'
                text_stream.seek(0)

            csv_reader = csv.reader(text_stream, dialect)
            header = [h.strip().lower() for h in next(csv_reader)]

            if 'placa' not in header or 'km_atual' not in header:
                flash('O cabeçalho do arquivo CSV deve conter as colunas "placa" e "km_atual".', 'danger')
                return redirect(url_for('main.lista_placas'))

            placa_idx = header.index('placa')
            km_idx = header.index('km_atual')

            sucessos = 0
            erros_validacao = []
            placas_nao_encontradas = []

            # Filtra as placas permitidas para o usuário de uma só vez
            query_base = filtrar_query_por_usuario(Placa.query, Placa)
            placas_permitidas = {p.placa: p for p in query_base.all()}

            for row_num, row in enumerate(csv_reader, start=2):
                if not any(field.strip() for field in row): continue 
                
                if len(row) <= max(placa_idx, km_idx):
                    erros_validacao.append(f"Linha {row_num}: A linha está mal formatada ou incompleta.")
                    continue

                placa_csv = row[placa_idx].strip().upper()
                km_novo_str = row[km_idx].strip()

                if not placa_csv or not km_novo_str:
                    erros_validacao.append(f"Linha {row_num}: Placa ou KM em branco.")
                    continue

                if not km_novo_str.isdigit():
                    erros_validacao.append(f"Linha {row_num}: KM inválido para a placa {placa_csv} ('{km_novo_str}').")
                    continue
                
                km_novo = int(km_novo_str)

                placa_obj = placas_permitidas.get(placa_csv)

                if not placa_obj:
                    # Verifica se a placa existe mas o usuário não tem permissão
                    if Placa.query.filter_by(placa=placa_csv).first():
                        erros_validacao.append(f"Linha {row_num}: Você não tem permissão para atualizar a placa {placa_csv}.")
                    else:
                        placas_nao_encontradas.append(placa_csv)
                    continue
                
                km_atual_db = placa_obj.km_atual or 0
                if km_novo < km_atual_db:
                    erros_validacao.append(f"Linha {row_num}: KM da placa {placa_csv} ({format_km(km_novo)}) é menor que o atual ({format_km(km_atual_db)}). Atualização ignorada.")
                    continue

                if km_novo != km_atual_db:
                    placa_obj.km_atual = km_novo
                    placa_obj.data_ultima_atualizacao_km = datetime.now(pytz.timezone("America/Fortaleza"))
                    registrar_log(current_user, f"Atualizou KM em massa do veículo {placa_obj.placa} para {format_km(km_novo)}")
                    sucessos += 1

            db.session.commit()

            if sucessos > 0:
                 flash(f"{sucessos} veículo(s) teve(tiveram) o KM atualizado com sucesso.", 'success')

            if erros_validacao or placas_nao_encontradas:
                mensagem_erro_html = "<strong>Ocorreram os seguintes problemas durante a atualização:</strong><ul>"
                for erro in erros_validacao:
                    mensagem_erro_html += f"<li>{erro}</li>"
                if placas_nao_encontradas:
                    mensagem_erro_html += f"<li><strong>Placas não encontradas no sistema:</strong> {', '.join(sorted(list(set(placas_nao_encontradas))))}</li>"
                mensagem_erro_html += "</ul>"
                flash(Markup(mensagem_erro_html), 'warning')
            
            if sucessos == 0 and not erros_validacao and not placas_nao_encontradas:
                flash("Nenhuma alteração foi necessária. Os KMs no arquivo são iguais ou inferiores aos já registrados.", "info")

        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro inesperado ao processar o arquivo: {e}', 'danger')
            traceback.print_exc(file=sys.stderr)

        return redirect(url_for('main.lista_placas'))

    return render_template('atualizar_km_massa.html', form=form)



@main.route('/cadastro-veiculo', methods=['GET', 'POST'])
@login_required
@requer_tipo("master", "comum", "teste", "visualizador", "adm")
def cadastro_veiculo():
    veiculo_id = request.args.get('id')
    form = VehicleForm()

    # Edição: carregando veículo existente
    if veiculo_id:
        veiculo = Veiculo.query.get_or_404(veiculo_id)

        if request.method == 'GET':
            # Preenche os campos do formulário para exibição
            form.placa.data = veiculo.placa
            form.modelo.data = veiculo.modelo
            form.fabricante.data = veiculo.fabricante
            form.ano.data = veiculo.ano
            form.unidade.data = veiculo.unidade
            form.motorista.data = veiculo.motorista
            form.km_ultima_revisao_preventiva.data = veiculo.km_ultima_revisao_preventiva
            form.km_ultima_revisao_intermediaria.data = veiculo.km_ultima_revisao_intermediaria
            form.km_troca_preventiva.data = veiculo.km_troca_preventiva
            form.km_troca_intermediaria.data = veiculo.km_troca_intermediaria
            form.km_atual.data = veiculo.km_atual
            form.troca_oleo_diferencial.data = veiculo.troca_oleo_diferencial
            form.intervalo_oleo_diferencial.data = veiculo.intervalo_oleo_diferencial
            form.troca_oleo_cambio.data = veiculo.troca_oleo_cambio
            form.intervalo_oleo_cambio.data = veiculo.intervalo_oleo_cambio
            form.placa_1.data = veiculo.placa_1
            form.placa_2.data = veiculo.placa_2
            form.data_calibragem.data = veiculo.data_calibragem

        elif form.validate_on_submit():
            # --- CORREÇÃO APLICADA AQUI ---
            if not tem_permissao("alterar_dados"):
                flash("Você não tem permissão para alterar veículos.", "danger")
                return redirect(url_for('main.cadastro_veiculo', id=veiculo.id))

            # Atualiza os dados do veículo
            veiculo.placa = form.placa.data.upper()
            veiculo.modelo = form.modelo.data.upper()
            veiculo.fabricante = form.fabricante.data.upper()
            veiculo.ano = form.ano.data.upper()
            veiculo.unidade = form.unidade.data.upper()
            veiculo.motorista = form.motorista.data.upper()
            veiculo.km_ultima_revisao_preventiva = form.km_ultima_revisao_preventiva.data
            veiculo.km_ultima_revisao_intermediaria = form.km_ultima_revisao_intermediaria.data
            veiculo.km_troca_preventiva = form.km_troca_preventiva.data
            veiculo.km_troca_intermediaria = form.km_troca_intermediaria.data
            veiculo.km_atual = form.km_atual.data
            veiculo.troca_oleo_diferencial = form.troca_oleo_diferencial.data
            veiculo.intervalo_oleo_diferencial = form.intervalo_oleo_diferencial.data
            veiculo.troca_oleo_cambio = form.troca_oleo_cambio.data
            veiculo.intervalo_oleo_cambio = form.intervalo_oleo_cambio.data
            veiculo.placa_1 = form.placa_1.data.upper() if form.placa_1.data else None
            veiculo.placa_2 = form.placa_2.data.upper() if form.placa_2.data else None
            veiculo.data_calibragem = form.data_calibragem.data

            db.session.commit()
            registrar_log(current_user, f"Atualizou o veículo {veiculo.placa}")
            flash(f'Veículo {veiculo.placa} atualizado com sucesso!', 'success')
            return redirect(url_for('main.cadastro_veiculo', id=veiculo.id))

    else:
        # Cadastro novo
        if form.validate_on_submit():
            # --- CORREÇÃO APLICADA AQUI ---
            if not tem_permissao("alterar_dados"):
                flash("Você não tem permissão para cadastrar novos veículos.", "danger")
                return redirect(url_for('main.cadastro_veiculo'))

            placa_formatada = form.placa.data.upper()
            existente = Veiculo.query.filter_by(placa=placa_formatada).first()
            if existente:
                flash(f"A placa {placa_formatada} já está cadastrada.", "warning")
                return redirect(url_for('main.cadastro_veiculo'))

            veiculo = Veiculo(
                placa=placa_formatada,
                modelo=form.modelo.data.upper(),
                fabricante=form.fabricante.data.upper(),
                ano=form.ano.data.upper(),
                unidade=form.unidade.data.upper(),
                motorista=form.motorista.data.upper(),
                km_ultima_revisao_preventiva=form.km_ultima_revisao_preventiva.data,
                km_ultima_revisao_intermediaria=form.km_ultima_revisao_intermediaria.data,
                km_troca_preventiva=form.km_troca_preventiva.data,
                km_troca_intermediaria=form.km_troca_intermediaria.data,
                km_atual=form.km_atual.data or 0,
                troca_oleo_diferencial=form.troca_oleo_diferencial.data,
                intervalo_oleo_diferencial=form.intervalo_oleo_diferencial.data,
                troca_oleo_cambio=form.troca_oleo_cambio.data,
                intervalo_oleo_cambio=form.intervalo_oleo_cambio.data,
                placa_1=form.placa_1.data.upper() if form.placa_1.data else None,
                placa_2=form.placa_2.data.upper() if form.placa_2.data else None,
                data_calibragem=form.data_calibragem.data
            )

            db.session.add(veiculo)
            db.session.commit()
            registrar_log(current_user, f"Cadastrou o veículo {veiculo.placa}")
            flash(f'Veículo {veiculo.placa} cadastrado com sucesso!', 'success')
            return redirect(url_for('main.cadastro_veiculo', id=veiculo.id))

    return render_template('vehicle_register.html', form=form)

# @main.route('/editar-veiculo/<int:id>', methods=['GET', 'POST'])
# @login_required
# @requer_tipo("master")
# def editar_veiculo(id):
#     veiculo = Veiculo.query.get_or_404(id)

#     novos_dados = {
#         "placa": request.form.get('placa', '').upper(),
#         "carreta1": request.form.get('carreta1', '').upper(),
#         "carreta2": request.form.get('carreta2', '').upper(),
#         "motorista": request.form.get('motorista', '').upper(),
#         "modelo": request.form.get('modelo', '').upper(),
#         "fabricante": request.form.get('fabricante', '').upper(),
#         "ano": request.form.get('ano', '').upper(),
#         "km_atual": int(request.form.get('km_atual')) if request.form.get('km_atual', '').isdigit() else 0
#     }

#     alteracoes = detectar_alteracoes(veiculo, novos_dados)
#     print("Alterações detectadas:", alteracoes)


#     if alteracoes:
#         for campo, valor in novos_dados.items():
#             setattr(veiculo, campo, valor)

#         db.session.commit()
#         registrar_log(current_user, f"Editou veículo {veiculo.placa}: " + "; ".join(alteracoes))
#         flash(f'Dados do veículo {veiculo.placa} atualizados no painel!', 'success')
#     else:
#         flash(f'Nenhuma alteração detectada no veículo {veiculo.placa}.', 'info')

#     return redirect(url_for('main.lista_placas'))

def _registrar_manutencao_core(placa_id, tipo_manutencao, km_manutencao, data_manutencao, observacoes, usuario_log):
    """
    Função ÚNICA e CENTRAL para registrar uma manutenção, agora com a lógica de negócio CORRETA.
    """
    try:
        placa_obj = Placa.query.get(placa_id)
        if not placa_obj:
            return (False, f"Erro Crítico: Placa com ID {placa_id} não encontrada.")

        tipo_upper = tipo_manutencao.upper()
        
        # --- ATUALIZAÇÃO DO ESTADO DA PLACA ---
        if tipo_upper == 'PREVENTIVA':
            placa_obj.km_ultima_revisao_preventiva = km_manutencao
            placa_obj.data_ultima_revisao_preventiva = data_manutencao
            placa_obj.km_ultima_revisao_intermediaria = km_manutencao
            placa_obj.data_ultima_revisao_intermediaria = data_manutencao
        
        elif tipo_upper == 'INTERMEDIARIA':
            placa_obj.km_ultima_revisao_intermediaria = km_manutencao
            placa_obj.data_ultima_revisao_intermediaria = data_manutencao
        
        elif tipo_upper == 'DIFERENCIAL':
            placa_obj.troca_oleo_diferencial = km_manutencao
            placa_obj.data_troca_oleo_diferencial = data_manutencao
        
        elif tipo_upper == 'CAMBIO':
            placa_obj.troca_oleo_cambio = km_manutencao
            placa_obj.data_troca_oleo_cambio = data_manutencao
        
        elif tipo_upper == 'CARRETA':
            # --- LÓGICA CORRIGIDA PARA ENCONTRAR E ATUALIZAR A CARRETA ---
            # O usuário seleciona a placa do cavalo (placa_obj), então precisamos encontrar o conjunto.
            veiculo_conjunto = Veiculo.query.filter_by(placa_cavalo_id=placa_obj.id).first()

            if not veiculo_conjunto or not veiculo_conjunto.placa_carreta1:
                return (False, "A placa selecionada não pertence a um conjunto com uma carreta associada.")

            # Atualiza a data de revisão no objeto correto (a carreta).
            carreta_a_atualizar = veiculo_conjunto.placa_carreta1
            carreta_a_atualizar.data_proxima_revisao_carreta = data_manutencao + relativedelta(months=+6)
            db.session.add(carreta_a_atualizar) # Garante que a alteração na carreta será salva.
        
        else:
            return (False, f"Tipo de manutenção desconhecido: {tipo_upper}")

        # Atualiza o KM principal da placa se o da manutenção for mais recente
        if km_manutencao > (placa_obj.km_atual or 0):
            placa_obj.km_atual = km_manutencao
            placa_obj.data_ultima_atualizacao_km = datetime.now(pytz.timezone("America/Fortaleza"))

        nova_manutencao = Manutencao(
            placa_id=placa_obj.id, tipo=tipo_upper, km_realizado=km_manutencao,
            data_troca=data_manutencao, observacoes=observacoes
        )
        db.session.add(nova_manutencao)
        db.session.add(placa_obj) # Garante que as alterações na placa do cavalo (como KM) sejam salvas
        db.session.flush()

        # Libera bloqueios pendentes
        tipos_a_liberar = {'PREVENTIVA': ['Preventiva', 'Intermediária'], 'INTERMEDIARIA': ['Intermediária'], 'DIFERENCIAL': ['Diferencial'], 'CAMBIO': ['Câmbio']}.get(tipo_upper, [])
        if tipos_a_liberar:
            HistoricoBloqueio.query.filter(
                HistoricoBloqueio.placa_id == placa_obj.id,
                HistoricoBloqueio.tipo_manutencao.in_(tipos_a_liberar),
                HistoricoBloqueio.liberado == False
            ).update({'liberado': True, 'data_liberacao': datetime.utcnow(), 'manutencao_id': nova_manutencao.id}, synchronize_session='fetch')
        
        db.session.commit()
        
        log_obs = "via PDF" if "PDF" in str(observacoes) else "manualmente"
        registrar_log(usuario_log, f"Registrou manutenção {tipo_upper} for {placa_obj.placa} ({log_obs})")
        
        return (True, f"Manutenção '{tipo_upper}' para a placa {placa_obj.placa} registrada com sucesso!")

    except Exception as e:
        db.session.rollback()
        print(f"Erro no core de registro de manutenção: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return (False, "Ocorreu um erro interno grave ao tentar registrar a manutenção.")



@main.route('/realizar-manutencao', methods=['GET', 'POST'])
@login_required
@requer_tipo("master", "comum", "adm")
def realizar_manutencao():
    """ Rota para o formulário manual. Apenas coleta dados e chama a função core. """
    form = ManutencaoForm()
    placas = Placa.query.order_by(Placa.placa).all()
    form.veiculo_id.choices = [(p.id, p.placa) for p in placas]

    if request.method == 'GET':
        placa_parametro = request.args.get('placa_pre_selecionada', '').upper().strip()
        if placa_parametro:
            placa_pre_selecionada = next((p for p in placas if p.placa == placa_parametro), None)
            if placa_pre_selecionada:
                form.veiculo_id.data = placa_pre_selecionada.id

    if form.validate_on_submit():
        if not tem_permissao('alterar_dados'):
            flash("Você não tem permissão para registrar manutenções.", "warning")
            return redirect(url_for('main.realizar_manutencao'))

        placa_id = form.veiculo_id.data
        tipo = form.tipo.data
        km_realizado = form.km_realizado.data or 0
        
        if tipo.upper() != 'CARRETA' and km_realizado <= 0:
            placa_obj = Placa.query.get(placa_id)
            flash("Informe o KM atual para este tipo de manutenção.", "danger")
            return redirect(url_for('main.realizar_manutencao', placa_pre_selecionada=placa_obj.placa if placa_obj else ''))

        sucesso, mensagem = _registrar_manutencao_core(
            placa_id=placa_id, tipo_manutencao=tipo, km_manutencao=km_realizado,
            data_manutencao=form.data.data, observacoes=form.observacoes.data,
            usuario_log=current_user
        )

        if sucesso:
            flash(mensagem, 'success')
        else:
            flash(mensagem, 'danger')
        
        return redirect(url_for('veiculos.gerenciar_veiculos'))

    return render_template('realizar_manutencao.html', form=form)




@main.route('/excluir-veiculo/<int:id>')
@login_required
@requer_tipo("master",'adm')
def excluir_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    Manutencao.query.filter_by(veiculo_id=veiculo.id).delete()  # Apaga manutenções primeiro
    db.session.delete(veiculo)
    db.session.commit()
    registrar_log(current_user, f"Excluiu o veículo {veiculo} e suas manutenções vinculadas")
    flash(f'Veículo {veiculo.placa} removido com sucesso.', 'info')
    return redirect(url_for('main.lista_placas'))



# Em app/routes.py, substitua a função inteira por esta:

@main.route('/placas')
@login_required
def lista_placas():
    # 1. Captura os filtros da URL
    filial_filtro = request.args.get('filial', '').upper()
    unidade_filtro = request.args.get('unidade', '').upper()

    # 2. Query base com filtro de permissão e joins necessários
    query = filtrar_query_por_usuario(Veiculo.query, Veiculo).options(
        joinedload(Veiculo.placa_cavalo),
        joinedload(Veiculo.placa_carreta1),
        joinedload(Veiculo.placa_carreta2),
        joinedload(Veiculo.motorista)
    )
    
    # Garante que apenas veículos ativos sejam exibidos.
    query = query.filter(Veiculo.ativo == True)

    # 3. Aplica os filtros USANDO a tabela Veiculo como fonte
    if filial_filtro:
        query = query.filter(Veiculo.filial == filial_filtro)
    if unidade_filtro:
        query = query.filter(Veiculo.unidade == unidade_filtro)

    # 4. Executa a query e agrupa os veículos pela unidade do CONJUNTO
    veiculos_filtrados = query.order_by(Veiculo.unidade, Veiculo.nome_conjunto).all()
    unidades_agrupadas = defaultdict(list)
    for v in veiculos_filtrados:
        # --- CORREÇÃO APLICADA AQUI ---
        # A fonte de verdade para a unidade do conjunto deve ser o próprio objeto 'v' (Veiculo).
        if v.unidade:
            unidades_agrupadas[v.unidade.upper()].append(v)

    # 5. Lógica para popular os menus de filtro (baseada nos Veículos para consistência)
    filiais_disponiveis = []
    unidades_para_filtro = []
    filial_unidade_map = {}
    todas_as_unidades_gerais = []

    if current_user.tipo in ['adm', 'master']:
        # Busca todas as combinações únicas de filial/unidade da tabela Veiculo
        pares_filial_unidade = db.session.query(Veiculo.filial, Veiculo.unidade).distinct().filter(Veiculo.unidade != None, Veiculo.unidade != '').all()
        
        filiais_set = set()
        unidades_set = set()

        for filial, unidade in pares_filial_unidade:
            unidades_set.add(unidade)
            if filial:
                filiais_set.add(filial)
                if filial not in filial_unidade_map:
                    filial_unidade_map[filial] = []
                filial_unidade_map[filial].append(unidade)

        filiais_disponiveis = sorted(list(filiais_set))
        todas_as_unidades_gerais = sorted(list(unidades_set))
        
        for f in filial_unidade_map:
            filial_unidade_map[f].sort()

        if filial_filtro:
            unidades_para_filtro = filial_unidade_map.get(filial_filtro, [])
        else:
            unidades_para_filtro = todas_as_unidades_gerais
    
    return render_template(
        'placas.html', 
        unidades=unidades_agrupadas, 
        current_date=date.today(),
        filiais_disponiveis=filiais_disponiveis,
        unidades_para_filtro=unidades_para_filtro,
        todas_unidades_json=todas_as_unidades_gerais, 
        filial_selecionada=filial_filtro,
        unidade_selecionada=unidade_filtro,
        filial_unidade_map=filial_unidade_map
    )





@main.route('/unidade/<unidade>')
@login_required
@requer_tipo("master", "comum",'adm')
def filtrar_unidade(unidade):
    veiculos = Veiculo.query.filter_by(unidade=unidade.upper()).order_by(Veiculo.placa).all()
    return render_template('index.html', veiculos=veiculos, current_date=date.today())


@main.route('/nova-manutencao')
@login_required
@requer_tipo("master", "comum",'adm')
def nova_manutencao():
    return render_template('new_entry.html')


#@main.route('/teste-alerta')
#def teste_alerta():
 #   from alertas import disparar_alertas_reais
  #  disparar_alertas_reais()
  #  flash("🚨 Alerta via template disparado com sucesso!", "success")
  #  return redirect(url_for('main.index'))

@main.route('/teste-alerta')
@login_required
def teste_alerta():
    if current_user.tipo.upper() != 'MASTER':
        flash("❌ Apenas usuários MASTER podem disparar alertas!", "danger")
        return redirect(url_for('main.index'))

    from manutencao.app.alertas import disparar_alertas_multiplos
    disparar_alertas_multiplos()
    flash("🚨 Alertas enviados com sucesso!", "success")
    return redirect(url_for('main.index'))



@main.route('/gerar-relatorio-pdf')
@login_required
@requer_tipo("master", "comum",'adm')
def gerar_relatorio_pdf():
    linhas = extrair_dados()

    if not linhas:
        flash("Nenhum veículo está com revisão próxima.", "info")
        return redirect(url_for('main.index'))

    html = render_template_string("""
    <html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>

        <style>
            body {
                font-family: Helvetica, Arial, sans-serif;
                padding: 30px;
                color: #333;
            }
            h1 {
                text-align: center;
                color: #004085;
                border-bottom: 2px solid #007bff;
                padding-bottom: 5px;
                margin-bottom: 30px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            th, td {
                border: 1px solid #999;
                padding: 8px;
                font-size: 12px;
                text-align: center;
            }
            th {
                background-color: #e3e3e3;
            }
            .footer {
                margin-top: 40px;
                font-size: 11px;
                text-align: center;
                color: #777;
            }
        </style>
    </head>
    <body>
        <h1>Relatório de Manutenção</h1>
        <p><strong>Data:</strong> {{ hoje }}</p>
        <table>
            <thead>
                <tr>
                    <th>Placa</th>
                    <th>Motorista</th>
                    <th>KM Atual</th>
                    <th>Preventiva</th>
                    <th>Intermediária</th>
                </tr>
            </thead>
            <tbody>
                {% for linha in linhas %}
                <tr>
                    <td>{{ linha.placa }}</td>
                    <td>{{ linha.motorista }}</td>
                    <td>{{ linha.km_atual }}</td>
                    <td>{{ linha.preventiva }}</td>
                    <td>{{ linha.intermediaria }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        <div class="footer">
            Sistema de Gestão de Frota - {{ hoje }}
        </div>
    </body>
    </html>
    """, hoje=datetime.today().strftime('%d/%m/%Y'), linhas=linhas)

    pdf_buffer = BytesIO()
    pisa.CreatePDF(BytesIO(html.encode('utf-8')), dest=pdf_buffer)

    response = make_response(pdf_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=relatorio_manutencao.pdf'  # 🔽 Gatilho pra download
    return response

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome_usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        usuario = Usuario.query.filter(func.lower(Usuario.usuario) == nome_usuario.lower()).first()

        # --- LÓGICA DE LOGIN ATUALIZADA ---
        if usuario and usuario.verificar_senha(senha):
            # Adiciona verificação para impedir login de usuário inativo
            if not usuario.ativo:
                flash('Este usuário está desativado e não pode acessar o sistema.', 'warning')
                return redirect(url_for('main.login'))
            
            login_user(usuario)
            session.permanent = True
            registrar_log(usuario, f"Fez login no sistema")
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
            
    return render_template('login.html', ano=datetime.now().year)



@main.route('/logout')
@login_required
def logout():
    registrar_log(current_user, f"Fez logout do sistema")
    logout_user()
    flash("Logout realizado com sucesso!", "info")
    return redirect(url_for('main.login'))


@main.route('/usuarios', methods=['GET'])
@login_required
@requer_tipo('adm')
def gerenciar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.id).all()
    
    # Busca apenas por unidades únicas para o dropdown
    unidades_query = db.session.query(Placa.unidade).distinct().order_by(Placa.unidade).all()
    
    # Extrai os valores da tupla para uma lista simples
    lista_unidades = [u[0] for u in unidades_query if u[0]]
    
    # A variável 'filiais' foi removida do render_template
    return render_template('cadastro_usuario.html', 
                           usuarios=usuarios,
                           unidades=lista_unidades)



@main.route('/usuarios/adicionar', methods=['POST'])
@login_required
@requer_tipo('adm')
def adicionar_usuario():
    nome = request.form.get('nome')
    senha = request.form.get('senha')
    tipo = request.form.get('tipo').lower()
    filial = request.form.get('filial')
    unidade = request.form.get('unidade')

    if Usuario.query.filter(func.lower(Usuario.usuario) == nome.lower()).first():
        flash('Usuário já existe!', 'warning')
    else:
        # Trata os campos para garantir consistência (maiúsculas, sem espaços)
        # Se a opção "Nenhuma" for selecionada, o valor será uma string vazia, que se tornará None.
        filial_tratada = filial.strip().upper() if filial else None
        unidade_tratada = unidade.strip().upper() if unidade else None

        novo = Usuario(
            usuario=nome.lower(), 
            nome=nome.title(), 
            tipo=tipo, 
            filial=filial_tratada, 
            unidade=unidade_tratada
        )
        novo.set_senha(senha)
        db.session.add(novo)
        db.session.commit()
        
        log_msg = f"Cadastrou o usuário {nome}"
        if filial_tratada: log_msg += f" na filial {filial_tratada}"
        if unidade_tratada: log_msg += f" e unidade {unidade_tratada}"
        registrar_log(current_user, log_msg)
        
        flash(f'Usuário {nome} criado com sucesso!', 'success')

    return redirect(url_for('main.gerenciar_usuarios'))


@main.route('/usuarios/alternar_status/<int:id>', methods=['POST'])
@login_required
@requer_tipo('adm')
def alternar_status_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    if usuario.usuario.lower() == 'admin':
        flash('O status do usuário "admin" não pode ser alterado.', 'danger')
    elif usuario.id == current_user.id:
        flash('Você não pode desativar a si mesmo.', 'danger')
    else:
        # Lógica para INVERTER o status do usuário
        usuario.ativo = not usuario.ativo
        db.session.commit()
        
        # Mensagens dinâmicas
        status_texto = "reativado" if usuario.ativo else "desativado"
        log_msg = f"{status_texto.capitalize()} o usuário {usuario.nome}"
        registrar_log(current_user, log_msg)
        
        flash(f'Usuário {usuario.nome} foi {status_texto} com sucesso.', 'info')

    return redirect(url_for('main.gerenciar_usuarios'))


@main.route("/logs")
@login_required
def exibir_logs():
    logs = LogSistema.query.order_by(LogSistema.data.desc()).limit(200).all()

    for log in logs:
        if log.data.tzinfo is None:
            log.data = log.data.replace(tzinfo=ZoneInfo("UTC"))
        log.data = log.data.astimezone(ZoneInfo("America/Fortaleza"))

    # 🔥 Ordena no Python após aplicar timezone
    logs.sort(key=lambda l: l.data, reverse=True)

    return render_template("logs.html", logs=logs)

@main.route('/manutencao/<placa>', methods=['POST'])
@login_required
def atualizar_manutencao(placa):
    if current_user.tipo.upper() != 'MASTER':
        abort(403)

    veiculo = Veiculo.query.filter_by(placa=placa).first_or_404()
    veiculo.em_manutencao = not veiculo.em_manutencao
    db.session.commit()
    return jsonify({'status': 'ok', 'ativo': veiculo.em_manutencao})


@main.route('/pneus', methods=['GET', 'POST'])
@login_required
def mostrar_pneus():
    form = PneuAplicadoForm()

    if form.validate_on_submit():
        numero_fogo = form.numero_fogo.data.upper()
        pneu_estoque = EstoquePneu.query.filter_by(numero_fogo=numero_fogo, status='DISPONIVEL').first()
        if not pneu_estoque:
            registrar_log(current_user, f"Tentativa de aplicar pneu indisponível: {numero_fogo}")
            flash('❌ Este pneu não está disponível no estoque!', 'danger')
            return render_template('pneus.html', form=form, pneus=[])

        pneu = PneuAplicado(
            placa=form.placa.data.upper(),
            referencia=form.referencia.data.upper(),
            dot=form.dot.data.upper(),
            numero_fogo=numero_fogo,
            quantidade=form.quantidade.data,
            data_aplicacao=form.data_aplicacao.data,
            unidade=form.unidade.data,
            observacoes=form.observacoes.data,
            extra=form.extra.data
        )
        db.session.add(pneu)
        pneu_estoque.status = 'APLICADO'
        db.session.commit()

        registrar_log(current_user, f"Pneu aplicado: {numero_fogo} na placa {form.placa.data.upper()}")
        flash('✅ Pneu aplicado com sucesso!', 'success')
        return redirect('/pneus')

    placa = request.args.get('placa', '').upper()
    fogo = request.args.get('numero_fogo', '').upper()
    unidade = request.args.get('unidade', '')
    query = PneuAplicado.query
    if placa:
        query = query.filter(PneuAplicado.placa.ilike(f"%{placa}%"))
    if fogo:
        query = query.filter(PneuAplicado.numero_fogo.ilike(f"%{fogo}%"))
    if unidade:
        query = query.filter(PneuAplicado.unidade == unidade)

    pneus = query.order_by(PneuAplicado.id.desc()).limit(15).all()
    return render_template('pneus.html', form=form, pneus=pneus)


@main.route('/pneus/editar_placa', methods=['POST'])
@login_required
def editar_placa():
    id = request.form.get('id')
    nova_placa = request.form.get('placa', '').upper()
    nova_unidade = request.form.get('unidade', '').upper()

    pneu = PneuAplicado.query.get(id)
    if pneu:
        pneu.placa = nova_placa
        pneu.unidade = nova_unidade
        db.session.commit()
        registrar_log(current_user, f"Edição de placa do pneu ID {id}: nova placa {nova_placa}, unidade {nova_unidade}")
        flash(f'✅ Dados atualizados com sucesso!', 'success')
    else:
        registrar_log(current_user, f"Tentativa de editar placa: pneu ID {id} não encontrado")
        flash('❌ Pneu não encontrado', 'danger')

    return redirect('/pneus')


@main.route('/pneus/pdf', methods=['GET'])
@login_required
def gerar_pdf():
    placa = request.args.get('placa', '').upper()
    fogo = request.args.get('numero_fogo', '').upper()
    unidade = request.args.get('unidade', '')

    query = PneuAplicado.query
    if placa:
        query = query.filter(PneuAplicado.placa.ilike(f"%{placa}%"))
    if fogo:
        query = query.filter(PneuAplicado.numero_fogo.ilike(f"%{fogo}%"))
    if unidade:
        query = query.filter(PneuAplicado.unidade == unidade)

    pneus = query.order_by(PneuAplicado.id.desc()).all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height - 50, "Relatório de Pneus Aplicados")

    pdf.setFont("Helvetica", 10)
    y = height - 80
    for i, p in enumerate(pneus, start=1):
        linha = f"{i}. Placa: {p.placa} | Ref: {p.referencia} | DOT: {p.dot} | Fogo: {p.numero_fogo} | Qtd: {p.quantidade} | Data: {p.data_aplicacao.strftime('%d/%m/%Y')} | Unidade: {p.unidade}"
        pdf.drawString(50, y, linha)
        y -= 15
        if y < 50:
            pdf.showPage()
            y = height - 50

    pdf.save()
    buffer.seek(0)
    registrar_log(current_user, f"PDF de pneus aplicado gerado: placa={placa}, fogo={fogo}, unidade={unidade}")
    return send_file(buffer, as_attachment=True, download_name="pneus_aplicados.pdf", mimetype='application/pdf')

@main.route('/estoque', methods=['GET', 'POST'])
@login_required
def cadastrar_estoque():
    form = EstoquePneuForm()

    if form.validate_on_submit():
        existente = EstoquePneu.query.filter_by(numero_fogo=form.numero_fogo.data.upper()).first()
        if existente:
            registrar_log(current_user, f"Tentativa duplicada de cadastro: {form.numero_fogo.data.upper()}")
            flash('❌ Este número de fogo já está cadastrado no estoque.', 'danger')
            return redirect('/estoque')

        pneu = EstoquePneu(
            numero_fogo=form.numero_fogo.data.upper(),
            vida=form.vida.data,
            modelo=form.modelo.data.upper(),
            desenho=form.desenho.data.upper(),
            dot=form.dot.data.upper(),
            data_entrada=form.data_entrada.data,
            observacoes=form.observacoes.data
        )
        db.session.add(pneu)
        db.session.commit()
        registrar_log(current_user, f"Cadastro de pneu no estoque: {form.numero_fogo.data.upper()}")
        flash('✅ Pneu cadastrado no estoque com sucesso!', 'success')
        return redirect('/estoque')

    return render_template('estoque_pneus.html', form=form)


@main.route('/estoque/visualizar', methods=['GET'])
@login_required
def visualizar_estoque():
    numero_fogo = request.args.get('numero_fogo', '').upper()
    modelo = request.args.get('modelo', '').upper()
    desenho = request.args.get('desenho', '').upper()

    query = EstoquePneu.query.filter_by(status='DISPONIVEL')
    if numero_fogo:
        query = query.filter(EstoquePneu.numero_fogo.ilike(f"%{numero_fogo}%"))
    if modelo:
        query = query.filter(EstoquePneu.modelo.ilike(f"%{modelo}%"))
    if desenho:
        query = query.filter(EstoquePneu.desenho == desenho)

    pneus = query.order_by(EstoquePneu.id.desc()).all()
    total_estoque = EstoquePneu.query.filter_by(status='DISPONIVEL').count()
    total_aplicados = PneuAplicado.query.count()
    liso = EstoquePneu.query.filter_by(desenho='LISO', status='DISPONIVEL').count()
    borrachudo = EstoquePneu.query.filter_by(desenho='BORRACHUDO', status='DISPONIVEL').count()

    registrar_log(current_user, f"Visualização do estoque: fogo={numero_fogo}, modelo={modelo}, desenho={desenho}")
    return render_template('estoque_visualizar.html', pneus=pneus,
                           total_estoque=total_estoque,
                           total_aplicados=total_aplicados,
                           liso=liso, borrachudo=borrachudo)



@main.route('/estoque/pdf', methods=['GET'])
@login_required
def gerar_pdf_estoque():
    numero_fogo = request.args.get('numero_fogo', '').upper()
    modelo = request.args.get('modelo', '').upper()
    desenho = request.args.get('desenho', '').upper()

    query = EstoquePneu.query
    if numero_fogo:
        query = query.filter(EstoquePneu.numero_fogo.ilike(f"%{numero_fogo}%"))
    if modelo:
        query = query.filter(EstoquePneu.modelo.ilike(f"%{modelo}%"))
    if desenho:
        query = query.filter(EstoquePneu.desenho == desenho)

    pneus = query.order_by(EstoquePneu.id.desc()).all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height - 50, "📦 Relatório de Estoque de Pneus")

    pdf.setFont("Helvetica", 10)
    y = height - 80
    for i, p in enumerate(pneus, start=1):
        linha = f"{i}. Fogo: {p.numero_fogo} | Vida: {p.vida} | Modelo: {p.modelo} | Desenho: {p.desenho} | DOT: {p.dot} | Entrada: {p.data_entrada.strftime('%d/%m/%Y')}"
        pdf.drawString(50, y, linha)
        y -= 15
        if y < 50:
            pdf.showPage()
            y = height - 50

    pdf.save()
    buffer.seek(0)

    # 📝 Registrar log da ação
    registrar_log(current_user, f"PDF do estoque gerado: fogo={numero_fogo}, modelo={modelo}, desenho={desenho}")

    return send_file(buffer, as_attachment=True, download_name="estoque_pneus.pdf", mimetype='application/pdf')


@main.route('/pneus/detalhes', methods=['GET'])
@login_required
def detalhes_pneu():
    numero_fogo = request.args.get('numero_fogo', '').upper()

    # Verifica se já foi aplicado
    pneu = PneuAplicado.query.filter_by(numero_fogo=numero_fogo).order_by(PneuAplicado.id.desc()).first()
    if pneu:
        return jsonify({
            'placa': pneu.placa,
            'referencia': pneu.referencia,   # campo existe no PneuAplicado
            'dot': pneu.dot,
            'quantidade': 1
        })

    # Verifica no estoque
    estoque = EstoquePneu.query.filter_by(numero_fogo=numero_fogo, status='DISPONIVEL').first()
    if estoque:
        return jsonify({
            'placa': '',                      # Ainda não aplicado
            'referencia': estoque.modelo,     # usa 'modelo' como referência
            'dot': estoque.dot,
            'quantidade': 1
        })

    return jsonify({})

#################################################################
#RELAORIOS

# Esta função auxiliar lê a imagem e a prepara para o PDF
def get_image_file_as_base64_data(file_path):
    """Lê um arquivo de imagem e o converte para uma string data URI em Base64."""
    try:
        with open(file_path, "rb") as image_file:
            image_type = 'jpeg' if file_path.lower().endswith(('.jpg', '.jpeg')) else 'png'
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:image/{image_type};base64,{encoded_string}"
    except (IOError, FileNotFoundError):
        print(f"ERRO: A imagem em '{file_path}' não foi encontrada.")
        return ""

@main.route('/relatorios/pdf')
@login_required
def baixar_relatorio_pdf():
    """Gera e baixa um relatório em PDF com base no tipo solicitado."""
    tipo = request.args.get('tipo')
    if not tipo:
        flash('É necessário especificar um tipo de relatório.', 'warning')
        return redirect(url_for('main.relatorios'))

    company_data = {
        "name": "TRANSP TRANSPORTES DE PETRÓLEO LTDA",
        "address": "RODOVIA AVENIDA PIL PEREIRA TIM, Nº-910A, EMAUS, - PARNAMIRIM, RN, CEP: 59149-090",
        "cnpj": "40.760.217/0006-29",
        "phone": "(84) 9 9612-9655"
    }

    dados = []
    template_path = ""
    titulo_pdf = ""

    # --- LÓGICA DO FILTRO 'A VENCER' ADICIONADA AQUI ---
    if tipo == 'a_vencer':
        template_path = 'report_a_vencer.html'
        titulo_pdf = 'Relatório de Manutenções a Vencer'
        
        todos_veiculos = Veiculo.query.order_by(Veiculo.placa).all()
        #todos_veiculos = Veiculo.query.filter(Veiculo.unidade != 'SMART').order_by(Veiculo.placa).all()# exclui SMART da lista

        veiculos_a_vencer = []
        
        for v in todos_veiculos:
            manutencoes = []
            # Verifica KMs próximos (entre 1 e 5000 km)
            if v.km_para_preventiva and 0 < v.km_para_preventiva <= 5000:
                manutencoes.append(f"Preventiva em {v.km_para_preventiva} km")
            if v.km_para_intermediaria and 0 < v.km_para_intermediaria <= 5000:
                manutencoes.append(f"Intermediária em {v.km_para_intermediaria} km")
            if v.km_para_diferencial and 0 < v.km_para_diferencial <= 5000:
                manutencoes.append(f"Diferencial em {v.km_para_diferencial} km")
            if v.km_para_cambio and 0 < v.km_para_cambio <= 5000:
                manutencoes.append(f"Câmbio em {v.km_para_cambio} km")
            
            # Verifica data da carreta (próximos 30 dias)
            if v.data_proxima_revisao_carreta and date.today() < v.data_proxima_revisao_carreta <= date.today() + timedelta(days=30):
                manutencoes.append(f"Carreta em {v.data_proxima_revisao_carreta.strftime('%d/%m/%Y')}")

            if manutencoes:
                v.manutencoes_pendentes_texto = manutencoes # Propriedade temporária para o template
                veiculos_a_vencer.append(v)
                
        dados = veiculos_a_vencer

    elif tipo == 'bloqueados':
        template_path = 'report_bloqueados.html'
        titulo_pdf = 'Relatório de Veículos Bloqueados'
        dados = HistoricoBloqueio.query.filter_by(liberado=False).order_by(HistoricoBloqueio.data_bloqueio).all()
        #dados = HistoricoBloqueio.query.join(Veiculo).filter(
        #Veiculo.unidade != 'SMART',HistoricoBloqueio.liberado == False).order_by(HistoricoBloqueio.data_bloqueio).all()# exclui SMART da lista


    elif tipo == 'historico_bloqueios':
        template_path = 'report_historico_bloqueios.html'
        titulo_pdf = 'Histórico Completo de Bloqueios'
        dados = HistoricoBloqueio.query.order_by(HistoricoBloqueio.id.desc()).all()
        #dados = HistoricoBloqueio.query.join(Veiculo).filter(Veiculo.unidade != 'SMART').order_by(HistoricoBloqueio.id.desc()).all()# exclui SMART da lista


    elif tipo == 'realizadas':
        template_path = 'report_realizadas.html'
        titulo_pdf = 'Relatório de Manutenções Realizadas'
        dados = Manutencao.query.order_by(Manutencao.data_troca.desc()).all()
        #dados = Manutencao.query.join(Veiculo).filter(Veiculo.unidade != 'SMART').order_by(Manutencao.data_troca.desc()).all()# exclui SMART da lista

    
    else:
        flash(f'Tipo de relatório "{tipo}" desconhecido.', 'danger')
        return redirect(url_for('main.relatorios'))

    if not dados:
        flash(f'Nenhum dado encontrado para o relatório de "{titulo_pdf}".', 'info')
        return redirect(url_for('main.relatorios'))

    logo_file_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.jpg')
    logo_data_uri = get_image_file_as_base64_data(logo_file_path)

    html = render_template(
        template_path, data=dados, title=titulo_pdf, logo_path=logo_data_uri,
        generation_date=date.today().strftime('%d/%m/%Y'),
        company_name=company_data["name"], company_address=company_data["address"],
        company_cnpj=company_data["cnpj"], company_phone=company_data["phone"]
    )

    pdf_stream = BytesIO()
    pisa_status = pisa.CreatePDF(html.encode('utf-8'), dest=pdf_stream, encoding='utf-8')

    if pisa_status.err:
        flash('Ocorreu um erro ao gerar o relatório PDF.', 'danger')
        return redirect(url_for('main.relatorios'))

    pdf_stream.seek(0)
    response = make_response(pdf_stream.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={tipo}_{date.today()}.pdf'
    
    return response




@main.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')


@main.route('/plano-manutencao')
@login_required
def plano_manutencao():
    page = request.args.get('page', 1, type=int)
    unidade_selecionada = request.args.get('unidade', '')
    filial_selecionada = request.args.get('filial', '') if current_user.tipo == 'adm' else ''

    # 1. APLICA O FILTRO DE PERMISSÃO, STATUS ATIVO E FILTROS DO FORMULÁRIO
    # =============================== ALTERAÇÃO REALIZADA AQUI ===============================
    query = filtrar_query_por_usuario(Veiculo.query, Veiculo).filter(Veiculo.ativo == True)
    # =======================================================================================
    
    if unidade_selecionada:
        query = query.filter(Veiculo.unidade == unidade_selecionada)
    if filial_selecionada:
        query = query.filter(Veiculo.filial == filial_selecionada)

    # 2. OTIMIZA A CONSULTA
    query = query.options(
        joinedload(Veiculo.motorista),
        joinedload(Veiculo.placa_cavalo),
        joinedload(Veiculo.placa_carreta1)
    )

    # 3. ORDENAÇÃO
    def chave_ordenacao(veiculo):
        if not veiculo.placa_cavalo or veiculo.placa_cavalo.km_atual is None:
            return float('inf')
        kms_restantes = [
            km for km in [
                veiculo.placa_cavalo.km_para_preventiva,
                veiculo.placa_cavalo.km_para_intermediaria,
                veiculo.placa_cavalo.km_para_diferencial,
                veiculo.placa_cavalo.km_para_cambio
            ] if km is not None
        ]
        return min(kms_restantes) if kms_restantes else float('inf')

    veiculos_ordenados = sorted(query.all(), key=chave_ordenacao)

    # 4. PAGINAÇÃO MANUAL
    per_page = 50
    total = len(veiculos_ordenados)
    start = (page - 1) * per_page
    end = start + per_page
    itens_paginados = veiculos_ordenados[start:end]

    class FakePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items; self.page = page; self.per_page = per_page; self.total = total
            self.pages = max(0, total - 1) // per_page + 1
            self.has_prev = page > 1; self.has_next = page < self.pages
            self.prev_num = page - 1; self.next_num = page + 1
        def iter_pages(self, l_e=1, l_c=2, r_c=2, r_e=1):
            last = 0
            for num in range(1, self.pages + 1):
                if num <= l_e or (self.page - l_c -1 < num < self.page + r_c + 1) or num > self.pages - r_e:
                    if last + 1 != num: yield None
                    yield num
                    last = num

    pagination = FakePagination(itens_paginados, page, per_page, total)

    # 5. BUSCA LISTAS PARA OS FILTROS
    unidades_query = filtrar_query_por_usuario(db.session.query(Veiculo.unidade).distinct(), Veiculo)
    unidades = [row[0] for row in unidades_query.order_by(Veiculo.unidade) if row[0]]
    
    filiais = []
    if current_user.tipo == 'adm':
        filiais_query = db.session.query(Veiculo.filial).distinct()
        filiais = [row[0] for row in filiais_query.order_by(Veiculo.filial) if row[0]]

    # 6. RENDERIZA O TEMPLATE
    return render_template(
        'plano_manutencao.html',
        pagination=pagination,
        unidades=unidades,
        filiais=filiais,
        unidade_selecionada=unidade_selecionada,
        filial_selecionada=filial_selecionada,
        current_date=date.today()
    )






# ---------------------------------------------------------------------------
# ROTA PARA O DASHBOARD DE KPIS - VERSÃO FINAL COM TRATAMENTO DE NULOS
# ---------------------------------------------------------------------------

@main.route('/kpis')
@login_required
def kpis():
    unidade_selecionada = request.args.get('unidade', '')

    # APLICA O FILTRO DE PERMISSÃO À QUERY BASE
    query_base = filtrar_query_por_usuario(Veiculo.query, Veiculo)
    
    if unidade_selecionada:
        query = query_base.filter(Veiculo.unidade == unidade_selecionada)
    else:
        query = query_base

    veiculos_ok = 0
    veiculos_radar = 0
    veiculos_vencidos = 0
    lista_vencidos = []
    lista_radar = []

    for v in query.all():
        is_vencido = (
            (v.placa_cavalo.km_para_preventiva is not None and v.placa_cavalo.km_para_preventiva < 0) or
            (v.placa_cavalo.km_para_intermediaria is not None and v.placa_cavalo.km_para_intermediaria < 0) or
            (v.placa_cavalo.km_para_diferencial is not None and v.placa_cavalo.km_para_diferencial < 0) or
            (v.placa_cavalo.km_para_cambio is not None and v.placa_cavalo.km_para_cambio < 0)
        ) if v.placa_cavalo else False
        is_radar = (
            (v.placa_cavalo.km_para_preventiva is not None and 0 <= v.placa_cavalo.km_para_preventiva <= 5000) or
            (v.placa_cavalo.km_para_intermediaria is not None and 0 <= v.placa_cavalo.km_para_intermediaria <= 5000) or
            (v.placa_cavalo.km_para_diferencial is not None and 0 <= v.placa_cavalo.km_para_diferencial <= 5000) or
            (v.placa_cavalo.km_para_cambio is not None and 0 <= v.placa_cavalo.km_para_cambio <= 5000)
        ) if v.placa_cavalo else False

        if is_vencido:
            veiculos_vencidos += 1
            lista_vencidos.append(v)
        elif is_radar:
            veiculos_radar += 1
            lista_radar.append(v)
        else:
            veiculos_ok += 1

    frota_disponivel = query.count()
    
    unidades_query = filtrar_query_por_usuario(db.session.query(Veiculo.unidade).distinct(), Veiculo)
    unidades = [row[0] for row in unidades_query.order_by(Veiculo.unidade) if row[0]]

    return render_template(
        'kpis.html',
        unidades=unidades,
        unidade_selecionada=unidade_selecionada,
        veiculos_ok=veiculos_ok,
        veiculos_radar=veiculos_radar,
        veiculos_vencidos=veiculos_vencidos,
        frota_disponivel=frota_disponivel,
        lista_vencidos=lista_vencidos,
        lista_radar=lista_radar
    )



@main.route('/kpi/data')
@login_required
def kpi_data():
    unidade_selecionada = request.args.get('unidade', '')
    
    # APLICA O FILTRO DE PERMISSÃO À QUERY BASE
    query = filtrar_query_por_usuario(Veiculo.query, Veiculo)
    if unidade_selecionada:
        query = query.filter(Veiculo.unidade == unidade_selecionada)

    # Restante da função para gerar dados JSON
    from sqlalchemy import func
    
    km_atual = func.coalesce(Placa.km_atual, 0)
    preventiva_vencida = (func.coalesce(Placa.km_ultima_revisao_preventiva, 0) + func.coalesce(Placa.km_troca_preventiva, 0) - km_atual) < 0
    intermediaria_vencida = (func.coalesce(Placa.km_ultima_revisao_intermediaria, 0) + func.coalesce(Placa.km_troca_intermediaria, 0) - km_atual) < 0
    cambio_vencido = (func.coalesce(Placa.troca_oleo_cambio, 0) + func.coalesce(Placa.intervalo_oleo_cambio, 0) - km_atual) < 0
    diferencial_vencido = (func.coalesce(Placa.troca_oleo_diferencial, 0) + func.coalesce(Placa.intervalo_oleo_diferencial, 0) - km_atual) < 0

    vencidas_preventiva = query.join(Veiculo.placa_cavalo).filter(preventiva_vencida).count()
    vencidas_intermediaria = query.join(Veiculo.placa_cavalo).filter(intermediaria_vencida).count()
    vencidas_cambio = query.join(Veiculo.placa_cavalo).filter(cambio_vencido).count()
    vencidas_diferencial = query.join(Veiculo.placa_cavalo).filter(diferencial_vencido).count()

    manutencoes_vencidas_por_tipo = {
        'labels': ['Preventiva', 'Intermediária', 'Câmbio', 'Diferencial'],
        'data': [vencidas_preventiva, vencidas_intermediaria, vencidas_cambio, vencidas_diferencial]
    }

    bloqueios_query_base = filtrar_query_por_usuario(HistoricoBloqueio.query.filter_by(liberado=False), HistoricoBloqueio)
    bloqueios_agrupados = bloqueios_query_base.group_by(HistoricoBloqueio.tipo_manutencao).with_entities(
        HistoricoBloqueio.tipo_manutencao,
        func.count(HistoricoBloqueio.id)
    ).all()

    bloqueios_por_motivo = {
        'labels': [item[0].replace('_', ' ').title() for item in bloqueios_agrupados],
        'data': [item[1] for item in bloqueios_agrupados]
    }

    km_por_unidade_query = filtrar_query_por_usuario(db.session.query(
        Veiculo.unidade,
        func.sum(func.coalesce(Placa.km_atual, 0))
    ).join(Veiculo.placa_cavalo), Veiculo).group_by(Veiculo.unidade).order_by(func.sum(func.coalesce(Placa.km_atual, 0)).desc()).limit(10).all()

    km_por_unidade = {
        'labels': [item[0] if item[0] else 'N/A' for item in km_por_unidade_query],
        'data': [float(item[1]) for item in km_por_unidade_query]
    }

    return jsonify({
        'manutencoesVencidasPorTipo': manutencoes_vencidas_por_tipo,
        'bloqueiosPorMotivo': bloqueios_por_motivo,
        'kmPorUnidade': km_por_unidade
    })


