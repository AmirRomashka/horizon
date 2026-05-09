# database/orm_query/base_repository.py
from typing import TypeVar, Generic, Type, Optional, List, Any
from sqlalchemy import select, update, delete, func, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    """Базовый репозиторий с CRUD операциями"""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    def _get_primary_key_column(self) -> str:
        """Автоматически определяет имя первичного ключа для модели"""
        mapper = inspect(self.model)
        pk = mapper.primary_key
        if pk:
            return pk[0].name
        return "id"

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get(self, id: int | str) -> Optional[ModelType]:
        """Получает запись по первичному ключу"""
        pk_column = self._get_primary_key_column()
        
        result = await self.session.execute(
            select(self.model).where(getattr(self.model, pk_column) == id)
        )
        return result.scalar_one_or_none()

    async def get_by_field(self, field_name: str, value: Any) -> Optional[ModelType]:
        """Получает запись по любому полю"""
        result = await self.session.execute(
            select(self.model).where(getattr(self.model, field_name) == value)
        )
        return result.scalar_one_or_none()

    async def get_by(self, **filters) -> Optional[ModelType]:
        """Получает запись по фильтрам"""
        query = select(self.model)
        for key, value in filters.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        **filters
    ) -> List[ModelType]:
        query = select(self.model)
        for key, value in filters.items():
            query = query.where(getattr(self.model, key) == value)
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update(self, id: int | str, **kwargs) -> Optional[ModelType]:
        pk_column = self._get_primary_key_column()
        
        await self.session.execute(
            update(self.model)
            .where(getattr(self.model, pk_column) == id)
            .values(**kwargs)
        )
        await self.session.flush()
        return await self.get(id)

    async def delete(self, id: int | str) -> bool:
        pk_column = self._get_primary_key_column()
        
        result = await self.session.execute(
            delete(self.model).where(getattr(self.model, pk_column) == id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def count(self, **filters) -> int:
        query = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def exists(self, **filters) -> bool:
        return await self.count(**filters) > 0