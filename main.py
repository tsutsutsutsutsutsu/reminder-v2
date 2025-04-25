from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()

# Flask アプリの準備
app = Flask(__name__)

# LINE Messaging API 設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Google Sheets 認証設定
cred_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
cred_dict = json.loads(cred_json)
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
gc = gspread.authorize(credentials)

# スプレッドシートのIDとシートの取得
SHEET_ID = "1cmnNlCU04Pe31l1IrUAn5SGlsx4T3o-KTgA715jss4Q"
worksheet = gc.open_by_key(SHEET_ID).sheet1

# Webhook エンドポイント
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# メッセージイベントハンドラー
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    reply_text = f"受け取ったメッセージ: {msg}"
    
    # スプレッドシートに書き込む
    worksheet.append_row([msg, event.source.user_id])

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# Railway用にポート指定
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
