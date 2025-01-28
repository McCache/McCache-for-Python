import base64
import datetime
import gc
import hashlib
import logging
import os
import pickle
import random
import socket
import time

from   collections  import OrderedDict
from   copy         import deepcopy
from   faker        import Faker

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
                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.WRN ,tsm=cache.tsm_version() ,nms=ctx['nms'] ,key=ctx['key'] ,crc=ctx['newcrc']
                                                ,msg=f"^   WRN {ctx['key']} got deleted     within {ctx['elp']:6} sec ({ctx['tsm']} - {ctx['lkp']}) in the background." )
            case 2: # Updates
                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.WRN ,tsm=cache.tsm_version() ,nms=ctx['nms'] ,key=ctx['key'] ,crc=ctx['newcrc']
                                                ,msg=f"^   WRN {ctx['key']} got updated     within {ctx['elp']:6} sec ({ctx['tsm']} - {ctx['lkp']}) in the background." )
            case 3: # Incoherence
                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.WRN ,tsm=cache.tsm_version() ,nms=ctx['nms'] ,key=ctx['key'] ,crc=ctx['newcrc']
                                                ,msg=f"^   WRN {ctx['key']} got incoherent  within {ctx['elp']:6} sec ({ctx['tsm']} - {ctx['lkp']}) in the background." )
    return  True

def get_data( doBig: bool = False ) -> dict:
    if  doBig:
        # Generate big data to send.
        val = deepcopy( BIG_DATA )
        val['key'] = key
        val['updated_on'] = datetime.datetime.now(datetime.UTC)
        pkl: bytes = pickle.dumps( val )
        crc: str   = base64.b64encode( hashlib.md5( pkl ).digest() ).decode()   # noqa: S324
        val = { 'data': val ,'crc': crc ,'size': len(pkl) }
    else:
        val = (mc.SRC_IP_SEQ ,datetime.datetime.now(datetime.UTC) ,ctr) # The minimum fields to totally randomize the value.
    return  val

def get_snooze( aperture: float ,scl: int | None=None) -> float:
    # Get a snooze time that is narrow around the aperture.
    #
    #       Aperture                Scale   Aperture range
    #       --------    -------     -----   --------------
    #       5              5 s      1       
    #       1              1 s      1       0.65        >= 1.00     >= 1.35
    #       0.5          500 ms     10      
    #       0.1          100 ms     10      0.065       >= 0.10     >= 0.135
    #       0.05          50 ms     100     
    #       0.01          10 ms     100     0.0065      >= 0.01     >= 0.0135
    #       0.005          5 ms     1000    
    #       0.001          1 ms     1000    0.00065     >= 0.001    >= 0.002
    #       0.0005       0.5 ms     10000   
    #       0.0001       0.1 ms     10000   0.000065    >= 0.0001   >= 0.0002   
    #       0.00005     0.05 ms     100000  
    if  scl is  None:
        scl =   1    # The number of digits to the right of the decimal.
        while (aperture * scl) < 1:
            scl *= 10

    skew: int =  random.randrange( 0 ,35 ,5 )   # Approx 1 stddev.
    match  random.randrange( -1 ,2 ):
        case -1: # Skew down.
            aperture -= (skew/(scl*100))
        case 0: # No skew.
            pass
        case 1: # Skew up.
            aperture += (skew/(scl*100))  if scl <= 100 else (skew/(scl*35))

    return  round( aperture ,6 )

def check_straggler( skew: int = 0 ) -> None:
    # NOTE: During high stress testing the queue can back up beyond 40K of entries and can take more than 6 minutes to process all the entries.
    while not mc._mcIBQueue.empty() or not mc._mcOBQueue.empty():
        # NOTE: During high stress testing the queue can back up beyond 40K of entries and can take more than 6 minutes to process all the entries.
        tsm = cache.tsm_version_str()
        ibs = mc._mcIBQueue.qsize()
        obs = mc._mcOBQueue.qsize()
        if  ibs > 0 or obs > 0:
            msg=f'Internal message queue size. IB:{ibs:>6} ,OB:{obs:>4}'
            if  mc._mcConfig.debug_level < mc.McCacheDebugLevel.BASIC:
                mc.logger.info( f'Im:{mc.SRC_IP_ADD:11} {msg} at {tsm}' )
            else:
                mc._log_ops_msg( logging.INFO   ,opc=mc.OpCode.WRN ,tsm=cache.tsm_version() ,nms=cache.name ,msg=msg )

        time.sleep( skew + (2 ^ mc._mcConfig.multicast_hops))

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
    'text': fake.text( max_nb_chars=9216 ), # 9K
    'dates':[ {time.time_ns() : datetime.datetime.now(datetime.UTC)} for _ in range(8) ], # List of dicts.
    'updated_on': None,
    'counter': None
}


