@ECHO OFF

:: Setup the variable to be passed into the container composer.
FOR /f "tokens=*" %%v in ('powershell get-date -format "{_yyyyMMdd_HHmmU}"') DO SET RUN_TIMESTAMP=%%v

@ECHO Running McCache unit test with envar RUN_TIMESTAMP: %RUN_TIMESTAMP%
ECHO:

:: Bring up the cluster of containers.
::podman-compose up

:: Wait for the test run to be completed in the cluster and test the output log.
::pytest -q .
