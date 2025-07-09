import os
import json
import gspread
import threading
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, abort
from google.oauth2.service_account import Credentials
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage, MessageEvent, TextMessage

# --- 環境変数の読み込み ---
load_dotenv()
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_CREDENTIALS_JSON")  # Renderの環境変数名に合わせる
SHEET_ID = "1cmnNlCU04Pe31l1IrUAn5SGlsx4T3o-KTgA715jss4Q"

# --- LINE API 初期化 ---
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# --- Google Sheets 初期化 ---
cred_dict = json.loads(GOOGLE_SERVICE_ACCOUNT)
# 改行を戻す（Renderの環境変数対応）
cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
gc = gspread.authorize(credentials)
worksheet = gc.open_by_key(SHEET_ID).sheet1

# --- Flask アプリケーション ---
app = Flask(__name__)

# --- Webhook エンドポイント ---
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"❌ Webhookエラー: {e}")
        abort(400)
    return "OK"

# --- LINEメッセージ受信時の処理 ---
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print("✅ メッセージ受信！")
    user_id = event.source.user_id
    print(f"ユーザーID: {user_id}")
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="予約を受け付けました！"))

# --- 通知処理 ---
def send_line_message(user_id, message, row_index):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=message))
        worksheet.update_cell(row_index, 5, "送信済み")  # E列: 状態
        worksheet.update_cell(row_index, 7, datetime.now().strftime("%Y/%m/%d %H:%M"))
        print(f"✅ 通知送信成功: {user_id}")
    except Exception as e:
        print(f"❌ 通知エラー: {e}")
        fail_count = int(worksheet.cell(row_index, 6).value or 0) + 1
        worksheet.update_cell(row_index, 6, str(fail_count))
        worksheet.update_cell(row_index, 5, "エラー")

# --- 通知チェックループ ---
def monitor_sheet():
    while True:
        rows = worksheet.get_all_values()[1:]  # ヘッダーを除く
        for idx, row in enumerate(rows, start=2):
            if len(row) < 6:
                continue
            id_, message, remind_time, user_id, status, fail_count = row[:6]
            if status.strip() in ["送信済み", "キャンセル"]:
                continue
            try:
                remind_dt = datetime.strptime(remind_time, "%Y/%m/%d %H:%M")
            except ValueError:
                continue
            if datetime.now() >= remind_dt:
                send_line_message(user_id, message, idx)
        time.sleep(10)

# --- アプリ起動 ---
if __name__ == "__main__":
    # スレッドを開始
    threading.Thread(target=monitor_sheet, daemon=True).start()
    # Renderでの実行用にhostとportを設定
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)