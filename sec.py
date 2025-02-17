import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("Ошибка: API-ключ отсутствует!")
else:
    print(f"API-ключ загружен: {api_key[:5]}********")
