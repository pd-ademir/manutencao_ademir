from flask import current_app
from datetime import datetime
import requests
from .models import Veiculo, whatsapp_numeros
import requests
import urllib.parse
import os
from . import whatsapp
from flask_login import current_user
from .models import registrar_log
from dotenv import load_dotenv
from datetime import date
load_dotenv()


# === Envia mensagem via CallMeBot ===

def disparar_alertas_multiplos():
    mensagem = gerar_resumo_veiculos()
    if not mensagem:
        print("✅ Nenhum veículo próximo da manutenção.")
        return

    destinatarios = {
        "18981430410": "8852576",
        "8894664001": "8070210",
        #"8491174367": "2805644",
        #"8491464250": "2137056",
        "18981430214": "4358893"
    }

    print("📨 MENSAGEM GERADA:\n", mensagem)

    for numero, chave in destinatarios.items():
        sucesso = enviar_mensagem_whatsapp(numero, mensagem, chave)
        status = "✔️ OK" if sucesso else "❌ FALHOU"
        print(f"{status} para {numero}")



def enviar_mensagem_whatsapp(numero, mensagem, apikey):
    if not apikey:
        print(f"❌ API Key não definida para {numero}!")
        registrar_log(current_user, f"Envio de alerta para {numero} — Falha (API Key ausente)")
        return False

    numero_formatado = f'+55{numero.lstrip("+")}'
    params = {
        "phone": numero_formatado,
        "text": mensagem,
        "apikey": apikey
    }

    url = f"https://api.callmebot.com/whatsapp.php?{urllib.parse.urlencode(params)}"
    print(f"🔗 URL gerada: {url}")

    try:
        resposta = requests.get(url, timeout=10)
        print(f"📤 Enviado para {numero}: {resposta.status_code} - {resposta.text}")

        sucesso = (
            resposta.status_code == 200 and
            ("message queued" in resposta.text.lower() or
             "message successfully sent" in resposta.text.lower())
        )

        # 📋 Status resumido
        if sucesso:
            status = "✅ Sucesso"
        elif "apikey is invalid" in resposta.text.lower():
            status = "❌ API inválida"
        elif "paused" in resposta.text.lower():
            status = "⏸️ Conta pausada"
        else:
            status = "⚠️ Entrega incerta"

        registrar_log(current_user, f"Envio de alerta para {numero_formatado} — {status}")
        return sucesso

    except Exception as e:
        erro = str(e)
        print(f"❌ Erro ao enviar para {numero}: {erro}")
        registrar_log(current_user, f"Erro ao enviar alerta para {numero_formatado} — {erro}")
        return False




# === Monta uma mensagem detalhada com os veículos em alerta ===
def gerar_resumo_veiculos():
    with current_app.app_context():
        veiculos = Veiculo.query.all()

        em_alerta = [
            v for v in veiculos if (
                (v.km_para_preventiva is not None and v.km_para_preventiva <= 5000) or
                (v.km_para_intermediaria is not None and v.km_para_intermediaria <= 5000)
            )
        ]

        if not em_alerta:
            return None  # Nenhum veículo relevante

        linhas = [f"📅 ALERTA de Manutenção - {date.today().strftime('%d/%m/%Y')}"]

        for v in em_alerta:
            linhas.append(f"\n🚛 {v.placa}")
            linhas.append(f"• KM Atual: {v.km_atual:,.0f} km".replace(",", "."))

            if v.km_para_preventiva is not None and v.km_para_preventiva <= 5000:
                linhas.append(f"• Preventiva: {v.km_para_preventiva:,.0f} km".replace(",", "."))

            if v.km_para_intermediaria is not None and v.km_para_intermediaria <= 5000:
                linhas.append(f"• Intermediária: {v.km_para_intermediaria:,.0f} km".replace(",", "."))

        return "\n".join(linhas)

# === Envia mensagem para todos os números cadastrados ===
def disparar_alertas_reais():
    mensagem = gerar_resumo_veiculos()
    if not mensagem:
        print("✅ Nenhum veículo com manutenção próxima.")
        return

    print("📨 MENSAGEM GERADA:\n", mensagem)

    for numero in whatsapp_numeros:
        sucesso = enviar_mensagem_whatsapp(numero, mensagem)
        print(f"✔️ Enviado para {numero}: {'OK' if sucesso else 'FALHOU'}")


# === Extra: gera dados como dicionário, útil para exibir na interface ===
def extrair_dados():
    with current_app.app_context():
        veiculos = Veiculo.query.all()
        em_alerta = [
            v for v in veiculos if (
                (v.km_para_preventiva is not None and v.km_para_preventiva <= 5000) or
                (v.km_para_intermediaria is not None and v.km_para_intermediaria <= 5000)
            )
        ]

        linhas = []
        for v in em_alerta:
            linhas.append({
                "placa": v.placa,
                "motorista": v.motorista,
                "km_atual": f"{v.km_atual:,}".replace(",", ".") + " km",
                "preventiva": f"{v.km_para_preventiva or 'N/D'} km",
                "intermediaria": f"{v.km_para_intermediaria or 'N/D'} km"
            })
        return linhas
