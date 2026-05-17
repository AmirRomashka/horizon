from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base_model import Base
from database.enumerate.host_enum import HostStatus


class Hosts(Base):
    __tablename__ = "hosts"

    host_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_url: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    api_token: Mapped[str] = mapped_column(String(255), nullable=True, default="")  # НОВОЕ ПОЛЕ
    inbound_id: Mapped[int] = mapped_column(Integer, default=1)
    location: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[HostStatus] = mapped_column(String(20), default=HostStatus.ACTIVE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_clients: Mapped[int] = mapped_column(Integer, default=100)
    current_clients: Mapped[int] = mapped_column(Integer, default=0)
    api_path: Mapped[str] = mapped_column(String(100), nullable=True, default="")

    def __repr__(self) -> str:
        return f"<Hosts(host_id={self.host_id}, name={self.name}, status={self.status.value})>"

    def is_available(self) -> bool:
        return (
            self.status == HostStatus.ACTIVE 
            and self.is_active 
            and self.current_clients < self.max_clients
        )

    def is_under_maintenance(self) -> bool:
        return self.status == HostStatus.MAINTENANCE

    def get_web_base_url(self) -> str:
        """Возвращает базовый URL с webBasePath"""
        base = self.api_url.rstrip('/')
        if self.api_path:
            return f"{base}/{self.api_path.rstrip('/')}"
        return base

    def get_panel_api_url(self) -> str:
        """URL для panel API"""
        return f"{self.get_web_base_url()}/panel/api"

    def get_inbounds_url(self) -> str:
        return f"{self.get_panel_api_url()}/inbounds/list"

    def get_inbound_by_id_url(self, inbound_id: int) -> str:
        return f"{self.get_panel_api_url()}/inbounds/get/{inbound_id}"

    def get_add_client_url(self) -> str:
        return f"{self.get_panel_api_url()}/inbounds/addClient"

    def get_delete_client_url(self, inbound_id: int, client_id: str) -> str:
        return f"{self.get_panel_api_url()}/inbounds/{inbound_id}/delClient/{client_id}"

    def get_delete_client_by_email_url(self, inbound_id: int, email: str) -> str:
        return f"{self.get_panel_api_url()}/inbounds/{inbound_id}/delClientByEmail/{email}"

    def get_client_traffic_url(self, client_email: str) -> str:
        return f"{self.get_panel_api_url()}/inbounds/getClientTraffics/{client_email}"

    def get_client_traffic_by_uuid_url(self, client_uuid: str) -> str:
        return f"{self.get_panel_api_url()}/inbounds/getClientTrafficsById/{client_uuid}"

    def get_reset_client_traffic_url(self, inbound_id: int, email: str) -> str:
        return f"{self.get_panel_api_url()}/inbounds/{inbound_id}/resetClientTraffic/{email}"

    def get_server_status_url(self) -> str:
        return f"{self.get_panel_api_url()}/server/status"