import os, re
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

app = FastAPI()

DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# Store temporary clients for login {phone: client}
pending_clients = {}

def session_path(phone):
    safe = re.sub(r'[^0-9+]', '', phone)
    return os.path.join(DATA_DIR, f"{safe}.txt")

def get_saved_client(phone):
    path = session_path(phone)
    if os.path.exists(path):
        with open(path, "r") as f:
            sess = f.read().strip()
            if sess:
                return TelegramClient(StringSession(sess), API_ID, API_HASH)
    return TelegramClient(StringSession(), API_ID, API_HASH)

HTML = """
<!DOCTYPE html>
<html>
<head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wazzup Login</title>
<style>
body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:480px;margin:auto}
input,button{width:100%;padding:13px;margin:8px 0;border-radius:10px;border:none;font-size:15px}
button{background:#2aabee;color:#fff;font-weight:bold;cursor:pointer}
button:disabled{background:#555}
.card{background:#222;padding:16px;border-radius:14px;margin:12px 0}
.small{color:#aaa;font-size:12px}
.step{display:none}.step.active{display:block}
.ok{color:#4f4} .err{color:#f55}
</style>
</head>
<body>
<h2>⚡ Wazzup MTProto</h2>

<div class="card step active" id="step1">
<h3>1. Connect Your Telegram</h3>
<input id="phone" placeholder="+234... with country code">
<button onclick="sendCode()" id="btn1">Get Login Code</button>
<p class="small">We will send code inside your Telegram app</p>
<p id="msg1"></p>
</div>

<div class="card step" id="step2">
<h3>2. Enter Code</h3>
<input id="code" placeholder="12345">
<input id="pass2fa" placeholder="2FA Password (if any) - leave empty if none">
<button onclick="verifyCode()" id="btn2">Verify & Login</button>
<p id="msg2"></p>
</div>

<div class="card step" id="step3">
<h3>✅ Connected as <span id="me"></span></h3>
<p class="small" id="sessInfo"></p>
<input id="to" placeholder="Test to: @username or +234...">
<input id="text" placeholder="Message: Hi from Wazzup">
<button onclick="sendDM()" id="btn3">Send via MTProto</button>
<p id="msg3"></p>
<button style="background:#333" onclick="logout()">Logout / Use another number</button>
</div>

<script>
let currentPhone = "";
async function sendCode(){
  let phone=document.getElementById('phone').value;
  if(!phone){alert('Enter phone');return}
  document.getElementById('btn1').disabled=true;
  document.getElementById('msg1').innerText='Sending...';
  let r = await fetch('/login/send_code', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({phone})});
  let j = await r.json();
  document.getElementById('btn1').disabled=false;
  document.getElementById('msg1').innerText=JSON.stringify(j);
  document.getElementById('msg1').className = j.ok ? 'ok' : 'err';
  if(j.ok){
    currentPhone=phone;
    document.getElementById('step1').classList.remove('active');
    document.getElementById('step2').classList.add('active');
  }
}
async function verifyCode(){
  let code=document.getElementById('code').value;
  let password=document.getElementById('pass2fa').value;
  document.getElementById('btn2').disabled=true;
  document.getElementById('msg2').innerText='Verifying...';
  let r = await fetch('/login/verify', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({phone: currentPhone, code, password})});
  let j = await r.json();
  document.getElementById('btn2').disabled=false;
  document.getElementById('msg2').innerText=JSON.stringify(j);
  if(j.ok){
    document.getElementById('step2').classList.remove('active');
    document.getElementById('step3').classList.add('active');
    document.getElementById('me').innerText=j.user;
    document.getElementById('sessInfo').innerText='Session: '+j.session_path;
  }
}
async function sendDM(){
  let to=document.getElementById('to').value;
  let message=document.getElementById('text').value;
  document.getElementById('msg3').innerText='Sending...';
  let r = await fetch('/send', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({phone: currentPhone, to, message})});
  let j = await r.json();
  document.getElementById('msg3').innerText=JSON.stringify(j);
  document.getElementById('msg3').className=j.ok?'ok':'err';
}
function logout(){
  currentPhone=""; location.reload();
}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML

@app.post("/login/send_code")
async def send_code(request: Request):
    data = await request.json()
    phone = data.get("phone", "").strip()
    if not phone:
        return JSONResponse({"ok": False, "error": "Phone required"}, 400)
    try:
        client = get_saved_client(phone)
        await client.connect()
        # If already authorized
        if await client.is_user_authorized():
            with open(session_path(phone), "w") as f:
                f.write(client.session.save())
            me = await client.get_me()
            await client.disconnect()
            return {"ok": True, "already": True, "user": f"{me.first_name} @{me.username}"}
        
        sent = await client.send_code_request(phone)
        pending_clients[phone] = client
        return {"ok": True, "msg": "Code sent to Telegram", "phone_code_hash": sent.phone_code_hash}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, 500)

@app.post("/login/verify")
async def verify(request: Request):
    data = await request.json()
    phone = data.get("phone")
    code = data.get("code")
    password = data.get("password", "")
    client = pending_clients.get(phone)
    if not client:
        client = get_saved_client(phone)
        await client.connect()
    try:
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            if not password:
                return JSONResponse({"ok": False, "error": "2FA password required"}, 400)
            await client.sign_in(password=password)
        
        # Save session
        with open(session_path(phone), "w") as f:
            f.write(client.session.save())
        
        me = await client.get_me()
        pending_clients.pop(phone, None)
        # keep client connected? disconnect to avoid leak
        await client.disconnect()
        return {"ok": True, "user": f"{me.first_name} (@{me.username})", "session_path": session_path(phone)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, 500)

@app.post("/send")
async def send_dm(request: Request):
    data = await request.json()
    phone = data.get("phone")
    to = data.get("to")
    message = data.get("message")
    if not phone or not to or not message:
        return JSONResponse({"ok": False, "error": "phone, to, message required"}, 400)
    try:
        client = get_saved_client(phone)
        await client.connect()
        if not await client.is_user_authorized():
            return JSONResponse({"ok": False, "error": "Not logged in. Please login first"}, 401)
        # Resolve entity to avoid GetContactsRequest bug
        entity = await client.get_entity(to)
        await client.send_message(entity, message)
        await client.disconnect()
        return {"ok": True, "sentTo": to, "from": phone}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, 500)

@app.get("/health")
async def health():
    files = os.listdir(DATA_DIR) if os.path.exists(DATA_DIR) else []
    return {"status": "ok", "sessions": len(files), "files": files}
