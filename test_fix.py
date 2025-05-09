import os
import requests
import datetime
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import ExchangeRate

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание сессии базы данных
engine = create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)

def get_exchange_rate(from_currency: str, to_currency: str, date: datetime.date = None) -> float:
    """
    Получает курс обмена валют на указанную дату.
    Если курс уже сохранен в базе - возвращает его,
    иначе использует текущий курс из API и сохраняет его.
    """
    if from_currency == to_currency:
        return 1.0
    
    if not date:
        date = datetime.datetime.now().date()
    
    session = Session()
    try:
        # Проверяем, есть ли сохраненный курс для этой даты
        saved_rate = session.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.date == date
        ).first()
        
        if saved_rate:
            logger.info(f"Найден сохраненный курс на {date}: 1 {from_currency} = {saved_rate.rate} {to_currency}")
            return saved_rate.rate
        
        # Если курса нет - получаем текущий и сохраняем его
        api_key = os.getenv('EXCHANGE_RATE_API_KEY')
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_currency}/{to_currency}"
        logger.info(f"Запрос текущего курса для сохранения на дату {date}")
        
        response = requests.get(url)
        if response.status_code != 200:
            error_msg = f"Ошибка API: статус код {response.status_code}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        data = response.json()
        if 'result' not in data or data.get('result') == 'error':
            error_msg = f"Ошибка получения курса валют: {data.get('error', 'Неизвестная ошибка')}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        rate = data.get('conversion_rate')
        if not rate:
            error_msg = "Не удалось получить курс валют из ответа API"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Сохраняем полученный курс
        new_rate = ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
            date=date
        )
        session.add(new_rate)
        session.commit()
        
        logger.info(f"Сохранен новый курс на {date}: 1 {from_currency} = {rate} {to_currency}")
        return rate
    
    except Exception as e:
        logger.error(f"Критическая ошибка при получении курса валют: {e}")
        raise ValueError(f"Не удалось получить курс валют: {str(e)}")
    finally:
        session.close()

# Тестирование функции
if __name__ == "__main__":
    try:
        rate = get_exchange_rate("UAH", "RUB")
        print(f"Текущий курс: 1 UAH = {rate} RUB")
    except Exception as e:
        print(f"Ошибка: {e}") 