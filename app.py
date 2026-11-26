import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telethon import TelegramClient
from telethon.sessions import StringSession

app = FastAPI()

DATA_DIR = "./data"
SESSION_FILE = os.path.join(DATA_DIR, "session.txt")
os.makedirs(DATA_DIR, exist_ok=True)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

session_string = ""
if os.path.exists(SESSION_FILE):
    with open(SESSION_FILE, "r") as f:
        session_string = f.read().strip()

client = TelegramClient(StringSession(session_string), API_ID, API_HASH)

@app.on_event("startup")
async def startup():
    await client.connect()
    print("MTProto connected!")
    with open(SESSION_FILE, "w") as f:
        f.write(client.session.save())
    print(f"Session saved to {SESSION_FILE}")

@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()

HTML = """
<!DOCTYPE html>
<html>
<head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wazzup MTProto</title>
<style>
body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:500px;margin:auto}
input,button{width:100%;padding:12px;margin:8px 0;border-radius:8px;border:none}
button{background:#2aabee;color:#fff;font-weight:bold;cursor:pointer}
.card{background:#222;padding:15px;border-radius:12px;margin:10px 0}
</style>
</head>
<body>
<h2>⚡ Wazzup MTProto FastAPI</h2>
<div class="card">
<b>Status:</b> <span id="status">Checking...</span><br>
<small id="path"></small>
</div>
<div class="card">
<h3>Test Send</h3>
<input id="to" placeholder="@username or +234...">
<input id="msg" placeholder="Message">
<button onclick="sendMsg()">Send via MTProto</button>
<p id="result"></p>
</div>
<script>
async function checkHealth(){
  let r = await fetch('/health'); let j = await r.json();
  document.getElementById('status').innerText = j.connected ? '✅ Connected' : '❌ Not connected';
  document.getElementById('path').innerText = 'Session: '+j.sessionExists+' | '+j.path;
}
async function sendMsg(){
  let to=document.getElementById('to').value;
  let msg=document.getElementById('msg').value;
  let r = await fetch('/send', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({to,to, message:msg})});
  // fix body
  let res = await fetch('/send', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({to: to, message: msg})});
  let j = await res.json(); document.getElementById('result').innerText = JSON.stringify(j);
}
checkHealth();
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "sessionExists": os.path.exists(SESSION_FILE),
        "path": SESSION_FILE,
        "connected": client.is_connected()
    }

@app.post("/send")
async def send_msg(request: Request):
    data = await request.json()
    to = data.get("to")
    message = data.get("message")
    try:
        await client.send_message(to, message)
        return {"ok": True, "sentTo": to}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
