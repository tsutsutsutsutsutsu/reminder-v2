import os
import json
import gspread
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, abort
from google.oauth2.service_account import Credentials
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# .env 読み込み
load_dotenv()

# LINE設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Google Sheets設定
cred_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
cred_dict = json.loads(cred_json)
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
gc = gspread.authorize(credentials)

SHEET_ID = "1cmnNlCU04Pe31l1IrUAn5SGlsx4T3o-KTgA715jss4Q"
sh = gc.open_by_key(SHEET_ID)
worksheet = sh.sheet1

app = Flask(__name__)

# 通知タスク管理
reminder_tasks = {}

def send_reminder(user_id, message, id):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=message))
    except Exception as e:
        print(f"送信エラー: {e}")
    if id in reminder_tasks:
        del reminder_tasks[id]

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"エラー: {e}")
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    user_id = event.source.user_id

    try:
        now = datetime.now()
        remind_dt = now + timedelta(minutes=1)  # 1分後
        now_id = now.strftime("%Y%m%d%H%M%S")

        # スプレッドシートに書き込む
        new_row = [now_id, text, remind_dt.strftime("%Y-%m-%d %H:%M"), user_id, ""]
        worksheet.append_row(new_row)

        # すぐ送信セット
        delay = (remind_dt - now).total_seconds()
        timer = threading.Timer(delay, send_reminder, args=(user_id, text, now_id))
        timer.start()
        reminder_tasks[now_id] = timer

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="リマインドを登録しました！（1分後に通知）")
        )
    except Exception as e:
        print(f"登録エラー: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="エラーが発生しました。")
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))