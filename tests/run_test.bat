:: Dependent on your environment having the Unix/Linux utilties.  SEE: Installing Git with Optional Unix tools.
:: SEE: https://ss64.com/nt/syntax-variables.html
:: Change the following to ECHO ON to trace the execution.
@ECHO OFF
::@ECHO ON

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
SET TEST_MAX_ENTRIES=100

:: Setup the variable TEST_RUN_DURATION to be passed into the container composer.
SET TEST_RUN_DURATION=5

:: Setup the variable TEST_SLEEP_SPAN to be passed into the container composer.
SET TEST_SLEEP_SPAN=100

:: Setup the variable TEST_SLEEP_SPAN to be passed into the container composer.
SET TEST_SLEEP_UNIT=100

:: Setup the variable TEST_MONKEY_TANTRUM to be passed into the container composer.
SET TEST_MONKEY_TANTRUM=0

:: Setup the variable TEST_CLUSTER_SIZE to be passed into the container composer.
SET TEST_CLUSTER_SIZE=3


:: Start of CLI.
:SOF_CLI
IF  /I "%~1"=="-k"  GOTO :SET_TEST_MAX_ENTRIES
IF  /I "%~1"=="-d"  GOTO :SET_TEST_RUN_DURATION
IF  /I "%~1"=="-s"  GOTO :SET_TEST_SLEEP_SPAN
IF  /I "%~1"=="-u"  GOTO :SET_TEST_SLEEP_UNIT
IF  /I "%~1"=="-m"  GOTO :SET_TEST_MONKEY_TANTRUM
IF  /I "%~1"=="-c"  GOTO :SET_TEST_CLUSTER_SIZE
IF  /I "%~1"==""    GOTO :EOF_CLI

ECHO Invalid parameter value.  Try the following:
ECHO %0  [-k ###] [-m ###] [-s ###] [-u ###] [-m ###] [-c ###]
ECHO -k ###  Max entries.    Default 100.
ECHO -d ###  Run duration.   Default 5 minutes.
ECHO -s ###  Sleep span.     Default 100.
ECHO -u ###  Sleep unit.     Default 100.
ECHO -m ###  Monkey tantrum. Default 0.
ECHO -c ###  Cluster size.   Default 3.  Max is 9.
GOTO :EOF_SCRIPT

:SET_TEST_MAX_ENTRIES
SET  TEST_MAX_ENTRIES=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_RUN_DURATION
SET  TEST_RUN_DURATION=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_SLEEP_SPAN
SET  TEST_SLEEP_SPAN=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_SLEEP_UNIT
SET  TEST_SLEEP_UNIT=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_MONKEY_TANTRUM
SET  TEST_MONKEY_TANTRUM=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_CLUSTER_SIZE
SET  TEST_CLUSTER_SIZE=%2
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
ECHO    TEST_CLUSTER_SIZE:  %TEST_CLUSTER_SIZE%
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
SET     ROOTDIR=%ROOTDIR:tests\=%
PUSHD  %ROOTDIR%

:: Create the log directory if it doesn't exist, else empty the directory before we start.
::
IF NOT EXIST  log (MD log) ELSE (DEL /q log\*)

:: Initialize a minimum of two nodes.
SET  NODE01=node01
SET  NODE02=node02

FOR /L %%v  IN ( 1 ,1 ,%TEST_CLUSTER_SIZE% )  DO  SET NODE0%%v=node0%%v

:: Bring up the cluster of containers and wait until we are done exercising the cache.
::
ECHO Starting the test cluster with %TEST_CLUSTER_SIZE% nodes.
:: Keep in foregound with the maximum of 9 nodes as specified in "docker-compose.yml"
%CONTAINER_EXE% up  %NODE01% %NODE02% %NODE03% %NODE04% %NODE05% %NODE06% %NODE07% %NODE08% %NODE09%

:: Wait for the test run to be completed in the cluster and test the output log.
ECHO Run test using the output log from the cluster.

:: Extract out and clean up the INQ result from each of the debug log files into a result file.
tail log/debug0*.log |grep "INQ" |grep -Ev "Fr:|Multicasted" |sed "s/{/\n  /" |tr "}" "\n"  > log/result.txt

:: pipenv run  pytest -q .

:EOF_SCRIPT
POPD
