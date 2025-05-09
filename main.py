import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import requests
import logging
import logging.handlers
import pandas as pd

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

# Основной файл логов
file_handler = logging.handlers.RotatingFileHandler(
    'bot_logs.log', 
    maxBytes=10485760,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_formatter)

# Отдельный файл для логов API курсов валют
currency_handler = logging.handlers.RotatingFileHandler(
    'currency_api_logs.log', 
    maxBytes=10485760,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
currency_handler.setLevel(logging.INFO)
currency_handler.setFormatter(log_formatter)

# Фильтр для выделения логов API курсов валют
class CurrencyFilter(logging.Filter):
    def filter(self, record):
        return 'курс' in record.getMessage().lower() or 'валют' in record.getMessage().lower()

currency_handler.addFilter(CurrencyFilter())

# Консольный обработчик
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# Настройка корневого логгера
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler],
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Добавление обработчика для логов валют
logger = logging.getLogger(__name__)
logger.addHandler(currency_handler)

# Загрузка переменных окружения
load_dotenv()

# Создание таблиц
Base.metadata.create_all(engine)

# Добавляем новое состояние в начало файла, после других состояний
ADD_INVESTOR_NAME = 'add_investor_name'
REMOVE_INVESTOR_SELECT = 'remove_investor_select'
INVESTOR_INVESTMENTS_SELECT = 'investor_investments_select'  # Новое состояние
ADD_RATE_DATE = 'add_rate_date'
ADD_RATE_FROM_CURRENCY = 'add_rate_from_currency'
ADD_RATE_TO_CURRENCY = 'add_rate_to_currency'
ADD_RATE_VALUE = 'add_rate_value'

def get_exchange_rate(from_currency: str, to_currency: str, date: datetime.date = None) -> float:
    """
    Получает курс обмена валют на указанную дату из базы данных.
    """
    # Если обе валюты одинаковые
    if from_currency == to_currency:
        return 1.0
    
    # Проверяем, что дата указана
    if not date:
        logger.warning("Дата не указана для получения курса валют, используется текущая дата")
        date = datetime.now().date()
    
    session = Session()
    try:
        # Ищем курс в базе данных
        rate = session.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.date == date
        ).first()
        
        if rate:
            logger.info(f"Найден курс на {date}: 1 {from_currency} = {rate.rate} {to_currency}")
            return rate.rate
        else:
            error_msg = f"Не найден курс для конвертации {from_currency} в {to_currency} на дату {date.strftime('%d.%m.%Y')}. Пожалуйста, добавьте курс вручную через меню 'Добавить курс'"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    finally:
        session.close()

def calculate_total_purchases():
    """Расчет общей суммы закупок"""
    try:
        session = Session()
        purchases = session.query(ServicePurchase).all()
        if not purchases:
            return 0.0, "RUB"
        
        total_rub = 0.0
        for purchase in purchases:
            amount = float(purchase.amount)
            if purchase.currency != 'RUB':
                try:
                    rate = get_exchange_rate(purchase.currency, 'RUB', purchase.date)
                    amount *= rate
                except ValueError as e:
                    logger.error(f"Ошибка при конвертации валюты для закупки {purchase.id}: {e}")
                    # Пропускаем эту закупку, если не можем получить курс
                    continue
            
            total_rub += amount
            
        return round(total_rub, 2), "RUB"
    except Exception as e:
        logger.error(f"Ошибка при расчете общей суммы закупок: {e}")
        return 0.0, "RUB"
    finally:
        session.close()

