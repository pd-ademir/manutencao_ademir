from flask import Blueprint, render_template, request, redirect, flash, url_for
from .checklist_form import ChecklistForm
from sqlalchemy.sql import text
from collections import namedtuple
from flask_login import current_user
from flask_login import login_required, current_user
from .checklist_db import engine_checklist
from .models import registrar_log




checklist_bp = Blueprint('checklist', __name__, template_folder='templates')

@checklist_bp.route('/novo', methods=['GET', 'POST'])
def novo_checklist():
    if request.method == 'POST':
        with engine_checklist.begin() as conn:
            for i in range(1, 101):
                id_existente = request.form.get(f"id_{i}")
                placa = request.form.get(f"placa_{i}")
                item = request.form.get(f"item_{i}")

                # 🔒 Só processa linhas com ID e dados essenciais preenchidos
                if not item:
                    continue

                dados = {
                    "mes": request.form.get(f"mes_{i}"),
                    "data_registro": request.form.get(f"data_registro_{i}"),
                    "placa": placa,
                    "item": item,
                    "fonte": request.form.get(f"fonte_{i}"),
                    "tipo_manutencao": request.form.get(f"tipo_manutencao_{i}"),
                    "status": request.form.get(f"status_{i}"),
                    "ordem_servico": request.form.get(f"ordem_servico_{i}"),
                    "conclusao": request.form.get(f"conclusao_{i}"),
                    "data_servico": request.form.get(f"data_servico_{i}")
                }

                # 🔍 Buscar dados atuais do banco
                select = text("SELECT * FROM checklist WHERE id = :id")
                atual = conn.execute(select, {"id": id_existente}).mappings().first()

                alteracoes = []
                for campo, novo_valor in dados.items():
                    valor_atual = atual.get(campo)

                    # Comparação robusta: normaliza e ignora espaços/letras
                    valor_atual_str = str(valor_atual or "").strip().upper()
                    novo_valor_str = str(novo_valor or "").strip().upper()

                    if valor_atual_str != novo_valor_str:
                        alteracoes.append(f"{campo}='{valor_atual_str}' → '{novo_valor_str}'")

                if alteracoes:
                    update = text("""
                        UPDATE checklist SET
                            mes = :mes,
                            data_registro = :data_registro,
                            placa = :placa,
                            item = :item,
                            fonte = :fonte,
                            tipo_manutencao = :tipo_manutencao,
                            status = :status,
                            ordem_servico = :ordem_servico,
                            conclusao = :conclusao,
                            data_servico = :data_servico
                        WHERE id = :id
                    """)
                    dados["id"] = id_existente
                    conn.execute(update, dados)

                    registrar_log(
                        current_user,
                        f"Atualizou checklist (ID {id_existente}): " + ", ".join(alteracoes)
                    )

        flash("Dados salvos com sucesso!", "success")
        return redirect(url_for('checklist.novo_checklist'))

    # GET: carregar os dados existentes
    with engine_checklist.begin() as conn:
        registros = conn.execute(text("SELECT * FROM checklist ORDER BY id")).fetchall()

    linhas = []
    for i in range(100):
        if i < len(registros):
            r = registros[i]
            linhas.append({
                "id": r.id,
                "mes": r.mes or "",
                "data_registro": r.data_registro or "",
                "placa": r.placa or "",
                "item": r.item or "",
                "fonte": r.fonte or "",
                "tipo_manutencao": r.tipo_manutencao or "",
                "status": r.status or "",
                "ordem_servico": r.ordem_servico or "",
                "conclusao": r.conclusao or "",
                "data_servico": r.data_servico or ""
            })
        else:
            linhas.append({
                "id": "",
                "mes": "", "data_registro": "", "placa": "", "item": "",
                "fonte": "", "tipo_manutencao": "", "status": "",
                "ordem_servico": "", "conclusao": "", "data_servico": ""
            })

    return render_template('checklist_gerenciar.html', linhas=linhas)

