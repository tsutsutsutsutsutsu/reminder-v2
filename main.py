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
    text = event.message.text
    user_id = event.source.user_id

    try:
        now = datetime.now()
        remind_dt = now + timedelta(minutes=1)  # 1分後
        now_id = now.strftime("%Y%m%d%H%M%S")

        # スプレッドシートに書き込む（初期状態は「予約中」固定）
        new_row = [now_id, text, remind_dt.strftime("%Y-%m-%d %H:%M"), user_id, "予約中"]
        worksheet.append_row(new_row)

        delay = (remind_dt - now).total_seconds()
        timer = threading.Timer(delay, check_status_and_send, args=(user_id, text, now_id))
        timer.start()
        reminder_tasks[now_id] = timer

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"リマインド登録完了！\nID: {now_id}\nキャンセルしたい時はシートの状態を「キャンセル」にしてね。")
        )
    except Exception as e:
        print(f"登録エラー: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="登録中にエラーが発生しました。")
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))