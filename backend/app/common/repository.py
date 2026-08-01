from typing import Generic, Type, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session


ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):

    def __init__(
        self,
        model: Type[ModelType],
    ):
        self.model = model
    
    def get_by_id(
        self,
        db: Session,
        obj_id: UUID,
    ) -> ModelType | None:
        return(
            db.query(self.model)
            .filter(self.model.id == obj_id)
            .first()
        )
    
    def get_all(
        self,
        db: Session,
    ) -> list[ModelType]:
        return db.query(self.model).all()


    def add(
        self,
        db: Session,
        obj: ModelType,
    ) -> ModelType:
        db.add(obj)
        return obj

    def delete(
        self,
        db: Session,
        obj: ModelType,
    ) -> None:
        db.delete(obj)

    def flush(self, db: Session) -> None:
        db.flush()

    def refresh(
        self,
        db: Session,
        obj: ModelType,
    ) -> None:
        db.refresh(obj)