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

#RG         IMAGE_VERSION=latest
ARG         IMAGE_VERSION=slim
FROM        python:${IMAGE_VERSION}

ENV         USRGRP=mccache
ENV         LANG    C.UTF-8

RUN         apt-get update
#UN         apt-get install -y  iproute2  vim
RUN         pip     install     pipenv

# Setup mccache user workspace.
#
RUN         useradd -U -md  /home/${USRGRP} ${USRGRP}
WORKDIR     /home/${USRGRP}
COPY    .   /home/${USRGRP}
RUN         mkdir   -p  /var/log/${USRGRP}  \
        &&  chown   -R  ${USRGRP}:${USRGRP} /var/log/${USRGRP}
RUN         mkdir   -p  /home/${USRGRP}/log \
        &&  chown   -R  ${USRGRP}:${USRGRP} /home/${USRGRP}

# Get Python project dependencies ready.
#
USER        ${USRGRP}
RUN         pipenv  install
RUN         pipenv  check

# Start the test run.
#
CMD         ["sleep" ,"60m"]
