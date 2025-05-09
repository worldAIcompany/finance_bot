from datetime import datetime
from models import Base, ExchangeRate
from database import engine, Session

# Создаем таблицы заново
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

session = Session()

try:
    # Добавляем курсы для прошлых дат
    rates = [
        # Июнь 2024
        ExchangeRate(
            from_currency="INR",
            to_currency="RUB",
            rate=1.0022,
            date=datetime(2024, 6, 13).date()
        ),
        # Август 2024
        ExchangeRate(
            from_currency="RUB",
            to_currency="RUB",
            rate=1.0,
            date=datetime(2024, 8, 13).date()
        ),
        # Декабрь 2024
        ExchangeRate(
            from_currency="INR",
            to_currency="RUB",
            rate=1.0022,
            date=datetime(2024, 12, 4).date()
        )
    ]
    
    session.add_all(rates)
    session.commit()
    print("Курсы валют успешно добавлены")
    
except Exception as e:
    print(f"Ошибка при добавлении курсов валют: {e}")
    session.rollback()
finally:
    session.close() 