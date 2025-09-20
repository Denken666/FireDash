import psutil, GPUtil, time, requests, socket, platform, logging, os, sys
from pathlib import Path
from shutil import copy2

APP_NAME = "FireDashClient"
LOG_DIR = Path.home() / '.fire_dash'
LOG_FILE = LOG_DIR / 'client.log'
INSTALL_FLAG = LOG_DIR / 'installed.flag'
LOG_DIR.mkdir(exist_ok=True)

with open(str(Path.home() / '.fire_dash' / 'pid.txt'), 'w') as f:
    f.write(str(os.getpid()))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE)]
)

def copy_to_autostart():
    exe_path = Path(sys.executable)
    if platform.system() == "Windows":
        startup = Path(os.getenv('APPDATA')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
        startup.mkdir(parents=True, exist_ok=True)
        target = startup / f"{APP_NAME}.exe"
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
        return
    else:
        logging.warning("ОС не поддерживается")
        return

    if not target.exists():
        try:
            copy2(exe_path, target)
            logging.info(f"Скопирован в автозапуск: {target}")
        except Exception as e:
            logging.error(f"Ошибка копирования: {e}")

def install_if_needed():
    if not INSTALL_FLAG.exists():
        logging.info("Первая установка: добавляю в автозапуск...")
        copy_to_autostart()
        INSTALL_FLAG.write_text("installed")
        logging.info("Установка завершена.")

def detach_console():
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.kernel32.FreeConsole()
        except: pass
    elif platform.system() == "Linux":
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
            os.setsid()
        except: pass

def get_top_processes(n=3):
    try:
        return [p.info['name'] for p in sorted(
            psutil.process_iter(['name', 'cpu_percent']),
            key=lambda x: x.info['cpu_percent'], reverse=True
        )[:n]]
    except: return []

def get_gpu_usage():
    try:
        gpus = GPUtil.getGPUs()
        return float(gpus[0].load * 100) if gpus else 0.0
    except: return 0.0

def collect_data():
    return {
        "device_name": socket.gethostname(),
        "os": platform.system(),
        "battery": int(psutil.sensors_battery().percent) if psutil.sensors_battery() else 100,
        "cpu": psutil.cpu_percent(interval=1),
        "gpu": get_gpu_usage(),
        "uptime": time.strftime('%H:%M:%S', time.gmtime(time.time() - psutil.boot_time())),
        "top_processes": get_top_processes()
    }

def send_log():
    try:
        data = collect_data()
        r = requests.post("http://localhost:8000/api/logs/", json=data, timeout=5)
        r.raise_for_status()
        logging.info(f"Данные отправлены: {data['device_name']} — OK")
    except Exception as e:
        logging.warning(f"Ошибка отправки: {e}")

def main():
    install_if_needed()
    detach_console()
    while True:
        send_log()
        time.sleep(60)

if __name__ == '__main__':
    main()
