import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from schemas import Command, DeviceAction
from database import create_document, get_documents, db

app = FastAPI(title="Phone Control Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Phone Control Agent Backend Running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set"
            response["database_name"] = getattr(db, 'name', '✅ Connected')
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# In-memory pairing tokens are avoided; we will persist pairings
class PairRequest(BaseModel):
    device_id: str
    device_name: Optional[str] = None

class PairAck(BaseModel):
    device_id: str
    acknowledged: bool

@app.post("/pair")
def register_device(req: PairRequest):
    # Persist device pair info
    doc_id = create_document("pair", {
        "device_id": req.device_id,
        "device_name": req.device_name,
    })
    return {"status": "ok", "id": doc_id}

@app.get("/pairs")
def list_pairs():
    pairs = get_documents("pair")
    # Convert ObjectId to string
    for p in pairs:
        p["_id"] = str(p["_id"]) if "_id" in p else None
    return pairs

# Command planning
class PlanRequest(BaseModel):
    text: str
    language: Optional[str] = None
    device_id: Optional[str] = None

@app.post("/plan", response_model=Command)
def plan_command(req: PlanRequest):
    # naive rule-based intent detection supporting Bangla and English keywords
    t = req.text.strip().lower()
    intent = "unknown"
    actions: List[DeviceAction] = []

    def act(a_type: str, target: Optional[str] = None, **kwargs):
        return DeviceAction(type=a_type, target=target, args=kwargs)

    # Examples intents
    if any(k in t for k in ["কল কর", "ফোন কর", "call", "dial"]):
        intent = "call_contact"
        # extract simple target after 'to' or 'কে'
        target = None
        for sep in ["to ", "কে ", "কেকে "]:
            if sep in t:
                target = t.split(sep, 1)[1].strip()
                break
        actions = [act("open_app", target="com.android.dialer"), act("search", target=target), act("tap", target="call_button")]
    elif any(k in t for k in ["মেসেজ", "message", "sms", "টেক্সট"]):
        intent = "send_message"
        target = None
        for sep in ["to ", "কে "]:
            if sep in t:
                target = t.split(sep, 1)[1].strip()
                break
        actions = [act("open_app", target="com.google.android.apps.messaging"), act("search", target=target), act("type_text", args={"text": ""}), act("tap", target="send_button")]
    elif any(k in t for k in ["ইউটিউব", "youtube", "ভিডিও চালাও", "play video"]):
        intent = "open_youtube"
        query = t.replace("ইউটিউব", "").replace("youtube", "").strip()
        actions = [act("open_app", target="com.google.android.youtube"), act("search", target=query), act("tap", target="first_result")]
    elif any(k in t for k in ["wifi", "ওয়াইফাই", "ওয়াইফাই", "wi-fi"]):
        intent = "toggle_wifi"
        actions = [act("open_app", target="com.android.settings"), act("search", target="Wi‑Fi"), act("tap", target="toggle_wifi")]
    elif any(k in t for k in ["ব্লুটুথ", "bluetooth"]):
        intent = "toggle_bluetooth"
        actions = [act("open_app", target="com.android.settings"), act("search", target="Bluetooth"), act("tap", target="toggle_bluetooth")]
    elif any(k in t for k in ["ব্রাউজ", "ওপেন", "open", "visit", "url"]):
        intent = "open_url"
        # naive url pick
        words = t.split()
        url = next((w for w in words if w.startswith("http") or ".com" in w), None)
        actions = [act("open_url", target=url or "http://google.com")]
    else:
        intent = "unknown"
        actions = [act("unknown")] 

    cmd = Command(text=req.text, language=req.language, intent=intent, actions=actions, device_id=req.device_id)

    # persist command plan
    doc_id = create_document("command", cmd)
    return cmd

# Outbox for device to pull actions (long-poll style simple API)
class PullRequest(BaseModel):
    device_id: str
    limit: int = 10

@app.post("/pull")
def pull_actions(req: PullRequest):
    # get latest commands for this device that are pending/sent
    docs = get_documents("command", {"device_id": req.device_id})
    out: List[dict] = []
    for d in docs[::-1]:  # newest last
        for a in d.get("actions", []):
            if a.get("status", "pending") in ("pending", "sent"):
                out.append(a)
                if len(out) >= req.limit:
                    break
        if len(out) >= req.limit:
            break
    return {"actions": out}

# Receive execution status updates from device
class ActionStatus(BaseModel):
    device_id: str
    action_index: int
    command_id: Optional[str] = None
    status: str
    error: Optional[str] = None

@app.post("/status")
def update_status(s: ActionStatus):
    # For simplicity, we just store a status log collection
    create_document("status", s)
    return {"ok": True}

# Simple history endpoint
@app.get("/history")
def history():
    items = get_documents("command")
    for it in items:
        it["_id"] = str(it["_id"]) if "_id" in it else None
    return items

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
