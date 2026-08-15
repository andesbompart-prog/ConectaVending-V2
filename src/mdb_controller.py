import serial
import time
import logging
import threading

logger = logging.getLogger(__name__)

class MDBController:
    def __init__(self, port, baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_running = False
        self.read_thread = None
        self.vend_request_callback = None
        self.session_complete_callback = None

    def connect(self):
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            logger.info(f"Conectado a Waferstar MDB en el puerto {self.port}")
            self.is_running = True
            
            # Start background thread to read from serial
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            return True
        except serial.SerialException as e:
            logger.error(f"Error conectando al puerto serie {self.port}: {e}")
            return False

    def disconnect(self):
        self.is_running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Desconectado de Waferstar MDB")

    def _send_command(self, hex_str):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                # El Waferstar SI espera bytes crudos (raw hex), me equivoque al pasarlo a ASCII
                data_bytes = bytes.fromhex(hex_str)
                self.serial_conn.write(data_bytes)
                logger.debug(f"MDB TX: {hex_str}")
            except Exception as e:
                logger.error(f"Error al enviar comando MDB: {e}")

    def begin_session(self):
        """
        Send Begin Session command to VMC to indicate card funds available.
        Using 03FFFF01 as recommended by manual to provide maximum credit.
        """
        logger.info("MDB: Iniciando sesión (Enviando 03FFFF01 para despertar la máquina)")
        self._send_command("03FFFF01")

    def end_session(self):
        """
        Send End Session command (0707 -> 07 + 07 Checksum)
        """
        logger.info("MDB: Finalizando sesión")
        self._send_command("0707")

    def approve_vend(self, price_hex="0000"):
        """
        Send Vend Approved command.
        Example: 05 + Amount (2 bytes) + Checksum
        """
        logger.info(f"MDB: Aprobando venta por {price_hex}")
        # Command 05 (Vend Approve) + Amount
        # Calculamos checksum (suma de bytes)
        amount_bytes = bytes.fromhex(price_hex)
        cmd = bytes.fromhex("05") + amount_bytes
        chksum = sum(cmd) & 0xFF
        cmd_with_chksum = cmd + bytes([chksum])
        self._send_command(cmd_with_chksum.hex())

    def deny_vend(self):
        """
        Send Vend Denied command (0606 -> 06 + 06 Checksum)
        """
        logger.info("MDB: Denegando venta")
        self._send_command("0606")

    def set_callbacks(self, on_vend_request, on_session_complete):
        self.vend_request_callback = on_vend_request
        self.session_complete_callback = on_session_complete

    def _read_loop(self):
        buffer = b""
        while self.is_running:
            try:
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    buffer += data
                    
                    # Decodificar ignorando caracteres especiales como STX (\x02) y ETX (\x03)
                    text_data = buffer.decode('ascii', errors='ignore')
                    
                    if text_data:
                        logger.debug(f"MDB RX ASCII: {text_data}")
                    
                    # Check for Vend Request (Starts with 1300)
                    if "1300" in text_data:
                        idx = text_data.find("1300")
                        if len(text_data) >= idx + 14:
                            vend_cmd = text_data[idx:idx+14]
                            # Precio está en el byte 2 y 3 (index 4 al 7)
                            price_hex = vend_cmd[4:8]
                            price_int = int(price_hex, 16)
                            logger.info(f"MDB: Vend Request recibido. Precio Hex: {price_hex} -> {price_int}")
                            
                            buffer = b"" # Clear buffer
                            if self.vend_request_callback:
                                self.vend_request_callback(price_int, price_hex)
                    
                    # Check for Session Complete (1304), Vend Success (1302), or Vend Failed (1303)
                    elif "1304" in text_data or "1302" in text_data or "1303" in text_data:
                        logger.info("MDB: Session Complete / Vend Success / Vend Failed recibido.")
                        buffer = b"" # Clear buffer
                        if self.session_complete_callback:
                            self.session_complete_callback()
                            
                    elif len(buffer) > 100:
                        buffer = b"" # Prevent overflow
                        
            except Exception as e:
                logger.error(f"Error leyendo del puerto serie: {e}")
            time.sleep(0.1)
