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
if 'TEST_RANDOM_SEED' in os.environ:
    rndseed = int(os.environ['TEST_RANDOM_SEED'])
else:
    rndseed = int(str(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET )[0][4][0]).split(".")[3])
random.seed( rndseed )

sleepspan = 50  # 1000 = 1sec
if 'TEST_SLEEP_SPAN'  in os.environ:
    sleepspan = int(os.environ['TEST_SLEEP_SPAN'])    # In seconds.

sleepunit = 100 # 1000 = 0.001s ,100 = 0.01s ,10 = 0.1s ,1 = 1s
if 'TEST_SLEEP_UNIT'  in os.environ:
    sleepunit = int(os.environ['TEST_SLEEP_GRAIN'])

entries = 100
if 'TEST_MAX_ENTRIES' in os.environ:
    entries = int(os.environ['TEST_MAX_ENTRIES'])

duration = 5    # Five minute.
if 'TEST_RUN_DURATION' in os.environ:
    duration = int(os.environ['TEST_RUN_DURATION'])  # In minutes.

for h in mc.logger.handlers:
    if  h.formatter._fmt == mc.LOG_FORMAT.replace('{__app__}' ,mc.__app__):
        h.formatter._fmt = "%(asctime)s.%(msecs)03d L#%(lineno)04d %(message)s"
        h.formatter._style._fmt = "%(asctime)s.%(msecs)03d L#%(lineno)04d %(message)s"

NEXT_SSEC = 3   # Synchronize seconds.
cache = mc.get_cache()
bgn = time.time()
bgnsec = time.localtime().tm_sec
time.sleep( bgnsec +(NEXT_SSEC - (bgnsec % NEXT_SSEC)) )    # Try to get the cluster to start at the same second to reduce RAK.
end = time.time()

# Random test section.
#
mc.logger.setLevel( logging.DEBUG ) # Enable detail logging in McCache for testing.
mc.logger.info(f"Start testing with: Random seed={rndseed:3} Duration={duration:3} min.")

ctr = 0 # Counter
while (end - bgn) < (duration*60):   # Seconds.
    time.sleep( random.randint(1 ,sleepspan) / sleepunit )
    ctr += 1
    key = f'K{int((time.time_ns()/100) % entries):04}'
    opc = random.randint( 0 ,20 )
    match opc:
        case 0:
            if  key in cache:
                # Evict cache.
                del cache[ key ]
            # Inquire a snapshot of the cache from all members including myself.
            # mc.get_cache_checksum( cache.name )
        case 1|2|3:
            if  key not in cache:
                # Insert cache.
                cache[ key ] = (datetime.datetime.utcnow() ,ctr)
        case 4|5|6|7|8: # Simulate much more updates than inserts.
            if  key in cache:
                # Update cache.
                cache[ key ] = (datetime.datetime.utcnow() ,ctr)
        case _:
            # Look up cache.
            _ = cache.get( key ,None )
    end = time.time()

# Wait for all members to catch up before existing together.
bgn = time.time()
bgnsec = time.localtime().tm_sec
time.sleep( bgnsec +(NEXT_SSEC - (bgnsec % NEXT_SSEC)) )    # Try to get the cluster to stop at the same second to reduce RAK.
end = time.time()

# Format ouput to be consistent with the McCache log format.
msg = (mc.OpCode.NOP ,None ,None ,None ,None ,'Done  testing.')
mc.logger.info(f"Im:{mc.SRC_IP_ADD}\t   {mc.FRM_IP_PAD}\tMsg:{msg}" ,extra=mc.LOG_EXTRA)

mc.get_cache_checksum()
