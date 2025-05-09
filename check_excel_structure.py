import pandas as pd
import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('excel_check.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def check_investor_transfers():
    """Проверка структуры файла с переводами инвесторов"""
    try:
        df = pd.read_excel('investor_transfers.xlsx')
        print("\nСтруктура файла investor_transfers.xlsx:")
        print("Колонки:", df.columns.tolist())
        print("Первые 5 записей:")
        print(df.head())
        print("\nТипы данных:")
        print(df.dtypes)
    except Exception as e:
        print(f"Ошибка при чтении файла переводов: {e}")

def check_service_purchases():
    """Проверка структуры файла с покупками услуг"""
    try:
        df = pd.read_excel('service_payments.xlsx')
        print("\nСтруктура файла service_payments.xlsx:")
        print("Колонки:", df.columns.tolist())
        print("Первые 5 записей:")
        print(df.head())
        print("\nТипы данных:")
        print(df.dtypes)
    except Exception as e:
        print(f"Ошибка при чтении файла покупок: {e}")

if __name__ == "__main__":
    print("Проверка структуры Excel файлов...")
    check_investor_transfers()
    check_service_purchases() 