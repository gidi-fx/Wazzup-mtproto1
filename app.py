 = import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

app = FastAPI()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
clients = {}

@app.get("/", response_class=HTMLResponse)
async def home():
    return '<h2>Wazzup MTProto - Generate Session</h2><form action="/send_code" method="get">Phone (e.g +2348012345678):<br><input name="phone" style="width:300px"><br><br><button>Send Code</button></form>'

@app.get("/send_code", response_class=HTMLResponse)
async def send_code(phone: str):
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    await client.send_code_request(phone)
    clients[phone] = client
    return f'<h3>Code sent to {phone}</h3><form action="/login" method="get"><input type="hidden" name="phone" value="{phone}">Code: <input name="code"><br>2FA Password (if any): <input name="password"><br><br><button>Login</button></form>'

@app.get("/login", response_class=HTMLResponse)
async def login(phone: str, code: str, password: str = ""):
    client = clients.get(phone)
    if not client:
        return HTMLResponse("Session expired, go back to home")
    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        await client.sign_in(password=password)
    except Exception as e:
        return HTMLResponse(f"Error: {e}")
    session_str = client.session.save()
    await client.disconnect()
    return f'<h2>COPY YOUR SESSION:</h2><textarea style="width:100%;height:200px">{session_str}</textarea><p>Copy this and add to Render ENV as SESSION</p>'

@app.get("/health")
async def health():
    return {"ok": True}