@checklist_bp.route('/gerenciar', methods=['GET', 'POST'])
def gerenciar_checklists():
    if request.method == 'POST':
        with engine_checklist.connect() as conn:
            for i in range(1, 101):
                placa = request.form.get(f"placa_{i}")
                item = request.form.get(f"item_{i}")

                # Só salva se placa e item estiverem preenchidos
                if placa and item:
                    dados = {
                        "mes": request.form.get(f"mes_{i}"),
                        "data_registro": request.form.get(f"data_registro_{i}"),
                        "placa": placa,
                        "item": item,
                        "fonte": request.form.get(f"fonte_{i}"),
                        "tipo_manutencao": request.form.get(f"tipo_manutencao_{i}"),
                        "status": request.form.get(f"status_{i}"),
                        "ordem_servico": request.form.get(f"ordem_servico_{i}"),
                        "conclusao": request.form.get(f"conclusao_{i}"),
                        "data_servico": request.form.get(f"data_servico_{i}")
                    }

                    # Insere novo registro
                    insert = text("""
                        INSERT INTO checklist (
                            mes, data_registro, placa, item,
                            fonte, tipo_manutencao, status,
                            ordem_servico, conclusao, data_servico
                        ) VALUES (
                            :mes, :data_registro, :placa, :item,
                            :fonte, :tipo_manutencao, :status,
                            :ordem_servico, :conclusao, :data_servico
                        )
                    """)
                    conn.execute(insert, dados)
                    log_detalhado = ", ".join([f"{chave}='{valor}'" for chave, valor in dados.items()])
                    registrar_log(
                        current_user,
                        f"Adicionou novo checklist: {log_detalhado}"
                    )


        flash("Dados salvos com sucesso!", "success")
        return redirect('/checklist/gerenciar')

    # GET — carrega os dados existentes
    with engine_checklist.begin() as conn:
        registros = conn.execute(text("SELECT * FROM checklist ORDER BY id")).fetchall()

    # Gera 100 linhas fixas, preenchendo com os dados do banco
    linhas = []
    for i in range(100):
        if i < len(registros):
            r = registros[i]
            linhas.append({
                "mes": r.mes or "",
                "data_registro": r.data_registro or "",
                "placa": r.placa or "",
                "item": r.item or "",
                "fonte": r.fonte or "",
                "tipo_manutencao": r.tipo_manutencao or "",
                "status": r.status or "",
                "ordem_servico": r.ordem_servico or "",
                "conclusao": r.conclusao or "",
                "data_servico": r.data_servico or ""
            })
        else:
            linhas.append({
                "mes": "", "data_registro": "", "placa": "", "item": "",
                "fonte": "", "tipo_manutencao": "", "status": "",
                "ordem_servico": "", "conclusao": "", "data_servico": ""
            })

    return render_template('checklist_gerenciar.html', linhas=linhas)


