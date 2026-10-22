import os
from fastapi import FastAPI, Request
from telethon import TelegramClient
from telethon.sessions import StringSession
app=FastAPI()
API_ID=int(os.getenv("API_ID","0"))
API_HASH=os.getenv("API_HASH","")
@app.get("/")
async def root(): return {"status":"Wazzup MTProto Running"}
@app.api_route("/health", methods=["GET","HEAD"])
async def health(): return {"ok": True}
@app.post("/send")
async def send_message(req: Request):
    data=await req.json()
    chat_id=data.get("chat_id")
    text=data.get("text")
    session_str=data.get("session") # user own session
    client=TelegramClient(StringSession(session_str),API_ID,API_HASH)
    await client.connect()
    await client.send_message(chat_id,text)
    await client.disconnect()
    return {"ok": True}
