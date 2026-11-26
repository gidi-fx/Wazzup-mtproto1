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
input,button,select{width:100%;padding:13px;margin:8px 0;border-radius:10px;border:none;font-size:15px}
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
<select id="method">
<option value="app">📱 Code to Telegram App (Fast)</option>
<option value="call">📞 Call My Number</option>
<option value="sms">💬 SMS</option>
</select>
<button onclick="sendCode()" id="btn1">Get Login Code</button>
<p class="small">App = code inside Telegram. Call = robot calls you read code. SMS = text message</p>
<p id="msg1"></p>
</div>

<div class="card step" id="step2">
<h3>2. Enter Code</h3>
<input id="code" placeholder="Enter code you received">
<input id="pass2fa" placeholder="2FA Password (if any)">
<button onclick="verifyCode()" id="btn2">Verify & Login</button>
<p id="msg2"></p>
</div>

<div class="card step" id="step3">
<h3>✅ Connected as <span id="me"></span></h3>
<input id="to" placeholder="Test to: @username or +234...">
<input id="text" placeholder="Message: Hello">
<button onclick="sendDM()" id="btn3">Send Test DM via MTProto</button>
<p id="msg3"></p>
<button style="background:#333" onclick="location.reload()">Use another number</button>
</div>

<script>
let currentPhone = "";
async function sendCode(){
  let phone=document.getElementById('phone').value;
  let method=document.getElementById('method').value;
  if(!phone){alert('Enter phone');return}
  document.getElementById('btn1').disabled=true;
  document.getElementById('msg1').innerText='Sending '+method+' code to '+phone+'...';
  let r = await fetch('/login/send_code', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({phone, method})});
  let j = await r.json();
  document.getElementById('btn1').disabled=false;
  document.getElementById('msg1').innerText=j.msg || JSON.stringify(j);
  document.getElementById('msg1').className=j.ok?'ok':'err';
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
    method = data.get("method", "app")
    if not phone:
        return JSONResponse({"ok": False, "error": "Phone required"}, 400)
    try:
        client = get_saved_client(phone)
        await client.connect()
        
        if await client.is_user_authorized():
            with open(session_path(phone), "w") as f:
                f.write(client.session.save())
            me = await client.get_me()
            await client.disconnect()
            return {"ok": True, "already": True, "msg": f"Already logged in as {me.first_name}", "user": f"{me.first_name}"}
        
        if method == "app":
            sent = await client.send_code_request(phone)
            msg = f"✅ Code sent to Telegram App. Open Telegram on another device!"
        elif method == "sms":
            sent = await client.send_code_request(phone, force_sms=True)
            msg = f"✅ SMS sent to {phone}"
        elif method == "call":
            # First send app code, then request call on second attempt
            sent = await client.send_code_request(phone)
            try:
                # Try to trigger call - second request often triggers call
                sent = await client.send_code_request(phone)
            except:
                pass
            msg = f"📞 Telegram will call {phone} in ~60 seconds if app code not used. Pick call for code."
        else:
            sent = await client.send_code_request(phone)
            msg = "Code sent"

        pending_clients[phone] = client
        return {"ok": True, "msg": msg, "method": method}
    except Exception as e:
        return JSONResponse({"ok": False, "msg": str(e), "error": str(e)}, 500)

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
                return JSONResponse({"ok": False, "msg": "2FA password required, enter it"}, 400)
            await client.sign_in(password=password)
        
        with open(session_path(phone), "w") as f:
            f.write(client.session.save())
        
        me = await client.get_me()
        pending_clients.pop(phone, None)
        await client.disconnect()
        return {"ok": True, "user": f"{me.first_name} (@{me.username})", "msg": "Logged in!"}
    except Exception as e:
        return JSONResponse({"ok": False, "msg": str(e), "error": str(e)}, 500)

@app.post("/send")
async def send_dm(request: Request):
    data = await request.json()
    phone = data.get("phone")
    to = data.get("to")
    message = data.get("message")
    if not phone or not to or not message:
        return JSONResponse({"ok": False, "error": "All fields required"}, 400)
    try:
        client = get_saved_client(phone)
        await client.connect()
        if not await client.is_user_authorized():
            return JSONResponse({"ok": False, "error": "Not logged in"}, 401)
        entity = await client.get_entity(to)
        await client.send_message(entity, message)
        await client.disconnect()
        return {"ok": True, "msg": f"Sent to {to} via {phone}"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, 500)

@app.get("/health")
async def health():
    files = os.listdir(DATA_DIR) if os.path.exists(DATA_DIR) else []
    return {"status": "ok", "sessions": len(files)}
