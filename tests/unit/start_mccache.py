import base64
import datetime
import gc
import hashlib
import logging
import os
import pickle
import random
import socket
import sys
import time

from   copy  import deepcopy
from   faker import Faker

import mccache as mc
from   pycache import Cache

# Callback method for key that are updated within 1 second of lookup in the background.
#
def test_callback(ctx: dict) -> None:
    """Callback method to be notified of changes within one second of previous lookup.

    Args:
        ctx :dict   A context dictionary of the following format:
                    {
                        typ:    Type of alert. 1=Deletion ,2=Update ,3=Incoherence
                        nms:    Cache namespace.
                        key:    Identifying key.
                        lkp:    Lookup timestamp.
                        tsm:    Current entry timestamp.
                        elp:    Elapsed time.
                        prvcrc: Previous value CRC.
                        newcrc: Current  value CRC.
                    }
    """
    # DEBUG trace.
    if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.BASIC:
        match ctx['typ']:
            case 1: # Deletion
                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.WRN ,tsm=cache.TSM_VERSION() ,nms=ctx['nms'] ,key=ctx['key'] ,crc=ctx['newcrc']
                                                ,msg=f"^   WRN {ctx['key']} got deleted     within {ctx['elp']:0.5f} sec in the background." )
            case 2: # Updates
                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.WRN ,tsm=cache.TSM_VERSION() ,nms=ctx['nms'] ,key=ctx['key'] ,crc=ctx['newcrc']
                                                ,msg=f"^   WRN {ctx['key']} got updated     within {ctx['elp']:0.5f} sec in the background." )
            case 3: # Incoherence
                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.WRN ,tsm=cache.TSM_VERSION() ,nms=ctx['nms'] ,key=ctx['key'] ,crc=ctx['newcrc']
                                                ,msg=f"^   WRN {ctx['key']} got incoherent  within {ctx['elp']:0.5f} sec in the background." )
    return  True


# Initialization section.
#
rndseed = 17
if 'TEST_RANDOM_SEED' in os.environ:
    rndseed = int(os.environ['TEST_RANDOM_SEED'])
else:
    rndseed = int(str(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET )[0][4][0]).split(".")[3])
random.seed( rndseed )

fake = Faker()
Faker.seed( rndseed )
BIG_DATA = {
    'key': None,
    'name': fake.name(),
    'address': fake.address(),
    'text': fake.text( max_nb_chars=10240 ),    # 10K
    'counter': None,
    'updated_on': None
}


# The artificial pauses in between cache operation.  Targeting between 10 to 30 ms.
# SEE: https://www.centurylink.com/home/help/internet/how-to-improve-gaming-latency.html
#
aperture:float=0.01 if 'TEST_APERTURE'      not in os.environ else float(os.environ['TEST_APERTURE'])
entries:int   = 200 if 'TEST_MAX_ENTRIES'   not in os.environ else int(  os.environ['TEST_MAX_ENTRIES'])
duration:int  = 5   if 'TEST_RUN_DURATION'  not in os.environ else int(  os.environ['TEST_RUN_DURATION'])
cluster:int   = 3   if 'TEST_CLUSTER_SIZE'  not in os.environ else int(  os.environ['TEST_CLUSTER_SIZE'])
datatype:int  = 1   if 'TEST_DATA_SIZE_MIX' not in os.environ else int(  os.environ['TEST_DATA_SIZE_MIX'])  # 1= small ,2= large ,3= mixed
syncpulse:int = mc._mcConfig.cache_pulse
callbackw:int = mc._mcConfig.callback_win

if  mc._mcConfig.callback_win > 0:
    cache = mc.get_cache( callback=test_callback )
else:
    cache = mc.get_cache( callback=None )

bgn = time.time()
end = time.time()
frg = '{'+'frg:0{l}'.format( l=len(str( entries )))+'}'

# Random test section.
#
msg = f"Config: Seed={rndseed:3}  ,Cluster={cluster} ,Entries={entries} ,Pulse={syncpulse}m ,Aperture={aperture}s ,Duration={duration}m ,CBackWin={callbackw}s"
if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.BASIC:
    mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.FYI ,tsm=cache.TSM_VERSION() ,nms=cache.name ,msg=msg )
else:
    mc.logger.info( msg )

itg = 0 # Integral, the digits to the left of the decimal.
scl = 1 # The number of digits to the right of the decimal.
while (aperture * scl) < 1:
    scl *= 10
itg = int(scl * aperture)   # The factor to offset upwards of teh aperture.

