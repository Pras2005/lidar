import requests
import threading
import time
from datetime import datetime

try:
    import serial
except ImportError:
    serial = None

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

class HardwareAlertClient:
    """
    Client to trigger physical alerts over HTTP, serial, or Raspberry Pi GPIO.
    """
    def __init__(
        self,
        ip: str,
        port: int = 80,
        enabled: bool = False,
        transport: str = 'http',
        serial_port: str = '/dev/ttyUSB0',
        baudrate: int = 115200,
        serial_timeout: float = 0.5,
        cooldown_s: float = 0.5,
        gpio_pin: int = 18,
        gpio_active_high: bool = True,
        gpio_duration_s: float = 0.3,
    ):
        self.timeout = 0.5
        self.last_sent_at = 0.0
        self._gpio_initialized = False
        self._configured_gpio_pin = None
        self._gpio_lock = threading.Lock()
        self.configure(
            enabled=enabled,
            ip=ip,
            port=port,
            transport=transport,
            serial_port=serial_port,
            baudrate=baudrate,
            serial_timeout=serial_timeout,
            cooldown_s=cooldown_s,
            gpio_pin=gpio_pin,
            gpio_active_high=gpio_active_high,
            gpio_duration_s=gpio_duration_s,
        )

    def configure(
        self,
        enabled=None,
        ip=None,
        port=None,
        transport=None,
        serial_port=None,
        baudrate=None,
        serial_timeout=None,
        cooldown_s=None,
        gpio_pin=None,
        gpio_active_high=None,
        gpio_duration_s=None,
    ):
        if enabled is not None:
            self.enabled = enabled
        if ip is not None:
            self.ip = ip
        if port is not None:
            self.port = port
        if transport is not None:
            self.transport = transport
        if serial_port is not None:
            self.serial_port = serial_port
        if baudrate is not None:
            self.baudrate = baudrate
        if serial_timeout is not None:
            self.serial_timeout = serial_timeout
        if cooldown_s is not None:
            self.cooldown_s = cooldown_s
        if gpio_pin is not None:
            self.gpio_pin = int(gpio_pin)
        if gpio_active_high is not None:
            self.gpio_active_high = bool(gpio_active_high)
        if gpio_duration_s is not None:
            self.gpio_duration_s = float(gpio_duration_s)

        self.url = f"http://{self.ip}:{self.port}/alert"

    def trigger_alert(self, level: str, value: float):
        """
        Sends an alert trigger in a background thread
        to avoid blocking the main LiDAR processing pipeline.
        """
        if not self.enabled:
            return
        now = time.time()
        if now - self.last_sent_at < self.cooldown_s:
            return
        self.last_sent_at = now

        threading.Thread(target=self._send_alert, args=(level, value), daemon=True).start()

    def _build_payload(self, level, value):
        return {
            'status': 'ALERT',
            'transport': self.transport,
            'level': level,
            'value': value,
            'timestamp': str(datetime.now())
        }

    def _send_alert(self, level, value):
        if self.transport == 'gpio':
            self._send_gpio(level, value)
            return
        if self.transport == 'serial':
            self._send_serial(level, value)
            return
        self._send_http(level, value)

    def _send_http(self, level, value):
        try:
            data = self._build_payload(level, value)
            response = requests.post(self.url, json=data, timeout=self.timeout)
            if response.status_code == 200:
                print(f"📡 HTTP alert sent: {level}")
        except Exception as e:
            print(f"❌ HTTP alert communication error: {e}")

    def _send_serial(self, level, value):
        if serial is None:
            print("❌ Serial alert communication error: pyserial is not installed")
            return

        try:
            payload = self._build_payload(level, value)
            line = (
                f"ALERT,{payload['level']},{payload['value']:.4f},"
                f"{payload['timestamp']}\n"
            )
            with serial.Serial(self.serial_port, self.baudrate, timeout=self.serial_timeout) as ser:
                ser.write(line.encode('utf-8'))
                ser.flush()
            print(f"🔌 Serial alert sent: {level}")
        except Exception as e:
            print(f"❌ Serial alert communication error: {e}")

    def _send_gpio(self, level, value):
        if GPIO is None:
            print("❌ GPIO alert communication error: RPi.GPIO is not installed")
            return

        try:
            self._ensure_gpio_ready()
            active_state = GPIO.HIGH if self.gpio_active_high else GPIO.LOW
            inactive_state = GPIO.LOW if self.gpio_active_high else GPIO.HIGH
            with self._gpio_lock:
                GPIO.output(self.gpio_pin, active_state)
                time.sleep(max(0.0, self.gpio_duration_s))
                GPIO.output(self.gpio_pin, inactive_state)
            print(f"🔔 GPIO alert sent on BCM {self.gpio_pin}: {level} ({value:.3f})")
        except Exception as e:
            print(f"❌ GPIO alert communication error: {e}")

    def _ensure_gpio_ready(self):
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is unavailable")

        if self._gpio_initialized and self._configured_gpio_pin == self.gpio_pin:
            return

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_pin, GPIO.OUT)
        inactive_state = GPIO.LOW if self.gpio_active_high else GPIO.HIGH
        GPIO.output(self.gpio_pin, inactive_state)
        self._gpio_initialized = True
        self._configured_gpio_pin = self.gpio_pin

    def close(self):
        if GPIO is None or not self._gpio_initialized:
            return
        try:
            inactive_state = GPIO.LOW if self.gpio_active_high else GPIO.HIGH
            GPIO.output(self.gpio_pin, inactive_state)
            GPIO.cleanup(self.gpio_pin)
        except Exception as e:
            print(f"Warning: GPIO cleanup failed: {e}")
        finally:
            self._gpio_initialized = False
            self._configured_gpio_pin = None


ESP32AlertClient = HardwareAlertClient
GPIOAlertClient = HardwareAlertClient
