from uuid import UUID

from sqlalchemy.orm import Session

from app.common.repository import BaseRepository
from app.customer.model import Customer


class CustomerRepository(BaseRepository[Customer]):

    def __init__(self):
        super().__init__(Customer)

    def get_by_id_and_workspace(
        self,
        db: Session,
        customer_id: UUID,
        workspace_id: UUID,
    ) -> Customer | None:
        return (
            db.query(Customer)
            .filter(
                Customer.id == customer_id,
                Customer.workspace_id == workspace_id,
            )
            .first()
        )

    def get_by_email_and_workspace(
        self,
        db: Session,
        email: str,
        workspace_id: UUID,
    ) -> Customer | None:
        return (
            db.query(Customer)
            .filter(
                Customer.email == email,
                Customer.workspace_id == workspace_id,
            )
            .first()
        )

    def get_all_by_workspace(
        self,
        db: Session,
        workspace_id: UUID,
    ) -> list[Customer]:
        return (
            db.query(Customer)
            .filter(Customer.workspace_id == workspace_id)
            .order_by(Customer.created_at.desc())
            .all()
        )

    def update(
        self,
        db: Session,
        customer: Customer,
        data: dict,
    ) -> Customer:
        for key, value in data.items():
            if value is not None and hasattr(customer, key):
                setattr(customer, key, value)
        return customer
