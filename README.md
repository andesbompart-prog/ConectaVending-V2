# ConectaVending V2 (MercadoPago + MDB)

Este repositorio contiene la lógica final, limpia y validada, para conectar una máquina Vending (vía un módulo MDB) a la pasarela de pagos de MercadoPago (Orders V1) a través de un SBC (ej. Arduino Portenta X8, Raspberry Pi, etc.).

## Características
- **MDB Controller:** Lee e interactúa asincrónicamente con el bus MDB (ej. interfaz Waferstar).
- **MercadoPago Client:** Implementación de la API Oficial "Orders V1" para dispositivos Smart Point 2.
- **Botón Físico:** Lógica con `evdev` para detectar la pulsación de un botón iluminado que habilita la sesión de compra con tarjeta.
- **Temporizadores Asíncronos:** Cancela automáticamente las órdenes en MercadoPago si el usuario no realiza la selección en la máquina Vending.
- **Aprobación de Venta:** Completa el flujo `Vend Approve` en MDB solo después de que MercadoPago confirma el pago `processed`.

## Requisitos de Hardware
- Ordenador Linux (Arduino Portenta X8 / Raspberry Pi).
- Módulo adaptador MDB a USB/Serial (ej. Waferstar).
- Botón USB (emulador de teclado) asignado a un evento de input.
- Terminal MercadoPago Point Smart 2 en Modo "Punto de Venta" (PDV).

## Instalación en un nuevo Arduino/SBC Linux

1. Clonar este repositorio en la carpeta deseada (ej. `/home/arduino/ArduinoApps/Antigravity-ConectaVending-Deploy`).
2. Instalar las dependencias de Python 3:
   ```bash
   pip3 install -r requirements.txt
   ```
3. Renombrar el archivo `src/config.example.json` a `src/config.json` y completarlo con tu Token de MercadoPago y el ID de tu terminal Point Smart 2.
   ```json
   {
       "MERCADOPAGO_ACCESS_TOKEN": "APP_USR-XXXX-XXXX-XXXX",
       "DEVICE_ID": "NEWLAND_N950__XXXXXXXXX",
       "PORT_MDB": "/dev/ttyUSB0",
       "BUTTON_INPUT_PATH": "/dev/input/by-id/usb-..."
   }
   ```
4. Copiar el archivo del servicio de Systemd para asegurar ejecución en el arranque:
   ```bash
   sudo cp conectavending.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable conectavending.service
   sudo systemctl start conectavending.service
   ```

## Notas sobre Terminales Point Smart 2
Debido a políticas de energía en versiones recientes de Android de MercadoPago (como la v12.1.8), es posible que la terminal no "despierte" la pantalla automáticamente al recibir un "Push". El cajero o el cliente deberá tocar la pantalla y presionar "Actualizar" para ver el cobro si la pantalla estaba en "reposo profundo".
Para mitigar esto, se recomienda mantener la terminal Point Smart 2 siempre conectada a su cargador USB dentro de la máquina Vending.
