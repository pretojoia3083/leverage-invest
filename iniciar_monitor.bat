@echo off
echo ============================================
echo   LEVERAGE INVEST - Iniciando MT5 Monitor
echo ============================================
sc start LeverageInvestMT5
echo.
sc query LeverageInvestMT5
echo.
echo ============================================
echo   Verificando status...
echo ============================================
pause
