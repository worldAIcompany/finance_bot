from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Transfer
import os
from dotenv import load_dotenv
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Подключение к базе данных
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def clean_duplicate_transfers():
    """Удаление дубликатов переводов из базы данных"""
    try:
        # Получаем все уникальные комбинации полей
        unique_transfers = session.query(
            Transfer.investor_id,
            Transfer.amount,
            Transfer.currency,
            Transfer.transfer_date
        ).distinct().all()
        
        logger.info(f"Найдено {len(unique_transfers)} уникальных переводов")
        
        # Удаляем все записи
        deleted_count = session.query(Transfer).delete()
        logger.info(f"Удалено {deleted_count} записей")
        
        # Добавляем только уникальные записи обратно
        for transfer_data in unique_transfers:
            transfer = Transfer(
                investor_id=transfer_data[0],
                amount=transfer_data[1],
                currency=transfer_data[2],
                transfer_date=transfer_data[3]
            )
            session.add(transfer)
        
        session.commit()
        logger.info(f"Добавлено {len(unique_transfers)} уникальных записей обратно")
        
    except Exception as e:
        logger.error(f"Ошибка при очистке дубликатов: {e}")
        session.rollback()

if __name__ == "__main__":
    print("Начало очистки дубликатов...")
    clean_duplicate_transfers()
    print("Очистка дубликатов завершена") 