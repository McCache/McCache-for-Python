#   Steps to build and run this container.  You can either use podman or docker.
#
#$  podman  build   -t          mccache-img     .
#$  podman  run  -d --rm --name mccache-test    mccache-img
#$  podman  ps
#$  podman  exec    -it         mccache-test    bash
#$  podman  stop                mccache-test
#
#$  pipenv  install     --dev   podman-compose
#$  podman-compose  up  -d
#$  podman-compose  down
#
#   SEE: https://dzone.com/articles/podman-compose-vs-docker-compose
#

ARG         IMAGE_VERSION=latest
#RG         IMAGE_VERSION=slim
#RG         IMAGE_VERSION=3.11.4
FROM        python:${IMAGE_VERSION}

ENV         USRGRP=mccache
ENV         LANG    C.UTF-8

# Dont need the following if you are using the lastest image.
#
#UN         apt-get update
#UN         apt-get install -y  vim
#UN         pip     install -U  pip

# Setup mccache user workspace.
#
RUN         useradd -U -md                      /home/${USRGRP} ${USRGRP}
WORKDIR     /home/${USRGRP}
COPY       .                                    /home/${USRGRP}
COPY       ./tests/unit/start_mccache.py        /home/${USRGRP}

RUN         mkdir   -p  /var/log/${USRGRP}  \
        &&  chown   -R  ${USRGRP}:${USRGRP} /var/log/${USRGRP}
RUN         mkdir   -p  /home/${USRGRP}/log \
        &&  chown   -R  ${USRGRP}:${USRGRP} /home/${USRGRP}

# Get Python project dependencies ready.
#
USER        ${USRGRP}

# Install the McCache project using pyproject.toml
#
# Debug why it breaks the build.
#UN         pip         install -e .

# Start the test run.
#
CMD         ["sleep" ,"60m"]
