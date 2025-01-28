:: Dependent on your environment having the Unix/Linux utilties.  SEE: Installing Git with Optional Unix tools.
:: SEE: https://ss64.com/nt/syntax-variables.html
:: Change the following to ECHO ON to trace the execution.
@ECHO OFF
::@ECHO ON
SET SCRIPT_NAME=%0

:: All variables set in this script shall be local variables.
SETLOCAL

:: Check if either podman or docker is installed.
::
WHERE podman.exe           2> NUL
IF %ERRORLEVEL% GTR 0 GOTO :DOCKER_COMPOSE_CHK

:PODMAN_COMPOSE_CHK
WHERE podman-compose.exe   2> NUL
IF %ERRORLEVEL% EQU 0 GOTO :EOF_PODMAN_CHK

:DOCKER_COMPOSE_CHK
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

:: Setup the variable RUN_TIMESTAMP to be passed into the container composer.
::
FOR /f "tokens=*" %%v IN ('powershell get-date -format "{_yyyyMMdd_HHmm}"') DO SET RUN_TIMESTAMP=%%v

:: Setup the variables to be passed into the container composer.
SET TEST_DEBUG_LEVEL=0
SET TEST_CLUSTER_SIZE=5
SET TEST_KEY_ENTRIES=200
SET TEST_APERTURE=0.05
SET TEST_DATA_SIZE_MIX=1
SET TEST_RUN_DURATION=5
SET TEST_MONKEY_TANTRUM=0
SET MCCACHE_CACHE_TTL=3600
SET MCCACHE_CACHE_MAX=256
SET MCCACHE_CACHE_SIZE=8388608
SET MCCACHE_CACHE_PULSE=5
SET MCCACHE_CALLBACK_WIN=0
SET MCCACHE_CRYPTO_KEY=


:: Start of CLI.
:: Parse the command line parameters with the following format:
:: run_test.bat [ key1 val1 [key2 val2 [key3 val3 [...]]]]
:: where the keys are case sensitive:
:SOF_CLI
:: Test CLI flags.
IF  "%~1"=="-D"  GOTO :SET_DOCKER_CONTAINER
IF  "%~1"=="-P"  GOTO :SET_PODMAN_CONTAINER
IF  "%~1"=="-L"  GOTO :SET_TEST_DEBUG_LEVEL
IF  "%~1"=="-C"  GOTO :SET_TEST_CLUSTER_SIZE
IF  "%~1"=="-K"  GOTO :SET_TEST_KEY_ENTRIES
IF  "%~1"=="-A"  GOTO :SET_TEST_APERTURE
IF  "%~1"=="-M"  GOTO :SET_TEST_DATA_SIZE_MIX
IF  "%~1"=="-R"  GOTO :SET_TEST_RUN_DURATION
IF  "%~1"=="-T"  GOTO :SET_TEST_MONKEY_TANTRUM
::  McCache config.
IF  "%~1"=="-e"  GOTO :SET_MCCACHE_CACHE_MAX
IF  "%~1"=="-s"  GOTO :SET_MCCACHE_CACHE_SIZE
IF  "%~1"=="-p"  GOTO :SET_MCCACHE_CACHE_PULSE
IF  "%~1"=="-t"  GOTO :SET_MCCACHE_CACHE_TTL
IF  "%~1"=="-w"  GOTO :SET_MCCACHE_CALLBACK_WIN
IF  "%~1"=="-k"  GOTO :SET_MCCACHE_CRYPTO_KEY


IF  "%~1"==""    GOTO :EOF_CLI

