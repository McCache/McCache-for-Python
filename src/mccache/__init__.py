# See MIT license at the bottom of this script.
#
"""
This is a distributed application cache build on top of the `cachetools` package.  SEE: https://pypi.org/project/cachetools/
It uses UDP multicasting hence the name "Multi-Cast Cache", playfully abbreviated to "McCache".

When an object is insert/update an object into the cache, it is assumed that the instance shall be the latest.
McCache default behaviour is to notify all member in the cluster of this update and the other members shall evict their entry in their local cache.
If an entry is no longer in cache, re-calculation/processing or retrieve from storage is required.
The state of your object in storage should be the latest.

The worst case sceenario is an extra re-processing or retrieval from storage.
The best  case sceenario is that NO external call shall be made.
Once configured in more optimism mode then the default, more sophisticate cache coherence protocol shall be used.

This tool can be a good fit if your use cases meet most of the following guidelines:
    1. Not to be "dependent" on an external caching service such as memcached ,redis or riak.
    2. Keep the programming API "consistent" working with local cache.
    3. A small local network cluster of nodes running "identical" piece of software and setup.
    4. Number of objects to cache are not "many".
    5. Changes to the cache objects are not "frequent".
    6. Size of the value to be cache is "smaller" than the ethernet MTU (< 1472 bytes).
    7. Your load balancer could be configured to support "sticky" session.

Having stated the above, you need to quantify the above guidelines to match your use case.
There are 3 levels of optimism on the cache notification.  They are:

### 1. PESSIMISTIC:
    * All communication will required acknowledgement.
    * Changes to local cache shall propagate an eviction to the other member's local cache.
        - Without an entry in the member's local cache ,they have to re-fetch it from persistance storage, which should be the freshest.
    *`Total Time to Live` cache algorithmn.  Default is 15 minutes.
    * Multicast out 4 messages at 0, 10 ,30 ms apart

### 2. NEUTRAL (default):
    * No acknowledgement is required from the other members.
    * Changes to local cache will propagate an update to the other member's local cache.
        - Members with an existing local entry shall update their own local cache.
    *`Least Recently Used` cache algorithmn.
    * Multicast out 3 messages at 0 ,10 ms apart.

### 3. OPTIMISIC:
    * No acknowledgement is required from the other members.
    * Keep a global coherent cache.
        - All members shall update their own local cache with the multicasted change.
        - Increased size of cache for more objects.
    *`Least Recently Used` cache algorithmn.
    * Multicast out 2 message at 0 ms apart.
"""
__app__     = "McCache"
__author__  = "Edward Lau<elau1004@netscape.net>"
__version__ = "0.1.0"
__date__    = "2023-07-01"

import base64
import datetime
import hashlib
import logging
import os
import pickle
import queue
import random
import socket
import struct
import threading
import time

import cachetools

from dataclasses import dataclass
from enum import Enum

class McCacheLevel(Enum):
    PESSIMISTIC = 3 # Something out there is going to screw you.  Requires acknowledgement.  Evict the caches.
    NEUTRAL     = 5 # Default.
    OPTIMISTIC  = 7 # Life is great on the happy path.  Acknowledgment is not required.  Sync the caches.

class OpCode(Enum):
    # Keep everythng here as 3 character fixed length strings.
    ACK = 'ACK'     # Acknowledgement of a received request.
#   BYE = 'BYE'     # Member announcing it is leaving the group.
    DEL = 'DEL'     # Member requesting the group to evict the cache entry.
#   ERR = 'ERR'     # Member announcing an error to the group.
    INI = 'INI'     # Member announcing its initialization to the group.
    INQ = 'INQ'     # Member inquiring about a cache entry from the group.
    NEW = 'NEW'     # New member annoucement to join the group.
#   NOP = 'NOP'     # No operation.
#   PST = 'PST'     # Post?
#   PAT = 'PCH'     # Patch?
    PUT = 'PUT'     # Member annoucing a new cache entry is put into its local cache.
    QRY = 'QRY'     # Query the cache.
    RST = 'RST'     # Reset the cache.
    UPD = 'UPD'     # Update an existing cache entry.


