import logging
import os
import platform
import socket
import sys
import threading
import time
from pathlib import Path
from shutil import copy2

import GPUtil
import psutil
import requests
import pystray
from PIL import Image, ImageDraw

APP_NAME = "FireDashClient"
LOG_DIR = Path.home() / '.fire_dash'
LOG_FILE = LOG_DIR / 'client.log'
INSTALL_FLAG = LOG_DIR / 'installed.flag'
SEND_INTERVAL_SECONDS = 60

LOG_DIR.mkdir(exist_ok=True)

with open(str(LOG_DIR / 'pid.txt'), 'w') as f:
    f.write(str(os.getpid()))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE)]
)


class FireDashClient:
    def __init__(self):
        self.stop_event = threading.Event()
        self.send_enabled = True
        self.send_lock = threading.Lock()
        self.worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
        self.icon = None

    def copy_to_autostart(self):
        exe_path = Path(sys.executable)
        if platform.system() == "Windows":
            startup = Path(os.getenv('APPDATA')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
            startup.mkdir(parents=True, exist_ok=True)

            if getattr(sys, 'frozen', False):
                target = startup / f"{APP_NAME}.exe"
                if not target.exists():
                    copy2(exe_path, target)
                    logging.info(f"Скопирован в автозапуск: {target}")
            else:
                target = startup / f"{APP_NAME}.vbs"
                pythonw = exe_path.with_name('pythonw.exe')
                script_path = Path(__file__).resolve()
                target.write_text(
                    f'Set WshShell = CreateObject("WScript.Shell")\n'
                    f'WshShell.Run "\"{pythonw}\" \"{script_path}\"", 0, False\n',
                    encoding='utf-8'
                )
                logging.info(f"Создан vbs-автозапуск: {target}")
        elif platform.system() == "Linux":
            autostart = Path.home() / '.config' / 'autostart'
            autostart.mkdir(parents=True, exist_ok=True)
            target = autostart / f"{APP_NAME}.desktop"
            target.write_text(f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec={exe_path}
Terminal=false
""")
            logging.info(f"Создан .desktop автозапуск: {target}")
        else:
            logging.warning("ОС не поддерживается")

    def install_if_needed(self):
        if not INSTALL_FLAG.exists():
            logging.info("Первая установка: добавляю в автозапуск...")
            self.copy_to_autostart()
            INSTALL_FLAG.write_text("installed")
            logging.info("Установка завершена.")

    def hide_console(self):
        if platform.system() != "Windows":
            return

        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
            logging.info("Консоль скрыта")

    def set_send_enabled(self, enabled: bool):
        with self.send_lock:
            self.send_enabled = enabled
        state = "включена" if enabled else "выключена"
        logging.info(f"Отправка данных {state}")

    def toggle_send(self, icon=None, item=None):
        with self.send_lock:
            self.send_enabled = not self.send_enabled
            enabled = self.send_enabled
        state = "включена" if enabled else "выключена"
        logging.info(f"Отправка данных {state}")

    def is_send_enabled(self, item=None):
        with self.send_lock:
            return self.send_enabled

    def get_top_processes(self, n=3):
        try:
            return [p.info['name'] for p in sorted(
                psutil.process_iter(['name', 'cpu_percent']),
                key=lambda x: x.info['cpu_percent'], reverse=True
            )[:n]]
        except Exception:
            return []

    def get_gpu_usage(self):
        try:
            gpus = GPUtil.getGPUs()
            return float(gpus[0].load * 100) if gpus else 0.0
        except Exception:
            return 0.0

    def collect_data(self):
        battery = psutil.sensors_battery()
        return {
            "device_name": socket.gethostname(),
            "os": platform.system(),
            "battery": int(battery.percent) if battery else 100,
            "cpu": psutil.cpu_percent(interval=1),
            "gpu": self.get_gpu_usage(),
            "uptime": time.strftime('%H:%M:%S', time.gmtime(time.time() - psutil.boot_time())),
            "top_processes": self.get_top_processes()
        }

    def send_log(self):
        try:
            data = self.collect_data()
            response = requests.post("http://localhost:8000/api/logs/", json=data, timeout=5)
            response.raise_for_status()
            logging.info(f"Данные отправлены: {data['device_name']} — OK")
        except Exception as e:
            logging.warning(f"Ошибка отправки: {e}")

    def worker_loop(self):
        while not self.stop_event.is_set():
            with self.send_lock:
                enabled = self.send_enabled

            if enabled:
                self.send_log()

            if self.stop_event.wait(SEND_INTERVAL_SECONDS):
                break

    def stop_app(self, icon=None, item=None):
        logging.info("Остановка клиента")
        self.stop_event.set()
        if self.icon:
            self.icon.stop()

    def create_tray_image(self):
        image = Image.new('RGB', (64, 64), color=(30, 30, 30))
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 56, 56), outline=(255, 80, 80), width=4)
        draw.rectangle((20, 20, 44, 44), fill=(255, 80, 80))
        return image

    def run(self):
        self.install_if_needed()
        self.hide_console()

        self.worker_thread.start()

        menu = pystray.Menu(
            pystray.MenuItem('Отправка включена', self.toggle_send, checked=self.is_send_enabled),
            pystray.MenuItem('Выключить отправку', lambda icon, item: self.set_send_enabled(False)),
            pystray.MenuItem('Включить отправку', lambda icon, item: self.set_send_enabled(True)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Выход', self.stop_app),
        )

        self.icon = pystray.Icon(APP_NAME, self.create_tray_image(), APP_NAME, menu)
        self.icon.run()
        self.worker_thread.join(timeout=5)


def main():
    FireDashClient().run()


if __name__ == '__main__':
    main()
