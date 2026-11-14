"""Create a demo workspace + owner login (idempotent). Run from backend/: python -m scripts.create_demo_user"""
import app.database.models  # noqa: F401
from app.auth.commands.register import RegisterCommand
from app.auth.repositories.user_repository import UserRepository
from app.auth.schema import RegisterRequest
from app.database.database import SessionLocal

EMAIL = "demo@cortexcx.com"
PASSWORD = "Demo@12345"

db = SessionLocal()
try:
    if UserRepository().get_by_email(db=db, email=EMAIL):
        print("Demo user already exists")
    else:
        RegisterCommand.execute(
            db,
            RegisterRequest(
                company_name="Demo Company",
                company_slug="demo",
                full_name="Demo Owner",
                email=EMAIL,
                password=PASSWORD,
            ),
        )
        print("Created demo user")
    print(f"Email: {EMAIL}\nPassword: {PASSWORD}")
finally:
    db.close()
