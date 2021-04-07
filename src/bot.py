import telegram
import telegram.ext
import textwrap
import json
import psycopg2
import requests

SET_LOCATION_MENU = 1


def help_command(update, context):
    help_message = textwrap.dedent("""\
                                    /help - available commands
                                    /set_location - set a weather forecast location
                                    /get_weather - get a weather forecast
                                """)

    context.bot.send_message(chat_id=update.effective_chat.id, text=help_message)


def start(update, context):
    start_message = textwrap.dedent("""\
                                    Welcome to the weather bot!
                                    Here you can get a forecast for any location!
                                """)

    context.bot.send_message(chat_id=update.effective_chat.id, text=start_message)
    help_command(update, context)


def open_db_connection():
    return psycopg2.connect(
        database="database",
        user="postgres",
        password="password",
        host="127.0.0.1",
        port="5432"
    )


def get_location_from_db(user_id):
    with open_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT latitude, longitude FROM users WHERE id = {user_id}")
            location = cur.fetchone()
    return location


def current_location(update, context):
    location_button = telegram.KeyboardButton(text="Send location", request_location=True)
    cancel_button = telegram.KeyboardButton(text="Cancel")
    keyboard = [[location_button], [cancel_button]]
    reply_markup = telegram.ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    user_id = update.effective_user.id
    location = get_location_from_db(user_id)

    if location is None:
        context.bot.send_message(chat_id=user_id, text="Your current location is not set")
    else:
        context.bot.send_message(chat_id=user_id, text="Your current location: ")
        context.bot.send_location(chat_id=user_id, latitude=location[0], longitude=location[1])

    context.bot.send_message(chat_id=user_id, text="Do you want to set the new location?", reply_markup=reply_markup)
    return SET_LOCATION_MENU


def set_location(update, context):
    with open_db_connection() as conn:
        with conn.cursor() as cur:
            latitude = update.message.location.latitude
            longitude = update.message.location.longitude
            cur.execute(f"""INSERT INTO users VALUES({update.effective_user.id}, {latitude}, {longitude}) 
                            ON CONFLICT(id) DO UPDATE SET latitude = {latitude}, longitude = {longitude};""")

    user_id = update.effective_user.id
    message = "The new location is successfully set"
    context.bot.send_message(chat_id=user_id, text=message, reply_markup=telegram.ReplyKeyboardRemove())


def cancel(update, context):
    return telegram.ext.ConversationHandler.END


def get_weather(update, context):
    user_id = update.effective_user.id
    location = get_location_from_db(user_id)

    if location is None:
        message = textwrap.dedent("""\
                                    Your current location is not set
                                    Please use this command /set_location
                                """)

        context.bot.send_message(chat_id=user_id, text=message)

    else:
        api_key = context.bot_data['weather_api_key']
        latitude = location[0]
        longitude = location[1]

        url = f"http://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
        response = requests.get(url)

        data = json.loads(response.text)
        forecast = textwrap.dedent(f"""\
                                    {data["weather"][0]["main"]}

                                    Temp: {data["main"]["temp"]}°C
                                    Max temp: {data["main"]["temp_max"]}°C
                                    Min temp: {data["main"]["temp_min"]}°C
                                    Humidity: {data["main"]["humidity"]}%
                                    Wind speed: {data["wind"]["speed"]} m/s
                                """)

        context.bot.send_message(chat_id=user_id, text=forecast)


def main():
    persistence = telegram.ext.PicklePersistence(filename="pickle_data")
    updater = telegram.ext.Updater(token="token", persistence=persistence,
                                   use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.bot_data["weather_api_key"] = "api_key"

    conv_handler = telegram.ext.ConversationHandler(
        entry_points=[telegram.ext.CommandHandler("set_location", current_location)],
        states={
            SET_LOCATION_MENU: [
                telegram.ext.MessageHandler(telegram.ext.Filters.location, set_location),
            ],
        },
        fallbacks=[telegram.ext.MessageHandler(telegram.ext.Filters.regex("^Cancel$"), cancel)],
        persistent=True,
        name='conv_handler'
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(telegram.ext.CommandHandler("start", start))
    dispatcher.add_handler(telegram.ext.CommandHandler("help", help_command))
    dispatcher.add_handler(telegram.ext.CommandHandler("get_weather", get_weather))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