# Module initialization.
#
_lock = threading.RLock()   # Module-level lock for serializing access to shared data.
_mcCacheDict = {}   # Private dict to segeregate the cache namespace.
_mcPending = {}     # Pending acknowledgement inpessivemistic mode. Use 'cachetools.TTLCache' instead.
_mcMember = {}      # Members in the group.  ID/Timestamp.
_mcQueue = queue.Queue()
_mcIPAdd = {
    224: {
        0: {
            # Local Network.
            0:  set({3 ,26 ,255}).union({d for d in range(69 ,101)}).union({d for d in range(122 ,150)}).union({d for d in range(151 ,251)}),
            # Adhoc Block I.
            2:  set({0}).union({d for d in range(18 ,64)}),
            6:  set({d for d in range(145 ,161)}).union({d for d in range(152 ,192)}),
            12: set({d for d in range(136 ,256)}),
            17: set({d for d in range(128 ,256)}),
            20: set({d for d in range(208 ,256)}),
            21: set({d for d in range(128 ,256)}),
            23: set({d for d in range(182 ,192)}),
            245:set({d for d in range(0   ,256)}),
            # TODO: Adhoc Block II.
            # TODO: Adhoc Block III.
        },
    }
}

ipv4: str = socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET )[0][4][0]
ipV4: str = "".join([hex(int(g)).removeprefix("0x").zfill(2) for g in ipv4.split(".")])    # Uppercase "V"
ipv6: str = socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET6)[0][4][0]
ipV6: str = ipv6.replace(':' ,'')   # Uppercase "V"

SOURCE_ADD = f"{ipv4}:{os.getpid()}"
LOG_FORMAT = f"%(asctime)s.%(msecs)03d (%(ipV4)s.%(process)d.%(thread)05d)[%(levelname)s {__app__}] %(message)s"
LOG_EXTRA = {'ipv4': ipV4 ,'ipV4': ipV4 ,'ipv6': ipv6 ,'ipV6': ipV6}    # Extra fields for the logger mesage.
logger = logging.getLogger()    # Root logger.

# Configure McCache.
#
@dataclass
class McCache_Config():
    ttl: int  = 900             # Total Time to Live in seconds for a cached entry.
    mc_gip: str = '224.0.0.3'   # Unassigned multi-cast IP.
    mc_port: int = 4000         # Unofficial port.  Was Diablo II game.
    mc_hops: int = 1            # Only local subnet.
    mc_transport: int = None    # Network transaport. UDP or TCP.
    max_size: int = 2048        # Entries.
    op_level: int = McCacheLevel.NEUTRAL.value
    debug_log: str = None       # Full pathname of the log file.
    house_keeping_slots: str = '5,8,13,21,55' # Periods for first 5 slots: Very frequent ,Frequent ,Normal ,Slow ,Very slow.

_config = McCache_Config()

try:
    _config.ttl = int(os.environ['MCCACHE_TTL'])
except:
    pass
try:
    _config.op_level = int(os.environ['MCCACHE_LEVEL'])
    if  _config.op_level == McCacheLevel.PESSIMISTIC:
        _config.max_size =  1024
    if  _config.op_level == McCacheLevel.OPTIMISTIC:
        _config.max_size =  4096
except:
    pass
try:
    _config.max_size = int(os.environ['MCCACHE_MAXSIZE'])
except:
    pass
try:
    _config.house_keeping_slots = int(os.environ['MCCACHE_SLOTS'])
except:
    pass
try:
    _config.debug_log = os.environ['MCCACHE_DEBUG_FILE']
except:
    pass
try:
    _config.mc_hops = int(os.environ['MCCACHE_MULTICAST_HOPS'])
except:
    pass
_ip = None
try:
    # SEE: https://www.iana.org/assignments/multicast-addresses/multicast-addresses.xhtml
    if 'MCCACHE_MULTICAST_IP' in os.environ['MCCACHE_MULTICAST_IP']:
        if ':' not in os.environ['MCCACHE_MULTICAST_IP']:
            _config.mc_gip  = os.environ['MCCACHE_MULTICAST_IP']
        else:
            _config.mc_gip  = os.environ['MCCACHE_MULTICAST_IP'].split(':')[0]
            _config.mc_port = int(os.environ['MCCACHE_MULTICAST_IP'].split(':')[1])

        _ip = [int(d) for d in _config.mc_gip.split(".")]
        if  len(_ip) != 4 or _ip[0] != 224:
            raise ValueError("{_mcCache_gip} is an invalid multicast IP address!")

        if  not(_ip[0] in _mcIPAdd and \
                _ip[1] in _mcIPAdd[_ip[0]] and \
                _ip[2] in _mcIPAdd[_ip[0]][_ip[1]] and \
                _ip[3] in _mcIPAdd[_ip[0]][_ip[1]][_ip[2]]
            ):
            raise ValueError("{_mcCache_gip} is an unavailable multicast IP address! See: https://tinyurl.com/4cymemdf")
