@echo off
rem DKDS demo panelini baslatir: cift tikla.
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
    echo Sanal ortam bulunamadi. Once kurulum yapin: python -m venv .venv ve pip install -r requirements.txt
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
echo DKDS paneli aciliyor. Tarayici kendiliginden acilmazsa http://localhost:8501 adresine gidin.
echo Kapatmak icin bu pencereyi kapatin.
streamlit run app.py
pause
