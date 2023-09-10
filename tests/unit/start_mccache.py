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

for h in mc.logger.handlers:
    if  h.formatter._fmt == mc.LOG_FORMAT.replace('{__app__}' ,mc.__app__):
        h.formatter._fmt = "%(asctime)s.%(msecs)03d %(message)s"
        h.formatter._style._fmt = "%(asctime)s.%(msecs)03d %(message)s"

cache = mc.get_cache()
bgn = time.time()
time.sleep( 1 )
end = time.time()

# Random test section.
#
mc.logger.setLevel( logging.DEBUG ) # Enable detail logging in McCache for testing.
mc.logger.info(f"Start testing with: Random seed={rndseed:3} Duration={duration:3} min.")

stats = {
    'get': 0,
    'ins': 0,
    'upd': 0,
    'del': 0,
}
while (end - bgn) < (duration*60):   # Seconds.
    time.sleep( random.randint(1 ,70)/1000.0 )
    key = int((time.time_ns() /100)  %entries)
    opc = random.randint(0 ,13)
    match opc:
        case 0:
            if  key in cache:
                # Evict cache.
                del cache[key]
                stats['del'] += 1
        case 1|2:
            if  key not in cache:
                # Insert cache.
                cache[key] = datetime.datetime.utcnow()
                stats['ins'] += 1
        case 3|4|5|6:
            if  key in cache:
                # Update cache.
                cache[key] = datetime.datetime.utcnow()
                stats['upd'] += 1
        case _:
            # Look up cache.
            _ = cache.get( key ,None )
            stats['get'] += 1
    end = time.time()

keys = list(cache.keys())
keys.sort()
ksh = {k: cache[k] for k in keys}
msg = (mc.OpCode.QRY.name ,None ,cache.name ,None ,None ,ksh)
mc.logger.debug(f"Im:{mc.SRC_IP_ADD}\tFr:{' '*len(mc.SRC_IP_ADD.split(':')[0])}\tMsg:{msg}" ,extra=mc.LOG_EXTRA)

msg = (mc.OpCode.NOP.name ,None ,'Statistics' ,None ,None ,stats)
mc.logger.debug(f"Im:{mc.SRC_IP_ADD}\tFr:{' '*len(mc.SRC_IP_ADD.split(':')[0])}\tMsg:{msg}" ,extra=mc.LOG_EXTRA)

mc.logger.info(f"Done  testing.")