# The artificial pauses in between cache operation.  Targeting between 10 to 30 ms.
# SEE: https://www.centurylink.com/home/help/internet/how-to-improve-gaming-latency.html
#
aperture:float=0.01 if 'TEST_APERTURE'      not in os.environ else float(os.environ['TEST_APERTURE'])
entries:int   = 200 if 'TEST_KEY_ENTRIES'   not in os.environ else int(  os.environ['TEST_KEY_ENTRIES'])
duration:int  = 5   if 'TEST_RUN_DURATION'  not in os.environ else int(  os.environ['TEST_RUN_DURATION'])
cluster:int   = 3   if 'TEST_CLUSTER_SIZE'  not in os.environ else int(  os.environ['TEST_CLUSTER_SIZE'])
datamix:int   = 1   if 'TEST_DATA_SIZE_MIX' not in os.environ else int(  os.environ['TEST_DATA_SIZE_MIX'])  # 1= small ,2= large ,3= mixed
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
msg = f"Config: Seed={rndseed:3}  ,Cluster={cluster} ,Entries={entries} ,DataMix={datamix} ,Pulse={syncpulse}m ,Aperture={aperture}s ,Duration={duration}m ,CBackWin={callbackw}s"
if  mc._mcConfig.debug_level < mc.McCacheDebugLevel.BASIC:
    mc.logger.info( f'Im:{mc.SRC_IP_ADD:11} {msg}' )
else:
    mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.FYI ,tsm=cache.tsm_version() ,nms=cache.name ,msg=msg )

dg1:int = datetime.datetime.now().minute

scl = 1 # The number of digits to the right of the decimal.
while (aperture * scl) < 1:
    scl *= 10

ctr:int   = 0   # Counter
slp:float = 0.0 # Average sleep interval.
while (end - bgn) < (duration*60):  # Seconds.
    # NOTE: Turn on logging one minutes prior to done to collect the finish logs.
    if  mc._mcConfig.debug_level <= mc.McCacheDebugLevel.DISABLE and (end - bgn) > (duration-1)*60:
        mc._mcConfig.debug_level =  mc.McCacheDebugLevel.BASIC

    # Randomly snooze in-between operation around the aperture.
    snooze = get_snooze( aperture ,scl )
    assert snooze <= 15 # Circuit breaker.  No more than 15 seconds.
    # SEE: https://stackoverflow.com/questions/1133857/how-accurate-is-pythons-time-sleep (1ms)
    time.sleep( snooze )

    elp = time.time() - end
    slp = ((slp *ctr) + elp) / (ctr +1) # Running average of sleep time.
    ctr +=  1

    # DEBUG trace.
    if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
        glp = '~' if abs((elp - snooze) / snooze) < 0.335 else '!'  # 33% Glyph.
        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.FYI ,tsm=cache.tsm_version() ,nms=cache.name ,key=' '*8
                                        ,msg=f">   {round(elp ,5):0.5f} {glp} {round(snooze ,5):0.5f} sec paused in test script." )

    # Generate a random key.
    rnd = random.randint( 0 ,entries )
    seg = frg.format( frg=rnd )

    if  random.randint(0 ,20) == 5: # Arbitrarily 5% is strictly to be only generate on this node.
        # Keys unique to this node.
        key = f'K{mc.SRC_IP_SEQ:03}-{seg}'
    else:
        # Keys can be generated by every nodes.
        key = f'K000-{seg}'

    # Generate a random operation.
    opc =   random.randint( 0 ,20 )

    # Decide on the data size.
    doBig: bool =   False
    match   datamix:
        case 1:
            doBig = False
        case 2:
            doBig = True
        case 3:
            doBig = True if opc in {2 ,4 ,6 ,8 } else False

    match   opc:
        case 0:
            if  dg1 != datetime.datetime.now().minute:
                dg1  = datetime.datetime.now().minute
                if  len(mc._mcPending) > 9 or len(mc._mcArrived) > 9:
                    mc.logger.warning(f"{cache.tsm_version_str()} Pending:{len(mc._mcPending):5} {sorted(mc._mcPending.keys() ,reverse=True )}")
                    mc.logger.warning(f"{cache.tsm_version_str()} Arrive: {len(mc._mcArrived):5} {sorted(mc._mcArrived.keys() ,reverse=True )}")

            time.sleep( 0.25 )  # A breather pause.  DONT delete this line or it could congest.
#       case 1|2|3|4:   # NOTE: 20% are inserts.    This has lots of hot spots.
        case 1|3|5|7:   # NOTE: 20% are inserts.
            if  key not in cache:
                val =  get_data( doBig )
                pkl: bytes = pickle.dumps( val )
                crc: str   = base64.b64encode( hashlib.md5( pkl ).digest() ).decode()  # noqa: S324

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.EXTRA:
                    mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                    ,msg=f">   INS {key}={val} in test script." )

                # Insert cache entry.
                cache[ key ] = val

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                    if  key not in cache:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   ERR:{key} NOT persisted in cache in test script!" )
                    else:
                        try:
                            if  val != cache[ key ]:
                                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                                ,msg=f">   ERR:{key} value is incoherent in cache in test script!" )
                            else:
                                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                                ,msg=f">   OK: {key} persisted in cache in test script." )
                        except KeyError:
                            mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                            ,msg=f">   ERR:{key} Not found in cache after insert in test script." )

