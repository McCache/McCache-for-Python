:: SEE: https://ss64.com/nt/syntax-variables.html
:: Change the following to ECHO ON to trace the execution.
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
FOR /f "tokens=*" %%v in ('powershell get-date -format "{_yyyyMMdd_HHmmU}"') DO SET RUN_TIMESTAMP=%%v

ECHO Running McCache unit test with envar RUN_TIMESTAMP: %RUN_TIMESTAMP%
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

:: Change over to the directory where this script resides.
PUSHD %~p0

:: Create the log directory if it doesn't exist, else empty the directory before we start.
::
IF NOT EXIST  log (MD log) ELSE (DEL /q log\*)

:: Bring up the cluster of containers and wait until we are done exercising the cache.
::
ECHO Starting the test cluster.
PUSHD ..\Docker
%CONTAINER_EXE% up
POPD

:: Wait for the test run to be completed in the cluster and test the output log.
ECHO Run test using the output log from the cluster.
::pytest -q .

:EOF_SCRIPT
POPD