:HELP_SCREEN
ECHO Invalid parameter %~1 value.  Try the following:
ECHO %SCRIPT_NAME%  [-D ] [ -P] [-L #] [-C #] [-S #] [-M #] [-R #] [-T #]  [-t #] [-e #] [-s #] [-p #] [-w #] [-k #]
ECHO        Test configuration:
ECHO -D     Use Docker container.
ECHO -P     Use Podman container.
ECHO -L #   Debug level.            Default %TEST_DEBUG_LEVEL%.  0=Off ,1=Basic ,3=Extra ,5=Superfluous
ECHO -K #   Max key entries to use. Default %TEST_KEY_ENTRIES%
ECHO -C #   Cluster size.           Default %TEST_CLUSTER_SIZE%.  Max is 9.
ECHO -A #   Sleep aperture.         Default %TEST_APERTURE% second pause between operations.  1=1s ,0.1=100ms ,0.01=10ms ,0.001=1ms ,0.0005=0.5ms ,0.0001=0.1ms/100us
ECHO -M #   Data size mix.          Default %TEST_DATA_SIZE_MIX%.  1=Small ,2=Big ,3=Mix.
ECHO -R #   Run duration.           Default %TEST_RUN_DURATION% minutes.
ECHO -T #   Monkey tantrum.         Default %TEST_MONKEY_TANTRUM% percent of dropped packets.  0=Disabled.
ECHO        Test configuration:
ECHO -t #   Time-to-live.           Default %MCCACHE_CACHE_TTL% seconds.
ECHO -e #   Maximum cache entries.  Default %MCCACHE_CACHE_MAX% entries.
ECHO -s #   Maximum cache storage.  Default %MCCACHE_CACHE_SIZE% bytes.
ECHO -p #   Cache sync pulse.       Default %MCCACHE_CACHE_PULSE% seconds.
ECHO -w #   Callback spike window.  Default %MCCACHE_CALLBACK_WIN% seconds.
ECHO -k #   Cryptography key.       Default is none.  For testing, try:  "sjQNjXGt_AygJrrFUu7C5hN6voq9a9WBBorVXkuD3Xc="
GOTO :EOF_SCRIPT

:SET_DOCKER_CONTAINER
SET CONTAINER_EXE=podman-compose
WHERE docker.exe    2> NUL
IF %ERRORLEVEL% EQU 0 GOTO :EOF_SET_DOCKER_CONTAINER
ECHO docker executable NOT found!
GOTO :HELP_SCREEN
:EOF_SET_DOCKER_CONTAINER
SHIFT
GOTO :SOF_CLI

:SET_PODMAN_CONTAINER
SET CONTAINER_EXE=podman-compose
WHERE podman.exe    2> NUL
IF %ERRORLEVEL% EQU 0 GOTO :EOF_SET_PODMAN_CONTAINER
ECHO podman executable NOT found!
GOTO :HELP_SCREEN
:EOF_SET_PODMAN_CONTAINER
SHIFT
GOTO :SOF_CLI

:SET_TEST_DEBUG_LEVEL
SET  TEST_DEBUG_LEVEL=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_CLUSTER_SIZE
SET  TEST_CLUSTER_SIZE=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_KEY_ENTRIES
SET  TEST_KEY_ENTRIES=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_APERTURE
SET  TEST_APERTURE=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_DATA_SIZE_MIX
SET  TEST_DATA_SIZE_MIX=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_RUN_DURATION
SET  TEST_RUN_DURATION=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_TEST_MONKEY_TANTRUM
SET  TEST_MONKEY_TANTRUM=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_MCCACHE_CACHE_TTL
SET  MCCACHE_CACHE_TTL=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_MCCACHE_CACHE_MAX
SET  MCCACHE_CACHE_MAX=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_MCCACHE_CACHE_SIZE
SET  MCCACHE_CACHE_SIZE=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_MCCACHE_CACHE_PULSE
SET  MCCACHE_CACHE_PULSE=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_MCCACHE_CALLBACK_WIN
SET  MCCACHE_CALLBACK_WIN=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:SET_MCCACHE_CRYPTO_KEY
SET  MCCACHE_CRYPTO_KEY=%2
SHIFT
SHIFT
GOTO :SOF_CLI

:: End of CLI.
:EOF_CLI


ECHO Running McCache test with following environment variables:
ECHO    CONTAINER_EXE:          %CONTAINER_EXE%
ECHO    RUN_TIMESTAMP:          %RUN_TIMESTAMP%
ECHO    TEST_DEBUG_LEVEL:       %TEST_DEBUG_LEVEL%
ECHO    TEST_CLUSTER_SIZE:      %TEST_CLUSTER_SIZE%
ECHO    TEST_KEY_ENTRIES:       %TEST_KEY_ENTRIES%
ECHO    TEST_APERTURE:          %TEST_APERTURE%
ECHO    TEST_DATA_SIZE_MIX:     %TEST_DATA_SIZE_MIX%
ECHO    TEST_MONKEY_TANTRUM:    %TEST_MONKEY_TANTRUM%
ECHO    TEST_RUN_DURATION:      %TEST_RUN_DURATION%
ECHO    MCCACHE_CACHE_TTL:      %MCCACHE_CACHE_TTL%
ECHO    MCCACHE_CACHE_MAX:      %MCCACHE_CACHE_MAX%
ECHO    MCCACHE_CACHE_SIZE:     %MCCACHE_CACHE_SIZE%
ECHO    MCCACHE_CACHE_PULSE:    %MCCACHE_CACHE_PULSE%
ECHO    MCCACHE_CALLBACK_WIN:   %MCCACHE_CALLBACK_WIN%
ECHO    MCCACHE_CRYPTO_KEY:     %MCCACHE_CRYPTO_KEY%
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

:: Unset previously set env vars.
FOR /L %%v  IN ( 3 ,1 ,%TEST_CLUSTER_SIZE% )  DO  SET NODE0%%v=
FOR /L %%v  IN ( 1 ,1 ,%TEST_CLUSTER_SIZE% )  DO  SET NODE0%%v=node0%%v

:: Bring up the cluster of containers and wait until we are done exercising the cache.
::
ECHO Starting the test cluster with %TEST_CLUSTER_SIZE% nodes.
:: Keep in foregound with the maximum of 9 nodes as specified in "docker-compose.yml"
%CONTAINER_EXE% up  %NODE01% %NODE02% %NODE03% %NODE04% %NODE05% %NODE06% %NODE07% %NODE08% %NODE09%

:: Wait for the test run to be completed in the cluster and test the output log.
ECHO Run test using the output log from the cluster.

:: Extract out and clean up the INQ result from each of the debug log files into a result file.
:: NOTE: There is a embedded TAB character in the search string.
cat     log/*debug0*.log |grep -E "	INQ	|process|Done|Exiting" |grep -Ev "Fr:|Out going|Delete" |sed "/Exiting/a}" |sed "s/{/\n /" |sed "/[0-9]'}}$/s/},/}\n/g" |sed "s/'}}/'}}\n/"    |sed "s/}, /}, \n/g" > log/result.txt

:: Validate the stress test rsults.
pytest  tests\stress\test_stress.py log/result.txt

:: Sort the logs in chronological order.
sort    log/*.log   >log/chronological.txt

:: Extract details.
grep -iE  "after lookup|in the background"          log/chronological.txt   >log/detail_expire.log
grep -iE  "message queue size|done testing"         log/chronological.txt   >log/detail_queue_pressure.log
grep -iE  "sending local|requesting sender"         log/chronological.txt   >log/detail_synchronization.log
grep -iE  "cache incoherent"                        log/chronological.txt   >log/detail_incoherent.log
grep -iE  "monkey is angry"                         log/chronological.txt   >log/detail_drop_packets.log

:: Extract sumamries.
IF  %TEST_DEBUG_LEVEL%  GEQ 1   (
    :: Outbound Op codes.
    :: NOTE: There is a embedded TAB character in the search string.
    cat log/chronological.txt   |grep " Im:" |grep -vE "	Fr:|	>"  |awk 'BEGIN{ FS="\t"}  $3 ~ /[A-Z]+/  {print $3}'  |sort   |uniq -c    >log/sumamry_opcode.log
)

:EOF_SCRIPT
POPD
::Restore all variables from the start of SETLOCAL.
ENDLOCAL
