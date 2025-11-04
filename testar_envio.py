import requests

# 🔐 Substitua pelos seus dados reais
token = "EAAKA1BO7HoQBO2XZBK20MIasODTgIKriQRMcxVns5iD2ZARrVdkbIWZCTc36XEQHPZBBhh7lBKRRZBIRe0d6RrMbQtgdTQutuFuow0ZCZBnZBr0X3uByHFPhd7KKcekmRf8EMiZB98jEIkhwtQMZCZArw2cSFOXYbmZABDGRhaNTZAswZBMJ77KHxaoXfiKstYitwnkSk2gPOxcNU3rtvzxL4n7rtSH1qbkGS8YHAhoW3ZCrwIJsnmJeAZDZD"
phone_number_id = "700570819805323"
numero_destino = "+5584991464250"

def enviar_template_whatsapp(numero):
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": "hello_world",
            "language": { "code": "en_US" }
        }
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    print("Código:", response.status_code)
    print("Resposta:", response.text)

enviar_template_whatsapp(numero_destino)
