[fintech_dl_hse_bot](https://t.me/fintech_dl_hse_bot)

## Команды:

* /qa <вопрос> - Отвечает на вопрос, используя в контексте README курса
* /help - Список доступных команд
* /get_chat_id - Получить id текущего чата и thread id
* /github [nickname] - Привязать или показать привязанный GitHub
* /invit <github_nickname> - Проверить наличие репозиториев ДЗ по шаблонам
* /quiz - Запустить первый незавершённый квиз (в личных сообщениях)
* /quiz_stat - Статистика по квизам (в личных сообщениях)

## Команды для админов:
* /add_admin <user_id> - Добавить администратора
* /course_chat <chat_id> - Установить чат курса. Бот должен быть администратором в этом чате
* /course_members - Статистика по пользователям из личных сообщений
* /new_quiz <quiz_id> - Создать квиз
* /quiz_list - Список квизов. Каждый квиз отправляется отдельным сообщением
* /quiz_delete <quiz_id> - Удалить квиз
* /quiz_admin_stat - Админ-статистика по квизам (кол-во студентов, mean/std попыток по квизам)
* /hw_templates list | add \<template\> | remove \<N\> - Управление шаблонами репозиториев ДЗ (например fintech-dl-hse/hw-mlp-{github_nickname})

## Конфиг

Бот читает настройки из JSON файла. Путь передаётся через CLI аргумент `--config`.
Файл **перечитывается при каждом новом сообщении**.

Пример конфига: `assistant_bot/bot_config.json`

Для команды `/invit` нужна переменная окружения `GITHUB_TOKEN` или `GITHUB_ACCESS_TOKEN` (GitHub Personal Access Token с доступом на чтение репозиториев).

```json
{
  "admin_users": [123456789, "my_username"],
  "course_chat_id": -1001234567890,
  "hw_templates": [
    "fintech-dl-hse/hw-mlp-{github_nickname}",
    "fintech-dl-hse/hw-autograd-mlp-{github_nickname}"
  ]
}
```

Запуск:

```bash
python src/bot.py --config assistant_bot/bot_config.json --pm-log-file assistant_bot/private_messages.jsonl --quizzes-file assistant_bot/quizzes.json --quiz-state-file assistant_bot/quiz_state.json
```

## TODO
- Слинковать github аккаунт
- Уведомления о том, что домашка получила какую-то оценку из автогрейдера
- Сделать апи для получения данных по студенту (по нику в гитхабе), чтобы студенты могли пользоваться им как тулзой и узнать текущую оценку за курс
- Пререхать с файликов на таблички и в облако
