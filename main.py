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

def check_status_and_send(user_id, message, reminder_id):
    try:
        all_data = worksheet.get_all_values()
        headers = all_data[0]
        rows = all_data[1:]
        data_dict = {row[0]: dict(zip(headers, row)) for row in rows}

        record = data_dict.get(reminder_id)
        if record:
            status = record.get("状態", "").strip()

            # もし状態が「キャンセル」なら送信しない
            if status.lower() == "キャンセル":
                print(f"リマインドID {reminder_id} はキャンセルされました。通知スキップ。")
                return

            # それ以外（「予約中」など）なら送信
            line_bot_api.push_message(user_id, TextSendMessage(text=message))

            # 送信後に「送信済み」に更新
            cell = worksheet.find(reminder_id)
            if cell:
                worksheet.update_cell(cell.row, headers.index("状態") + 1, "送信済み")

            print(f"リマインド送信成功: {message}")
    except Exception as e:
        print(f"エラー発生: {e}")
    finally:
        if reminder_id in reminder_tasks:
            del reminder_tasks[reminder_id]

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
    # 何もせずOKを返すだけ
    pass

def schedule_reminders():
    while True:
        now = datetime.now()
        all_data = worksheet.get_all_values()
        headers = all_data[0]
        rows = all_data[1:]

        for row in rows:
            data = dict(zip(headers, row))
            reminder_id = data.get("ID")
            user_id = data.get("ユーザーID")
            message = data.get("メッセージ")
            remind_time = data.get("リマインド時刻")
            status = data.get("状態", "").strip()

            if not reminder_id or not user_id or not message or not remind_time:
                continue
            if status not in ["予約中"]:
                continue
            if reminder_id in reminder_tasks:
                continue

            try:
                remind_dt = datetime.strptime(remind_time, "%Y-%m-%d %H:%M")
                delay = (remind_dt - now).total_seconds()
                if delay > 0:
                    timer = threading.Timer(delay, check_status_and_send, args=(user_id, message, reminder_id))
                    timer.start()
                    reminder_tasks[reminder_id] = timer
                    print(f"リマインド予約セット: {reminder_id} (delay {delay}秒)")
            except Exception as e:
                print(f"予約エラー: {e}")

        threading.Event().wait(60)  # 60秒ごとに再チェック

if __name__ == "__main__":
    threading.Thread(target=schedule_reminders, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))