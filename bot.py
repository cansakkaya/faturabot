import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from retriever import answer_question

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]

@app.event("message")
def handle_message(event, say, client):
    if event.get("bot_id"):
        return
    if event.get("channel") != CHANNEL_ID:
        return
    if event.get("thread_ts"):
        return

    question = event.get("text", "").strip()
    if not question:
        return

    thread_ts = event.get("ts")

    try:
        answer = answer_question(question)
    except Exception:
        answer = "Something went wrong while processing your question. Please try again."

    say(text=answer, thread_ts=thread_ts)

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("Bot is running. Listening for messages...")
    handler.start()
