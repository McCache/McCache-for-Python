import base64
import datetime
import hashlib
import logging
import os
import pickle
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

sleepspan = 100 # 1000 = 1sec
if 'TEST_SLEEP_SPAN'  in os.environ:
    sleepspan = int(os.environ['TEST_SLEEP_SPAN'])    # In seconds.

sleepunit = 100 # 1000 = 0.001s ,100 = 0.01s ,10 = 0.1s ,1 = 1s
if 'TEST_SLEEP_UNIT'  in os.environ:
    sleepunit = int(os.environ['TEST_SLEEP_UNIT'])

entries = 100
if 'TEST_MAX_ENTRIES' in os.environ:
    entries = int(os.environ['TEST_MAX_ENTRIES'])

duration = 5    # Five minute.
if 'TEST_RUN_DURATION' in os.environ:
    duration = int(os.environ['TEST_RUN_DURATION'])  # In minutes.

# for h in mc.logger.handlers:
#     if  h.formatter._fmt == mc.LOG_FORMAT.replace('{__app__}' ,mc.__app__):
#         h.formatter._fmt = "%(asctime)s.%(msecs)03d L#%(lineno)04d %(message)s"
#         h.formatter._style._fmt = "%(asctime)s.%(msecs)03d L#%(lineno)04d %(message)s"

NEXT_SSEC = 5   # Synchronize seconds.
cache = mc.get_cache()
bgn = time.time()
end = time.time()


# Random test section.
#
mc.logger.setLevel( logging.DEBUG ) # Enable detail logging in McCache for testing.
mc.logger.info(f"Test config: Seed={rndseed:3} ,Duration={duration:3} min ,Keys={entries:3} ,Span={sleepspan:3} ,Unit={sleepunit:3}")

mc.get_cache_checksum( cache.name ) # Query the cache to make sure it is empty.

ctr:int = 0     # Counter
while (end - bgn) < (duration*60):  # Seconds.
    time.sleep( random.randint(1 ,sleepspan) / sleepunit )

    if  random.randint(0 ,20) % 5 == 0: # Arbitarily.
        # Keys unique to this node.
        key = f'K{mc.SRC_IP_SEQ:03}-{int((time.time_ns()/100) % entries):04}'
    else:
        key = f'K000-{int((time.time_ns()/100) % entries):04}'

    ctr +=  1
    opc =   random.randint( 0 ,21 )
    match   opc:
        case 0:
            if  key in cache:
                msg = (mc.OpCode.FYI ,time.time_ns() ,cache.name ,key ,None ,f"DEL {key} from test script.")
                mc.logger.info(f"Im:{mc.SRC_IP_ADD}\tFr:{mc.FRM_IP_PAD}\tMsg:{msg}" ,extra=mc.LOG_EXTRA)

                # Evict cache.
                del cache[ key ]
        case 1|2|3:
            if  key not in cache:
                val = (mc.SRC_IP_SEQ ,datetime.datetime.utcnow() ,ctr) # The mininum fields to totally randomize the value.
                pkl: bytes = pickle.dumps( val )
                crc: str   = base64.b64encode( hashlib.md5( pkl ).digest() ).decode()  # noqa: S324
                msg = (mc.OpCode.FYI ,time.time_ns() ,cache.name ,key ,crc ,f"INS {key}={val} from test script.")
                mc.logger.info(f"Im:{mc.SRC_IP_ADD}\tFr:{mc.FRM_IP_PAD}\tMsg:{msg}" ,extra=mc.LOG_EXTRA)

                # Insert cache.
                cache[ key ] = val
        case 4|5|6|7|8: # Simulate much more updates than inserts.
            if  key in cache:
                val = (mc.SRC_IP_SEQ ,datetime.datetime.utcnow() ,ctr) # The mininum fields to totally randomize the value.
                pkl: bytes = pickle.dumps( val )
                crc: str   = base64.b64encode( hashlib.md5( pkl ).digest() ).decode()  # noqa: S324
                msg = (mc.OpCode.FYI ,time.time_ns() ,cache.name ,key ,crc ,f"UPD {key}={val} from test script.")
                mc.logger.info(f"Im:{mc.SRC_IP_ADD}\tFr:{mc.FRM_IP_PAD}\tMsg:{msg}" ,extra=mc.LOG_EXTRA)

                # Update cache.
                cache[ key ] = val
        case _:
            # Look up cache.
            _ = cache.get( key ,None )
    end = time.time()

# Wait for all members to catch up before existing together.
bgn = time.time()
bgnsec = time.localtime().tm_sec
time.sleep(NEXT_SSEC +(NEXT_SSEC - (bgnsec % NEXT_SSEC)))   # Try to get the cluster to stop at the same second to reduce RAK.
end = time.time()

# Format ouput to be consistent with the McCache log format.
msg = (mc.OpCode.NOP ,None ,None ,None ,None ,'Done  testing.')
mc.logger.info(f"Im:{mc.SRC_IP_ADD}\t   {mc.FRM_IP_PAD}\tMsg:{msg}" ,extra=mc.LOG_EXTRA)

# Spread out the wait to not congest the container.
time.sleep(random.randint(0,9))

msg = (mc.OpCode.NOP ,None ,None ,None ,None ,'Querying cache checksum.')
mc.logger.info(f"Im:{mc.SRC_IP_ADD}\t   {mc.FRM_IP_PAD}\tMsg:{msg}" ,extra=mc.LOG_EXTRA)

mc.get_cache_checksum( cache.name ) # Query the cache at exit.

msg = (mc.OpCode.NOP ,None ,None ,None ,None ,'Exiting.')
mc.logger.info(f"Im:{mc.SRC_IP_ADD}\t   {mc.FRM_IP_PAD}\tMsg:{msg}" ,extra=mc.LOG_EXTRA)
