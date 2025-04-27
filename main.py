import os
import json
import gspread
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

# LINE設定
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Google Sheets設定
cred_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
cred_dict = json.loads(cred_json)
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
gc = gspread.authorize(credentials)
SHEET_ID = "1cmnNlCU04Pe31l1IrUAn5SGlsx4T3o-KTgA715jss4Q"
worksheet = gc.open_by_key(SHEET_ID).sheet1

# Flaskアプリ
app = Flask(__name__)

# 通知予約する関数
def schedule_notification(user_id, message, send_time, row_index):
    delay = (send_time - datetime.now()).total_seconds()
    if delay < 0:
        delay = 0

    def task():
        try:
            line_bot_api.push_message(user_id, TextSendMessage(text=message))
            worksheet.update_cell(row_index, 5, "送信済み")
        except Exception as e:
            print(f"通知失敗: {e}")

    threading.Timer(delay, task).start()

# Webhook受信
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

# LINEメッセージ受信時
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="通知を登録しました！")
    )

    # ここでスプレッドシートから通知予約する
    values = worksheet.get_all_values()

    for idx, row in enumerate(values[1:], start=2):
        if len(row) < 4:
            continue
        if row[4] != "未送信":
            continue
        if "キャンセル" in row:
            continue

        try:
            schedule_time = datetime.strptime(row[1], "%Y/%m/%d %H:%M")
            message_to_send = row[2]
            schedule_notification(user_id, message_to_send, schedule_time, idx)
            worksheet.update_cell(idx, 5, "予約済み")
        except Exception as e:
            print(f"スケジュール登録失敗: {e}")

# ローカルサーバー起動
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
