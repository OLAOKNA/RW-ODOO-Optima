@echo off
.venv\Scripts\pyinstaller.exe --onedir --windowed --name "RW-ODOO-Optima" main.py
echo.
echo Plik exe znajduje sie w folderze dist\
pause
