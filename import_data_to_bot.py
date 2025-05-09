import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio

# Настройка доступа к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# Открываем таблицу
spreadsheet = client.open("finance_bot")

# Получаем данные из листа "Вложения"
attachments_sheet = spreadsheet.worksheet("Вложения")
attachments_data = attachments_sheet.get_all_records()

# Получаем данные из листа "Расходы"
expenses_sheet = spreadsheet.worksheet("Расходы")
expenses_data = expenses_sheet.get_all_records()

# Объединяем данные
combined_data = {
    "attachments": attachments_data,
    "expenses": expenses_data
}

# Функция для передачи данных в бота
async def send_data_to_bot(data):
    # Здесь вы можете использовать ваш код для передачи данных в бота
    for attachment in data['attachments']:
        await bot.send_message(chat_id, f"Вложение: {attachment['Продукт/Перевод']} - {attachment['Сумма, руб.']} (Дата: {attachment['Дата']})")

    for expense in data['expenses']:
        await bot.send_message(chat_id, f"Расход: {expense['Продукт/Перевод']} - {expense['Сумма, руб.']} (Дата: {expense['Дата']})")

# Запуск передачи данных
asyncio.run(send_data_to_bot(combined_data))
