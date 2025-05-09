# Finance Bot

Telegram бот для учета финансовых операций инвесторов и закупок сервисов.

## Требования

- Python 3.8+
- PostgreSQL
- Telegram Bot Token
- API ключ для получения курсов валют

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd finance-bot
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте базу данных PostgreSQL:
```sql
CREATE DATABASE finance_bot;
```

5. Создайте файл .env и заполните его:
```
TELEGRAM_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finance_bot
EXCHANGE_RATE_API_KEY=your_exchange_rate_api_key
```

## Запуск

```bash
python main.py
```

## Функциональность

1. Общая сумма закупок сервисов, курсов и нейросетей
2. Сумма всех вложенных денег всеми инвесторами
3. Сумма вложений конкретного инвестора
4. Остаток казны на текущий момент

## Структура базы данных

- `investors` - таблица инвесторов
- `purchases` - таблица покупок инвесторов
- `transfers` - таблица переводов денежных средств
- `service_purchases` - таблица покупок сервисов 