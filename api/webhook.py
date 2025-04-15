from flask import Flask, request, Response
import telegram
from osint_bot import setup_bot
import os

app = Flask(__name__)
bot = setup_bot()

@app.route('/api/webhook', methods=['POST'])
def webhook():
    if request.method == "POST":
        update = telegram.Update.de_json(request.get_json(force=True), bot)
        setup_bot(update)
        return Response('ok', status=200)
    return Response('error', status=400)

@app.route('/api/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = 'YOUR_VERCEL_URL/api/webhook'
    s = bot.setWebhook(webhook_url)
    if s:
        return Response('Webhook setup ok', status=200)
    return Response('Webhook setup failed', status=400)

@app.route('/')
def home():
    return 'Bot is running!' 