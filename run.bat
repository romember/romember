@echo off
rem One-command runner for the trading ruleset agent (native Windows).
rem
rem   run.bat                      -> offline demo (no keys, no network)
rem   run.bat AAPL NVDA            -> screen live tickers via Yahoo Finance
rem   run.bat --config config.yaml AAPL
rem   run.bat --provider alphavantage AAPL
rem
rem On first run it creates a virtualenv in .venv and installs dependencies.
rem Set ANTHROPIC_API_KEY to enable the Claude qualitative layer.
setlocal
cd /d "%~dp0"

if not defined PYTHON set "PYTHON=python"
set "VENV=.venv"

if not exist "%VENV%\" (
  echo [setup] creating virtualenv in %VENV% ...
  %PYTHON% -m venv "%VENV%" || goto :error
  call "%VENV%\Scripts\activate.bat"
  echo [setup] installing dependencies ...
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt || goto :error
) else (
  call "%VENV%\Scripts\activate.bat"
)

if "%~1"=="" (
  echo [demo] no tickers given -- running the offline sample screen.
  echo        pass ticker symbols to screen live data, e.g. run.bat AAPL
  echo.
  python -m trading_agent --no-ai --from-json examples\sample_stocks.json GOODCO PARABOLIC CRYPTOX
  goto :eof
)

python -m trading_agent %*
goto :eof

:error
echo [error] setup failed.
exit /b 1
