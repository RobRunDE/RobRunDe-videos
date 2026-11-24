"""Telegram bridge between the owner and the autopilot.

Secrets come from the environment (never from the repo):
    TELEGRAM_BOT_TOKEN   token from @BotFather
    TELEGRAM_CHAT_ID     the owner's chat id (only messages from this chat are accepted)

CLI:
    python3 pipeline/telegram.py send "Text"                      # plain message (HTML allowed)
    python3 pipeline/telegram.py video <mp4> "Caption" <SLUG>     # video with ✅ / ❌ / ✏️ buttons
    python3 pipeline/telegram.py inbox                            # new owner messages + button presses as JSON
    python3 pipeline/telegram.py ack <callback_id> "Text"         # confirm a button press
    python3 pipeline/telegram.py chatid                           # setup helper: show chat ids that wrote to the bot

State (not secret) lives in plan/telegram_state.json (update offset) and plan/approvals.json.
"""
import json, os, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "plan", "telegram_state.json")
APPROVALS = os.path.join(ROOT, "plan", "approvals.json")

def _tok():
    t = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not t: sys.exit("TELEGRAM_BOT_TOKEN fehlt (Umgebungsvariable)")
    return t

def _chat():
    c = os.environ.get("TELEGRAM_CHAT_ID")
    if not c: sys.exit("TELEGRAM_CHAT_ID fehlt (Umgebungsvariable)")
    return c

def api(method, params=None):
    data = urllib.parse.urlencode({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in (params or {}).items()}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{_tok()}/{method}", data=data, headers={"User-Agent": "curl/8.5.0"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    if not r.get("ok"): raise RuntimeError(r)
    return r["result"]

def buttons(slug):
    return {"inline_keyboard": [[{"text": "✅ Freigeben", "callback_data": f"ok:{slug}"},
                                 {"text": "❌ Ablehnen", "callback_data": f"no:{slug}"}],
                                [{"text": "✏️ Änderung wünschen", "callback_data": f"fb:{slug}"}]]}

def send(text, markup=None):
    p = {"chat_id": _chat(), "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if markup: p["reply_markup"] = markup
    return api("sendMessage", p)

def send_video(path, caption, slug=None):
    # curl multipart; --form-string keeps the caption literal
    args = ["curl", "-sS", "-X", "POST", f"https://api.telegram.org/bot{_tok()}/sendVideo",
            "--form-string", f"chat_id={_chat()}", "--form-string", f"caption={caption[:1000]}",
            "--form-string", "parse_mode=HTML", "--form-string", "supports_streaming=true", "-F", f"video=@{path}"]
    if slug: args += ["--form-string", "reply_markup=" + json.dumps(buttons(slug))]
    r = json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)
    if not r.get("ok"): raise RuntimeError(r.get("description"))
    return r["result"]

def inbox():
    st = json.load(open(STATE)) if os.path.exists(STATE) else {"offset": 0}
    ups = api("getUpdates", {"offset": st["offset"], "timeout": 0, "allowed_updates": ["message", "callback_query"]})
    me, out = str(_chat()), []
    for u in ups:
        st["offset"] = u["update_id"] + 1
        if "callback_query" in u:
            cq = u["callback_query"]
            if str(cq["message"]["chat"]["id"]) != me: continue
            act, _, slug = cq.get("data", "").partition(":")
            out.append({"type": "button", "action": {"ok": "approve", "no": "reject", "fb": "feedback"}.get(act, act),
                        "slug": slug, "callback_id": cq["id"], "date": cq["message"].get("date")})
        elif "message" in u:
            m = u["message"]
            if str(m["chat"]["id"]) != me: continue
            out.append({"type": "message", "text": m.get("text") or m.get("caption") or "", "date": m.get("date"),
                        "reply_to_video": (m.get("reply_to_message") or {}).get("caption", "")[:200],
                        "has_media": any(k in m for k in ("video", "photo", "document", "voice"))})
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w"))
    return out

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == "send": print(send(a[1])["message_id"])
    elif a[0] == "video": print(send_video(a[1], a[2], a[3] if len(a) > 3 else None)["message_id"])
    elif a[0] == "inbox": print(json.dumps(inbox(), ensure_ascii=False, indent=1))
    elif a[0] == "ack": api("answerCallbackQuery", {"callback_query_id": a[1], "text": a[2] if len(a) > 2 else "OK"}); print("ok")
    elif a[0] == "chatid":
        for u in api("getUpdates", {"timeout": 0}):
            m = u.get("message") or (u.get("callback_query") or {}).get("message") or {}
            c = m.get("chat", {}); print(c.get("id"), c.get("first_name") or c.get("title"), "|", (m.get("text") or "")[:40])
