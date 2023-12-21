#   Steps to build and run this container.  You can either use podman or docker.
#
#$  podman  build   -t          mccache-img     .
#$  podman  run  -d --rm --name mccache-test    mccache-img
#$  podman  ps
#$  podman  exec    -it         mccache-test    bash
#$  podman  stop                mccache-test
#
#$  pipenv  install --dev       podman-compose
#$  podman-compose    up  -d
#$  podman-compose    down
#
#   SEE: https://dzone.com/articles/podman-compose-vs-docker-compose
#

#RG         IMAGE_VERSION=3.8.18
#RG         IMAGE_VERSION=3.9.18
#RG         IMAGE_VERSION=3.10.13
#RG         IMAGE_VERSION=3.11.6
ARG         IMAGE_VERSION=3.11.7
#RG         IMAGE_VERSION=3.12.0
#RG         IMAGE_VERSION=latest
#RG         IMAGE_VERSION=slim
FROM        python:${IMAGE_VERSION}

ENV         USRGRP=mccache
ENV         LANG    C.UTF-8

# Dont need the following if you are using the lastest image.
#
RUN         apt-get update
RUN         apt-get install -y  vim

# NOTE: If you get the following error, you don't have internet connection:
#       WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x7f2aa8378c50>: Failed to establish a new connection: [Errno -3] Temporary failure in name resolution')': /simple/pip
RUN         pip     install -U  pip

# Setup mccache user workspace.
#
RUN         useradd -U -md                      /home/${USRGRP} ${USRGRP}
WORKDIR     /home/${USRGRP}
# NOTE: Must copy all pertinent files.  If not "pip install -e ." will break.
#       There is a `.dockerignore` file that is used to filter out files of no interest to us.
COPY    .   /home/${USRGRP}

RUN         mkdir   -p  /var/log/${USRGRP}  \
        &&  chown   -R  ${USRGRP}:${USRGRP} /var/log/${USRGRP}
RUN         mkdir   -p  /home/${USRGRP}/log \
        &&  chown   -R  ${USRGRP}:${USRGRP} /home/${USRGRP}

# Get Python project dependencies ready.
#
USER        ${USRGRP}

# Install runtime dependencies.
#
RUN         pip     install -r  requirements.txt

# Pickup the McCache project from the source directory.
#
ENV         PYTHONPATH=/home/${USRGRP}/src

# Start the test run.
#
#MD         ["sleep" ,"5m"]