@checklist_bp.route("/placa/<placa>", methods=["GET", "POST"])
@login_required
def por_placa(placa):
    if request.method == "POST":
        with engine_checklist.begin() as conn:
            for i in range(1, 101):
                item = request.form.get(f"item_{i}")
                if not item:
                    continue  # ignora linhas vazias

                dados = {
                    "mes": request.form.get(f"mes_{i}").upper() if request.form.get(f"mes_{i}") else "",
                    "data_registro": request.form.get(f"data_registro_{i}"),
                    "placa": placa.upper(),
                    "item": item.upper(),
                    "fonte": request.form.get(f"fonte_{i}", "").upper(),
                    "tipo_manutencao": request.form.get(f"tipo_manutencao_{i}", "").upper(),
                    "status": request.form.get(f"status_{i}", "").upper(),
                    "ordem_servico": request.form.get(f"ordem_servico_{i}", "").upper(),
                    "conclusao": request.form.get(f"conclusao_{i}", "").upper(),
                    "data_servico": request.form.get(f"data_servico_{i}")
                }

                id_existente = request.form.get(f"id_{i}")

                if id_existente:
                    # Atualização com verificação de alterações
                    select = text("SELECT * FROM checklist WHERE id = :id")
                    atual = conn.execute(select, {"id": id_existente}).mappings().first()

                    alteracoes = []
                    for campo, novo_valor in dados.items():
                        valor_atual = atual.get(campo)
                        valor_atual_str = str(valor_atual or "").strip().upper()
                        novo_valor_str = str(novo_valor or "").strip().upper()

                        if valor_atual_str != novo_valor_str:
                            alteracoes.append(f"{campo}='{valor_atual_str}' → '{novo_valor_str}'")

                    if alteracoes:
                        update = text("""
                            UPDATE checklist SET
                                mes = :mes,
                                data_registro = :data_registro,
                                placa = :placa,
                                item = :item,
                                fonte = :fonte,
                                tipo_manutencao = :tipo_manutencao,
                                status = :status,
                                ordem_servico = :ordem_servico,
                                conclusao = :conclusao,
                                data_servico = :data_servico
                            WHERE id = :id
                        """)
                        dados["id"] = id_existente
                        conn.execute(update, dados)

                        resumo = f"placa='{dados['placa']}', item='{dados['item']}', data_registro='{dados['data_registro']}'"
                        mensagem = f"Atualizou checklist (ID {id_existente}): {resumo} " + " ".join(alteracoes)
                        registrar_log(current_user, mensagem)

                else:
                    # Inserção de novo registro
                    insert = text("""
                        INSERT INTO checklist (
                            mes, data_registro, placa, item,
                            fonte, tipo_manutencao, status,
                            ordem_servico, conclusao, data_servico
                        ) VALUES (
                            :mes, :data_registro, :placa, :item,
                            :fonte, :tipo_manutencao, :status,
                            :ordem_servico, :conclusao, :data_servico
                        )
                    """)
                    conn.execute(insert, dados)

                    resumo = f"placa='{dados['placa']}', item='{dados['item']}', data_registro='{dados['data_registro']}'"
                    registrar_log(current_user, f"Adicionou novo checklist: {resumo}")

        flash(f"Checklist salvo para a placa {placa.upper()} com sucesso!", "success")
        return redirect(url_for('checklist.por_placa', placa=placa))

    # GET — carrega os dados da placa
    with engine_checklist.begin() as conn:
        registros = conn.execute(text("""
            SELECT * FROM checklist
            WHERE UPPER(placa) = :placa
            ORDER BY data_registro DESC
        """), {"placa": placa.upper()}).fetchall()

    linhas = []
    for i in range(100):
        if i < len(registros):
            r = registros[i]
            linhas.append({
                "id": r.id,
                "mes": r.mes or "",
                "data_registro": r.data_registro or "",
                "placa": r.placa or placa.upper(),
                "item": r.item or "",
                "fonte": r.fonte or "",
                "tipo_manutencao": r.tipo_manutencao or "",
                "status": r.status or "",
                "ordem_servico": r.ordem_servico or "",
                "conclusao": r.conclusao or "",
                "data_servico": r.data_servico or ""
            })
        else:
            linhas.append({
                "id": "",
                "mes": "", "data_registro": "", "placa": placa.upper(), "item": "",
                "fonte": "", "tipo_manutencao": "", "status": "",
                "ordem_servico": "", "conclusao": "", "data_servico": ""
            })

    return render_template("checklist_gerenciar.html", linhas=linhas, placa=placa.upper())

@checklist_bp.route("/placa/<placa>")
def checklist_por_placa(placa):
    with engine_checklist.begin() as conn:
        registros = conn.execute(text("""
            SELECT * FROM checklist
            WHERE UPPER(placa) = :placa
            ORDER BY data_registro DESC
        """), {"placa": placa.upper()}).fetchall()

    # Preenche as 100 linhas
    linhas = []
    for i in range(100):
        if i < len(registros):
            r = registros[i]
            linhas.append({
                "id": r.id,
                "mes": r.mes or "",
                "data_registro": r.data_registro or "",
                "placa": r.placa or "",
                "item": r.item or "",
                "fonte": r.fonte or "",
                "tipo_manutencao": r.tipo_manutencao or "",
                "status": r.status or "",
                "ordem_servico": r.ordem_servico or "",
                "conclusao": r.conclusao or "",
                "data_servico": r.data_servico or ""
            })
        else:
            linhas.append({
                "id": "",
                "mes": "", "data_registro": "", "placa": "", "item": "",
                "fonte": "", "tipo_manutencao": "", "status": "",
                "ordem_servico": "", "conclusao": "", "data_servico": ""
            })

    return render_template("checklist_gerenciar.html", linhas=linhas, placa=placa)

