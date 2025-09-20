import os
import shutil
import platform
import subprocess
import psutil
import winreg
from pathlib import Path
import ctypes

APP_NAME = "FireDash Client"
INSTALL_DIR = Path.home() / ".fire_dash"
CLIENT_EXE = "FireDashClient.exe"
SCHEDULED_TASK_NAME = "FireDashClientTask"  # если создавался планировщик
REG_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
]


def kill_processes():
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if proc.info["name"] and CLIENT_EXE.lower() in proc.info["name"].lower():
                proc.kill()
        except:
            pass


def delete_startup_shortcut():
    startup_path = Path(os.getenv("APPDATA")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    (startup_path / CLIENT_EXE).unlink(missing_ok=True)


def delete_registry_autorun():
    for hive, path in REG_KEYS:
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS) as key:
                i = 0
                while True:
                    try:
                        name, _, _ = winreg.EnumValue(key, i)
                        if "firedash" in name.lower():
                            winreg.DeleteValue(key, name)
                        else:
                            i += 1
                    except OSError:
                        break
        except FileNotFoundError:
            pass


def delete_scheduled_task():
    try:
        subprocess.run(["schtasks", "/Delete", "/TN", SCHEDULED_TASK_NAME, "/F"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass


def delete_installation():
    shutil.rmtree(INSTALL_DIR, ignore_errors=True)


def silent_uninstall():
    kill_processes()
    delete_startup_shortcut()
    delete_registry_autorun()
    delete_scheduled_task()
    delete_installation()


if __name__ == "__main__":
    if platform.system() == "Windows":
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    silent_uninstall()
