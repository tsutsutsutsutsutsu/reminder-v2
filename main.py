import os
import json
import gspread
from flask import Flask, request, abort
from google.oauth2.service_account import Credentials
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

# LINE設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('CHANNEL_SECRET')
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Google Sheets設定
cred_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
cred_dict = json.loads(cred_json)
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
gc = gspread.authorize(credentials)

# スプレッドシートアクセス
SHEET_ID = "1cmnNlCU04Pe31l1IrUAn5SGlsx4T3o-KTgA715jss4Q"
sh = gc.open_by_key(SHEET_ID)
worksheet = sh.sheet1

# Flaskアプリ
app = Flask(__name__)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    user_id = event.source.user_id

    # スプレッドシートからデータ取得
    rows = worksheet.get_all_values()

    for row in rows[1:]:  # 1行目はヘッダーなので飛ばす
        id_value = row[0]
        message = row[1]
        remind_time = row[2]
        target_user_id = row[3]
        status = row[4] if len(row) > 4 else ""

        if status.strip() == "キャンセル":
            continue  # キャンセルされたものはスキップ

        if user_id == target_user_id:
            reply_text = f"【リマインド】{message}\nリマインド時刻: {remind_time}"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
            return

    # 対応するものがなかった場合
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="リマインド登録がありません。")
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
