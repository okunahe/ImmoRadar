import os

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
  Application,
  CommandHandler,
  ContextTypes,
  ConversationHandler,
  MessageHandler,
  CallbackQueryHandler,
  filters,
 )

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Zustände des Dialogs
POSTCODE, RADIUS = range(2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
 await update.message.reply_text(
 " Willkommen bei ImmoRadar!\n\n"
 "Ich helfe dir, interessante Immobilienangebote zu finden.\n\n"
 "Benutze /search, um eine Suche zu starten."
 )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
 await update.message.reply_text(
 " Neue Immobiliensuche\n\n"
 "Bitte gib deine 5-stellige Postleitzahl ein:"
 )

 return POSTCODE


async def postcode_received(
 update: Update,
 context: ContextTypes.DEFAULT_TYPE
):
 postcode = update.message.text.strip()

 # PLZ überprüfen
 if not postcode.isdigit() or len(postcode) != 5:
  await update.message.reply_text(" Bitte gib eine gültige 5-stellige Postleitzahl ein.")
  return POSTCODE

 # PLZ speichern
 context.user_data["postcode"] = postcode

 keyboard = [
 [
 InlineKeyboardButton("5 km", callback_data="5"),
 InlineKeyboardButton("10 km", callback_data="10"),
 ],
 [
 InlineKeyboardButton("20 km", callback_data="20"),
 InlineKeyboardButton("50 km", callback_data="50"),
 ],
 ]

 await update.message.reply_text(
 f" Postleitzahl: {postcode}\n\n"
 "Wie groß soll der Suchradius sein?",
 reply_markup=InlineKeyboardMarkup(keyboard),
 )

 return RADIUS


async def radius_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
 query = update.callback_query

 await query.answer()

 radius = query.data
 postcode = context.user_data["postcode"]

 context.user_data["radius"] = radius

 await query.edit_message_text(
 " Suche wird vorbereitet...\n\n"
 f" Postleitzahl: {postcode}\n"
 f" Radius: {radius} km\n\n"
 " Im nächsten Schritt wird hier der "
 "Kleinanzeigen-Scraper gestartet."
 )

 return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
 await update.message.reply_text("Suche abgebrochen.")

 return ConversationHandler.END


def main():
 if not TOKEN:
  raise RuntimeError("TELEGRAM_BOT_TOKEN wurde nicht in der .env gefunden.")

 app = Application.builder().token(TOKEN).build()

 conversation = ConversationHandler(
 entry_points=[
 CommandHandler("search", search)
 ],
 states={
 POSTCODE: [
 MessageHandler(
 filters.TEXT & ~filters.COMMAND,
 postcode_received,
 )
 ],
 RADIUS: [
 CallbackQueryHandler(radius_received)
 ],
 },
 fallbacks=[
 CommandHandler("cancel", cancel)
 ],
 )

 app.add_handler(CommandHandler("start", start))
 app.add_handler(conversation)

 print(" ImmoRadar Bot läuft...")

 app.run_polling()


if __name__ == "__main__":
 main()



