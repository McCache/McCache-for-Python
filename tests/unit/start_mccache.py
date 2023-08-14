import datetime
import logging
import os
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

cache = mc.getCache()
mid = f"{mc.ipV4}:{os.getpid()}"  # My ID.
bgn = time.time()
time.sleep( 1 )
end = time.time()

# Random test section.
#
mc.logger.setLevel( logging.DEBUG ) # Enable detail logging in McCache for testing.
mc.logger.info(f"Start testing with: Random seed={rndseed:3} Duration={duration:3} min.")

while (end - bgn) < (duration*60):   # Seconds.
    time.sleep( random.randint(1 ,16)/10.0 )
    key = int((time.time_ns() /100) %entries)
    opc = random.randint(0 ,10)
    match opc:
        case 0:
            if  key in cache:
                # Evict cache.
                del cache[key]
        case 1|2:
            if  key not in cache:
                # Insert cache.
                cache[key] = datetime.datetime.utcnow()
        case 3|4|5|6:
            if  key in cache:
                # Update cache.
                cache[key] = datetime.datetime.utcnow()
        case _:
            # Look up cache.
            _ = cache.get( key ,None )
    end = time.time()

c = sorted( cache.items() ,lambda item: item[0] )
mc.logger.debug(f"Im:{mid} Msg:{(mc.OpCode.QRY.name ,None ,cache.name ,None ,c)}" ,extra=mc.LOG_XTR)
mc.logger.info(f"Done  testing.")
