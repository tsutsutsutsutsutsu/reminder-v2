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
        print(f"user_id={user_id}")  # ここを追加
        all_data = worksheet.get_all_values()
        headers = all_data[0]
        rows = all_data[1:]
        data_dict = {row[0]: dict(zip(headers, row)) for row in rows}

        record = data_dict.get(reminder_id)
        if record:
            status = record.get("\u72b6\u614b", "").strip()

            if status.lower() == "\u30ad\u30e3\u30f3\u30bb\u30eb":
                print(f"\u30ea\u30de\u30a4\u30f3\u30c9ID {reminder_id} \u306f\u30ad\u30e3\u30f3\u30bb\u30eb\u3055\u308c\u307e\u3057\u305f\u3002\u901a知\u30b9\u30adップ。")
                return

            line_bot_api.push_message(user_id, TextSendMessage(text=message))

            cell = worksheet.find(reminder_id)
            if cell:
                worksheet.update_cell(cell.row, headers.index("\u72b6\u614b") + 1, "\u9001\u4fe1\u6e08\u307f")

            print(f"\u30ea\u30de\u30a4\u30f3\u30c9\u9001\u4fe1\u6210\u529f: {message}")
    except Exception as e:
        print(f"\u30a8\u30e9\u30fc発生: {e}")
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
        print(f"\u30a8\u30e9\u30fc: {e}")
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    pass

def schedule_reminders():
    now = datetime.now()
    all_data = worksheet.get_all_values()
    headers = all_data[0]
    rows = all_data[1:]

    for row in rows:
        data = dict(zip(headers, row))
        reminder_id = data.get("ID")
        user_id = data.get("\u30e6\u30fc\u30b6\u30fcID")
        message = data.get("\u30e1\u30c3\u30bb\u30fc\u30b8")
        remind_date = data.get("\u30ea\u30de\u30a4\u30f3\u30c9\u65e5")
        status = data.get("\u72b6\u614b", "").strip()

        if not reminder_id or not user_id or not message or not remind_date:
            continue
        if status not in ["\u4e88\u7d04\u4e2d"]:
            continue
        if reminder_id in reminder_tasks:
            continue

        try:
            remind_dt = datetime.strptime(remind_date, "%Y/%m/%d")
            if remind_dt.date() == now.date():
                delay = 60  # 1分後
                timer = threading.Timer(delay, check_status_and_send, args=(user_id, message, reminder_id))
                timer.start()
                reminder_tasks[reminder_id] = timer
                print(f"\u30ea\u30de\u30a4\u30f3\u30c9予約セット: {reminder_id} (delay {delay}秒)")
        except Exception as e:
            print(f"\u4e88約エラー: {e}")

if __name__ == "__main__":
    threading.Thread(target=schedule_reminders, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
