import os, re, asyncio
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
phone_code_hashes = {}

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
<title>Wazzup MTProto</title>
<style>
body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:480px;margin:auto}
input,button{width:100%;padding:13px;margin:8px 0;border-radius:10px;border:none;font-size:15px}
button{background:#2aabee;color:#fff;font-weight:bold;cursor:pointer}
button.call{background:#ff3b30;margin-top:2px}
button:disabled{background:#555}
.card{background:#222;padding:16px;border-radius:14px;margin:12px 0}
.small{color:#aaa;font-size:12px}
.step{display:none}.step.active{display:block}
.ok{color:#4f4}.err{color:#f55}
</style>
</head>
<body>
<h2>⚡ Wazzup MTProto</h2>
<div class="card step active" id="step1">
<h3>1. Connect</h3>
<input id="phone" placeholder="+234906...">
<button onclick="sendCode()" id="btn1">Get Code via Telegram App</button>
<button class="call" onclick="reCall()" id="btnCall">📞 No code? Re-Call My Number</button>
<p class="small">First click = App. If you don't get it, click Re-Call</p>
<p id="msg1"></p>
</div>
<div class="card step" id="step2">
<h3>2. Enter Code</h3>
<input id="code" placeholder="Code you received">
<input id="pass2fa" placeholder="2FA if any">
<button onclick="verifyCode()" id="btn2">Verify</button>
<p id="msg2"></p>
</div>
<div class="card step" id="step3">
<h3>✅ <span id="me"></span></h3>
<input id="to" placeholder="@username">
<input id="text" placeholder="Test message">
<button onclick="sendDM()" id="btn3">Send DM</button>
<p id="msg3"></p>
</div>
<script>
let currentPhone="";
async function sendCode(){
  let phone=document.getElementById('phone').value;
  if(!phone)return alert('Enter phone');
  document.getElementById('btn1').disabled=true;
  document.getElementById('msg1').innerText='Sending to Telegram App...';
  let r=await fetch('/login/send_code',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone})});
  let j=await r.json();
  document.getElementById('btn1').disabled=false;
  document.getElementById('msg1').innerText=j.msg;
  document.getElementById('msg1').className=j.ok?'ok':'err';
  if(j.ok){currentPhone=phone;document.getElementById('step1').classList.remove('active');document.getElementById('step2').classList.add('active');}
}
async function reCall(){
  let phone=document.getElementById('phone').value||currentPhone;
  if(!phone)return alert('Enter phone first');
  document.getElementById('msg1').innerText='Requesting CALL to '+phone+'... wait 60s';
  let r=await fetch('/login/recall',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone})});
  let j=await r.json();
  document.getElementById('msg1').innerText=j.msg;
  document.getElementById('msg1').className=j.ok?'ok':'err';
  if(j.ok){currentPhone=phone;document.getElementById('step1').classList.remove('active');document.getElementById('step2').classList.add('active');}
}
async function verifyCode(){
  let code=document.getElementById('code').value;let password=document.getElementById('pass2fa').value;
  let r=await fetch('/login/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:currentPhone,code,password})});
  let j=await r.json();document.getElementById('msg2').innerText=JSON.stringify(j);
  if(j.ok){document.getElementById('step2').classList.remove('active');document.getElementById('step3').classList.add('active');document.getElementById('me').innerText=j.user;}
}
async function sendDM(){
  let to=document.getElementById('to').value;let message=document.getElementById('text').value;
  let r=await fetch('/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:currentPhone,to,message})});
  let j=await r.json();document.getElementById('msg3').innerText=JSON.stringify(j);
}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home(): return HTML

@app.post("/login/send_code")
async def send_code(request: Request):
    data = await request.json()
    phone = data.get("phone","").strip()
    try:
        client = get_saved_client(phone)
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            await client.disconnect()
            return {"ok": True, "msg": f"Already logged in as {me.first_name}"}
        sent = await client.send_code_request(phone)
        pending_clients[phone] = client
        phone_code_hashes[phone] = sent.phone_code_hash
        return {"ok": True, "msg": f"Code sent to Telegram App. Check app! Hash: {sent.phone_code_hash[:5]}..."}
    except Exception as e:
        return JSONResponse({"ok": False, "msg": str(e)}, 500)

@app.post("/login/recall")
async def recall(request: Request):
    data = await request.json()
    phone = data.get("phone","").strip()
    client = pending_clients.get(phone)
    if not client:
        client = get_saved_client(phone)
        await client.connect()
    try:
        # Force re-send which triggers call after timeout
        # First try SMS then call
        sent = await client.send_code_request(phone, force_sms=True)
        pending_clients[phone] = client
        phone_code_hashes[phone] = sent.phone_code_hash
        return {"ok": True, "msg": f"📞 CALL requested! Telegram will call {phone} in 30-60 seconds. Stay near phone."}
    except Exception as e:
        err = str(e)
        if "call" in err.lower() or "Call" in err:
            return {"ok": True, "msg": f"📞 CALL is coming to {phone}! Answer it."}
        return JSONResponse({"ok": False, "msg": err}, 500)

@app.post("/login/verify")
async def verify(request: Request):
    data = await request.json()
    phone, code, password = data.get("phone"), data.get("code"), data.get("password","")
    client = pending_clients.get(phone)
    if not client:
        client = get_saved_client(phone)
        await client.connect()
    try:
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hashes.get(phone))
        except SessionPasswordNeededError:
            await client.sign_in(password=password)
        with open(session_path(phone),"w") as f: f.write(client.session.save())
        me = await client.get_me()
        pending_clients.pop(phone,None)
        await client.disconnect()
        return {"ok": True, "user": f"{me.first_name} @{me.username}"}
    except Exception as e:
        return JSONResponse({"ok": False, "msg": str(e)}, 500)

@app.post("/send")
async def send_dm(request: Request):
    data = await request.json()
    phone, to, message = data.get("phone"), data.get("to"), data.get("message")
    client = get_saved_client(phone)
    await client.connect()
    entity = await client.get_entity(to)
    await client.send_message(entity, message)
    await client.disconnect()
    return {"ok": True, "msg": f"Sent to {to}"}
