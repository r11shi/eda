@echo off
rem Double-click: run or show ONE part of the project at a time (start the servers first with Start_Project.cmd).
cd /d "%~dp0"
:menu
cls
echo.
echo   FOOD SAFETY ANALYTICS - run or show one part at a time
echo   ------------------------------------------------------
echo    0  Are the servers running?
echo.
echo    RUN A PART (real output, about 1 minute each unless noted)
echo    1  Part A  clean the data + EDA charts
echo    2  Part B  build the star schema and load it (+ compare designs)
echo    3  Part C  the 5 checks, 10 business questions, indexes
echo    4  Part F  OLAP queries + build the dashboard
echo    5  The analytics table the models read
echo    6  Part G  regression
echo    7  Part H  association rules
echo    8  Part I  decision tree            (about 2 minutes)
echo    9  Part D  Citus distributed test   (about 5 minutes)
echo   10  Part E  real-time replay         (about 3 minutes, watch Grafana)
echo.
echo    SHOW (changes nothing)
echo   11  the data files          12  the warehouse tables
echo   13  the Citus cluster       14  the real-time data in ClickHouse
echo.
echo    Q  quit
echo.
set "c="
set /p c=  Choose:
if /i "%c%"=="q" exit /b
set "p="
if "%c%"=="0" set p=status
if "%c%"=="1" set p=A
if "%c%"=="2" set p=B
if "%c%"=="3" set p=C
if "%c%"=="4" set p=F
if "%c%"=="5" set p=mart
if "%c%"=="6" set p=G
if "%c%"=="7" set p=H
if "%c%"=="8" set p=I
if "%c%"=="9" set p=D
if "%c%"=="10" set p=E
if "%c%"=="11" set p=data
if "%c%"=="12" set p=db
if "%c%"=="13" set p=citus
if "%c%"=="14" set p=clickhouse
if "%p%"=="" goto menu
wsl -d Ubuntu -u root --cd "%~dp0" -- bash scripts/part.sh %p%
echo.
echo   Done. Press any key to go back to the menu.
pause >nul
goto menu