def calculate_total_investments():
    try:
        df = read_investor_transfers()
        if df.empty:
            logger.error("Не удалось прочитать данные о переводах")
            return 0.0, "RUB"
        
        total_rub = 0.0
        for _, row in df.iterrows():
            amount = float(row['Сумма'])
            currency = row['Валюта']
            date = row['Дата перевода'].strftime('%Y-%m-%d')
            
            if currency != 'RUB':
                rate = get_exchange_rate(currency, 'RUB', date)
                amount *= rate
            
            total_rub += amount
            
        return round(total_rub, 2), "RUB"
    except Exception as e:
        logger.error(f"Ошибка при расчете общей суммы инвестиций: {e}")
        return 0.0, "RUB"

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
    
    except Exception as e:
        logger.error(f"Ошибка при расчете общей суммы закупок: {e}")
        raise
    finally:
        session.close()

    return total

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
        logger.info(f"Найдено {len(transfers)} переводов")
        
        for transfer in transfers:
            logger.info(f"Обработка перевода: {transfer.amount} {transfer.currency.value}")
            try:
                rate = get_exchange_rate(transfer.currency.value, target_currency, transfer.transfer_date)
                subtotal = transfer.amount * rate
                logger.info(f"Конвертация: {transfer.amount} {transfer.currency.value} = {subtotal} {target_currency}")
                total += subtotal
            except ValueError as e:
                errors.append(f"Ошибка конвертации для перевода {transfer.amount} {transfer.currency.value}: {str(e)}")
        
        logger.info(f"Итоговая сумма вложений: {total} {target_currency}")
        
        if errors:
            raise ValueError("\n".join(errors))
            
    except Exception as e:
        logger.error(f"Ошибка при расчете общей суммы вложений: {e}")
        raise
    finally:
        session.close()

    return total

async def calculate_investor_investments(session, investor_id, target_currency):
    """
    Рассчитывает сумму вложений конкретного инвестора в указанной валюте
    """
    if isinstance(target_currency, Currency):
        target_currency = target_currency.value
        
    total = 0
    errors = []
    
    try:
        transfers = session.query(Transfer).filter(Transfer.investor_id == investor_id).all()
        logger.info(f"Найдено {len(transfers)} переводов для инвестора {investor_id}")
        
        for transfer in transfers:
            logger.info(f"Обработка перевода: {transfer.amount} {transfer.currency.value}")
            try:
                rate = get_exchange_rate(transfer.currency.value, target_currency, transfer.transfer_date)
                subtotal = transfer.amount * rate
                logger.info(f"Конвертация: {transfer.amount} {transfer.currency.value} = {subtotal} {target_currency}")
                total += subtotal
            except ValueError as e:
                errors.append(f"Ошибка конвертации для перевода {transfer.amount} {transfer.currency.value}: {str(e)}")
        
        logger.info(f"Итоговая сумма вложений инвестора: {total} {target_currency}")
        
        if errors:
            raise ValueError("\n".join(errors))
            
    except Exception as e:
        logger.error(f"Ошибка при расчете суммы вложений инвестора: {e}")
        raise
    finally:
        session.close()

    return total

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало работы с ботом"""
    keyboard = [
        [InlineKeyboardButton("Посмотреть общую сумму закупок", callback_data='total_purchases')],
        [InlineKeyboardButton("Посмотреть общую сумму вложений", callback_data='total_investments')],
        [InlineKeyboardButton("Посмотреть баланс казны", callback_data='treasury_balance')],
        [InlineKeyboardButton("Добавить перевод", callback_data='add_transfer')],
        [InlineKeyboardButton("Добавить покупку сервиса", callback_data='add_service_purchase')],
        [InlineKeyboardButton("Добавить инвестора", callback_data='add_investor')],
        [InlineKeyboardButton("Удалить инвестора", callback_data='remove_investor')],
        [InlineKeyboardButton("Добавить курс валют", callback_data='add_rate')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'Выберите действие:',
        reply_markup=reply_markup
    )

async def start_add_investor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления инвестора"""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text('Пожалуйста, введите имя нового инвестора:')
    return ADD_INVESTOR_NAME

