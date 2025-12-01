# Home Task Bot

Телеграм-бот для управления списком домашних дел.

## Возможности

- Создание новых задач
- Просмотр списка активных дел
- Отметка о выполнении

## Установка и запуск

1.  Клонируйте репозиторий:
    ```bash
    git clone <URL репозитория>
    cd home-task-bot
    ```

2.  Создайте и активируйте виртуальное окружение:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  Установите зависимости:
    ```bash
    pip install -r requirements.txt
    ```

4.  Создайте файл `.env` и добавьте в него токен вашего бота:
    ```
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN_HERE"
    ```

5.  Запустите бота:
    ```bash
    python bot.py
    ```

<!-- Trigger CI -->
<!-- Trigger CI 2 -->
