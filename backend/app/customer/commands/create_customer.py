from sqlalchemy.orm import Session

from app.auth.model import User
from app.customer.model import Customer
from app.customer.repositories.customer_repository import CustomerRepository
from app.customer.schema import (
    CustomerCreateRequest,
    CustomerResponse,
)


class CreateCustomerCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        data: CustomerCreateRequest,
    ) -> CustomerResponse:

        customer_repo = CustomerRepository()

        normalized_email = data.email.strip().lower()

        # 1. Check workspace-scoped email uniqueness
        existing_customer = customer_repo.get_by_email_and_workspace(
            db=db,
            email=normalized_email,
            workspace_id=current_user.workspace_id,
        )

        if existing_customer:
            raise ValueError(
                "Customer with this email already exists in this workspace"
            )

        # 2. Create customer record bound to caller's workspace
        new_customer = Customer(
            workspace_id=current_user.workspace_id,
            full_name=data.full_name.strip(),
            email=normalized_email,
            phone=data.phone.strip() if data.phone else None,
            company_name=data.company_name.strip() if data.company_name else None,
            status=data.status,
        )

        customer_repo.add(
            db=db,
            obj=new_customer,
        )

        db.commit()
        db.refresh(new_customer)

        return CustomerResponse.model_validate(new_customer)
