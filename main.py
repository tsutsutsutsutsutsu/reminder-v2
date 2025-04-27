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
                    # リマインド時刻が今±60秒以内なら送信
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
    if text == "テストリマインド":
        send_test_reminder()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="リマインド送信テストを開始しました！")
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="「テストリマインド」と送ってリマインド送信テスト！")
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))