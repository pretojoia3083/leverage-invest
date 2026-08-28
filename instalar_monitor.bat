@echo off
echo ============================================
echo   LEVERAGE INVEST - Instalando MT5 Monitor
echo ============================================

REM Remove o servico antigo
sc stop LeverageInvestMT5 >nul 2>&1
sc delete LeverageInvestMT5 >nul 2>&1

REM Cria tarefa agendada que inicia com o Windows
schtasks /create /tn "LeverageInvestMT5" /tr "\"C:\Users\Renato\AppData\Local\Python\bin\python3-64.exe\" \"C:\Users\Renato\Desktop\projetos code ia\trading-dashboard\mt5_monitor.py\"" /sc onlogon /rl highest /f

REM Inicia agora
schtasks /run /tn "LeverageInvestMT5"

echo.
echo ============================================
echo   Monitor instalado e iniciado!
echo   Vai rodar toda vez que voce fizer login.
echo ============================================
pause