#       case 5|6|7|8:   # NOTE: 20% are updates.    This has lots of hot spots.
        case 2|4|6|8:   # NOTE: 20% are updates.
            if  key in cache:
                val =  get_data( doBig )
                pkl: bytes = pickle.dumps( val )
                crc: str   = base64.b64encode( hashlib.md5( pkl ).digest() ).decode()   # noqa: S324

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.EXTRA:
                    mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.UPD ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                    ,msg=f">   UPD {key}={val} in test script." )

                # Update cache entry.
                cache[ key ] = val

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                    if  key not in cache:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.UPD ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   ERR:{key} NOT persisted in cache in test script!" )
                    else:
                        try:
                            if  val != cache[ key ]:
                                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.UPD ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                                ,msg=f">   ERR:{key} value is incoherent in test script!" )
                            else:
                                mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.UPD ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                                ,msg=f">   OK: {key} persisted in cache in test script!" )
                        except KeyError:
                            mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.INS ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                            ,msg=f">   ERR:{key} Not found in cache after update in test script." )
        case 9:     # NOTE: 5% are deletes.
            if  key in cache:
                # Evict cache.
                try:
                    # DEBUG trace.
                    if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.EXTRA:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.DEL ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=None
                                                        ,msg=f">   DEL {key} in test script." )
                    # Delete cache entry.
                    crc =  cache.metadata[ key ]['crc']

                    # DEBUG trace.
                    if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.DEL ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   DEL {key} in test script." )

                    del cache[ key ]
                except KeyError:
                    pass

                # DEBUG trace.
                if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                    if  key in cache:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.DEL ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   ERR:{key} still persist in cache in test script!" )
                    else:
                        mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.DEL ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=crc[:-2]
                                                        ,msg=f">   OK: {key} deleted from cache in test script." )
        case _:     # NOTE: 55% are lookups.
            # Look up cache.
            val = cache.get( key ,None )

            # DEBUG trace.
            if  mc._mcConfig.debug_level >= mc.McCacheDebugLevel.SUPERFLUOUS:
                if  not val:
                    mc._log_ops_msg( logging.DEBUG  ,opc=mc.OpCode.FYI ,tsm=cache.tsm_version() ,nms=cache.name ,key=key ,crc=None
                                                    ,msg=f">   WRN:{key} not in cache in test script!")
    end = time.time()

# Done stress testing.
#
msg = f"Done testing at {cache.tsm_version_str()} with {slp:0.4f} sec/ops with {ctr} ops."
if  mc._mcConfig.debug_level < mc.McCacheDebugLevel.BASIC:
    mc.logger.info( f'Im:{mc.SRC_IP_ADD:11} {msg}' )
else:
    mc._log_ops_msg( logging.INFO   ,opc=mc.OpCode.FYI ,tsm=cache.tsm_version() ,nms=cache.name ,msg=msg )

# Query the local metrics.
#
val = mc.get_local_metrics()
if  mc._mcConfig.debug_level < mc.McCacheDebugLevel.BASIC:
    mc.logger.info( f'Im:{mc.SRC_IP_ADD:11} {val}' )
else:
    mc._log_ops_msg( logging.INFO   ,opc=mc.OpCode.MET ,tsm=cache.tsm_version() ,nms=cache.name ,msg=val )

# Pace out the log entry.  It is not totally chronological.
time.sleep( 1 )

# Wait for some straggler to trickle in/out before to dump out the cache.
check_straggler( (cluster/3) )

# Query the local cache.
#
val = mc.get_local_checksum()
if  mc._mcConfig.debug_level < mc.McCacheDebugLevel.BASIC:
    mc.logger.info( f'Im:{mc.SRC_IP_ADD:11} {val}' )
else:
    mc._log_ops_msg( logging.INFO   ,opc=mc.OpCode.INQ ,tsm=cache.tsm_version() ,nms=cache.name ,msg=val )

msg = f"Exiting test at {cache.tsm_version_str()}."
if  mc._mcConfig.debug_level < mc.McCacheDebugLevel.BASIC:
    mc.logger.info( f'Im:{mc.SRC_IP_ADD:11} {msg}' )
else:
    mc._log_ops_msg( logging.INFO   ,opc=mc.OpCode.FYI ,tsm=cache.tsm_version() ,nms=cache.name ,msg=msg )

# Check one more time to determine if there is no false negative.
check_straggler()