async def process_add_investor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода имени нового инвестора"""
    investor_name = update.message.text.strip()
    session = Session()
    try:
        # Проверяем, существует ли уже такой инвестор
        existing_investor = session.query(Investor).filter(Investor.full_name == investor_name).first()
        if existing_investor:
            await update.message.reply_text(f'Инвестор с именем "{investor_name}" уже существует.')
        else:
            # Создаем нового инвестора
            new_investor = Investor(full_name=investor_name)
            session.add(new_investor)
            session.commit()
            await update.message.reply_text(f'Инвестор "{investor_name}" успешно добавлен!')
        
        # Возвращаемся в главное меню
        keyboard = [[InlineKeyboardButton("Вернуться в главное меню", callback_data='start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выберите действие:', reply_markup=reply_markup)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка при добавлении инвестора: {e}")
        await update.message.reply_text(f'Произошла ошибка при добавлении инвестора: {str(e)}')
        return ConversationHandler.END
    finally:
        session.close()

async def start_remove_investor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса удаления инвестора"""
    query = update.callback_query
    await query.answer()
    
    session = Session()
    try:
        investors = session.query(Investor).all()
        if not investors:
            await query.message.reply_text('Нет доступных инвесторов для удаления.')
            return ConversationHandler.END
        
        keyboard = []
        for investor in investors:
            keyboard.append([InlineKeyboardButton(investor.full_name, callback_data=f'remove_{investor.id}')])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text('Выберите инвестора для удаления:', reply_markup=reply_markup)
        return REMOVE_INVESTOR_SELECT
    except Exception as e:
        logger.error(f"Ошибка при получении списка инвесторов: {e}")
        await query.message.reply_text(f'Произошла ошибка: {str(e)}')
        return ConversationHandler.END
    finally:
        session.close()

