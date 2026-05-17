import json
import uuid
import requests
from typing import Optional, Dict, List, Tuple
from icecream import ic
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from database.models.host_model import Hosts


class XUIClient:
    """
    Клиент для взаимодействия с 3x-ui API (синхронная версия)
    Поддерживает Bearer Token авторизацию (рекомендуется)
    """
    
    def __init__(self, host: Hosts):
        self.host = host
        self.web_base_url = host.get_web_base_url()
        self.panel_api_url = host.get_panel_api_url()
        self.session: Optional[requests.Session] = None
        self._use_token = bool(host.api_token)
        
        ic(f"XUIClient initialized for host: {host.name}")
        ic(f"Panel API URL: {self.panel_api_url}")
        ic(f"Using Bearer Token: {self._use_token}")
    
    def _get_session(self) -> requests.Session:
        if self.session is None:
            self.session = requests.Session()
            self.session.verify = False
            
            # Если есть API токен - используем Bearer авторизацию
            if self._use_token and self.host.api_token:
                self.session.headers.update({
                    "Authorization": f"Bearer {self.host.api_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                })
                ic(f"✅ Using Bearer Token auth for {self.host.name}")
            else:
                ic(f"⚠️ No API token, will use session-based auth for {self.host.name}")
            
            ic(f"Created new session for {self.host.name}")
        return self.session
    
    def test_connection(self) -> Tuple[bool, str]:
        """Проверяет подключение к API"""
        try:
            session = self._get_session()
            
            # Если используем токен - просто пробуем получить список inbound'ов
            if self._use_token:
                url = f"{self.panel_api_url}/inbounds/list"
                response = session.get(url, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        return True, "✅ Подключение успешно (Bearer Token)"
                    else:
                        return False, f"❌ API error: {result.get('msg', 'Unknown error')}"
                else:
                    return False, f"❌ HTTP {response.status_code}: {response.text[:100]}"
            
            # Иначе пробуем авторизацию через login
            else:
                login_url = f"{self.web_base_url}/login"
                payload = {
                    "username": self.host.username,
                    "password": self.host.password
                }
                response = session.post(login_url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    return True, "✅ Подключение успешно (Session auth)"
                else:
                    return False, f"❌ Ошибка авторизации: HTTP {response.status_code}"
                    
        except Exception as e:
            return False, f"Ошибка: {str(e)[:50]}"
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> Tuple[bool, Optional[Dict]]:
        session = self._get_session()
        url = f"{self.panel_api_url}{endpoint}"
        
        ic("=" * 60)
        ic(f"REQUEST: {method} {url}")
        ic(f"Request data: {data}")
        
        try:
            response = session.request(
                method=method,
                url=url,
                json=data,
                timeout=30
            )
            ic(f"Response status: {response.status_code}")
            ic(f"Response body: {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                return True, result
            else:
                ic(f"❌ Request failed: {url}, status: {response.status_code}")
                return False, None
        except Exception as e:
            ic(f"❌ Request error: {e}")
            return False, None
    
    def get_inbounds(self) -> Optional[List[Dict]]:
        ic("Getting inbounds list...")
        success, result = self._request("GET", "/inbounds/list")
        if success and result and result.get("success"):
            inbounds = result.get("obj", [])
            ic(f"Found {len(inbounds)} inbounds")
            return inbounds
        ic("Failed to get inbounds")
        return None
    
    def get_inbound_by_id(self, inbound_id: int) -> Optional[Dict]:
        ic(f"Getting inbound by id: {inbound_id}")
        success, result = self._request("GET", f"/inbounds/get/{inbound_id}")
        
        if success and result and result.get("success"):
            inbound = result.get("obj")
            return inbound
        else:
            ic(f"Failed to get inbound {inbound_id}")
            return None
    
    def add_client(
        self,
        inbound_id: int,
        email: str,
        expiry_time: int,
        total_gb: int = 0,
    ) -> Tuple[bool, Optional[Dict]]:
        client_id = str(uuid.uuid4())
        
        ic("=" * 60)
        ic(f"ADDING CLIENT")
        ic(f"Inbound ID: {inbound_id}")
        ic(f"Email: {email}")
        ic(f"Expiry time: {expiry_time}")
        ic(f"Client ID: {client_id}")
        
        client_config = {
            "id": client_id,
            "email": email,
            "expiryTime": expiry_time,
            "totalGB": total_gb,
            "enable": True,
            "flow": "xtls-rprx-vision",
            "limitIp": 0,
            "reset": 0
        }
        
        settings_str = json.dumps({"clients": [client_config]})
        
        payload = {
            "id": inbound_id,
            "settings": settings_str
        }
        
        success, result = self._request("POST", "/inbounds/addClient", payload)
        
        if success and result and result.get("success"):
            ic(f"✅ Client added successfully!")
            vless_url = self._build_vless_url(client_id, inbound_id)
            client_config["vless_url"] = vless_url
            return True, client_config
        else:
            ic(f"❌ Failed to add client, result: {result}")
            return False, None
    
    def get_client_traffic_by_uuid(self, client_uuid: str) -> Optional[Dict]:
        """Получает трафик клиента по UUID"""
        ic(f"Getting traffic for client UUID {client_uuid}")
        success, result = self._request("GET", f"/inbounds/getClientTrafficsById/{client_uuid}")
        if success and result and result.get("success"):
            obj = result.get("obj")
            if isinstance(obj, list) and len(obj) > 0:
                return obj[0]
            return obj
        return None
    
    def _build_vless_url(self, client_id: str, inbound_id: int) -> str:
        ic(f"Building VLESS URL for client {client_id}")
    
        inbound = self.get_inbound_by_id(inbound_id)
        if not inbound:
            return f"vless://{client_id}@{self.host.api_url}:443?security=reality#ERROR"
    
        hostname = self.host.api_url.split('//')[-1].split(':')[0]
        port = inbound.get("port", 443)
    
        stream_settings = inbound.get("streamSettings", {})
        if isinstance(stream_settings, str):
            try:
                stream_settings = json.loads(stream_settings)
            except Exception as e:
                ic(f"Failed to parse streamSettings: {e}")
                stream_settings = {}
    
        reality = stream_settings.get("realitySettings", {})
        reality_settings = reality.get("settings", {})
        public_key = reality_settings.get("publicKey", "")
        server_name = reality.get("serverNames", ["www.amazon.com"])[0] if reality.get("serverNames") else "www.amazon.com"
        short_ids = reality.get("shortIds", [""])
        short_id = short_ids[0] if short_ids else ""
    
        vless_url = (
            f"vless://{client_id}@{hostname}:{port}"
            f"?type=tcp&encryption=none&security=reality"
            f"&pbk={public_key}&fp=chrome&sni={server_name}"
        )
    
        if short_id:
            vless_url += f"&sid={short_id}"
    
        vless_url += f"&flow=xtls-rprx-vision#HorizonVPN"
    
        return vless_url
    
    def get_clients_count(self) -> int:
        inbounds = self.get_inbounds()
        if not inbounds:
            return 0
        
        total = 0
        for inbound in inbounds:
            settings = inbound.get("settings", {})
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except:
                    settings = {}
            clients = settings.get("clients", [])
            total += len(clients)
        
        return total
    
    def close(self):
        if self.session:
            self.session.close()
            ic(f"Session closed")