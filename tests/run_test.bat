:: SEE: https://ss64.com/nt/syntax-variables.html
:: Change the following to ECHO ON to trace the execution.
@ECHO OFF
@ECHO ON

:: Check if either podman or docker is installed.
::
WHERE podman-compose.exe   2> NUL
IF %ERRORLEVEL% EQU 0 GOTO :EOF_PODMAN_CHK

WHERE docker-compose.exe   2> NUL
IF %ERRORLEVEL% EQU 0 GOTO :EOF_DOCKER_CHK

ECHO ERROR! Neither podman-compose or docker-compose is setup in your PATH.  Cannot continue ...
GOTO :EOF_SCRIPT

:EOF_PODMAN_CHK
SET CONTAINER_EXE=podman-compose
GOTO :EOF_CON_CHK

:EOF_DOCKER_CHK
SET CONTAINER_EXE=docker-compose

:EOF_CON_CHK
::ECHO %CONTAINER_EXE%


:: Setup the variable RUN_TIMESTAMP to be passed into the container composer.
::
FOR /f "tokens=*" %%v IN ('powershell get-date -format "{_yyyyMMdd_HHmm}"') DO SET RUN_TIMESTAMP=%%v

:: Parse the command line parameters with the following format:
:: run_test.bat [ key1 val1 [key2 val2 [key3 val3 [...]]]]
:: where the case insensitive keys:
::  TEST_MAX_ENTRIES    The maximum unique keys to use.
::  TEST_RUN_DURATION   The maximum duration, in minutes, for this test run.
::  TEST_SLEEP_SPAN     The maximum range for the random duration to sleep.
::  TEST_SLEEP_UNIT     The unit for the sleep duration. 1 = 1s ,10 = 0.1s ,100 = 0.01s ,1000 = 0.001s
::  TEST_MONKEY_TANTRUM The maximum percentage of simulated drop packets. 0-20

:: Setup the variable TEST_MAX_ENTRIES to be passed into the container composer.
SET TEST_MAX_ENTRIES=30

:: Setup the variable TEST_RUN_DURATION to be passed into the container composer.
SET TEST_RUN_DURATION=3

:: Setup the variable TEST_SLEEP_SPAN to be passed into the container composer.
SET TEST_SLEEP_SPAN=75

:: Setup the variable TEST_SLEEP_SPAN to be passed into the container composer.
SET TEST_SLEEP_UNIT=100

:: Setup the variable TEST_MONKEY_TANTRUM to be passed into the container composer.
SET TEST_MONKEY_TANTRUM=0

:: Start of CLI.
:SOF_CLI
IF  /I "TEST_MAX_ENTRIES"   =="%1" GOTO :SET_TEST_MAX_ENTRIES
IF  /I "TEST_RUN_DURATION"  =="%1" GOTO :SET_TEST_RUN_DURATION
IF  /I "TEST_SLEEP_SPAN"    =="%1" GOTO :SET_TEST_SLEEP_SPAN
IF  /I "TEST_SLEEP_UNIT"    =="%1" GOTO :SET_TEST_SLEEP_UNIT
IF  /I "TEST_MONKEY_TANTRUM"=="%1" GOTO :SET_TEST_MONKEY_TANTRUM
IF  /I ""                   =="%1" GOTO :EOF_CLI

ECHO Invalid parameter value.  Try the following:
ECHO    %0  [TEST_MAX_ENTRIES ###] [TEST_RUN_DURATION ###] [TEST_SLEEP_SPAN ###] [TEST_SLEEP_UNIT ###]
GOTO :EOF_SCRIPT

:SET_TEST_MAX_ENTRIES
SET TEST_MAX_ENTRIES=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_RUN_DURATION
SET TEST_RUN_DURATION=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_SLEEP_SPAN
SET TEST_SLEEP_SPAN=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_SLEEP_UNIT
SET TEST_SLEEP_UNIT=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_MONKEY_TANTRUM
SET TEST_MONKEY_TANTRUM=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:: End of CLI.
:EOF_CLI


ECHO Running McCache test with envar:
ECHO    RUN_TIMESTAMP:      %RUN_TIMESTAMP%
ECHO    TEST_MAX_ENTRIES:   %TEST_MAX_ENTRIES%
ECHO    TEST_RUN_DURATION:  %TEST_RUN_DURATION%
ECHO    TEST_SLEEP_SPAN:    %TEST_SLEEP_SPAN%
ECHO    TEST_SLEEP_UNIT:    %TEST_SLEEP_UNIT%
ECHO    TEST_MONKEY_TANTRUM:%TEST_MONKEY_TANTRUM%
ECHO:

:: The following are CLI input parameter you can use to parse out the script name information.
:: ECHO From Dir:     %CD%
:: ECHO Script:       %0
:: ECHO Full path:    %~f0
:: ECHO Drive:        %~d0
:: ECHO Path:         %~p0
:: ECHO Filename:     %~n0
:: ECHO Extension:    %~x0
:: ECHO:

:: Change over to the project root directory no matter where this script is invoked.
SET     ROOTDIR=%~p0
SET     ROOTDIR=%ROOT:tests\=%
PUSHD  %ROOTDIR%

:: Create the log directory if it doesn't exist, else empty the directory before we start.
::
IF NOT EXIST  log (MD log) ELSE (DEL /q log\*)

:: Bring up the cluster of containers and wait until we are done exercising the cache.
::
ECHO Starting the test cluster.
:: Keep in forgound
%CONTAINER_EXE% up      &:: Keep in foreground.

:: Wait for the test run to be completed in the cluster and test the output log.
ECHO Run test using the output log from the cluster.
pipenv run  pytest -q .

:EOF_SCRIPT
POPD
