@echo off
echo ============================================
echo   LEVERAGE INVEST - Reinstalando Monitor
echo ============================================
schtasks /end /tn "LeverageInvestMT5" >nul 2>&1
schtasks /delete /tn "LeverageInvestMT5" /f >nul 2>&1
schtasks /create /tn "LeverageInvestMT5" /tr "\"C:\Users\Renato\AppData\Local\Python\bin\python3-64.exe\" \"C:\Users\Renato\Desktop\projetos code ia\trading-dashboard\mt5_monitor.py\"" /sc onlogon /rl highest /f
schtasks /run /tn "LeverageInvestMT5"
echo.
echo ============================================
echo   Monitor reiniciado!
echo ============================================
pause