async def process_remove_investor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора инвестора для удаления"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancel':
        await query.message.reply_text('Операция отменена.')
        return ConversationHandler.END
    
    investor_id = int(query.data.split('_')[1])
    session = Session()
    try:
        investor = session.query(Investor).filter(Investor.id == investor_id).first()
        if investor:
            investor_name = investor.full_name
            session.delete(investor)
            session.commit()
            await query.message.reply_text(f'Инвестор "{investor_name}" успешно удален!')
        else:
            await query.message.reply_text('Инвестор не найден.')
        
        # Возвращаемся в главное меню
        keyboard = [[InlineKeyboardButton("Вернуться в главное меню", callback_data='start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text('Выберите действие:', reply_markup=reply_markup)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка при удалении инвестора: {e}")
        await query.message.reply_text(f'Произошла ошибка при удалении инвестора: {str(e)}')
        return ConversationHandler.END
    finally:
        session.close()

async def get_investor_transfers_details(session, investor_id, target_currency):
    """
    Получает детальную информацию о переводах инвестора
    """
    if isinstance(target_currency, Currency):
        target_currency = target_currency.value
    
    try:
        investor = session.query(Investor).filter(Investor.id == investor_id).first()
        if not investor:
            return None, "Инвестор не найден", 0
        
        transfers = session.query(Transfer).filter(Transfer.investor_id == investor_id).order_by(Transfer.transfer_date).all()
        if not transfers:
            return investor.full_name, [], 0  # Возвращаем три значения, включая total = 0
        
        details = []
        total = 0
        
        for transfer in transfers:
            rate = get_exchange_rate(transfer.currency.value, target_currency, transfer.transfer_date)
            amount_in_target = transfer.amount * rate
            total += amount_in_target
            
            details.append({
                "date": transfer.transfer_date.strftime("%d.%m.%Y"),
                "amount": transfer.amount,
                "currency": transfer.currency.value,
                "amount_in_target": amount_in_target,
                "rate": rate
            })
            
        return investor.full_name, details, total
    except Exception as e:
        logger.error(f"Ошибка при получении деталей вложений инвестора: {e}")
        return None, f"Ошибка: {str(e)}", 0

async def add_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления курса валют"""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "Введите дату для курса валют в формате ДД.ММ.ГГГГ:"
    )
    return ADD_RATE_DATE

async def process_rate_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенной даты"""
    try:
        date_str = update.message.text
        date = datetime.strptime(date_str, '%d.%m.%Y').date()
        context.user_data['rate_date'] = date
        
        # Создаем клавиатуру с доступными валютами
        keyboard = [
            [InlineKeyboardButton("UAH", callback_data="UAH"),
             InlineKeyboardButton("RUB", callback_data="RUB"),
             InlineKeyboardButton("USD", callback_data="USD")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Выберите исходную валюту:",
            reply_markup=reply_markup
        )
        return ADD_RATE_FROM_CURRENCY
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ:"
        )
        return ADD_RATE_DATE

async def process_rate_from_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора исходной валюты"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['from_currency'] = query.data
    
    # Создаем клавиатуру с оставшимися валютами
    keyboard = [
        [InlineKeyboardButton("UAH", callback_data="UAH"),
         InlineKeyboardButton("RUB", callback_data="RUB"),
         InlineKeyboardButton("USD", callback_data="USD")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=f"Выбрана исходная валюта: {query.data}\nВыберите целевую валюту:",
        reply_markup=reply_markup
    )
    return ADD_RATE_TO_CURRENCY

async def process_rate_to_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора целевой валюты"""
    query = update.callback_query
    await query.answer()
    
    if query.data == context.user_data['from_currency']:
        await query.edit_message_text(
            "Нельзя выбрать одинаковые валюты. Выберите другую целевую валюту:",
            reply_markup=query.message.reply_markup
        )
        return ADD_RATE_TO_CURRENCY
    
    context.user_data['to_currency'] = query.data
    await query.edit_message_text(
        f"Выбраны валюты: {context.user_data['from_currency']} → {query.data}\n"
        f"Введите курс обмена (например, 2.0379):"
    )
    return ADD_RATE_VALUE

async def process_rate_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного значения курса"""
    try:
        rate = float(update.message.text.replace(',', '.'))
        if rate <= 0:
            raise ValueError("Курс должен быть положительным числом")
        
        session = Session()
        try:
            # Проверяем, существует ли уже курс на эту дату
            existing_rate = session.query(ExchangeRate).filter(
                ExchangeRate.from_currency == context.user_data['from_currency'],
                ExchangeRate.to_currency == context.user_data['to_currency'],
                ExchangeRate.date == context.user_data['rate_date']
            ).first()
            
            if existing_rate:
                existing_rate.rate = rate
                action = "обновлен"
            else:
                new_rate = ExchangeRate(
                    from_currency=context.user_data['from_currency'],
                    to_currency=context.user_data['to_currency'],
                    rate=rate,
                    date=context.user_data['rate_date']
                )
                session.add(new_rate)
                action = "добавлен"
            
            session.commit()
            
            # Добавляем обратный курс
            inverse_rate = 1 / rate
            existing_inverse = session.query(ExchangeRate).filter(
                ExchangeRate.from_currency == context.user_data['to_currency'],
                ExchangeRate.to_currency == context.user_data['from_currency'],
                ExchangeRate.date == context.user_data['rate_date']
            ).first()
            
            if existing_inverse:
                existing_inverse.rate = inverse_rate
            else:
                inverse_rate_obj = ExchangeRate(
                    from_currency=context.user_data['to_currency'],
                    to_currency=context.user_data['from_currency'],
                    rate=inverse_rate,
                    date=context.user_data['rate_date']
                )
                session.add(inverse_rate_obj)
            
            session.commit()
            
            await update.message.reply_text(
                f"Курс успешно {action}!\n"
                f"Дата: {context.user_data['rate_date'].strftime('%d.%m.%Y')}\n"
                f"Курс: 1 {context.user_data['from_currency']} = {rate} {context.user_data['to_currency']}\n"
                f"Обратный курс: 1 {context.user_data['to_currency']} = {inverse_rate:.4f} {context.user_data['from_currency']}"
            )
            
        finally:
            session.close()
        
        return ConversationHandler.END
        
    except ValueError as e:
        await update.message.reply_text(
            "Неверный формат курса. Пожалуйста, введите положительное число:"
        )
        return ADD_RATE_VALUE

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    if query.data == 'add_rate':
        return await add_rate(update, context)
    elif query.data == 'total_purchases':
        session = Session()
        target_currency = Currency.RUB.value
        try:
            progress_message = await query.message.reply_text('🔄 Идет подсчет общей суммы закупок...')
            try:
                total = await calculate_total_purchases(session, target_currency)
                await progress_message.delete()
                await query.message.edit_text(f"Общая сумма закупок: {total:.2f} {target_currency}")
            except ValueError as e:
                await progress_message.delete()
                await query.message.edit_text(f'❌ Ошибка при расчете общей суммы закупок:\n{str(e)}')
        finally:
            session.close()
    elif query.data == 'add_transfer':
        return await start_transfer(update, context)
    elif query.data == 'add_service_purchase':
        return await start_service_purchase(update, context)
    elif query.data == 'start':
        await start(update, context)
        return ConversationHandler.END
    elif query.data == 'investor_investments':
        session = Session()
        try:
            investors = session.query(Investor).all()
            if not investors:
                await query.message.reply_text('Нет доступных инвесторов.')
                return ConversationHandler.END
            
            keyboard = []
            for investor in investors:
                keyboard.append([InlineKeyboardButton(investor.full_name, callback_data=f'inv_calc_{investor.id}')])
            keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text('Выберите инвестора для подсчета вложений:', reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при получении списка инвесторов: {e}")
            await query.message.reply_text(f'Произошла ошибка: {str(e)}')
        finally:
            session.close()
        return INVESTOR_INVESTMENTS_SELECT
    elif query.data.startswith('inv_calc_'):
        investor_id = int(query.data.split('_')[2])
        session = Session()
        target_currency = Currency.RUB.value
        try:
            progress_message = await query.message.reply_text('🔄 Идет подсчет вложений инвестора...')
            
            investor_name, transfers_details, total = await get_investor_transfers_details(session, investor_id, target_currency)
            
            if investor_name is None:
                await progress_message.delete()
                await query.message.reply_text(transfers_details)  # Это сообщение об ошибке
                return ConversationHandler.END
                
            if not transfers_details:
                await progress_message.delete()
                await query.message.reply_text(f'Инвестор {investor_name} не делал вложений.')
                return ConversationHandler.END
                
            # Формируем подробный ответ
            response = f"📊 *Вложения инвестора {investor_name}*\n\n"
            
            for i, transfer in enumerate(transfers_details, 1):
                response += f"{i}. Дата: {transfer['date']}\n"
                response += f"   Сумма: {transfer['amount']:.2f} {transfer['currency']}\n"
                response += f"   Курс: 1 {transfer['currency']} = {transfer['rate']:.4f} {target_currency}\n"
                response += f"   В {target_currency}: {transfer['amount_in_target']:.2f}\n\n"
                
            response += f"*Общая сумма вложений: {total:.2f} {target_currency}*"
            
            await progress_message.delete()
            await query.message.reply_text(response, parse_mode='Markdown')
            
            # Возвращаемся в главное меню
            keyboard = [[InlineKeyboardButton("Вернуться в главное меню", callback_data='start')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text('Выберите действие:', reply_markup=reply_markup)
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Ошибка при подсчете вложений инвестора: {e}")
            await query.message.reply_text(f'Произошла ошибка при подсчете вложений: {str(e)}')
            return ConversationHandler.END
        finally:
            session.close()
    elif query.data == 'cancel':
        await query.message.reply_text('Операция отменена.')
        return ConversationHandler.END
    
    # Восстанавливаем обработку общих кнопок
    session = Session()
    target_currency = Currency.RUB.value
    logger.info(f"Обработка кнопки: {query.data}")
    
    try:
        if query.data == 'total_investments':
            progress_message = await query.message.reply_text('🔄 Идет подсчет общей суммы вложений...')
            try:
                total = await calculate_total_investments(session, target_currency)
                await progress_message.delete()
                await query.message.reply_text(f'Общая сумма вложений: {total:.2f} {target_currency}')
            except ValueError as e:
                await progress_message.delete()
                await query.message.reply_text(f'❌ Ошибка при расчете общей суммы вложений:\n{str(e)}')
            
        elif query.data == 'treasury_balance':
            progress_message = await query.message.reply_text('🔄 Идет подсчет остатка казны...')
            try:
                total = await calculate_treasury(session, target_currency)
                await progress_message.delete()
                await query.message.reply_text(f'Остаток казны: {total:.2f} {target_currency}')
            except ValueError as e:
                await progress_message.delete()
                await query.message.reply_text(f'❌ Ошибка при расчете остатка казны:\n{str(e)}')
    
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки: {e}")
        await query.message.reply_text(f'❌ Произошла ошибка при обработке запроса: {str(e)}')
    finally:
        session.close()
    return

def read_investor_transfers():
    try:
        df = pd.read_excel('investor_transfers.xlsx')
        df['Сумма'] = pd.to_numeric(df['Сумма'].str.replace(' ', ''), errors='coerce')
        df['Дата перевода'] = pd.to_datetime(df['Дата перевода'], format='%Y-%m-%d')
        return df
    except Exception as e:
        logger.error(f"Ошибка при чтении файла investor_transfers.xlsx: {e}")
        return pd.DataFrame()

def read_service_payments():
    try:
        df = pd.read_excel('service_payments.xlsx')
        df['Сумма'] = pd.to_numeric(df['Сумма'].str.replace(' ', ''), errors='coerce')
        df['Дата оплаты'] = pd.to_datetime(df['Дата оплаты'], format='%Y-%m-%d')
        return df
    except Exception as e:
        logger.error(f"Ошибка при чтении файла service_payments.xlsx: {e}")
        return pd.DataFrame()

def main():
    try:
        application = (
            Application.builder()
            .token(os.getenv('TELEGRAM_TOKEN'))
            .connect_timeout(30.0)
            .read_timeout(30.0)
            .write_timeout(30.0)
            .build()
        )
        
        # Обработчик для просмотра вложений инвестора
        investor_investments_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(button_handler, pattern='^investor_investments$')],
            states={
                INVESTOR_INVESTMENTS_SELECT: [
                    CallbackQueryHandler(button_handler, pattern='^inv_calc_\d+$'),
                    CallbackQueryHandler(button_handler, pattern='^cancel$')
                ]
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            per_message=False
        )
        
        # Обработчик для добавления инвестора
        add_investor_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(start_add_investor, pattern='^add_investor$')],
            states={
                ADD_INVESTOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_investor)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        # Обработчик для удаления инвестора
        remove_investor_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(start_remove_investor, pattern='^remove_investor$')],
            states={
                REMOVE_INVESTOR_SELECT: [CallbackQueryHandler(process_remove_investor)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        # Обработчик для добавления перевода
        transfer_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(start_transfer, pattern='^add_transfer$')],
            states={
                TRANSFER_INVESTOR: [CallbackQueryHandler(process_transfer_investor)],
                TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_transfer_amount)],
                TRANSFER_CURRENCY: [CallbackQueryHandler(process_transfer_currency)],
                TRANSFER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_transfer_date)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        # Обработчик для добавления покупки сервиса
        service_purchase_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(start_service_purchase, pattern='^add_service_purchase$')],
            states={
                SERVICE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_service_name)],
                SERVICE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_service_amount)],
                SERVICE_CURRENCY: [CallbackQueryHandler(process_service_currency)],
                SERVICE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_service_date)],
                SERVICE_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_service_period)],
                SERVICE_PERIOD_UNIT: [CallbackQueryHandler(process_service_period_unit)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        # Обработчик для добавления курса валют
        rate_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(add_rate, pattern='^add_rate$')],
            states={
                ADD_RATE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_rate_date)],
                ADD_RATE_FROM_CURRENCY: [CallbackQueryHandler(process_rate_from_currency)],
                ADD_RATE_TO_CURRENCY: [CallbackQueryHandler(process_rate_to_currency)],
                ADD_RATE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_rate_value)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(investor_investments_handler)
        application.add_handler(add_investor_handler)
        application.add_handler(remove_investor_handler)
        application.add_handler(transfer_conv_handler)
        application.add_handler(service_purchase_conv_handler)
        application.add_handler(rate_conv_handler)
        application.add_handler(CallbackQueryHandler(button_handler))
        
        logger.info("Бот запущен")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

if __name__ == '__main__':
    main() 