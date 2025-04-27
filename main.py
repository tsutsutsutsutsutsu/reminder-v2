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

def schedule_reminders():
    while True:
        now = datetime.now()
        all_data = worksheet.get_all_values()
        headers = all_data[0]
        rows = all_data[1:]

        for row in rows:
            data = dict(zip(headers, row))
            id = data.get("ID")
            message = data.get("メッセージ")
            remind_time = data.get("リマインド時刻")
            user_id = data.get("ユーザーID")
            status = data.get("状態")

            if status == "キャンセル":
                if id in reminder_tasks:
                    reminder_tasks[id].cancel()
                    del reminder_tasks[id]
                continue

            if id not in reminder_tasks and remind_time and user_id:
                remind_dt = datetime.strptime(remind_time, "%Y-%m-%d %H:%M")
                delay = (remind_dt - now).total_seconds()
                if delay > 0:
                    timer = threading.Timer(delay, send_reminder, args=(user_id, message, id))
                    timer.start()
                    reminder_tasks[id] = timer

        threading.Event().wait(60)

def send_reminder(user_id, message, id):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=message))
    except Exception as e:
        print(f"送信エラー: {e}")
    if id in reminder_tasks:
        del reminder_tasks[id]

def send_test_reminder():
    try:
        all_data = worksheet.get_all_values()
        headers = all_data[0]
        rows = all_data[1:]

        now = datetime.now()

        for row in rows:
            data = dict(zip(headers, row))
            user_id = data.get("ユーザーID")
            message = data.get("メッセージ")
            remind_time = data.get("リマインド時刻")

            if user_id and message and remind_time:
                remind_dt = datetime.strptime(remind_time, "%Y-%m-%d %H:%M")
                if abs((remind_dt - now).total_seconds()) <= 60:
                    line_bot_api.push_message(user_id, TextSendMessage(text=f"[テスト送信] {message}"))
    except Exception as e:
        print(f"エラー発生: {e}")

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

    if text.startswith("リマインド "):
        try:
            _, time_text, reminder_text = text.split(" ", 2)
            remind_dt = datetime.strptime(time_text, "%Y-%m-%d %H:%M")
            now = datetime.now().strftime("%Y%m%d%H%M%S")
            new_row = [now, reminder_text, remind_dt.strftime("%Y-%m-%d %H:%M"), user_id, ""]
            worksheet.append_row(new_row)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="リマインドを登録しました！")
            )
        except Exception as e:
            print(f"登録エラー: {e}")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="登録失敗しました。フォーマットは リマインド YYYY-MM-DD HH:MM メッセージ内容 で送ってね！")
            )
    elif text == "テストリマインド":
        send_test_reminder()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="リマインド送信テストを開始しました！")
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="リマインドを登録するには「リマインド YYYY-MM-DD HH:MM メッセージ内容」と送ってね！")
        )

if __name__ == "__main__":
    threading.Thread(target=schedule_reminders, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))