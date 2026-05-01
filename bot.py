import os
import re
import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from retriever import answer_question

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])


def _md_to_mrkdwn(text: str) -> str:
    # **bold** → *bold*
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text, flags=re.DOTALL)
    # ### Heading / ## Heading / # Heading → *Heading*
    text = re.sub(r'^#{1,6}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
    # [text](url) → <url|text>
    text = re.sub(r'\[(.+?)\]\((https?://[^\)]+)\)', r'<\2|\1>', text)
    return text


CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
BOT_USER_ID = None


def _get_bot_user_id(client) -> str:
    global BOT_USER_ID
    if BOT_USER_ID is None:
        BOT_USER_ID = client.auth_test()["user_id"]
    return BOT_USER_ID


def _fetch_thread_history(client, channel: str, thread_ts: str) -> list[dict]:
    result = client.conversations_replies(channel=channel, ts=thread_ts)
    bot_id = _get_bot_user_id(client)
    history = []
    for msg in result["messages"]:
        text = msg.get("text", "").strip()
        if not text:
            continue
        if msg.get("user") == bot_id or msg.get("bot_id"):
            history.append({"role": "model", "text": text})
        else:
            history.append({"role": "user", "text": text})
    return history


@app.event("message")
def handle_message(event, say, client):
    if event.get("bot_id"):
        return
    if event.get("channel") != CHANNEL_ID:
        return

    question = event.get("text", "").strip()
    if not question:
        return

    thread_ts = event.get("thread_ts") or event.get("ts")
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] RECEIVED: {question[:80]}")

    # fetch conversation history if this is a thread reply
    if event.get("thread_ts"):
        history = _fetch_thread_history(client, event["channel"], thread_ts)
    else:
        history = [{"role": "user", "text": question}]

    print(f"[{ts}] GENERATING answer...")
    try:
        answer = answer_question(history)
        print(f"[{ts}] DONE ({len(answer)} chars)")
    except Exception as e:
        print(f"[{ts}] ERROR: {e}")
        answer = "Şu anda yanıt veremiyorum. Lütfe daha sonra tekrar dene."

    say(text=_md_to_mrkdwn(answer), thread_ts=thread_ts)
    print(f"[{ts}] REPLIED in thread {thread_ts}")

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass

if __name__ == "__main__":
    import sys
    print("Starting FaturaBot...", flush=True)
    port = int(os.environ.get("PORT", 8080))
    health_server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=health_server.serve_forever, daemon=True).start()
    print(f"Health check server on port {port}", flush=True)
    try:
        handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
        print("Bot is running. Listening for messages...", flush=True)
        handler.start()
    except Exception as e:
        print(f"FATAL: {e}", flush=True)
        sys.exit(1)
