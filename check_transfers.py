from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Transfer, Investor
import os
from dotenv import load_dotenv
from datetime import datetime

# Загрузка переменных окружения
load_dotenv()

# Подключение к базе данных
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def check_transfers():
    """Проверка переводов в базе данных"""
    try:
        # Получаем всех инвесторов
        investors = session.query(Investor).all()
        
        for investor in investors:
            try:
                print(f"\nПроверка данных инвестора: {investor.full_name}")
                print("-" * 50)
                
                # Получаем все переводы инвестора
                transfers = session.query(Transfer).filter_by(investor_id=investor.id).order_by(Transfer.transfer_date).all()
                
                if not transfers:
                    print("У инвестора нет переводов в базе данных")
                    continue
                
                print("\nСписок переводов:")
                for transfer in transfers:
                    try:
                        # Проверяем наличие всех необходимых данных
                        if not hasattr(transfer, 'transfer_date') or not hasattr(transfer, 'amount') or not hasattr(transfer, 'currency'):
                            print(f"ОШИБКА: Неполные данные в переводе (ID: {transfer.id})")
                            print(f"Доступные атрибуты: {dir(transfer)}")
                            continue
                            
                        print(f"ID перевода: {transfer.id}")
                        print(f"Дата: {transfer.transfer_date.strftime('%d.%m.%Y') if transfer.transfer_date else 'ОШИБКА: Дата отсутствует'}")
                        print(f"Сумма: {transfer.amount if transfer.amount is not None else 'ОШИБКА: Сумма отсутствует'}")
                        print(f"Валюта: {transfer.currency.name if transfer.currency else 'ОШИБКА: Валюта отсутствует'}")
                        print("-" * 30)
                    except Exception as e:
                        print(f"ОШИБКА при обработке перевода: {str(e)}")
                        print(f"Данные перевода: {vars(transfer)}")
                
                # Подсчет итогов по валютам
                total_by_currency = {}
                for transfer in transfers:
                    try:
                        if transfer.currency and transfer.amount is not None:
                            currency = transfer.currency.name
                            if currency not in total_by_currency:
                                total_by_currency[currency] = 0
                            total_by_currency[currency] += transfer.amount
                    except Exception as e:
                        print(f"ОШИБКА при подсчете итогов: {str(e)}")
                
                print("\nИтого по валютам:")
                for currency, amount in total_by_currency.items():
                    print(f"{currency}: {amount:,.2f}")
                
            except Exception as e:
                print(f"ОШИБКА при обработке инвестора {investor.full_name}: {str(e)}")
            
            print("=" * 50)
            
    except Exception as e:
        print(f"ОШИБКА при выполнении скрипта: {str(e)}")

if __name__ == "__main__":
    print("Проверка данных в базе:")
    check_transfers() 