import os
import sys
import json
import time
import threading
import serial
import evdev
from select import select
import logging

from mdb_controller import MDBController
from mercadopago_client import MercadoPagoClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

AUDIO_DIR = "/home/arduino/ConectaVending_Firmware"

def play_audio(filename):
    def _play():
        path = os.path.join(AUDIO_DIR, filename)
        if os.path.exists(path):
            os.system(f"mpg123 -q {path} >/dev/null 2>&1")
    threading.Thread(target=_play, daemon=True).start()

class VendingApp:
    def __init__(self):
        self.config = self.load_config()
        self.mdb = MDBController(
            port=self.config.get("serial_port", "/dev/ttyUSB0"),
            baudrate=self.config.get("baudrate", 9600)
        )
        self.mp = MercadoPagoClient(
            access_token=self.config.get("mp_access_token"),
            device_id=self.config.get("mp_device_id")
        )
        self.session_active = False
        self.product_selected = False

    def load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error cargando config.json: {e}")
            return {}

    def on_vend_request(self, price_int, price_hex):
        logger.info(f"[Venta] Solicitud de producto por {price_int} unidades.")
        self.product_selected = True # !IMPORTANTE: Evita que el temporizador cancele
        threading.Thread(target=self._handle_vend_request, args=(price_int, price_hex), daemon=True).start()

    def _handle_vend_request(self, price_int, price_hex):
        play_audio("procesando.mp3")
        payment_intent_id = self.mp.create_payment_intent(amount=price_int)
        
        if not payment_intent_id:
            logger.error("[Venta] Fallo al crear Payment Intent.")
            self.mdb.deny_vend()
            play_audio("pago_rechazado.mp3")
            self.session_active = False
            self.product_selected = False
            return

        logger.info(f"[Venta] Cobro enviado a Terminal (ID: {payment_intent_id}). Esperando pago...")
        start_time = time.time()
        timeout = 60 # 60 segundos para procesar el pago
        
        while time.time() - start_time < timeout:
            is_finished, state, payment_status = self.mp.get_payment_status(payment_intent_id)
            if state == "FINISHED":
                if payment_status in ["approved", "accredited"]:
                    logger.info("[Venta] Pago APROBADO por MercadoPago.")
                    play_audio("pago_exitoso.mp3")
                    self.mdb.approve_vend(price_hex)
                else:
                    logger.info(f"[Venta] Pago RECHAZADO o no exitoso. Estado: {payment_status}")
                    self.mdb.deny_vend()
                    play_audio("pago_rechazado.mp3")
                self.session_active = False
                self.product_selected = False
                return
            elif state in ["CANCELED", "ABANDONED", "ERRORED"]:
                logger.info(f"[Venta] Transaccion terminada con estado: {state}")
                self.mdb.deny_vend()
                play_audio("pago_rechazado.mp3")
                self.session_active = False
                self.product_selected = False
                return
            time.sleep(2)

        logger.warning("[Venta] Tiempo de espera agotado en Smart Point 2. Cancelando...")
        self.mp.cancel_payment_intent(payment_intent_id)
        self.mdb.deny_vend()
        play_audio("pago_rechazado.mp3")
        self.session_active = False
        self.product_selected = False

    def run(self):
        if not self.mdb.connect():
            logger.error("No se pudo conectar al MDB.")
            return

        self.mdb.set_callbacks(self.on_vend_request, lambda: logger.info("Sesion terminada."))
        
        logger.info("Iniciando ConectaVending V14 (Restart Forzado)")
        
        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        except Exception as e:
            logger.error(f"Error buscando boton: {e}")
            return
            
        keyboard_devices = []
        for device in devices:
            try:
                if evdev.ecodes.EV_KEY in device.capabilities():
                    keys = device.capabilities()[evdev.ecodes.EV_KEY]
                    if evdev.ecodes.KEY_ENTER in keys or isinstance(keys, list):
                        keyboard_devices.append(device)
            except:
                pass

        logger.info("[Boton] Listo. Esperando pulsacion...")
        
        while True:
            try:
                r, w, x = select(keyboard_devices, [], [])
                for device in r:
                    for event in device.read():
                        if event.type == evdev.ecodes.EV_KEY:
                            key_event = evdev.categorize(event)
                            if key_event.keystate == 1:
                                if not self.session_active:
                                    logger.info("[Boton] Presionado! Activando sesion de tarjeta...")
                                    self.session_active = True
                                    self.product_selected = False
                                    play_audio("conectando.mp3")
                                    self.mdb.begin_session()
                                    
                                    # Temporizador para cancelar si NO escoge nada en 30s
                                    def timeout_session():
                                        time.sleep(30)
                                        if self.session_active and not self.product_selected: 
                                            logger.info("[MDB] Sesion expirada por inactividad al seleccionar.")
                                            self.mdb.end_session()
                                            self.session_active = False
                                            
                                    threading.Thread(target=timeout_session, daemon=True).start()
            except KeyboardInterrupt:
                self.mdb.disconnect()
                sys.exit(0)
            except Exception as e:
                time.sleep(1)

if __name__ == '__main__':
    app = VendingApp()
    app.run()
