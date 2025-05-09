import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from models import Base, Investor, Purchase, Transfer, ServicePurchase, Currency, PeriodUnit
import os
from dotenv import load_dotenv
import logging

# Загрузка переменных окружения
load_dotenv()

# Подключение к базе данных
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

logger = logging.getLogger(__name__)

def convert_amount(amount_str):
    """Конвертирует строку с суммой в число"""
    if isinstance(amount_str, (int, float)):
        return float(amount_str)
    # Удаляем пробелы и заменяем запятую на точку
    amount_str = str(amount_str).replace(' ', '').replace(',', '.')
    return float(amount_str)

def convert_period(period_str):
    """Конвертирует строку с периодом в число"""
    if isinstance(period_str, (int, float)):
        return int(period_str)
    if str(period_str).lower() == 'бессрочно':
        return 999999  # Используем большое число для обозначения бессрочного периода
    return int(period_str)

def load_investor_transfers():
    """Загрузка данных о переводах инвесторов"""
    try:
        df = pd.read_excel('investor_transfers.xlsx')
        # Удаляем строки, где все значения NaN
        df = df.dropna(how='all')
        logger.info(f"Загружено {len(df)} записей о переводах")
        
        for _, row in df.iterrows():
            # Пропускаем строки с пустыми значениями в обязательных полях
            if pd.isna(row['Инвестор']) or pd.isna(row['Сумма']) or \
               pd.isna(row['Валюта']) or pd.isna(row['Дата перевода']):
                logger.warning(f"Пропущена строка с пустыми значениями: {row.to_dict()}")
                continue
                
            # Проверяем существование инвестора
            investor = session.query(Investor).filter_by(full_name=row['Инвестор']).first()
            if not investor:
                investor = Investor(full_name=row['Инвестор'])
                session.add(investor)
                session.commit()
                logger.info(f"Добавлен новый инвестор: {investor.full_name}")
            
            # Проверяем существование перевода
            existing_transfer = session.query(Transfer).filter_by(
                investor_id=investor.id,
                amount=convert_amount(row['Сумма']),
                currency=Currency[row['Валюта']],
                transfer_date=row['Дата перевода']
            ).first()
            
            if not existing_transfer:
                # Создаем запись о переводе только если она не существует
                transfer = Transfer(
                    investor_id=investor.id,
                    amount=convert_amount(row['Сумма']),
                    currency=Currency[row['Валюта']],
                    transfer_date=row['Дата перевода']
                )
                session.add(transfer)
                logger.info(f"Добавлен перевод: {transfer.amount} {transfer.currency} на {transfer.transfer_date}")
            else:
                logger.info(f"Пропущен дубликат перевода: {row['Сумма']} {row['Валюта']} на {row['Дата перевода']}")
        
        session.commit()
        logger.info("Данные о переводах успешно загружены")
    except Exception as e:
        logger.error(f"Ошибка при загрузке переводов: {e}")
        session.rollback()

def load_service_purchases():
    """Загрузка данных о покупках услуг"""
    try:
        df = pd.read_excel('service_payments.xlsx')
        # Удаляем строки, где все значения NaN
        df = df.dropna(how='all')
        logger.info(f"Загружено {len(df)} записей о покупках услуг")
        
        for _, row in df.iterrows():
            # Пропускаем строки с пустыми значениями в обязательных полях
            if pd.isna(row['Название сервиса']) or pd.isna(row['Сумма']) or \
               pd.isna(row['Валюта']) or pd.isna(row['Дата оплаты']) or \
               pd.isna(row['Период оплаты']):
                logger.warning(f"Пропущена строка с пустыми значениями: {row.to_dict()}")
                continue
            
            # Для бессрочных покупок устанавливаем YEAR как единицу периода
            period_unit = row['Единица периода']
            if pd.isna(period_unit) and str(row['Период оплаты']).lower() == 'бессрочно':
                period_unit = 'YEAR'
            elif pd.isna(period_unit):
                logger.warning(f"Пропущена строка с пустым значением единицы периода: {row.to_dict()}")
                continue
                
            purchase = ServicePurchase(
                service_name=row['Название сервиса'],
                amount=convert_amount(row['Сумма']),
                currency=Currency[row['Валюта']],
                purchase_date=row['Дата оплаты'],
                period=convert_period(row['Период оплаты']),
                period_unit=PeriodUnit[period_unit]
            )
            session.add(purchase)
            logger.info(f"Добавлена покупка: {purchase.service_name} на сумму {purchase.amount} {purchase.currency}")
        
        session.commit()
        logger.info("Данные о покупках услуг успешно загружены")
    except Exception as e:
        logger.error(f"Ошибка при загрузке покупок: {e}")
        session.rollback()

if __name__ == "__main__":
    print("Начало загрузки данных...")
    load_investor_transfers()
    load_service_purchases()
    print("Загрузка данных завершена") 