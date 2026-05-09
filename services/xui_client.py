# services/xui_client.py
import json
import uuid
import requests
from typing import Optional, Dict, List, Tuple
from icecream import ic
from urllib3.exceptions import InsecureRequestWarning

# Отключаем предупреждения о SSL
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from database.models.host_model import Hosts


class XUIClient:
    """
    Клиент для взаимодействия с 3x-ui API (синхронная версия)
    """
    
    def __init__(self, host: Hosts):
        self.host = host
        self.web_base_url = host.get_web_base_url()
        self.panel_api_url = host.get_panel_api_url()
        self.login_url = host.get_login_url()
        self.session: Optional[requests.Session] = None
        self._is_authenticated = False
        ic(f"XUIClient initialized for host: {host.name}")
        ic(f"Panel API URL: {self.panel_api_url}")
        ic(f"Login URL: {self.login_url}")
    
    def _get_session(self) -> requests.Session:
        if self.session is None:
            self.session = requests.Session()
            self.session.verify = False  # ignore SSL
            ic(f"Created new session for {self.host.name}")
        return self.session
    
    def _login(self) -> bool:
        session = self._get_session()
        
        payload = {
            "username": self.host.username,
            "password": self.host.password
        }
        
        ic(f"Logging in to {self.host.name}")
        ic(f"Login URL: {self.login_url}")
        ic(f"Login payload: {payload}")
        
        try:
            response = session.post(self.login_url, json=payload, timeout=10)
            ic(f"Login response status: {response.status_code}")
            ic(f"Login response headers: {dict(response.headers)}")
            ic(f"Login response body: {response.text[:500]}")
            
            if response.status_code == 200:
                self._is_authenticated = True
                ic(f"✅ Logged in to {self.host.name}")
                return True
            else:
                ic(f"❌ Login failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            ic(f"❌ Login error: {e}")
            return False
    
    def _ensure_auth(self) -> bool:
        if not self._is_authenticated:
            ic(f"Auth required for {self.host.name}, attempting login...")
            return self._login()
        return True
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> Tuple[bool, Optional[Dict]]:
        if not self._ensure_auth():
            return False, None
        
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
            ic(f"Response body: {response.text[:1000]}")
            
            if response.status_code == 200:
                result = response.json()
                ic(f"Response JSON: {result}")
                return True, result
            else:
                ic(f"❌ Request failed: {url}, status: {response.status_code}")
                return False, None
        except Exception as e:
            ic(f"❌ Request error: {e}")
            return False, None
    
    def test_connection(self) -> Tuple[bool, str]:
        try:
            if self._login():
                return True, "✅ Подключение успешно"
            else:
                return False, "❌ Ошибка авторизации"
        except Exception as e:
            return False, f"Ошибка: {str(e)[:50]}"
    
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
            ic(f"Inbound data keys: {inbound.keys() if inbound else 'None'}")
            
            # Проверяем наличие streamSettings
            if inbound:
                stream_settings = inbound.get("streamSettings")
                ic(f"streamSettings type: {type(stream_settings)}")
                ic(f"streamSettings content: {stream_settings[:500] if isinstance(stream_settings, str) else stream_settings}")
                
                # Парсим streamSettings если это строка
                if isinstance(stream_settings, str):
                    try:
                        stream_settings = json.loads(stream_settings)
                        ic(f"Parsed streamSettings: {stream_settings.keys()}")
                    except:
                        ic("Failed to parse streamSettings")
                
                # Проверяем realitySettings
                if isinstance(stream_settings, dict):
                    reality = stream_settings.get("realitySettings")
                    ic(f"realitySettings: {reality}")
                    if reality:
                        ic(f"publicKey: {reality.get('publicKey', 'NOT FOUND')}")
                        ic(f"serverName: {reality.get('serverName', 'NOT FOUND')}")
                        ic(f"shortIds: {reality.get('shortIds', 'NOT FOUND')}")
            
            return inbound
        else:
            ic(f"Failed to get inbound {inbound_id}, result: {result}")
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
        ic(f"Settings string: {settings_str}")
        
        payload = {
            "id": inbound_id,
            "settings": settings_str
        }
        
        ic(f"Final payload: {payload}")
        
        success, result = self._request("POST", "/inbounds/addClient", payload)
        
        if success and result and result.get("success"):
            ic(f"✅ Client added successfully!")
            vless_url = self._build_vless_url(client_id, inbound_id)
            client_config["vless_url"] = vless_url
            ic(f"Generated VLESS URL: {vless_url}")
            return True, client_config
        else:
            ic(f"❌ Failed to add client, result: {result}")
            return False, None
    
    def _build_vless_url(self, client_id: str, inbound_id: int) -> str:
        ic(f"Building VLESS URL for client {client_id}")
    
        inbound = self.get_inbound_by_id(inbound_id)
        if not inbound:
            return f"vless://{client_id}@{self.host.api_url}:443?security=reality#ERROR"
    
        # Извлекаем hostname из api_url
        hostname = self.host.api_url.split('//')[-1].split(':')[0]
        port = inbound.get("port", 443)
        ic(f"Hostname: {hostname}, Port: {port}")
    
        # Парсим streamSettings
        stream_settings = inbound.get("streamSettings", {})
        if isinstance(stream_settings, str):
            try:
                stream_settings = json.loads(stream_settings)
            except Exception as e:
                ic(f"Failed to parse streamSettings: {e}")
                stream_settings = {}
    
        # Получаем realitySettings
        reality = stream_settings.get("realitySettings", {})
    
        # 🔧 ИСПРАВЛЕНИЕ: publicKey лежит внутри вложенного объекта 'settings'
        reality_settings = reality.get("settings", {})
        public_key = reality_settings.get("publicKey", "")
    
        # serverName может быть в realitySettings или в realitySettings.settings
        server_name = reality.get("serverNames", ["www.amazon.com"])[0] if reality.get("serverNames") else "www.amazon.com"
    
        short_ids = reality.get("shortIds", [""])
        short_id = short_ids[0] if short_ids else ""
    
        ic(f"Public key: {public_key}")
        ic(f"Server name: {server_name}")
        ic(f"Short ID: {short_id}")
    
        if not public_key:
            ic("⚠️ WARNING: public_key is empty! VLESS URL may not work!")
    
        vless_url = (
            f"vless://{client_id}@{hostname}:{port}"
            f"?type=tcp&encryption=none&security=reality"
            f"&pbk={public_key}&fp=chrome&sni={server_name}"
        )
    
        if short_id:
            vless_url += f"&sid={short_id}"
    
        vless_url += f"&flow=xtls-rprx-vision#HorizonVPN"
    
        ic(f"Generated VLESS URL: {vless_url}")
        return vless_url
    
    def delete_client(self, inbound_id: int, client_email: str) -> bool:
        ic(f"Deleting client {client_email} from inbound {inbound_id}")
        success, result = self._request("POST", f"/inbounds/{inbound_id}/delClient/{client_email}")
        return success and result and result.get("success", False)
    
    def get_client_traffic(self, client_email: str) -> Optional[Dict]:
        ic(f"Getting traffic for client {client_email}")
        success, result = self._request("GET", f"/inbounds/getClientTraffics/{client_email}")
        if success and result and result.get("success"):
            return result.get("obj")
        return None
    
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
            self._is_authenticated = False
            ic(f"Session closed")