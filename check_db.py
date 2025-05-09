from models import Base, Investor, Purchase, Transfer, ServicePurchase, Currency, ExchangeRate
from database import Session

def check_database():
    session = Session()
    try:
        print("\nИнвесторы:")
        investors = session.query(Investor).all()
        for i in investors:
            print(f"{i.id}: {i.full_name}")

        print("\nПереводы:")
        transfers = session.query(Transfer).all()
        for t in transfers:
            print(f"От {t.investor.full_name}: {t.amount} {t.currency.value} ({t.transfer_date})")

        print("\nПокупки:")
        purchases = session.query(Purchase).all()
        for p in purchases:
            print(f"{p.amount} {p.currency.value} ({p.purchase_date})")

        print("\nСервисные покупки:")
        service_purchases = session.query(ServicePurchase).all()
        for sp in service_purchases:
            print(f"{sp.service_name}: {sp.amount} {sp.currency.value} ({sp.purchase_date})")

    except Exception as e:
        print(f"Ошибка при проверке базы данных: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_database() 