import requests
import logging
import time
import uuid

logger = logging.getLogger(__name__)

class MercadoPagoClient:
    def __init__(self, access_token, device_id):
        self.access_token = access_token
        self.device_id = device_id
        # Usamos la API V1 Orders, que es la recomendada oficialmente.
        self.base_url = "https://api.mercadopago.com/v1/orders"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def create_payment_intent(self, amount, description="Vending Machine Sale"):
        url = self.base_url
        external_reference = f"VEND_{int(time.time())}"
        amount_str = f"{(amount / 100.0):.2f}"
        
        payload = {
            "type": "point",
            "description": description,
            "external_reference": external_reference,
            "transactions": {
                "payments": [
                    {
                        "amount": amount_str
                    }
                ]
            },
            "config": {
                "point": {
                    "terminal_id": self.device_id
                }
            }
        }

        headers = self.headers.copy()
        headers["X-Idempotency-Key"] = str(uuid.uuid4())

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code not in [200, 201]:
                logger.error(f"Error MercadoPago V1 Orders: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            order_id = data.get("id")
            
            if order_id:
                logger.info(f"Order V1 creada exitosamente. ID: {order_id}")
                return order_id
            else:
                logger.error("No se recibio ID de la orden en la respuesta.")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexion al crear Order V1: {e}")
            return None

    def get_payment_status(self, order_id):
        url = f"{self.base_url}/{order_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            status = data.get("status", "unknown")
            
            if status == "processed":
                return True, "FINISHED", "approved"
            elif status in ["failed", "canceled", "expired"]:
                return True, "CANCELED", "rejected"
            else:
                return False, "PENDING", "pending"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al obtener el estado de la Order: {e}")
            return False, "ERROR", "error"

    def cancel_payment_intent(self, order_id):
        url = f"{self.base_url}/{order_id}/cancel"
        
        headers = self.headers.copy()
        headers["X-Idempotency-Key"] = str(uuid.uuid4())
        
        try:
            response = requests.post(url, headers=headers, timeout=5)
            if response.status_code in [200, 201]:
                logger.info(f"Order {order_id} cancelada correctamente.")
                return True
            else:
                logger.warning(f"No se pudo cancelar Order. {response.status_code}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red al cancelar Order: {e}")
            return False
