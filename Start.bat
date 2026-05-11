@echo off
:: --- CONFIGURATION ---
:: If the server is not in the same folder, put the full path here.
:: For REBOOT_TIME set your server time 
:: log port=default is 7777  queryport=default is 27015"
set "EXE_NAME=HumanitZServer.exe"
set "ARGS=-log port=  queryport="
set "REBOOT_TIME=00:00"
:: ---------------------

:start_server
cls
echo [%date% %time%] Server launch...
start "" "%EXE_NAME%" %ARGS%

:check_loop
:: 60 SECOND WAIT
timeout /t 60 /nobreak > nul

:: 1. CRASH VERIFICATION
tasklist /FI "IMAGENAME eq %EXE_NAME%" | find /I "%EXE_NAME%" > nul
if errorlevel 1 (
    echo [%time%] SERVER CRASH ! Restarting...
    goto start_server
)

:: 2. TIME CHECK (HH:MM format)
set "curtime=%time:~0,5%"
set "curtime=%curtime: =0%"

if "%curtime%"=="%REBOOT_TIME%" (
    timeout /t 5 /nobreak > nul
    :: --- RCON SCRIPT CALL ---
    echo Sending the RCON SAVE and RESTART command...
    python humanitz_rcon.py
)

:: Back to the loop
goto check_loop
