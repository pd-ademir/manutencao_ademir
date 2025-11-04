import requests

def enviar_mensagem_whatsapp(numero, mensagem):
    token = "EAAKA1BO7HoQBO2XZBK20MIasODTgIKriQRMcxVns5iD2ZARrVdkbIWZCTc36XEQHPZBBhh7lBKRRZBIRe0d6RrMbQtgdTQutuFuow0ZCZBnZBr0X3uByHFPhd7KKcekmRf8EMiZB98jEIkhwtQMZCZArw2cSFOXYbmZABDGRhaNTZAswZBMJ77KHxaoXfiKstYitwnkSk2gPOxcNU3rtvzxL4n7rtSH1qbkGS8YHAhoW3ZCrwIJsnmJeAZDZD"
    phone_number_id = "700570819805323"
    
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": { "body": mensagem }
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    print(response.status_code, response.text)
    return response.status_code == 200
