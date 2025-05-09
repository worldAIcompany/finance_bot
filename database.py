import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка базы данных
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/finance_bot')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine) 