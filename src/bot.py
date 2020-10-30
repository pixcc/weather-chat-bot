from psycopg2.extensions import connection, cursor
from telegram import Update, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters, \
    ConversationHandler, PicklePersistence
from textwrap import dedent
from typing import Dict, Any, List, Tuple, Optional

import json
import psycopg2
import requests


SET_LOCATION_MENU = 1


def help_command(update: Update, context: CallbackContext) -> None:
    help_message: str = dedent("""\
                                /help - available commands
                                /set_location - set a weather forecast location
                                /get_weather - get a weather forecast
                            """)

    context.bot.send_message(chat_id=update.effective_chat.id, text=help_message)


def start(update: Update, context: CallbackContext) -> None:
    start_message: str = dedent("""\
                                Welcome to the weather bot!
                                Here you can get a forecast for any location!
                            """)

    context.bot.send_message(chat_id=update.effective_chat.id, text=start_message)
    help_command(update, context)


def open_db_connection() -> connection:
    return psycopg2.connect(
        database="database",
        user="postgres",
        password="password",
        host="127.0.0.1",
        port="5432"
    )


def get_location_from_db(user_id: int) -> Optional[Tuple[float, float]]:
    with open_db_connection() as conn:
        with conn.cursor() as cur:
            cur: cursor
            conn: connection
            cur.execute(f"""SELECT latitude, longitude FROM users WHERE id = {user_id}""")
            location: Optional[Tuple[float, float]] = cur.fetchone()
    return location


def current_location(update: Update, context: CallbackContext) -> int:
    location_button: KeyboardButton = KeyboardButton(text="Send location", request_location=True)
    cancel_button: KeyboardButton = KeyboardButton(text="Cancel")
    keyboard: List[List[KeyboardButton]] = [[location_button], [cancel_button]]
    reply_markup: ReplyKeyboardMarkup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    user_id: int = update.effective_user.id
    location: Optional[Tuple[float, float]] = get_location_from_db(user_id)

    if location is None:
        context.bot.send_message(chat_id=user_id, text="Your current location is not set")
    else:
        context.bot.send_message(chat_id=user_id, text="Your current location: ")
        context.bot.send_location(chat_id=user_id, latitude=location[0], longitude=location[1])

    context.bot.send_message(chat_id=user_id, text="Do you want to set the new location?", reply_markup=reply_markup)
    return SET_LOCATION_MENU


def set_location(update: Update, context: CallbackContext) -> None:
    with open_db_connection() as conn:
        with conn.cursor() as cur:
            cur: cursor
            conn: connection
            latitude: float = update.message.location.latitude
            longitude: float = update.message.location.longitude
            cur.execute(f"""INSERT INTO users VALUES({update.effective_user.id}, {latitude}, {longitude}) 
                            ON CONFLICT(id) DO UPDATE SET latitude = {latitude}, longitude = {longitude};""")

    user_id: int = update.effective_user.id
    message: str = "The new location is successfully set"
    context.bot.send_message(chat_id=user_id, text=message, reply_markup=ReplyKeyboardRemove())


def cancel(update: Update, context: CallbackContext) -> int:
    return ConversationHandler.END


def get_weather(update: Update, context: CallbackContext) -> None:
    user_id: int = update.effective_user.id
    location: Optional[Tuple[float, float]] = get_location_from_db(user_id)

    if location is None:
        message: str = dedent("""\
                                Your current location is not set
                                Please use this command /set_location
                            """)

        context.bot.send_message(chat_id=user_id, text=message)

    else:
        api_key: str = context.bot_data['weather_api_key']
        latitude: float = location[0]
        longitude: float = location[1]

        url: str = f"http://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
        response: requests.Response = requests.get(url)

        data: Dict[str, Any] = json.loads(response.text)
        forecast: str = dedent(f"""\
                                {data["weather"][0]["main"]}

                                Temp: {data["main"]["temp"]}°C
                                Max temp: {data["main"]["temp_max"]}°C
                                Min temp: {data["main"]["temp_min"]}°C
                                Humidity: {data["main"]["humidity"]}%
                                Wind speed: {data["wind"]["speed"]} m/s
                            """)

        context.bot.send_message(chat_id=user_id, text=forecast)


def main() -> None:
    persistence: PicklePersistence = PicklePersistence(filename="pickle_data")
    updater: Updater = Updater(token="token", persistence=persistence,
                               use_context=True)
    dispatcher: Dispatcher = updater.dispatcher
    dispatcher.bot_data["weather_api_key"] = "key"

    conv_handler: ConversationHandler = ConversationHandler(
        entry_points=[CommandHandler("set_location", current_location)],
        states={
            SET_LOCATION_MENU: [
                MessageHandler(Filters.location, set_location),
            ],
        },
        fallbacks=[MessageHandler(Filters.regex("^Cancel$"), cancel)],
        persistent=True,
        name='conv_handler'
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("get_weather", get_weather))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
