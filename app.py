import os
from fastapi import FastAPI, Request
from telethon import TelegramClient
from telethon.sessions import StringSession
app=FastAPI()
API_ID=int(os.getenv("API_ID","0"))
API_HASH=os.getenv("API_HASH","")
SESSION=os.getenv("SESSION","")
@app.get("/")
async def root(): return {"status":"Wazzup MTProto Running"}
@app.api_route("/health", methods=["GET","HEAD"])
async def health(): return {"ok": True}
@app.post("/send")
async def send_message(req: Request):
    data=await req.json()
    chat_id=data.get("chat_id")
    text=data.get("text")
    client=TelegramClient(StringSession(SESSION),API_ID,API_HASH)
    await client.connect()
    await client.send_message(chat_id,text)
    await client.disconnect()
    return {"ok": True}
