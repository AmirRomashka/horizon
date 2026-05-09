# database/orm_query/host_repository.py
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.base_repository import BaseRepository
from database.models.host_model import Hosts
from database.enumerate.host_enum import HostStatus
from services.xui_client import XUIClient


class HostRepository(BaseRepository[Hosts]):
    """Репозиторий для работы с хостами"""

    def __init__(self, session: AsyncSession):
        super().__init__(Hosts, session)

    async def get_by_name(self, name: str) -> Optional[Hosts]:
        """Получить хост по имени"""
        return await self.get_by(name=name)

    async def get_active_hosts(self) -> List[Hosts]:
        """Получить все активные хосты"""
        return await self.get_all(status=HostStatus.ACTIVE, is_active=True)

    async def get_available_hosts(self) -> List[Hosts]:
        """Получить хосты, доступные для подключения"""
        result = await self.session.execute(
            select(Hosts).where(
                Hosts.status == HostStatus.ACTIVE,
                Hosts.is_active == True,
                Hosts.current_clients < Hosts.max_clients
            )
        )
        return result.scalars().all()

    async def get_host_for_new_client(self) -> Optional[Hosts]:
        """Выбрать хост с наименьшей нагрузкой для нового клиента"""
        hosts = await self.get_available_hosts()
        if not hosts:
            return None
        return min(hosts, key=lambda h: h.current_clients)

    async def increment_clients(self, host_id: int) -> None:
        """Увеличить счётчик клиентов на хосте"""
        host = await self.get(host_id)
        if host:
            host.current_clients += 1
            await self.session.flush()

    async def decrement_clients(self, host_id: int) -> None:
        """Уменьшить счётчик клиентов на хосте"""
        host = await self.get(host_id)
        if host and host.current_clients > 0:
            host.current_clients -= 1
            await self.session.flush()

    async def create_with_test(self, **kwargs) -> Tuple[Optional[Hosts], str]:
        """
        Создаёт хост с проверкой подключения к API
        Returns: (host, message)
        """
        # Сначала создаём хост в БД (но не коммитим)
        host = self.model(**kwargs)
        self.session.add(host)
        await self.session.flush()
        
        try:
            # Проверяем подключение
            client = XUIClient(host)
            is_connected, message = await client.test_connection()
            await client.close()
            
            if not is_connected:
                # Откатываем создание хоста
                await self.session.rollback()
                return None, message
            
            # Подключение успешно, коммитим
            await self.session.commit()
            return host, "✅ Хост успешно создан и подключение проверено"
            
        except Exception as e:
            await self.session.rollback()
            return None, f"❌ Ошибка при проверке подключения: {str(e)}"
    
    async def test_connection(self, host_id: int) -> Tuple[bool, str]:
        """
        Проверяет подключение к существующему хосту
        Returns: (is_success, message)
        """
        host = await self.get(host_id)
        if not host:
            return False, "Хост не найден"
        
        client = XUIClient(host)
        is_connected, message = await client.test_connection()
        await client.close()
        
        if is_connected:
            # Обновляем статус хоста на ACTIVE если он был в ошибке
            if host.status != HostStatus.ACTIVE:
                await self.update(host_id, status=HostStatus.ACTIVE, is_active=True)
            return True, message
        else:
            # Можно пометить хост как неактивный
            if host.status == HostStatus.ACTIVE:
                await self.update(host_id, status=HostStatus.INACTIVE)
            return False, message
    
    async def update_clients_count(self, host_id: int) -> int:
        """
        Обновляет количество клиентов на хосте через API
        Returns: количество клиентов
        """
        host = await self.get(host_id)
        if not host:
            return 0
        
        client = XUIClient(host)
        clients_count = await client.get_clients_count()
        await client.close()
        
        if clients_count > 0:
            await self.update(host_id, current_clients=clients_count)
        
        return clients_count