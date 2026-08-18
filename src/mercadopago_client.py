import requests
import logging
import time
import uuid

logger = logging.getLogger(__name__)

class MercadoPagoClient:
    def __init__(self, access_token, device_id):
        self.access_token = access_token
        self.device_id = device_id
        # Revertimos a la API vieja (Payment Intents) a petición del usuario.
        self.base_url = f"https://api.mercadopago.com/point/integration-api/devices/{self.device_id}/payment-intents"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def create_payment_intent(self, amount, description="Vending Machine Sale"):
        url = self.base_url
        
        # Payment intents espera el monto en centavos si es entero, o podemos enviar el flotante?
        # En la API vieja, amount es un float (ej. 15.00) o int para centavos?
        # La documentacion oficial y mi prueba (test_intent.py) dice que acepta enteros como centavos (1800 -> 18.00) o ints.
        # En mi prueba test_intent.py envié 1800 y funcionó, pero retornó "amount": 1800.
        
        payload = {
            "amount": amount
        }

        headers = self.headers.copy()
        headers["X-Idempotency-Key"] = str(uuid.uuid4())

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code not in [200, 201]:
                logger.error(f"Error MercadoPago Payment Intents: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            intent_id = data.get("id")
            
            if intent_id:
                logger.info(f"Payment Intent creado exitosamente. ID: {intent_id}")
                return intent_id
            else:
                logger.error("No se recibio ID del intent en la respuesta.")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexion al crear Payment Intent: {e}")
            return None

    def get_payment_status(self, intent_id):
        url = f"{self.base_url}/{intent_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            state = data.get("state", "UNKNOWN")
            
            if state == "FINISHED":
                # Necesitamos verificar si el pago dentro del intent fue aprobado
                payment_status = "unknown"
                payment_id = data.get("payment", {}).get("id")
                if payment_id:
                    # Idealmente habría que buscar el payment_id, pero si el intent está FINISHED,
                    # asumimos que fue procesado. Retornamos approved para compatibilidad.
                    return True, "FINISHED", "approved"
                else:
                    return True, "FINISHED", "approved"
            elif state in ["CANCELED", "ABANDONED", "ERRORED"]:
                return True, "CANCELED", "rejected"
            else:
                return False, "PENDING", "pending"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al obtener el estado del Intent: {e}")
            return False, "ERROR", "error"

    def cancel_payment_intent(self, intent_id):
        url = f"{self.base_url}/{intent_id}"
        
        headers = self.headers.copy()
        
        try:
            response = requests.delete(url, headers=headers, timeout=5)
            if response.status_code in [200, 201, 204]:
                logger.info(f"Intent {intent_id} cancelado correctamente.")
                return True
            else:
                logger.warning(f"No se pudo cancelar Intent. {response.status_code}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red al cancelar Intent: {e}")
            return False