except KeyError:
    pass
except ValueError as ex:
    logger.warning(f"{ex} Defaulting to IP: {_config.mc_gip}", extra=LOG_EXTRA)
finally:
    del _ip
    del _mcIPAdd

# Setup McCache logger.
#
logger = logging.getLogger('mccache')   # McCache specific logger.
logger.propagate = False
logger.setLevel(logging.INFO)
_hdlr = logging.StreamHandler()
_fmtr = logging.Formatter(fmt=LOG_FORMAT ,datefmt='%Y%m%d%a %H%M%S' ,defaults=LOG_EXTRA)
_hdlr.setFormatter(_fmtr)
logger.addHandler(_hdlr)
if _config.debug_log:
    _hdlr = logging.FileHandler(_config.debug_log ,mode="a")
    _hdlr.setFormatter(_fmtr)
    logger.addHandler(_hdlr)
    logger.setLevel(logging.DEBUG)
del _hdlr
del _fmtr
logger.info(f"Setting: (level: {_config.op_level} ,size: {_config.max_size}) ,ttl: {_config.ttl} ,gip: {_config.mc_gip} ,dbg: {_config.debug_log is not None})")


# McCache classes.
#
class _Cache():
    """
    Boiler plate code for `__setitem__()` and `__delitem__()` to be used to overwrite all the cachetools caches classes.
    We need to queue up the changes to be multicast out to the members in the group.
    """
    # Name of this cache to be isolated from the other cache instances.
    name:str = None

    # TODO: Add future cache entry metadata.
    #       - Unique key
    #       - Value checksum
    #       - Timestamp

    def __setitem__(self ,key ,value ,multicast:bool = True):
        super().__setitem__( key ,value )

        if  multicast:
            if  _config.op_level == McCacheLevel.OPTIMISTIC.value:  # Distribute the cache entry to remote members.
                _mcQueue.put((OpCode.PUT.name ,time.time_ns() ,self.name ,key ,value))
            elif _config.op_level == McCacheLevel.NEUTRAL.value:    # Update remote member's cache entry if exist.
                _mcQueue.put((OpCode.UPD.name ,time.time_ns() ,self.name ,key ,value))
            else:   # Evict the remote member's cache entry.
                _mcQueue.put((OpCode.DEL.name ,time.time_ns() ,self.name ,key ,None))

    def __delitem__(self ,key ,multicast:bool = True):
        # NOTE: Also called by pop() and popitem().
        super().__delitem__( key )

        if  multicast:
            _mcQueue.put((OpCode.DEL.name ,time.time_ns() ,self.name ,key ,None))

# TODO: Maybe we need to track the CRC for the value.
#   def __getitem__(self, key ,multicast:bool = True):
#       super().__getitem__( key )


class FIFOCache(_Cache ,cachetools.FIFOCache):
    pass


class LFUCache(_Cache ,cachetools.LFUCache):
    pass


class LRUCache(_Cache ,cachetools.LRUCache):
    pass


class MRUCache(_Cache ,cachetools.MRUCache):
    pass


class RRCache(_Cache ,cachetools.RRCache):
    pass


class TTLCache(_Cache ,cachetools.TTLCache):
    pass


class TLRUCache(_Cache ,cachetools.TLRUCache):
    pass


# Public methods.
#
def getCache(name: str = None ,cache: _Cache|cachetools.Cache = None) -> _Cache|cachetools.Cache:
    """
    Return a cache with the specified name ,creating it if necessary.
    If no name is specified ,return the default TLRUCache or LRUCache cache depending on the optimism setting.
    SEE: https://dropbox.tech/infrastructure/caching-in-theory-and-practice

    Parameter
    ---------
        name: str       Name to isolate different caches.  Namespace dot notation is suggested.
        cache: Cache    Optional cache instance to override the default cache type.

    Return: Cache instance to use with given name.
    """
    if  name:
        if  not isinstance( name ,str ):
            raise TypeError('A cache name must be a string!')
    else:
        name = 'default'
    if  cache:
        if  not isinstance( cache ,_Cache ):
            raise TypeError(f"Cache name '{name}' is not of type McCache._Cache!")
        if  not isinstance( cache ,cachetools.Cache ):
            raise TypeError(f"Cache name '{name}' is not of type cachetools.Cache!")
    try:
        _lock.acquire()
        if  name in _mcCacheDict:
            cache = _mcCacheDict[ name ]
        else:
            if  not cache:
                # This will be the default type of cache for McCache.
                if _config.op_level == McCacheLevel.PESSIMISTIC:
                    cache = TLRUCache( maxsize=_config.max_size ,ttl=_config.ttl )
                else:
                    cache = LRUCache( maxsize=_config.max_size )

            if  cache.name is None:
                cache.name = name
                _mcQueue.put((OpCode.INI.name ,time.time_ns() ,cache.name ,None ,None))

            _mcCacheDict[ name ] = cache
    finally:
        _lock.release()

    return cache

