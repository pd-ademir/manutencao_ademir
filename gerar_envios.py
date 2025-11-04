import schedule
import time
from manutencao.app.alertas import gerar_resumo_veiculos, whatsapp_numeros
from manutencao.app.whatsapp import enviar_mensagem_whatsapp

def job_envio_diario():
    mensagem = gerar_resumo_veiculos()
    if not mensagem:
        print("✅ Nenhum veículo em manutenção crítica hoje.")
        return

    for numero in whatsapp_numeros:
        sucesso = enviar_mensagem_whatsapp(numero, mensagem)
        print(f'Enviado para {numero}: {"✔️" if sucesso else "❌"}')

# Só roda se executar diretamente: evita travar quando importar
if __name__ == '__main__':
    print("⏱️ Agendador iniciado. Esperando 08:00 para disparar alertas...")
    schedule.every().day.at("08:00").do(job_envio_diario)

    while True:
        schedule.run_pending()
        time.sleep(30)
