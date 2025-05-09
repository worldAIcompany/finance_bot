import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import requests
import logging
import logging.handlers

from models import Base, Investor, Purchase, Transfer, ServicePurchase, Currency, ExchangeRate
from database import engine, Session
from handlers import (
    start_transfer, process_transfer_investor, process_transfer_amount,
    process_transfer_currency, process_transfer_date,
    start_service_purchase, process_service_name, process_service_amount,
    process_service_currency, process_service_date, process_service_period,
    process_service_period_unit, cancel,
    TRANSFER_INVESTOR, TRANSFER_AMOUNT, TRANSFER_CURRENCY, TRANSFER_DATE,
    SERVICE_NAME, SERVICE_AMOUNT, SERVICE_CURRENCY, SERVICE_DATE,
    SERVICE_PERIOD, SERVICE_PERIOD_UNIT
)

# Настройка логирования
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_exchange_rate(from_currency: str, to_currency: str, date: datetime.date = None) -> float:
    """
    Получает курс обмена валют на указанную дату.
    Если курс уже сохранен в базе - возвращает его,
    иначе использует текущий курс из API и сохраняет его.
    """
    if from_currency == to_currency:
        return 1.0
    
    if not date:
        date = datetime.now().date()
    
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

async def calculate_total_purchases(session, target_currency):
    """
    Рассчитывает общую сумму закупок в указанной валюте
    """
    logger.info(f"Начало расчета общей суммы закупок в валюте {target_currency}")
    if isinstance(target_currency, Currency):
        target_currency = target_currency.value
        
    total = 0
    errors = []
    try:
        # Получаем все покупки инвесторов
        purchases = session.query(Purchase).all()
        logger.info(f"Найдено {len(purchases)} покупок инвесторов")
        for purchase in purchases:
            logger.info(f"Обработка покупки: {purchase.amount} {purchase.currency.value}")
            try:
                rate = get_exchange_rate(purchase.currency.value, target_currency, purchase.purchase_date)
                subtotal = purchase.amount * rate
                logger.info(f"Конвертация: {purchase.amount} {purchase.currency.value} = {subtotal} {target_currency}")
                total += subtotal
            except ValueError as e:
                errors.append(f"Ошибка конвертации для покупки {purchase.amount} {purchase.currency.value}: {str(e)}")
        
        # Получаем все покупки сервисов
        service_purchases = session.query(ServicePurchase).all()
        logger.info(f"Найдено {len(service_purchases)} покупок сервисов")
        for purchase in service_purchases:
            logger.info(f"Обработка покупки сервиса: {purchase.amount} {purchase.currency.value}")
            try:
                rate = get_exchange_rate(purchase.currency.value, target_currency, purchase.purchase_date)
                subtotal = purchase.amount * rate
                logger.info(f"Конвертация: {purchase.amount} {purchase.currency.value} = {subtotal} {target_currency}")
                total += subtotal
            except ValueError as e:
                errors.append(f"Ошибка конвертации для сервисной покупки {purchase.amount} {purchase.currency.value}: {str(e)}")
            
        logger.info(f"Итоговая сумма закупок: {total} {target_currency}")
        if errors:
            raise ValueError("\n".join(errors))
        return total
    except Exception as e:
        logger.error(f"Ошибка при расчете общей суммы закупок: {e}")
        raise

async def calculate_total_investments(session, target_currency):
    """
    Рассчитывает общую сумму вложений в указанной валюте
    """
    if isinstance(target_currency, Currency):
        target_currency = target_currency.value
        
    total = 0
    errors = []
    try:
        transfers = session.query(Transfer).all()
        for transfer in transfers:
            try:
                rate = get_exchange_rate(transfer.currency.value, target_currency, transfer.transfer_date)
                subtotal = transfer.amount * rate
                total += subtotal
            except ValueError as e:
                errors.append(f"Ошибка конвертации для перевода {transfer.amount} {transfer.currency.value}: {str(e)}")
        
        if errors:
            raise ValueError("\n".join(errors))
        return total
    except Exception as e:
        logger.error(f"Ошибка при расчете общей суммы вложений: {e}")
        raise

async def calculate_treasury(session, target_currency):
    """
    Рассчитывает остаток казны в указанной валюте
    """
    if isinstance(target_currency, Currency):
        target_currency = target_currency.value
        
    try:
        total_investments = await calculate_total_investments(session, target_currency)
        total_purchases = await calculate_total_purchases(session, target_currency)
        return total_investments - total_purchases
    except Exception as e:
        logger.error(f"Ошибка при расчете остатка казны: {e}")
        raise

# ... rest of the code ... 