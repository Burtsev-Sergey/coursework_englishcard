-- Создание таблицы users. Здесь хранятся пользователи с уникальными идентификаторами ID в ТГи состоянием
CREATE TABLE IF NOT exists users (
  id SERIAL PRIMARY KEY,
  user_id INT unique,
  current_state VARCHAR(50)
);

-- Создание таблицы user_words. Здесь хранятся уникальные слова, добавленные каждым пользователем.
CREATE TABLE IF NOT exists user_words (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(user_id),
  target_word VARCHAR(100),
  translate VARCHAR(100)
);

-- Создание таблицы default_words. Здесь хранятся слова, доступные всем пользователям.
CREATE TABLE IF NOT exists default_words (
  id SERIAL PRIMARY KEY,
  target_word VARCHAR(100),
  translate VARCHAR(100)
);

-- Заполнение таблицы default_words
insert into default_words(target_word, translate)
values ('Blue', 'Синий'), ('White', 'Белый'), ('Green','Зеленый'), ('Car', 'Автомобиль'),
       ('Hello', 'Здравствуйте'), ('Download', 'Скачать'), ('Runner', 'Бегун'), ('Before', 'Перед'),
       ('Drive', 'Ехать'), ('Dog', 'Собака');