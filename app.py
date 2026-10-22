import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

app = FastAPI()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSIONS = {}

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <h2>Wazzup MTProto - Generate Session</h2>
    <form action="/send_code" method="get">
      Phone with country code (e.g +2348012345678): <br>
      <input name="phone" style="width:300px"><br><br>
      <button>Send Code</button>
    </form>
    """

@app.get("/send_code")
async def send_code(phone: str):
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    await client.send_code_request(phone)
    SESSIONS[phone] = client
    return HTMLResponse(f"""
    <h3>Code sent to {phone}</h3>
    <form action="/login" method="get">
      <input type="hidden" name="phone" value="{phone}">
      Code: <input name="code"><br>
      2FA Password (if any): <input name="password"><br><br>
      <button>Login</button>
    </form>
    """)

@app.get("/login")
async def login(phone: str, code: str, password: str = ""):
    client = SESSIONS.get(phone)
    try:
        await client.sign_in(phone=phone, code=code, password=password or None)
    except SessionPasswordNeededError:
        await client.sign_in(password=password)
    session_str = client.session.save()
    await client.disconnect()
    return HTMLResponse(f"""
    <h2>COPY YOUR SESSION:</h2>
    <textarea style="width:100%;height:200px">{session_str}</textarea>
    """)import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

app = FastAPI()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSIONS = {}

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <h2>Wazzup MTProto - Generate Session</h2>
    <form action="/send_code" method="get">
      Phone with country code (e.g +2348012345678): <br>
      <input name="phone" style="width:300px"><br><br>
      <button>Send Code</button>
    </form>
    """

@app.get("/send_code")
async def send_code(phone: str):
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    await client.send_code_request(phone)
    SESSIONS[phone] = client
    return HTMLResponse(f"""
    <h3>Code sent to {phone}</h3>
    <form action="/login" method="get">
      <input type="hidden" name="phone" value="{phone}">
      Code: <input name="code"><br>
      2FA Password (if any): <input name="password"><br><br>
      <button>Login</button>
    </form>
    """)

@app.get("/login")
async def login(phone: str, code: str, password: str = ""):
    client = SESSIONS.get(phone)
    try:
        await client.sign_in(phone=phone, code=code, password=password or None)
    except SessionPasswordNeededError:
        await client.sign_in(password=password)
    session_str = client.session.save()
    await client.disconnect()
    return HTMLResponse(f"""
    <h2>COPY YOUR SESSION:</h2>
    <textarea style="width:100%;height:200px">{session_str}</textarea>
    """)
