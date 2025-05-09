from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, Enum, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

Base = declarative_base()

class Currency(enum.Enum):
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"
    UAH = "UAH"
    INR = "INR"
    TRY = "TRY"

class PeriodUnit(enum.Enum):
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"

class Investor(Base):
    __tablename__ = 'investors'
    
    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    purchases = relationship("Purchase", back_populates="investor")
    transfers = relationship("Transfer", back_populates="investor")

class Purchase(Base):
    __tablename__ = 'purchases'
    
    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey('investors.id'))
    service_name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(Enum(Currency), nullable=False)
    purchase_date = Column(Date, nullable=False)
    period = Column(Integer, nullable=False)
    period_unit = Column(Enum(PeriodUnit), nullable=False)
    
    investor = relationship("Investor", back_populates="purchases")

class Transfer(Base):
    __tablename__ = 'transfers'
    
    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey('investors.id'))
    amount = Column(Float, nullable=False)
    currency = Column(Enum(Currency), nullable=False)
    transfer_date = Column(Date, nullable=False)
    
    investor = relationship("Investor", back_populates="transfers")

class ServicePurchase(Base):
    __tablename__ = 'service_purchases'
    
    id = Column(Integer, primary_key=True)
    service_name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(Enum(Currency), nullable=False)
    purchase_date = Column(Date, nullable=False)
    period = Column(Integer, nullable=False)
    period_unit = Column(Enum(PeriodUnit), nullable=False)

class ExchangeRate(Base):
    """Модель для хранения курсов валют"""
    __tablename__ = 'exchange_rates'
    
    id = Column(Integer, primary_key=True)
    from_currency = Column(String, nullable=False)
    to_currency = Column(String, nullable=False)
    rate = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.now) 