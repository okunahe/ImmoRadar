import os
import asyncio
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from scraper import search_listings


load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Zustände des Dialogs
POSTCODE, RADIUS = range(2)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🏠 Willkommen bei ImmoRadar!\n\n"
        "Ich helfe dir, interessante Immobilienangebote zu finden.\n\n"
        "Benutze /search, um eine Suche zu starten."
    )


async def search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🔎 Neue Immobiliensuche\n\n"
        "Bitte gib deine 5-stellige Postleitzahl ein:"
    )

    return POSTCODE


async def postcode_received(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    postcode = update.message.text.strip()

    # PLZ überprüfen
    if not postcode.isdigit() or len(postcode) != 5:
        await update.message.reply_text(
            "❌ Bitte gib eine gültige "
            "5-stellige Postleitzahl ein."
        )

        return POSTCODE

    # PLZ speichern
    context.user_data["postcode"] = postcode

    keyboard = [
        [
            InlineKeyboardButton(
                "5 km",
                callback_data="5",
            ),
            InlineKeyboardButton(
                "10 km",
                callback_data="10",
            ),
        ],
        [
            InlineKeyboardButton(
                "20 km",
                callback_data="20",
            ),
            InlineKeyboardButton(
                "50 km",
                callback_data="50",
            ),
        ],
    ]

    await update.message.reply_text(
        f"📍 Postleitzahl: {postcode}\n\n"
        "Wie groß soll der Suchradius sein?",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )

    return RADIUS


async def radius_received(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    postcode = context.user_data["postcode"]
    radius = int(query.data)

    context.user_data["radius"] = radius

    await query.edit_message_text(
        "🔎 Suche läuft...\n\n"
        f"📍 Postleitzahl: {postcode}\n"
        f"📏 Radius: {radius} km\n\n"
        "Bitte einen Moment..."
    )

    # Immobilien suchen
    try:
        listings = await asyncio.to_thread(
            search_listings,
            postcode=postcode,
            radius=radius,
            max_results=100,
        )

    except Exception as error:
        print(
            "Scraper-Fehler:",
            error,
        )

        await query.message.reply_text(
            "❌ Bei der Immobiliensuche "
            "ist ein Fehler aufgetreten."
        )

        return ConversationHandler.END

    # Keine Ergebnisse
    if not listings:
        await query.message.reply_text(
            "😕 Keine Immobilien gefunden."
        )

        return ConversationHandler.END

    # Anzahl der Ergebnisse
    await query.message.reply_text(
        f"🏠 {len(listings)} Immobilien gefunden!"
    )

    # Ergebnisse einzeln an Telegram senden
    for listing in listings:

        # Kaufpreis
        if listing.price is not None:
            price_text = (
                f"{listing.price:,}"
                .replace(",", ".")
                + " €"
            )
        else:
            price_text = "Keine Angabe"

        # Wohnfläche
        if listing.area is not None:
            area_text = (
                f"{listing.area:g} m²"
            )
        else:
            area_text = "Keine Angabe"

        # Zimmer
        if listing.rooms is not None:
            rooms_text = str(
                listing.rooms
            )
        else:
            rooms_text = "Keine Angabe"

        # Hausgeld
        if listing.house_fee is not None:
            house_fee_text = (
                f"{listing.house_fee:g} €"
            )
        else:
            house_fee_text = "Keine Angabe"

        # Preis pro Quadratmeter
        if listing.price_per_sqm is not None:
            sqm_text = (
                f"{listing.price_per_sqm:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
                + " €/m²"
            )
        else:
            sqm_text = "Keine Angabe"

        # Ort
        if listing.location:
            location_text = listing.location
        else:
            location_text = "Keine Angabe"

        # Telegram-Nachricht
        message = (
            f"🏠 {listing.title}\n\n"
            f"💰 Kaufpreis: {price_text}\n"
            f"📐 Wohnfläche: {area_text}\n"
            f"🚪 Zimmer: {rooms_text}\n"
            f"💶 Hausgeld: {house_fee_text}\n"
            f"📊 Preis pro m²: {sqm_text}\n"
            f"📍 Ort: {location_text}\n\n"
            f"🔗 {listing.url}"
        )

        await query.message.reply_text(
            message,
            disable_web_page_preview=True,
        )

    return ConversationHandler.END


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "Suche abgebrochen."
    )

    return ConversationHandler.END


def main():
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN wurde "
            "nicht in der .env gefunden."
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler(
                "search",
                search,
            )
        ],
        states={
            POSTCODE: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    postcode_received,
                )
            ],
            RADIUS: [
                CallbackQueryHandler(
                    radius_received
                )
            ],
        },
        fallbacks=[
            CommandHandler(
                "cancel",
                cancel,
            )
        ],
    )

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        conversation
    )

    print("🚀 ImmoRadar Bot läuft...")

    app.run_polling()


if __name__ == "__main__":
    main()