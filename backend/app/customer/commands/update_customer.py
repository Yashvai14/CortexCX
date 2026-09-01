from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.customer.repositories.customer_repository import CustomerRepository
from app.customer.schema import (
    CustomerResponse,
    CustomerUpdateRequest,
)


class UpdateCustomerCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        customer_id: UUID,
        data: CustomerUpdateRequest,
    ) -> CustomerResponse:

        customer_repo = CustomerRepository()

        # 1. Tenant boundary: customer must exist in current user's workspace
        customer = customer_repo.get_by_id_and_workspace(
            db=db,
            customer_id=customer_id,
            workspace_id=current_user.workspace_id,
        )

        if not customer:
            raise LookupError("Customer not found")

        # 2. If email is changing, check workspace-scoped uniqueness
        if data.email:
            normalized_email = data.email.strip().lower()
            if normalized_email != customer.email.lower():
                existing = customer_repo.get_by_email_and_workspace(
                    db=db,
                    email=normalized_email,
                    workspace_id=current_user.workspace_id,
                )
                if existing and existing.id != customer.id:
                    raise ValueError(
                        "Customer with this email already exists in this workspace"
                    )
                customer.email = normalized_email

        # 3. Update remaining provided fields
        if data.full_name is not None:
            customer.full_name = data.full_name.strip()

        if data.phone is not None:
            customer.phone = data.phone.strip() if data.phone else None

        if data.company_name is not None:
            customer.company_name = (
                data.company_name.strip() if data.company_name else None
            )

        if data.status is not None:
            customer.status = data.status

        db.commit()
        db.refresh(customer)

        return CustomerResponse.model_validate(customer)
