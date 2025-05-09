from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
from models import Investor, Purchase, Transfer, ServicePurchase, Currency, PeriodUnit
from database import Session

# Состояния для ConversationHandler
PURCHASE_INVESTOR, PURCHASE_SERVICE, PURCHASE_AMOUNT, PURCHASE_CURRENCY, PURCHASE_DATE, PURCHASE_PERIOD, PURCHASE_PERIOD_UNIT = range(7)
TRANSFER_INVESTOR, TRANSFER_AMOUNT, TRANSFER_CURRENCY, TRANSFER_DATE = range(4)
SERVICE_NAME, SERVICE_AMOUNT, SERVICE_CURRENCY, SERVICE_DATE, SERVICE_PERIOD, SERVICE_PERIOD_UNIT = range(6)

# Обработчики для покупок инвесторов
async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    investors = session.query(Investor).all()
    keyboard = [[InlineKeyboardButton(investor.full_name, callback_data=f'investor_{investor.id}')] for investor in investors]
    keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text('Выберите инвестора:', reply_markup=reply_markup)
    session.close()
    return PURCHASE_INVESTOR

async def process_purchase_investor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == 'cancel':
        await query.message.reply_text('Операция отменена')
        return ConversationHandler.END
    investor_id = int(query.data.split('_')[1])
    context.user_data['purchase_investor_id'] = investor_id
    await query.message.reply_text('Введите название сервиса/курса/нейросети:')
    return PURCHASE_SERVICE

async def process_purchase_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['purchase_service'] = update.message.text
    await update.message.reply_text('Введите сумму:')
    return PURCHASE_AMOUNT

async def process_purchase_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        context.user_data['purchase_amount'] = amount
        keyboard = [[InlineKeyboardButton(currency.value, callback_data=f'currency_{currency.value}')] for currency in Currency]
        keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выберите валюту:', reply_markup=reply_markup)
        return PURCHASE_CURRENCY
    except ValueError:
        await update.message.reply_text('Пожалуйста, введите корректную сумму')
        return PURCHASE_AMOUNT

async def process_purchase_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == 'cancel':
        await query.message.reply_text('Операция отменена')
        return ConversationHandler.END
    currency = query.data.split('_')[1]
    context.user_data['purchase_currency'] = currency
    await query.message.reply_text('Введите дату покупки (YYYY-MM-DD):')
    return PURCHASE_DATE

async def process_purchase_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date = datetime.strptime(update.message.text, '%Y-%m-%d').date()
        context.user_data['purchase_date'] = date
        await update.message.reply_text('Введите срок (число):')
        return PURCHASE_PERIOD
    except ValueError:
        await update.message.reply_text('Пожалуйста, введите дату в формате YYYY-MM-DD')
        return PURCHASE_DATE

async def process_purchase_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        period = int(update.message.text)
        context.user_data['purchase_period'] = period
        keyboard = [[InlineKeyboardButton(unit.value, callback_data=f'unit_{unit.value}')] for unit in PeriodUnit]
        keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выберите единицу измерения срока:', reply_markup=reply_markup)
        return PURCHASE_PERIOD_UNIT
    except ValueError:
        await update.message.reply_text('Пожалуйста, введите корректное число')
        return PURCHASE_PERIOD

async def process_purchase_period_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == 'cancel':
        await query.message.reply_text('Операция отменена')
        return ConversationHandler.END
    
    session = Session()
    try:
        purchase = Purchase(
            investor_id=context.user_data['purchase_investor_id'],
            service_name=context.user_data['purchase_service'],
            amount=context.user_data['purchase_amount'],
            currency=context.user_data['purchase_currency'],
            purchase_date=context.user_data['purchase_date'],
            period=context.user_data['purchase_period'],
            period_unit=query.data.split('_')[1]
        )
        session.add(purchase)
        session.commit()
        await query.message.reply_text('Покупка успешно добавлена!')
    except Exception as e:
        await query.message.reply_text(f'Произошла ошибка: {str(e)}')
    finally:
        session.close()
        context.user_data.clear()
    return ConversationHandler.END

# Обработчики для переводов
async def start_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    investors = session.query(Investor).all()
    keyboard = [[InlineKeyboardButton(investor.full_name, callback_data=f'investor_{investor.id}')] for investor in investors]
    keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text('Выберите инвестора:', reply_markup=reply_markup)
    session.close()
    return TRANSFER_INVESTOR

