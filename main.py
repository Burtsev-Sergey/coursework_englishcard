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


""" Выбор слов из индивидуального словаря в таблице user_words.
Если слов в индивидуальном словаре меньше 4, слова выбираются из словаря в таблице default_words.
default_words заполняется предварительно.
Выбираются слова для кнопок и запроса пользователю на перевод слова """
def choice_words():
  cursor.execute("SELECT COUNT(*) FROM user_words")
  row_count = cursor.fetchone()[0]
  conn.commit()

  if row_count > 4:
    cursor.execute("SELECT target_word, translate FROM user_words ORDER BY RANDOM() LIMIT 1")
    target_word, translate = cursor.fetchone()
    tw = target_word
    t = translate
    conn.commit()

    cursor.execute("SELECT target_word FROM user_words WHERE target_word <> %s", (target_word,))
    other_words = cursor.fetchall()

    if len(other_words) >= 3:
      other_words = random.sample(other_words, 3)
    else:
      other_words = other_words

    other_words = [word[0] for word in other_words]
    ow = other_words
    conn.commit()

  else:
    cursor.execute("SELECT target_word, translate FROM default_words WHERE id = 3")
    target_word, translate = cursor.fetchone()
    tw = target_word
    t = translate
    conn.commit()

    cursor.execute("SELECT target_word FROM default_words WHERE target_word <> %s", (target_word,))
    other_words = cursor.fetchall()

    if len(other_words) >= 3:
      other_words = random.sample(other_words, 3)
    else:
      other_words = other_words

    other_words = [word[0] for word in other_words]
    ow = other_words
    conn.commit()
  
  return tw, t, ow


known_users = []
userStep = {}
buttons = []


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


""" Определение постоянных команд интерфейса бота. """
class Command:
    ADD_WORD = 'Добавить слово➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше⏭'


""" Определение возможных состояний пользователя в боте """
class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()


""" Проверка наличия uid пользоваетеля в списке known_users.
Если в спииске нет - добавить в список и перевести в стартовое состояние. """
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
Отправка сообщения со словом для перевода. """
@bot.message_handler(commands=['cards', 'start'])
def create_cards(message):
    cid = message.chat.id
    tw, t, ow = choice_words() 
    if cid not in known_users:
        known_users.append(cid)
        userStep[cid] = 0
        bot.send_message(cid, (
            f'Привет 👋\n\n'
            f'Бот помогает практиковаться в английском языке.\n'
            f'Тренировки можно проходить в удобном для себя темпе.\n'
            f'У вас есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения.\n\n'
            f'Для этого воспрользуйтесь инструментами:\n'
            f'- Добавить слово ➕,\n'
            f'- Удалить слово 🔙.\n\n'
            f'Перейти к следующему слову:\n'
            f'- Дальше⏭.\n\n'
            f'Ну что, начнём ⬇️'))
    markup = types.ReplyKeyboardMarkup(row_width=2)

    global buttons
    buttons = []
    target_word = tw
    translate = t
    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    others = ow
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([next_btn, add_word_btn, delete_word_btn])

    markup.add(*buttons)

    greeting = f"Выберите перевод слова:\n🇷🇺 {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others


""" Обработчик при нажатии на кнопку "Дальше⏭" перезапускает:
функцию choice_words - новая выборка слов для кнопок и запроса на перевод
функцию create_cards - обновление кнопок интерфейса бота """
@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    choice_words()
    create_cards(message)


""" Обработчик - удаляет слова из таблицы user_words индивидуально для каждого пользователя.
Проверяет корректностсь ввода слова. Принимает слово на английском от пользователя.
Устанавливает значение состояния пользователя равным 2.
После успешного удаления запускает функцию next_cards """
@bot.message_handler(func=lambda message: message.text.startswith("Удалить слово🔙"))
def handle_delete_word(message):
  cid = message.chat.id
  bot.send_message(cid, "Введите английское слово для удаления из вашего словаря.")
  bot.register_next_step_handler(message, delete_word)

def delete_word(message):
  cid = message.chat.id
  target_word = message.text.strip()

  if not target_word:
    bot.send_message(cid, "Ошибка ввода. Введите одно слово для удаления.")
    return

  cursor.execute("SELECT * FROM user_words WHERE user_id = %s AND target_word = %s", (cid, target_word))
  existing_word = cursor.fetchone()

  if existing_word:
    cursor.execute("DELETE FROM user_words WHERE user_id = %s AND target_word = %s", (cid, target_word))
    conn.commit()
    bot.send_message(cid, (f'Слово "{target_word}" и его перевод были успешно удалены из вашего словаря.\n'
    f'Возвращаемся к изучению английских слов📖'))
    userStep[cid] = 2
    next_cards(message)
  else:
    bot.send_message(cid, "Такого слова нет в вашем словаре. Пожалуйста, убедитесь в правильности ввода и попробуйте снова.")
    handle_delete_word(message)



""" Обработчик - добавляет в таблицу user_words - id пользователя в ТГ, новое слово и перевод слова.
Проверяет есть или нет новое слово в таблице user_words у конкретного пользователя.
Ввод английского слова и перевода слова через пробел.
Устанавливает значение состояния пользователя равным 1.
После успешного ввода запускает функцию next_cards  """
@bot.message_handler(func=lambda message: message.text == "Добавить слово➕" or userStep.get(message.chat.id, 0) == 1)
def handle_add_word(message):
    cid = message.chat.id
    bot.send_message(cid, "Введите новое английское слово и его перевод через пробел.")
    userStep[cid] = 1
    bot.register_next_step_handler(message, add_word)


def add_word(message):
    cid = message.chat.id
    userStep[cid] = 0 
    words = message.text.strip().split(maxsplit=1)

    if len(words) != 2:
      bot.send_message(cid, "Ошибка ввода. Введите одно английское слово и его перевод, разделенные пробелом.")
      userStep[cid] = 1
      bot.register_next_step_handler(message, add_word)
      return

    target_word, translate = words

    cursor.execute("SELECT * FROM user_words WHERE user_id = %s AND target_word = %s", (cid, target_word))
    existing_word = cursor.fetchone()

    if existing_word:
      bot.send_message(cid, "Слово уже есть в вашем словаре. Введите другое слово и его перевод через пробел.")
      userStep[cid] = 1
      bot.register_next_step_handler(message, add_word)
    else:
      if cid not in known_users:
        cursor.execute("INSERT INTO users (id, state) VALUES (%s, %s)", (cid, userStep[cid]))
        conn.commit()
        known_users.add(cid)

      cursor.execute("INSERT INTO user_words (user_id, target_word, translate) VALUES (%s, %s, %s)", (cid, target_word, translate))
      conn.commit()

      bot.send_message(cid, (f'Карточка с новым словом "{target_word}" и переводом "{translate}" успешно создана!\n'
                 f'Возвращаемся к изучению английских слов📖'))

      next_cards(message)
    

""" Обработчик - проверка правильности введенного английского слова для слова на русском """
@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
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
                              f"Попробуйте ещё раз вспомнить слово 🇷🇺{data['translate_word']}")
    markup.add(*buttons)
    bot.send_message(message.chat.id, hint, reply_markup=markup)
        

bot.add_custom_filter(custom_filters.StateFilter(bot))

""" Метод бота, который постоянно ожидает сообщения """
bot.infinity_polling(skip_pending=True)