del _Cache  # Undeclare it.


# Private thread methods.
#
def _multicaster() -> None:
    """
    Dequeue and multicast out the cache operation to all the members in the group.

    A message is constructed using the following format:
        OP Code:    Cache operation code.  SEE: OpCode enum.
        From:       Unique identify of the source concatenated using:
                        * IP address
                        * Process ID
        Timestamp:  When this request was generated in Python's nano seconds.
        CRC:        Checksum of the payload.
        Payload:    The namespace/key/value tuple for the cache operation.
                        * Namespace
                        * Key
                        * Value
    """    
    logger.debug(f"{SOURCE_ADD}\t{OpCode.NEW.value}\t{time.time_ns()}\t{None}\tMcCache broadcaster is ready." ,extra=LOG_EXTRA)

    sock = socket.socket( socket.AF_INET ,socket.SOCK_DGRAM ,socket.IPPROTO_UDP )
    sock.setsockopt( socket.IPPROTO_IP ,socket.IP_MULTICAST_TTL ,_config.mc_hops )

    while True:
        try:
            msg = _mcQueue.get()
            opc = msg[0]    # Op Code
            tsm = msg[1]    # Timestamp
            nms = msg[2]    # Namespace
            key = msg[3]    # Key
            val = msg[4]    # Value
            crc = None
            if _config.op_level >= McCacheLevel.NEUTRAL.value and val is not None:
                pkl = pickle.dumps( val )
                crc = base64.a85encode( hashlib.md5( pkl ).digest() ,foldspaces=True).decode()
            if _config.op_level == McCacheLevel.PESSIMISTIC:
                val = None
            msg = (SOURCE_ADD ,opc ,tsm ,nms ,key ,crc ,None)   # TODO: Use the 'val'.
            pkl = pickle.dumps( msg )   # Serialized out the tuple.

            if  logger.level == logging.DEBUG:
                logger.debug(f"Im:{SOURCE_ADD} Msg:{msg}" ,extra=LOG_EXTRA)
            
            if  _config.op_level <= McCacheLevel.PESSIMISTIC.value:
                # Need to be acknowledged.
                if (nms ,key ,tsm) not in _mcPending:
                    _mcPending[(nms ,key ,tsm)] = val

            # UDP is not reliable.  Send 2 messages.
            sock.sendto( pkl ,(_config.mc_gip ,_config.mc_port))
            sock.sendto( pkl ,(_config.mc_gip ,_config.mc_port))

            if  _config.op_level <= McCacheLevel.NEUTRAL.value:
                time.sleep(0.01)    # 10 msec.
                sock.sendto( pkl ,(_config.mc_gip ,_config.mc_port))
            if  _config.op_level <= McCacheLevel.PESSIMISTIC.value:
                time.sleep(0.03)    # 30 msec.
                sock.sendto( pkl ,(_config.mc_gip ,_config.mc_port))

        except  Exception as ex:
            logger.error(ex)

def _housekeeper() -> None:
    """
    Background house keeping thread.
    """
    _mcQueue.put((OpCode.NEW.name ,time.time_ns() ,None ,None ,None))
    logger.debug(f"Im:{SOURCE_ADD}\t{OpCode.NEW.value}\t{time.time_ns()}\t{None}\tMcCache housekeeper is ready." ,extra=LOG_EXTRA)

