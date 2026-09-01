from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.auth.schema import MessageResponse
from app.customer.repositories.customer_repository import CustomerRepository


class DeleteCustomerCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        customer_id: UUID,
    ) -> MessageResponse:

        customer_repo = CustomerRepository()

        # 1. Tenant boundary: customer must exist in current user's workspace
        customer = customer_repo.get_by_id_and_workspace(
            db=db,
            customer_id=customer_id,
            workspace_id=current_user.workspace_id,
        )

        if not customer:
            raise LookupError("Customer not found")

        # 2. Delete customer record
        customer_repo.delete(
            db=db,
            obj=customer,
        )

        db.commit()

        return MessageResponse(
            message="Customer deleted successfully",
        )
