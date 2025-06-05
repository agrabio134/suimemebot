import requests
response = requests.get("https://api.telegram.org/bot8169411740:AAHvtP4nQ4Bi_qhCs1Gp4I7iji4stIbilMc/getMe")
print(response.json())