async def process_transfer_investor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == 'cancel':
        await query.message.reply_text('Операция отменена')
        return ConversationHandler.END
    investor_id = int(query.data.split('_')[1])
    context.user_data['transfer_investor_id'] = investor_id
    await query.message.reply_text('Введите сумму перевода:')
    return TRANSFER_AMOUNT

async def process_transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        context.user_data['transfer_amount'] = amount
        keyboard = [[InlineKeyboardButton(currency.value, callback_data=f'currency_{currency.value}')] for currency in Currency]
        keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выберите валюту:', reply_markup=reply_markup)
        return TRANSFER_CURRENCY
    except ValueError:
        await update.message.reply_text('Пожалуйста, введите корректную сумму')
        return TRANSFER_AMOUNT

async def process_transfer_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == 'cancel':
        await query.message.reply_text('Операция отменена')
        return ConversationHandler.END
    currency = query.data.split('_')[1]
    context.user_data['transfer_currency'] = currency
    await query.message.reply_text('Введите дату перевода (YYYY-MM-DD):')
    return TRANSFER_DATE

async def process_transfer_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date = datetime.strptime(update.message.text, '%Y-%m-%d').date()
        session = Session()
        try:
            transfer = Transfer(
                investor_id=context.user_data['transfer_investor_id'],
                amount=context.user_data['transfer_amount'],
                currency=context.user_data['transfer_currency'],
                transfer_date=date
            )
            session.add(transfer)
            session.commit()
            await update.message.reply_text('Перевод успешно добавлен!')
        except Exception as e:
            await update.message.reply_text(f'Произошла ошибка: {str(e)}')
        finally:
            session.close()
            context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text('Пожалуйста, введите дату в формате YYYY-MM-DD')
        return TRANSFER_DATE

# Обработчики для покупок сервисов
async def start_service_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text('Введите название сервиса/курса/нейросети:')
    return SERVICE_NAME

async def process_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['service_name'] = update.message.text
    await update.message.reply_text('Введите сумму:')
    return SERVICE_AMOUNT

async def process_service_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        context.user_data['service_amount'] = amount
        keyboard = [[InlineKeyboardButton(currency.value, callback_data=f'currency_{currency.value}')] for currency in Currency]
        keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выберите валюту:', reply_markup=reply_markup)
        return SERVICE_CURRENCY
    except ValueError:
        await update.message.reply_text('Пожалуйста, введите корректную сумму')
        return SERVICE_AMOUNT

async def process_service_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == 'cancel':
        await query.message.reply_text('Операция отменена')
        return ConversationHandler.END
    currency = query.data.split('_')[1]
    context.user_data['service_currency'] = currency
    await query.message.reply_text('Введите дату покупки (YYYY-MM-DD):')
    return SERVICE_DATE

async def process_service_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date = datetime.strptime(update.message.text, '%Y-%m-%d').date()
        context.user_data['service_date'] = date
        await update.message.reply_text('Введите срок (число):')
        return SERVICE_PERIOD
    except ValueError:
        await update.message.reply_text('Пожалуйста, введите дату в формате YYYY-MM-DD')
        return SERVICE_DATE

async def process_service_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        period = int(update.message.text)
        context.user_data['service_period'] = period
        keyboard = [[InlineKeyboardButton(unit.name, callback_data=f'unit_{unit.value}')] for unit in PeriodUnit]
        keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выберите единицу измерения срока:', reply_markup=reply_markup)
        return SERVICE_PERIOD_UNIT
    except ValueError:
        await update.message.reply_text('Пожалуйста, введите корректное число')
        return SERVICE_PERIOD

async def process_service_period_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == 'cancel':
        await query.message.reply_text('Операция отменена')
        return ConversationHandler.END
    
    session = Session()
    try:
        period_unit_value = query.data.split('_')[1]
        period_unit = PeriodUnit(period_unit_value)  # Преобразуем строку в enum
        
        service_purchase = ServicePurchase(
            service_name=context.user_data['service_name'],
            amount=context.user_data['service_amount'],
            currency=context.user_data['service_currency'],
            purchase_date=context.user_data['service_date'],
            period=context.user_data['service_period'],
            period_unit=period_unit
        )
        session.add(service_purchase)
        session.commit()
        await query.message.reply_text('Покупка сервиса успешно добавлена!')
    except Exception as e:
        await query.message.reply_text(f'Произошла ошибка: {str(e)}')
    finally:
        session.close()
        context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Операция отменена')
    context.user_data.clear()
    return ConversationHandler.END 