def _listener() -> None:
    """
    Listen in the group for new cache operation from all members.
    """
    logger.debug(f"Im:{SOURCE_ADD}\t{OpCode.NEW.value}\t{time.time_ns()}\t{None}\tMcCache listener is ready." ,extra=LOG_EXTRA)

    # socket.AF_INET:           IPv4
    # socket.SOL_SOCKET:        The socket layer itself.
    # socket.IPPROTO_IP:        Value is 0 which is the default and creates a socket that will receive only IP packet.
    # socket.INADDR_ANY:        Binds the socket to all available local interfaces.
    # socket.SO_REUSEADDR:      Tells the kernel to reuse a local socket in TIME_WAIT state ,without waiting for its natural timeout to expire.
    # socket.IP_ADD_MEMBERSHIP: This tells the system to receive packets on the network whose destination is the group address (but not its own)
    #
    mreq = struct.pack( '4sl' ,socket.inet_aton(_config.mc_gip) ,socket.INADDR_ANY )

    sock = socket.socket( socket.AF_INET    ,socket.SOCK_DGRAM        ,socket.IPPROTO_UDP )
    sock.setsockopt(      socket.SOL_SOCKET ,socket.SO_REUSEADDR      ,1)
    sock.setsockopt(      socket.IPPROTO_IP ,socket.IP_ADD_MEMBERSHIP ,mreq )
    sock.bind((_config.mc_gip ,_config.mc_port))

    while True:
        try:
            pkl = sock.recv( 4096 )
            msg = pickle.loads( pkl )   # De-Serialized in the tuple.
            if  logger.level == logging.DEBUG:
                logger.debug(f"Im:{SOURCE_ADD} Msg:{msg}" ,extra=LOG_EXTRA)

            src = msg[0]    # Source address
            opc = msg[1]    # Op Code
            tsm = msg[2]    # Timestamp
            nms = msg[3]    # Namespace
            key = msg[4]    # Key
            crc = msg[5]    # CRC
            val = msg[6]    # Value

            if  src != SOURCE_ADD:  # Not receiving my own messages.
                mcc = getCache( nms )
                match opc:
                    case OpCode.ACK.value:
                        if (nms ,key ,tsm) in _mcPending:
                            del _mcPending[(nms ,key ,tsm)]
                    case OpCode.DEL.value:
                        if  key in mcc:
                            mcc.__delitem__( key ,False )
                    case OpCode.PUT.value | OpCode.UPD.value:
                        mcc.__setitem__( key ,val ,False )
                    case OpCode.INQ.value:
                        if  logger.level == logging.DEBUG:
                            if  key is  None:
                                c = sorted( mcc.items() ,lambda item: item[0] )
                                msg = (SOURCE_ADD ,opc ,None ,nms ,None ,None ,c)
                            else:
                                val = mcc.get( key ,None )
                                crc = base64.a85encode(hashlib.md5( val ).digest() ,foldspaces=True).decode()
                                msg = (SOURCE_ADD ,opc ,None ,nms ,key ,crc ,None)
                            logger.debug(f"Im:{SOURCE_ADD} Msg:{msg}" ,extra=LOG_EXTRA)
                    case _:
                        pass
        except  Exception as ex:
            logger.error(ex)

# Main section to start the background daemon threads.
#
t1 = threading.Thread(target=_multicaster ,daemon=True)
t1.start()
#t2 = threading.Thread(target=_housekeeper ,daemon=True)
#t2.start()
#t3 = threading.Thread(target=_listener ,daemon=True)
#t3.start()

if __name__ == "__main__":
    duration = 1
    entries = 10
    logger.setLevel(logging.DEBUG)
    cache = getCache()
    bgn = time.time()
    time.sleep( 1 )
    end = time.time()
    #while (end - bgn) < (duration*60):   # Seconds.
    for _ in range(0,60):
        time.sleep( random.randint(1 ,16)/10.0 )
        key = int((time.time_ns() /100) %entries)
        opc = random.randint(0 ,20)
        match opc:
            case 0:
                if  key in cache:
                    # Evict cache.
                    del cache[key]
            case 1|2|3:
                if  key not in cache:
                    # Insert cache.
                    cache[key] = datetime.datetime.utcnow()
            case 4|5|6|7:
                if  key in cache:
                    # Update cache.
                    cache[key] = datetime.datetime.utcnow()
            case _:
                # Look up cache.
                _ = cache.get( key ,None )
        end = time.time()
    time.sleep(3)


# The MIT License (MIT)
# Copyright (c) 2023 Edward Lau
# 
# Permission is hereby granted ,free of charge ,to any person obtaining a copy
# of this software and associated documentation files (the "Software") ,to deal
# in the Software without restriction ,including without limitation the rights
# to use ,copy ,modify ,merge ,publish ,distribute ,sublicense ,and/or sell
# copies of the Software ,and to permit persons to whom the Software is
# furnished to do so ,subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS" ,WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED ,INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY ,FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY ,WHETHER IN AN ACTION OF CONTRACT ,TORT OR
# OTHERWISE ,ARISING FROM ,OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
# OR OTHER DEALINGS IN THE SOFTWARE.
