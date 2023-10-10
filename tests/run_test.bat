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
::  MAX_KEYS    The maximum unique keys to use.
::  RUN_MINS    The maximum duration, in minutes, for this test run.

:: Setup the variable RUN_MAX_KEYS to be passed into the container composer.
SET RUN_MAX_KEYS=30

:: Setup the variable RUN_MINUTES  to be passed into the container composer.
SET RUN_MINUTES=3

:: Start of CLI.
:SOF_CLI
IF  /I "MAX_KEYS"=="%1" GOTO :SET_MAX_KEYS
IF  /I "RUN_MINS"=="%1" GOTO :SET_RUN_MINS
IF  /I         ""=="%1" GOTO :EOF_CLI

ECHO Invalid parameter value.  Try the following:
ECHO    %0  [MAX_KEYS ###] [RUN_MINS ###]
GOTO :EOF_SCRIPT

:SET_MAX_KEYS
SET RUN_MAX_KEYS=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_RUN_MINS
SET RUN_MINUTES=%2
SHIFT
SHIFT
GOTO :SOF_CLI
:: End of CLI.
:EOF_CLI


ECHO Running McCache test with envar:
ECHO    RUN_TIMESTAMP: %RUN_TIMESTAMP%
ECHO    RUN_MAX_KEYS:  %RUN_MAX_KEYS%
ECHO    RUN_MINUTES:   %RUN_MINUTES%
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
%CONTAINER_EXE% up  --build

:: Wait for the test run to be completed in the cluster and test the output log.
ECHO Run test using the output log from the cluster.
pipenv run  pytest -q .

:EOF_SCRIPT
POPD