ctr:int   = 0   # Counter
slp:float = 0.0 # Average sleep interval.
while (end - bgn) < (duration*60):  # Seconds.
    snooze = random.randrange( int(itg*scl) ,int(itg*scl*10) ,1 ) / (scl*scl)   # Keep it within 1 digit of the aperture scale.
    assert snooze <= 9  # Circuit breaker.  No more than 9 seconds.
    # SEE: https://stackoverflow.com/questions/1133857/how-accurate-is-pythons-time-sleep (1ms)
    time.sleep( snooze )

    elp = time.time() - end
    slp = ((slp *ctr) + elp) / (ctr +1) # Running average of sleep time.
    ctr +=  1

    # DEBUG trace.
    if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
        glp = '~' if abs((elp - snooze) / snooze) < 0.335 else '!'  # 33% Glyph.
        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.FYI ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=' '*8
                                        ,msg=f">   {round(elp ,5):0.5f} {glp} {round(snooze ,5):0.5f} sec paused in test script." )

    rnd = random.randint( 0 ,entries )
    seg = frg.format( frg=rnd )

    if  random.randint(0 ,20) == 5: # Arbitrarily 5% is strictly to be only generate on this node.
        # Keys unique to this node.
        key = f'K{mc.SRC_IP_SEQ:03}-{seg}'
    else:
        # Keys can be generated by every nodes.
        key = f'K000-{seg}'

    opc =   random.randint( 0 ,20 )
    match   opc:
        case 0:
            pass
        case 1|2|3|4:   # NOTE: 20% are inserts.
            if  key not in cache:
                val = (mc.SRC_IP_SEQ ,datetime.datetime.now(datetime.UTC) ,ctr) # The minimum fields to totally randomize the value.
                pkl: bytes = pickle.dumps( val )
                crc: str   = base64.b64encode( hashlib.md5( pkl ).digest() ).decode()  # noqa: S324

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.EXTRA:
                    mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                    ,msg=f">   INS {key}={val} in test script." )

                # Insert cache entry.
                cache[ key ] = val

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                    if  key not in cache:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   ERR:{key} NOT persisted in cache in test script!" )
                    else:
                        try:
                            if  val != cache[ key ]:
                                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                                ,msg=f">   ERR:{key} value is incoherent in cache in test script!" )
                            else:
                                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                                ,msg=f">   OK: {key} persisted in cache in test script." )
                        except KeyError:
                            mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                            ,msg=f">   ERR:{key} Not found in cache after insert in test script." )

        case 5|6|7|8:   # NOTE: 20% are updates.
            if  key in cache:
                if  opc in {-5 ,-7}:    # TODO: Enable this.
                    # Generate big data to send.
                    val = deepcopy( BIG_DATA )
                    val['key'] = key
                    val['counter'] = ctr
                    val['updated_on'] = datetime.datetime.now(datetime.UTC)
                    pkl: bytes = pickle.dumps( val )
                    crc: str   = base64.b64encode( hashlib.md5( pkl ).digest() ).decode()   # noqa: S324
                    val = { 'data': val ,'crc': crc ,'size': len(pkl) }
                else:
                    val = (mc.SRC_IP_SEQ ,datetime.datetime.now(datetime.UTC) ,ctr) # The minimum fields to totally randomize the value.

                pkl: bytes = pickle.dumps( val )
                crc: str   = base64.b64encode( hashlib.md5( pkl ).digest() ).decode()   # noqa: S324

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.EXTRA:
                    mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.UPD ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                    ,msg=f">   UPD {key}={val} in test script." )

                # Update cache entry.
                cache[ key ] = val

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                    if  key not in cache:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.UPD ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   ERR:{key} NOT persisted in cache in test script!" )
                    else:
                        try:
                            if  val != cache[ key ]:
                                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.UPD ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                                ,msg=f">   ERR:{key} value is incoherent in test script!" )
                            else:
                                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.UPD ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                                ,msg=f">   OK: {key} persisted in cache in test script!" )
                        except KeyError:
                            mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                            ,msg=f">   ERR:{key} Not found in cache after update in test script." )
        case 9:     # NOTE: 5% are deletes.
            if  key in cache:
                # Evict cache.
                try:
                    # DEBUG trace.
                    if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.EXTRA:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.DEL ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=None
                                                        ,msg=f">   DEL {key} in test script." )
                    # Delete cache entry.
                    crc =  cache.metadata[ key ]['crc']

                    # DEBUG trace.
                    if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.DEL ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   DEL {key} in test script." )

                    del cache[ key ]
                except KeyError:
                    pass

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                    if  key in cache:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.DEL ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   ERR:{key} still persist in cache in test script!" )
                    else:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.DEL ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   OK: {key} deleted from cache in test script." )
        case _:     # NOTE: 55% are lookups.
            # Look up cache.
            val = cache.get( key ,None )

            # DEBUG trace.
            if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                if  not val:
                    mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.FYI ,tsm=cache.TSM_VERSION() ,nms=cache.name ,key=key ,crc=None
                                                    ,msg=f">   WRN:{key} not in cache in test script!")
    end = time.time()

# Done stress testing.
#
msg = f"{mc.SRC_IP_ADD:11} Done testing at {cache.tsm_version_str()} with {slp:0.4f} sec/ops with {ctr} ops."
if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.BASIC:
    mc._log_ops_msg( logging.INFO   ,opc=mc.OpCode.FYI ,tsm=cache.TSM_VERSION() ,nms=cache.name ,msg=msg )
else:
    mc.logger.info( msg )

# Wait for some straggler to trickle in/out before to dump out the cache.
time.sleep( 1 )
while not mc._mcIBQueue.empty() or not mc._mcOBQueue.empty():
    # NOTE: During high stress testing the queue can back up beyond 40K of entries and can take more than 6 minutes to process all the entries.
    tsm = cache.tsm_version_str()
    ibs = mc._mcIBQueue.qsize()
    obs = mc._mcOBQueue.qsize()
    msg = f"{mc.SRC_IP_ADD:11} Internal message queue at {tsm} still has {ibs:3} IB and {obs:3} OB pending entries."
    if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.BASIC:
        mc._log_ops_msg( logging.INFO   ,opc=mc.OpCode.FYI ,tsm=cache.TSM_VERSION() ,nms=cache.name ,msg=msg )
    else:
        mc.logger.info( msg )
    time.sleep((cluster/3) + (2 ^ mc._mcConfig.multicast_hops))

# Query the local cache and metrics and exit.
#
mc.get_cache_checksum( name=cache.name ,node=mc.SRC_IP_ADD )
mc.get_cluster_metrics( node=mc.SRC_IP_ADD )

msg = f"{mc.SRC_IP_ADD:11} Exiting test at {cache.tsm_version_str()}."
if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.BASIC:
    mc._log_ops_msg( logging.INFO   ,opc=mc.OpCode.FYI ,tsm=cache.TSM_VERSION() ,nms=cache.name ,msg=msg )
else:
    mc.logger.info( msg )
