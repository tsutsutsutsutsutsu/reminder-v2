import os
import json
import gspread
import threading
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, abort
from google.oauth2.service_account import Credentials
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
from linebot.models import MessageEvent, TextMessage

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

# 通知管理
def send_line_message(user_id, message, reminder_id):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=message))
        # 送信後に"送信済み"に更新
        all_data = worksheet.get_all_values()
        headers = all_data[0]
        cell = worksheet.find(reminder_id)
        if cell:
            worksheet.update_cell(cell.row, headers.index("状態") + 1, "送信済み")
        print(f"通知送信成功: {user_id}")
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
    pass

def monitor_sheet():
    checked_ids = set()
    while True:
        all_data = worksheet.get_all_values()
        headers = all_data[0]
        rows = all_data[1:]

        for row in rows:
            data = dict(zip(headers, row))
            reminder_id = data.get("ID")
            user_id = data.get("ユーザーID")
            message = data.get("メッセージ")
            status = data.get("状態", "").strip()

            if not reminder_id or not user_id or not message:
                continue
            if status in ["送信済み", "キャンセル"]:
                continue
            if reminder_id in checked_ids:
                continue

            send_line_message(user_id, message, reminder_id)
            checked_ids.add(reminder_id)

        time.sleep(10)  # 10秒ごとにチェック

if __name__ == "__main__":
    threading.Thread(target=monitor_sheet, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))