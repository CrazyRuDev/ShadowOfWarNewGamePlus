@echo off
rem Builds NGPlusLevels.dll (a Middle-earth Mod Loader plugin) with the Visual Studio 2022 Build Tools.
setlocal
set VS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
if not exist build mkdir build
cl /nologo /LD /O2 /EHsc /MT /W3 /std:c++17 ngplus_levels.cpp /Fe:build\NGPlusLevels.dll /Fo:build\ /link /NOLOGO || exit /b 1
echo built: %~dp0build\NGPlusLevels.dll
