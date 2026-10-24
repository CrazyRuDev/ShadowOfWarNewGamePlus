@echo off
chcp 65001 >nul
rem Сборка двух версий программы в dist\:
rem   1) dist\SoWNGPlus\ и dist\SoWNGPlus.zip - ПАПКА, для раздачи (VirusTotal 0): SoWNGPlus.exe = неизменённый
rem      AutoHotkey64.exe (сам запускает SoWNGPlus.ahk рядом), python\ - встраиваемый Python с python.org,
rem      engine\sowtool\ - исходники движка. Раздавать zip: в нём нет data\, летописи и ini.
rem   2) dist\single\SoWNGPlus.exe - ОДИН ФАЙЛ, для себя: Ahk2Exe + движок PyInstaller внутри. Антивирусы его
rem      помечают (VirusTotal 4-7/71) - не выкладывать.
rem Нужны: AutoHotkey v2 с компилятором Ahk2Exe (autohotkey.com; Ahk2Exe - через AutoHotkey Dash - Compile) и
rem Python 3 (python.org, галочка "Add python.exe to PATH") - для второй версии.
setlocal
cd /d "%~dp0"
set "PYVER=3.13.15"
set "WORK=%TEMP%\sowngp_build"
set "AHK=%ProgramFiles%\AutoHotkey"
if not exist "%AHK%\v2\AutoHotkey64.exe" set "AHK=%LocalAppData%\Programs\AutoHotkey"
if not exist "%AHK%\v2\AutoHotkey64.exe" (
  echo Не найден AutoHotkey v2 - установите его с autohotkey.com.
  goto :fail
)

echo === 1/2 Папка: dist\SoWNGPlus
if not exist vendor\python\python.exe (
  echo --- встраиваемый Python %PYVER% с python.org
  powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -Uri https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip -OutFile vendor_py.zip; Expand-Archive vendor_py.zip vendor\python -Force; Remove-Item vendor_py.zip" || goto :fail
)
set "D=dist\SoWNGPlus"
if not exist %D% mkdir %D%
rem программа обновляется, а data\, летопись\ и ini игрока остаются
for %%X in (engine python bases) do if exist %D%\%%X rmdir /s /q %D%\%%X
mkdir %D%\engine\sowtool
copy /y "%AHK%\v2\AutoHotkey64.exe" %D%\SoWNGPlus.exe >nul || goto :fail
copy /y "%AHK%\license.txt" %D%\AutoHotkey-license.txt >nul
copy /y gui\SoWNGPlus.ahk %D%\ >nul || goto :fail
xcopy /y /i /q /e vendor\python %D%\python >nul || goto :fail
rem путь к движку для встраиваемого Python (без него он видит только свою папку)
>>%D%\python\python313._pth echo ..\engine
copy /y engine\sowtool\*.py %D%\engine\sowtool\ >nul || goto :fail
xcopy /y /i /q gui\bases %D%\bases >nul || goto :fail
copy /y README.md %D%\ >nul
if exist ..\LICENSE copy /y ..\LICENSE %D%\ >nul
vendor\python\python.exe tools\pack.py || goto :fail

echo === 2/2 Один файл: dist\single\SoWNGPlus.exe
if not exist "%AHK%\Compiler\Ahk2Exe.exe" (
  echo Не найден Ahk2Exe. Откройте AutoHotkey Dash ^(меню Пуск^) - Compile - он предложит скачать компилятор.
  goto :fail
)
python -c "import PyInstaller" 2>nul || python -m pip install --upgrade pyinstaller || goto :fail
if not exist "%WORK%" mkdir "%WORK%"
pushd engine
python -m PyInstaller --onefile --console --name sowtool --distpath "%WORK%" --workpath "%WORK%\pyi" --specpath "%WORK%\pyi" sowtool_entry.py >"%WORK%\pyinstaller.log" 2>&1 || (popd & echo PyInstaller: см. %WORK%\pyinstaller.log & goto :fail)
popd
python tools\single_ahk.py "%WORK%\sowtool.exe" "%WORK%\SoWNGPlus.ahk" || goto :fail
if not exist dist\single mkdir dist\single
"%AHK%\Compiler\Ahk2Exe.exe" /in "%WORK%\SoWNGPlus.ahk" /out "%~dp0dist\single\SoWNGPlus.exe" /base "%AHK%\v2\AutoHotkey64.exe" /silent || goto :fail

echo === Проверка Защитником Windows
"%ProgramFiles%\Windows Defender\MpCmdRun.exe" -Scan -ScanType 3 -File "%~dp0dist\SoWNGPlus.zip" -DisableRemediation
"%ProgramFiles%\Windows Defender\MpCmdRun.exe" -Scan -ScanType 3 -File "%~dp0dist\single\SoWNGPlus.exe" -DisableRemediation

echo.
echo Готово:
echo   dist\SoWNGPlus\      - папка (запускать SoWNGPlus.exe); dist\SoWNGPlus.zip - её и выкладывать
echo   dist\single\SoWNGPlus.exe - один файл, для себя
pause
exit /b 0

:fail
echo.
echo Сборка остановилась с ошибкой - пришлите этот текст.
pause
exit /b 1
