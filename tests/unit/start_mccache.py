import base64
import datetime
import hashlib
import logging
import os
import pickle   # noqa: B403
import random
import socket
import time

import mccache as mc

# Initialization section.
#
rndseed = 17
if 'MCCACHE_RANDOM_SEED' in os.environ:
    rndseed = int(os.environ['MCCACHE_RANDOM_SEED'])
else:
    rndseed = int(str(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET )[0][4][0]).split(".")[3])
random.seed( rndseed )

entries = 100
if 'MCCACHE_MAX_ENTRIES' in os.environ:
    entries = int(os.environ['MCCACHE_MAX_ENTRIES'])

duration = 1    # One minute.
if 'MCCACHE_RUN_DURATION' in os.environ:
    duration = int(os.environ['MCCACHE_RUN_DURATION'])  # In minutes.

for h in mc.logger.handlers:
    if  h.formatter._fmt == mc.LOG_FORMAT.replace('{__app__}' ,mc.__app__):
        h.formatter._fmt = "%(lineno)04d %(asctime)s.%(msecs)03d %(message)s"
        h.formatter._style._fmt = "%(lineno)05d %(asctime)s.%(msecs)03d %(message)s"
        # If debugging, output line number of source file for easy reference
        # h.formatter._fmt = "%(lineno)04d %(asctime)s.%(msecs)03d %(message)s"
        # h.formatter._style._fmt = "%(lineno)05d %(asctime)s.%(msecs)03d %(message)s"

cache = mc.get_cache()
bgn = time.time()
time.sleep( 1 )
end = time.time()

# Random test section.
#
mc.logger.setLevel( logging.DEBUG ) # Enable detail logging in McCache for testing.
mc.logger.info(f"Start testing with: Random seed={rndseed:3} Duration={duration:3} min.")

while (end - bgn) < (duration*60):   # Seconds.
    time.sleep( random.randint(1 ,60)/1000.0 )  # Milliseconds
    key = f'K{int((time.time_ns() /100)  %entries):03}'
    opc = random.randint( 0 ,15 )
    match opc:
        case 0:
            if  key in cache:
                # Evict cache.
                del cache[ key ]
        case 1|2|3:
            if  key not in cache:
                # Insert cache.
                cache[ key ] = datetime.datetime.utcnow()
        case 4|5|6|7|8: # Simulate much more updates than inserts.
            if  key in cache:
                # Update cache.
                cache[ key ] = datetime.datetime.utcnow()
        case _:
            # Look up cache.
            _ = cache.get( key ,None )
    end = time.time()

stats = mc._get_cache_metrics()
mc.logger.info(f"Cache stats. {stats}")
mc.logger.info(f"Done  testing.")
