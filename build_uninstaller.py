# build_uninstaller.py
import PyInstaller.__main__
import os
import shutil
from pathlib import Path

def build():
    print("Building uninstaller...")
    
    # Собираем EXE
    PyInstaller.__main__.run([
    '--onefile',
    '--noconsole',
    '--name=FireDashUninstaller',
    'uninstaller.py'
])
    
    # Переносим в папку dist
    dist_path = Path("dist") / "FireDashUninstaller.exe"
    if dist_path.exists():
        print(f"\nSuccess! Uninstaller created at:\n{dist_path}")
    else:
        print("\nError: Uninstaller was not created")

if __name__ == "__main__":
    build()