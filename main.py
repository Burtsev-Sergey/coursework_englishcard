import random

import psycopg2

from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

import os.path
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), 'config_tokens.env')

""" Проверка и загрузка переменных если файл config_dsn.env существует """
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
token = os.getenv('TG_TOKEN')

""" Инициализация бота, подключение бота в ТГ """
print('Start telegram bot...')

state_storage = StateMemoryStorage()

bot = TeleBot(token, state_storage=state_storage)

""" Подключение к базе данных """
dbname = os.getenv('DB_NAME')
user = os.getenv('USER')
password = os.getenv('PASSWORD')
host = os.getenv('HOST')
port = os.getenv('PORT')

conn = psycopg2.connect(
  dbname=dbname,
  user=user,
  password=password,
  host=host,  
  port=port
)
cursor = conn.cursor()

""" Выбор слов из общего словаря - таблица default_words.
Для кнопок и первого запроса-перевода """
cursor.execute("SELECT target_word, translate FROM default_words WHERE id = 2")
target_word, translate = cursor.fetchone()
tw = target_word
t = translate
# print(tw, t)
conn.commit()

cursor.execute("SELECT target_word FROM default_words WHERE target_word <> %s", (target_word,))
other_words = cursor.fetchall()
other_words = random.sample(other_words, 3)
other_words = [word[0] for word in other_words]
ow = other_words
# print(ow)
conn.commit()


known_users = []
userStep = {}
buttons = []


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"

""" Определение постоянных команд интерфейса бота. """
class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'

""" Определение возможных состояний пользователя """
class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()

""" Проверка наличия uid пользоваетеля в списке known_users.
Если нет добавить в список и перевести в стартовое состояние. """
def get_user_step(uid):
    if uid in userStep:
        return userStep[uid]
    else:
        known_users.append(uid)
        userStep[uid] = 0
        print("New user detected, who hasn't used \"/start\" yet")
        return 0


""" Обработчик стартовых команд бота cards и start. Отправка приветственного сообщения бота.
Добавление нового пользователя в список known_user. Создание клавиатуры интерфейса бота.
Отправка сообщения со словом для которого нужен перевод. """
@bot.message_handler(commands=['cards', 'start'])
def create_cards(message):
    cid = message.chat.id
    # print(f'ID пользователя Телеграм: {cid}')
    if cid not in known_users:
        known_users.append(cid)
        userStep[cid] = 0
        bot.send_message(cid, (
            f'Привет 👋\n\n'
            f'Давай попрактикуемся в английском языке.\n'
            f'Тренировки можешь проходить в удобном для себя темпе.\n'
            f'У тебя есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения.\n\n'
            f'Для этого воспрользуйся инструментами:\n'
            f'- добавить слово ➕,\n'
            f'- удалить слово 🔙.\n\n'
            f'Ну что, начнём ⬇️'))
    markup = types.ReplyKeyboardMarkup(row_width=2)

    global buttons
    buttons = []
    target_word = tw  # брать из БД
    translate = t  # брать из БД
    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    others = ow  # брать из БД
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([next_btn, add_word_btn, delete_word_btn])

    markup.add(*buttons)

    greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others


""" Обработчик который перезапускает обработчик create_cards """
@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


""" Обработчик который будет удалять слова из таблицы user_words """
@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        print(data['target_word'])  # удалить из БД


""" Обработчик который добавляет id в ТГ пользователя и слова в таблицу user_words.
Пока добавляет только английское слово и id. Устанавливает новое состояние пользователя """
@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    cid = message.chat.id
    userStep[cid] = 1
    state = userStep[cid]
    # print(message.text)  # сохранить в БД
    print(f'состояние пользователя в ADD_WORD: {state}')
    if cid not in known_users:
        cursor.execute(
            "INSERT INTO users (user_id, current_state) VALUES (%s, %s);",
            (cid, state)
            )
        conn.commit()
        cursor.execute(
            "INSERT INTO user_words (user_id, target_word) VALUES (%s, %s);",
            (cid, target_word)
            )
        conn.commit()
    else:
        cursor.execute(
            "INSERT INTO user_words (user_id, target_word) VALUES (%s, %s);",
            (cid, target_word)
            )
        conn.commit()


""" Обработчик Проверка введенного слова-перевода """
@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    cid = message.chat.id
    state = userStep[cid]
    print(f'состояние пользователя в проверке слова-перевода: {state}')
    if state != 1:
        text = message.text
        markup = types.ReplyKeyboardMarkup(row_width=2)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            target_word = data['target_word']
            if text == target_word:
                hint = show_target(data)
                hint_text = ["Отлично!❤", hint]
                next_btn = types.KeyboardButton(Command.NEXT)
                add_word_btn = types.KeyboardButton(Command.ADD_WORD)
                delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
                buttons.extend([next_btn, add_word_btn, delete_word_btn])
                hint = show_hint(*hint_text)
            else:
                for btn in buttons:
                    if btn.text == text:
                        btn.text = text + '❌'
                        break
                hint = show_hint("Допущена ошибка!",
                                 f"Попробуй ещё раз вспомнить слово 🇷🇺{data['translate_word']}")
        markup.add(*buttons)
        bot.send_message(message.chat.id, hint, reply_markup=markup)
    else:
        print('пользователь вводит слово')
        

bot.add_custom_filter(custom_filters.StateFilter(bot))

""" Метод бота, который постоянно ожидает сообщения """
bot.infinity_polling(skip_pending=True)