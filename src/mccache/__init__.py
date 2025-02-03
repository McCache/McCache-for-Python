# See MIT license at the bottom of this script.
#
"""
This is a distributed application cache build on top of the Python Ordered dictionary.
It uses UDP multicast as the transport hence the name "Multi-Cast Cache", playfully abbreviated to "McCache".
SEE: https://www.pico.net/kb/udp-vs-tcp/
SEE: https://stackoverflow.com/questions/47903/udp-vs-tcp-how-much-faster-is-it
SEE: https://support.biamp.com/General/Networking/Multicast_traffic_and_IGMP
SEE: https://en.wikipedia.org/wiki/Distributed_cache
SEE: https://www.centurylink.com/home/help/internet/how-to-improve-gaming-latency.html#:~:text=Low%20latency%20means%20less%20lag,a%20noticeable%20lag%20in%20gaming.
SEE: https://cache.industry.siemens.com/dl/files/587/94772587/att_113195/v1/94772587_ruggedcom_latency_switched_network_en.pdf
SEE: https://highscalability.com/gossip-protocol-explained/

2023-09-10:
    To implement a peer-to-peer communication will be a big management overhead.
    As the cluster is coming online subsequent nodes could miss the prior announcement.
    All the nodes need to setup their connections to connect to all the other cluster members.

    Instead, I am thinking of using the the same multi-cast infrastructure to communicate among the members of the cluster.
    `ACK` packets are small and UDP is faster than TCP.  Modern switches are reliable managing ports thus reducing collision.
    Draft design:
        - New member multicast their presence but member that is coming online later will have missed this announcement.
            - Upon receiving any operations, we check the `members` collection for existence.  Add it, if it doesn't exist.
            - Upon receiving the `BYE` operation, remove it from the `members` collection.
        - `DEL` and `UPD` operations will require acknowledgment.
            - A `pending` dictionary shall be used to keep track of un-acknowledge keys.
                - We queue up a `ACK` operation to be multicast out.
            - All members in the cluster will receive other members acknowledgements.
                - If the received acknowledgment is not in one's `pending` collect, just ignore it.
                - The house keeping thread shall monitor the acknowledgement and request re-acknowledgement.
                    - Keys that have not received an acknowledgement after the seasoning period,
                      a re-acknowledgment `RAK` is initiated.
                    - If we haven't receive acknowledgement after the seasoning period,
                      we log a `warning` or `critical` message.
                        - Remove the key from the `pending` collection.
                        - Remove the key from the `member`  collection.
                            - The member node is down.
            - Members in the cluster will be receiving message from the other members.
              Fragments of the message shall be maintained in memory until the entire message can be re-assembled.

    We will target a 50ms latency or better with the following rough guide:
        -   <30  ms little or no impact on user experience
        - 30-60  ms still OK but noticeable for certain applications (gaming etc.)
        - 60-100 ms mostly acceptable, but users do start to feel it: websites a little slower, downloads not fast enough, etc
        -100-150 ms user feels typically that "the Internet is slow".
        -   >150 ms "it works", but is not acceptable for most commercial applications these days

    Competition:
    So far I have not able to search for anything out on the internet that is doing what this project is doing.
    There is a Python project call `DistCache` but upon digging deeper it is a frontend to Redis.
        https://pypi.org/project/distcache/

    Are we so crazy to think of this design and implementation?
    Surely, this is a solved problem or the herd mentality is on the client-server model.
"""
import atexit
import base64
import logging
import logging.handlers
import os
import pickle
import queue
import random
import socket
import struct
import sys
import threading
import time
import traceback
from cryptography.fernet    import Fernet
from dataclasses            import dataclass, fields
from enum                   import Enum, Flag, IntEnum, StrEnum
from inspect                import getframeinfo, stack
from logging.handlers       import QueueListener  #,RotatingFileHandler
from types                  import FunctionType

import psutil

# If you are using VS Code, make sure your "cwd" and "PYTHONPATH" is set correctly in `launch.json`:
#   "cwd": "${workspaceFolder}",
#   "env": {"PYTHONPATH": "${workspaceFolder}${pathSeparator}src;${env:PYTHONPATH}"},
#
from mccache.__about__ import __app__, __version__  # noqa
from pycache import Cache as PyCache
from pycache import CallbackType

# McCache Section.
#
# FOR:  from mccache import *
__all__ = [ 'clear_cache',
            'get_cache',
            'get_cluster_metrics',
            'get_cache_checksum',
            'McCacheDebugLevel',
            'McCacheOption',
            'McCacheDebugLevel',
            'OpCode',
            'SRC_IP_ADD',
            'SRC_IP_SEQ',
            'FRM_IP_PAD' ]    #,'LOG_FORMAT' ,'LOG_MSGBDY']

BACKOFF     = {1 ,2 ,3 ,5 ,8 ,13}       # Fibonacci backoff.  Seen lots of dropped packets in dev if without backing off.
ONE_MIB     = 1_048_576                 # 1 Mib
ONE_NS_SEC  = 1_000_000_000             # One Nano second.
MAGIC_BYTE  = 0b11111001                # 241 (Pattern + Version)
HEADER_SIZE = 18                        # The fixed length header for each fragment packet.
SEASON_TIME = 1.00                      # Seasoning time to wait before considering a retry. Max of 3 second.  Work with backoff.
HUNDRED     = 100                       # Hundred percent.
UINT2       = 65535                     # Unsigned 2 bytes.
RETRIES     = 3                         # Number of retries before giving up.

class EnableMultiCast( Flag ):
    YES = True      # Multicast out the change.
    NO  = False     # Do not multicast out the change.  This is the default.

    def __repr__(self):
        return self.value

    def __str__(self):
        return str(self.value)

class SocketWorker( Enum ): # TODO: Change to Flag instead Enum.
    SENDER = True   # The sender of a message.
    LISTEN = False  # The listener for messages.

    def __repr__(self):
        return self.value

    def __str__(self):
        return str(self.value)

class McCacheMode( IntEnum ):
    PARTIAL = 0
    FULL    = 1

    def __repr__(self):
        return self.value

    def __str__(self):
        return str(self.value)

class McCacheDebugLevel(IntEnum):
    DISABLE     =   0   # Disabled.
    BASIC       =   1   # Basic detail output.
    EXTRA       =   3   # More  detail output.  Prefix: `>`
    SUPERFLUOUS =   5   # Very  detail output.  Prefix: `>>`

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value

class McCacheOption( StrEnum ):
    # Constants for linter to catch typos instead of at runtime.
    MCCACHE_CACHE_TTL       = 'MCCACHE_CACHE_TTL'
    MCCACHE_CACHE_MAX       = 'MCCACHE_CACHE_MAX'
    MCCACHE_CACHE_MODE      = 'MCCACHE_CACHE_MODE'
    MCCACHE_CACHE_SIZE      = 'MCCACHE_CACHE_SIZE'
    MCCACHE_CACHE_PULSE     = 'MCCACHE_CACHE_PULSE'
    MCCACHE_CONGESTION      = 'MCCACHE_CONGESTION'
    MCCACHE_CRYPTO_KEY      = 'MCCACHE_CRYPTO_KEY'
    MCCACHE_PACKET_MTU      = 'MCCACHE_PACKET_MTU'
#   MCCACHE_QUORUM_MEMBER   = 'MCCACHE_QUORUM_MEMBER'
    MCCACHE_MULTICAST_IP    = 'MCCACHE_MULTICAST_IP'
    MCCACHE_MULTICAST_PORT  = 'MCCACHE_MULTICAST_PORT'
    MCCACHE_MULTICAST_HOPS  = 'MCCACHE_MULTICAST_HOPS'
    MCCACHE_CALLBACK_WIN    = 'MCCACHE_CALLBACK_WIN'
    MCCACHE_DAEMON_SLEEP    = 'MCCACHE_DAEMON_SLEEP'
    MCCACHE_LOG_FILENAME    = 'MCCACHE_LOG_FILENAME'
    MCCACHE_LOG_FORMAT      = 'MCCACHE_LOG_FORMAT'
    MCCACHE_LOG_MSGFMT      = 'MCCACHE_LOG_MSGFMT'
    # Test Env Variables.
    TEST_DEBUG_LEVEL        = 'TEST_DEBUG_LEVEL'
    TEST_MONKEY_TANTRUM     = 'TEST_MONKEY_TANTRUM'

    def __repr__(self):
        return self.value

    def __str__(self):
        return str(self.value)

class OpCode(StrEnum):
    # Keep everything here as 3 character fixed length strings.
    ACK = 'ACK'     # Acknowledgement of a received message fragment.
    BYE = 'BYE'     # Member announcing it is leaving the group.
    DBG = 'DBG'     # Member communicating debug information..
    DEL = 'DEL'     # Member requesting the group to delete the cache entry.
    ERR = 'ERR'     # Member announcing an error to the group.
    EVT = 'EVT'     # Member announcing an eviction to the group.
    FYI = 'FYI'     # Member communicating information.
    INQ = 'INQ'     # Member inquiring about a cache entry from the group.
    INS = 'INS'     # Insert a new cache entry.
    MET = 'MET'     # Member inquiring about the cache metrics from the group.
    NAV = 'NAV'     # Member informing that the request cannot be service for the entry is no longer available.
    NEW = 'NEW'     # New member announcement to join the group.
    NAK = 'NAK'     # Negative acknowledgement.  Didn't receive the message fragment.
    NOP = 'NOP'     # No operation.
    PAU = 'PAU'     # Member requesting the group to pause a little for it to catch up.
    RAK = 'RAK'     # Member requesting acknowledgment for a message from the group.
    REQ = 'REQ'     # Member requesting resend message fragment from originator.
    RSD = 'RSD'     # Member to re-send the entire message to the group.
    RST = 'RST'     # Member requesting reset of the cache.
    SYC = 'SYC'     # Member requesting cache synchronizing among the group members.
    UPD = 'UPD'     # Update an existing cache entry.
    WRN = 'WRN'     # Member announcing an warning to the group.

    def __repr__(self):
        return self.value

    def __str__(self):
        return str(self.value)


@dataclass
class McCacheConfig:
    alert_email: str    = None          # Email address to send alert messages. Scheme: smtp://username;password@server:port
    cache_ttl: int      = 3600          # Total Time to Live in seconds for a cached entry.
                                        # SEE: https://dev.acquia.com/blog/how-choose-right-cache-expiry-lifetime
    cache_max: int      = 256           # Max entries threshold for triggering entries eviction.
    cache_size: int     = 256*4096*8    # Max size in bytes threshold for triggering entries eviction.
    cache_pulse:int     = 5             # Cache synchronization heartbeat pulse in minutes.
    cache_mode: int     = 1             # Cache consistent syncing mode.  0=Partial sync ,1=Full sync.
    cache_sync_on: float= 0.0           # Cache last synchronized time from this node to the members.
    congestion: int     = 25            # The maximum cutoff to start congestion control.
    crypto_key: str     = None          # The encryption/decryption key.
    packet_mtu: int     = 1472          # Maximum Transmission Unit of your network packet payload.
                                        # Ethernet frame is 1500 without the static 20 bytes IP and 8 bytes ICMP headers.  Jumbo frame is 9000.
                                        # SEE: https://www.youtube.com/watch?v=Od5SEHEZnVU and https://www.youtube.com/watch?v=GjiDmU6cqyA
    packet_pace: float  = 0.1           # 100ms for congestion control.
                                        # SEE: https://cdn.ttgtmedia.com/rms/onlineimages/split_seconds-h.png
                                        # OS quanta: Windows ~ 120ms and *nix ~ 100ms.
#   quorum_member: int  = 0             # A flag to designate if this node is a member of the quorum.  Quorum member have extra duty.
    multicast_ip: str   ='224.0.0.3'    # Unassigned multi-cast IP.
    multicast_port: int = 4000          # Unofficial port.  Was for Diablo II game.
    multicast_hops: int = 3             # 1 is only local subnet on the same switch/router.
#   queue_ib_size: int  = 65536         # Internal  in-bound queue size to prevent run away memory consumption.  Set it large but no infinite.
#   queue_ob_size: int  = 65536         # Internal out-bound queue size to prevent run away memory consumption.  Set it large but no infinite.
    callback_win: int   = 5             # Change callback window size seconds (1-999).
    monkey_tantrum: int = 0             # Chaos monkey tantrum % level (0 - 99).
    daemon_sleep: float = SEASON_TIME   # House keeping snooze seconds (0.33 - 3.0).
    random_seed: int    = int(str(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET )[0][4][0]).split(".")[3])
    log_filename: str   = 'log/mccache.log'
    log_format: str     = f"%(asctime)s.%(msecs)03d (%(ipV4)s.%(process)d.%(thread)05d)[%(levelname)s {__app__}@%(lineno)d] %(message)s"
    log_msgfmt: str     = '{now} L#{lno:>4} Im:{iam}\t{sdr}\t{opc}\t{tsm:<18}\t{nms}\t{key}\t{crc}\t{msg}'
    debug_level: int    = 0             # Debug tracing is default to off/false. 0=off ,1=basic ,3=extra ,5=superfluous

# Module initialization.
#
_lock = threading.RLock()               # Module-level lock for serializing access to shared data.
_mySelf:    dict[str]         = {}      # All my IP address.
_mcConfig:  McCacheConfig     = None    # Private McCache configuration.
_mcCrypto:  Fernet            = None    # Private encryption/decryption function.
_mcCache:   dict[str   ,dict] = {}      # Private dictionary to segregate the cache namespace.
_mcArrived: dict[tuple ,dict] = {}      # Private dictionary to manage arriving fragments to be assemble into a value message.
_mcPending: dict[tuple ,dict] = {}      # Private dictionary to manage send fragment needing acknowledgements.
_mcMember:  dict[str   ,int]  = {}      # Private dictionary to manage members in the group.  IP: Timestamp.
_mcLgLsnr:QueueListener= None           # Private log listener.
_mcIBQueue:queue.Queue = queue.Queue()  # Private inbound  operation queue.
_mcOBQueue:queue.Queue = queue.Queue()  # Private outbound operation queue.
_mcQueueStats: dict = {
    'ibq': {'count': 1 ,'avgsize': 0 ,'maxsize': 0 ,'opc': {}},
    'obq': {'count': 1 ,'avgsize': 0 ,'maxsize': 0 ,'opc': {}}
}

# Setup normal and short IP addresses for logging and other use.
_mySelf = { me[4][0] for me in socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET ) }

LOG_EXTRA: dict   = {'ipv4': None ,'ipV4': None ,'ipv6': None ,'ipV6': None }    # Extra fields for the logger message.
LOG_EXTRA['ipv4'] = sorted(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET ))[0][4][0].strip()
LOG_EXTRA['ipV4'] = ''.join([hex(int(g)).removeprefix("0x").zfill(2) for g in LOG_EXTRA['ipv4'].split('.')])
try:
    LOG_EXTRA['ipv6'] = socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET6)[0][4][0]
    LOG_EXTRA['ipV6'] = LOG_EXTRA['ipv6'].replace(':' ,'')
except socket.gaierror:
    pass
SRC_IP_ADD: str = f"{LOG_EXTRA['ipv4']}"        # Source IP address.
SRC_IP_SEQ: int = int(SRC_IP_ADD.split('.')[3]) # Last octet.
FRM_IP_PAD: str = ' '*len(LOG_EXTRA['ipv4'])


# Public methods.
#
def _default_callback(ctx: dict) -> bool:
    """Default callback method to be notified of changes.

    Don't write code in here that will block the caller.
    If you are going to use your own method, you should spin out on a different thread to handle this alert.

    Args:
        ctx :dict   A context dictionary of the following format:
                {
                    typ:    Type of alert. 1=Deletion ,2=Update ,3=Incoherent
                    nms:    Cache namespace.
                    key:    Identifying key.
                    lkp:    Lookup timestamp.
                    tsm:    Current entry timestamp.
                    elp:    Elapsed time.
                    prvcrc: Previous value CRC.
                    newcrc: Current  value CRC.
                }
    Return:
        bool    True means this method is successful and the caller should continue down its execution path.
    """
    if  _mcConfig.debug_level >= McCacheDebugLevel.BASIC:
        match ctx['typ']:
            case 1: # Deletion
                _log_ops_msg( logging.DEBUG ,opc=OpCode.WRN ,tsm=PyCache.tsm_version() ,nms=ctx['nms'] ,key=ctx['key'] ,crc=ctx['newcrc']
                                            ,msg=f"^   WRN {ctx['key']} got deleted     within {ctx['elp']:6} sec in the background." )
            case 2: # Updates
                _log_ops_msg( logging.DEBUG ,opc=OpCode.WRN ,tsm=PyCache.tsm_version() ,nms=ctx['nms'] ,key=ctx['key'] ,crc=ctx['newcrc']
                                            ,msg=f"^   WRN {ctx['key']} got updated     within {ctx['elp']:6} sec in the background." )
            case 3: # Incoherence
                _log_ops_msg( logging.DEBUG ,opc=OpCode.WRN ,tsm=PyCache.tsm_version() ,nms=ctx['nms'] ,key=ctx['key'] ,crc=ctx['newcrc']
                                            ,msg=f"^   WRN {ctx['key']} got incoherent  within {ctx['elp']:6} sec in the background." )
    return  True

def get_cache( name: str | None=None ,callback: FunctionType = _default_callback ) -> PyCache:
    """Return a cache with the specified name ,creating it if necessary.

    If no name is provided, it shall be defaulted to `mccache`.

    SEE: https://dropbox.tech/infrastructure/caching-in-theory-and-practice
    Args:
        name:       Name to isolate different caches.  Namespace dot notation is suggested.
        callback:   Your function to call if a value got updated just after you have read it.
    Return:
        Cache instance identified with given name or the default `mccache`.
    """
    if  name:
        if  not isinstance( name ,str ):
            raise TypeError('The cache name must be a string!')
    else:
        name  =  'mccache'

    if  name  in _mcCache:
        cache =  _mcCache[ name ]
    else:
        debug =(_mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS)
        msgbdy= _mcConfig.log_msgfmt.replace('{iam}' ,SRC_IP_ADD ).replace('{sdr}' ,f'   {FRM_IP_PAD}').replace('{msg}' ,'>>> {msg}')
        cache = PyCache(
                    name    = name,
                    max     =_mcConfig.cache_max,
                    size    =_mcConfig.cache_size,
                    ttl     =_mcConfig.cache_ttl,
                    msgbdy  = msgbdy,
                    logger  = logger,
                    queue   =_mcOBQueue,
                    callback= callback,
                    cbwindow=_mcConfig.callback_win,
                    debug   = debug # Enable extra debugging inside this object.
                )
        _mcCache[ name ] = cache
    return cache

def clear_cache( name: str | None = None ,node: str | None = None ) -> None:
    """Clear all the distributed caches.

    Request all the members in the cluster to clear their cache without rebooting their instance.
    This method is intended to be used from a node that is not participating in the cluster.

    Args:
        name:   Name of the cache.  If none is provided, all caches checksum shall be produced.
        node:   IP address for a specific member to query.
                If none is provided, all members in the cluster shall be queried.
    Return:
        None
    """
    # TODO: Rethink querying local and all nodes.
    if  node and node not in _mcMember and node not in _mySelf:
        logger.error(f"Node: {node} does not exist in the cluster.")
        return

    _mcOBQueue.put((OpCode.RST ,PyCache.tsm_version() ,name ,None ,None ,None ,node))
    _mcOBQueue.put((OpCode.INQ ,PyCache.tsm_version() ,name ,None ,None ,None ,node))

def get_cluster_metrics( name: str | None = None ,node: str | None = None ) -> None:
    """Inquire the metrics for all the distributed caches.

    Queue the `MET` operation into the cluster.

    Args:
        name:   Name of the cache.  If none is provided, all caches checksum shall be produced.
        node:   IP address for a specific member to query.
                If none is provided, all members in the cluster shall be queried.
    Return:
        None
    """
    # TODO: Rethink querying local and all nodes.
    if  node and node not in _mcMember and node not in _mySelf:
        logger.error(f"Node: {node} does not exist in the cluster.")
        return

    _mcOBQueue.put((OpCode.MET ,PyCache.tsm_version() ,name ,None ,None ,None ,node))

def get_local_metrics( name: str | None = None ) -> dict:
    """Inquire the local cache metrics.
    """
    return  _get_local_metrics( name )

def get_cache_checksum( name: str | None = None ,key: str | None = None ,node: str | None = None ) -> None:
    """Inquire the checksum for all the distributed caches.

    Queue the `INQ` operation into the cluster.

    Args:
        name:   Name of the cache.  If none is provided, all caches checksum shall be produced.
        key:    Specific key to checksum.
        node:   IP address for a specific member to query.
                If none is provided, all members in the cluster shall be queried.
    Return:
        None
    """
    # TODO: Rethink querying local and all nodes.
    if  node and not( node in _mySelf or node in _mcMember ):
        logger.error(f"Input node: {node} does not exist in the cluster.")
        return

    tsm = PyCache.tsm_version() # To maintain a common unique checkpoint across the cluster.
    if  node is None or node != SRC_IP_ADD:
        # Either broadcast the inquiry out or unicast to a specific member in the cluster other than myself.
        _mcOBQueue.put((OpCode.INQ ,tsm ,name ,key ,None ,None ,node))
    else:
        aky_t = ()
        key_t = ( name ,key ,tsm )
        val_o = ( OpCode.INQ ,None ,None )
        _ = _decode_message( aky_t ,key_t ,val_o ,sdr=None )    # Ask myself.

def get_local_checksum( name: str | None = None ,key: str | None = None ) -> dict:
    """
    Inquire the local cache checksum.
    """
    return  _get_local_checksum( name ,key )


# Private utilities methods.
#
def _is_valid_multicast_ip( ip: str ) -> bool:
    """Validate the input is a valid multicast ip address.

    Args:
        ip: str IPv4 address
    Return:
        bool    True if it is a valid multicast IP address, else False.
    """
    # SEE: https://www.iana.org/assignments/multicast-addresses/multicast-addresses.xhtml
    mcips = {
        224: {
            0: {
                # Local Network.
                0:  {3 ,26 ,255}.union({range(69 ,101)}).union({range(122 ,150)}).union({range(151 ,251)}),
                # Adhoc Block I.
                2:  {0}.union({range(18 ,64)}),
                6:  {range(145 ,161)}.union({range(152 ,192)}),
                12: {range(136 ,256)},
                17: {range(128 ,256)},
                20: {range(208 ,256)},
                21: {range(128 ,256)},
                23: {range(182 ,192)},
                245:{range(0   ,256)},
                # TODO: Adhoc Block II.
                # TODO: Adhoc Block III.
            },
        }
    }

    sgm = [ int(d) for d in ip.split(".")]  # IP address segments.
    return  not(len(sgm) == 4 and   # noqa: PLR2004
                sgm[0] == 224 and   # noqa: PLR2004
                sgm[0] in mcips and
                sgm[1] in mcips[ sgm[0]] and
                sgm[2] in mcips[ sgm[0]][ sgm[1]] and
                sgm[3] in mcips[ sgm[0]][ sgm[1]][ sgm[2]]
            )

def _load_config( project_config: str = 'pyproject.toml' ):
    """Load the McCache configuration.

    Configuration will loaded in the following order over writing the previously set values.
    1) `pyproject.toml`
    2) Environment variables.

    Data type validation is performed.

    Args:
        project_config: Path to the configuration 'pyproject.toml' file.
    Return:
        Dataclass   A new configuration.
    """
    tmlcfg = {}
    config = McCacheConfig()

    try:
        import tomllib  # Introduced in Python 3.11.
        with open( project_config ,encoding="utf-8" ) as fp:
            tmlcfg = tomllib.loads( fp.read() )
    except  FileNotFoundError:
        pass

    fldtyp = { f.name: f.type for f in fields( config )}
    for envar in McCacheOption:
        cfvar = str( envar ).replace('MCCACHE_' ,'').replace('TEST_' ,'').lower()

        if 'tool' in tmlcfg and 'mccache' in  tmlcfg['tool'] and cfvar in tmlcfg['tool']['mccache']:
            # Dynamically set the config properties.
            if   fldtyp[ cfvar ] is int   and isinstance(tmlcfg['tool']['mccache'][ cfvar ] ,int):
                setattr( config ,cfvar              ,int(tmlcfg['tool']['mccache'][ cfvar ]))
            elif fldtyp[ cfvar ] is float and isinstance(tmlcfg['tool']['mccache'][ cfvar ] ,float):
                setattr( config ,cfvar            ,float(tmlcfg['tool']['mccache'][ cfvar ]))
            else:   # String
                setattr( config ,cfvar              ,str(tmlcfg['tool']['mccache'][ cfvar ]))

        # NOTE: Config from environment variables trump over config read from a file.
        if  envar in os.environ and cfvar in  fldtyp:
            # Dynamically set the config properties.
            if   fldtyp[ cfvar ] is bool  and     str(os.environ[ envar ]).isnumeric():
                setattr( config ,cfvar          ,bool(os.environ[ envar ]))
            elif fldtyp[ cfvar ] is int   and     str(os.environ[ envar ]).isnumeric():
                setattr( config ,cfvar           ,int(os.environ[ envar ]))
            elif fldtyp[ cfvar ] is float and not str(os.environ[ envar ]).isnumeric() and str(os.environ[ envar ]).replace('.' ,'').isnumeric():
                setattr( config ,cfvar         ,float(os.environ[ envar ]))
            else:
                setattr( config ,cfvar           ,str(os.environ[ envar ]))

        if  cfvar == 'multicast_ip' and ':' in config.multicast_ip:
            mcip = config.multicast_ip.split(':')
            config.multicast_ip = mcip[0]
            if  len(mcip) > 1:
                config.multicast_port = int(mcip[1])

        if  _is_valid_multicast_ip( config.multicast_ip ):
            cfgip =  config.multicast_ip
            _mcip = _mcConfig.multicast_ip
            _port = _mcConfig.multicast_port
            logger.warning(f"{cfgip} is an invalid multicast IP address!  Defaulting to IP: {_mcip}:{_port}", extra=LOG_EXTRA)
            config.multicast_ip   = _mcConfig.multicast_ip
            config.multicast_port = _mcConfig.multicast_port
    return  config

def _get_mccache_logger( debug_log: str | None = None ) -> logging.Logger:
    """Setup the McCache specific logger.

    Args:
        debug_log   Full path to a file for the log message to be written to.
    Return:
        A logger specific to the McCache.
    """
    shdlr = None
    fhdlr = None
    logger: logging.Logger = logging.getLogger('mccache')   # McCache specific logger.
    logger.propagate = False
    logger.handlers.clear() # This is strictly a McCache logger.
    fmtr  = logging.Formatter(fmt=_mcConfig.log_format ,datefmt='%Y%m%d%a %H%M%S' ,defaults=LOG_EXTRA)

    if 'TERM' in os.environ or ('SESSIONNAME' in os.environ and os.environ['SESSIONNAME'] == 'Console'):
        shdlr = logging.StreamHandler()
        shdlr.setFormatter( fmtr )
        logger.setLevel( logging.INFO )
    if  debug_log:
        os.makedirs( os.path.dirname( debug_log ), exist_ok=True )
        fhdlr = logging.FileHandler(  debug_log ,mode="a" ,encoding="utf-8" )
        fhdlr.setFormatter( fmtr )
#       fhdlr = RotatingFileHandler(  debug_log ,mode="a" ,encoding="utf-8" ,maxBytes=(2*1024*1024*1024), backupCount=99)   # 2Gib with 99 backups.
#       fhdlr.setFormatter( fmtr )
        logger.setLevel( logging.DEBUG )

    logQ  = queue.Queue()
    qhdlr = logging.handlers.QueueHandler( logQ )
    logger.addHandler( qhdlr )
    if  shdlr and fhdlr:
        logLstnr = logging.handlers.QueueListener( logQ ,shdlr ,fhdlr )
    elif  shdlr:
        logLstnr = logging.handlers.QueueListener( logQ ,shdlr )
    elif fhdlr:
        logLstnr = logging.handlers.QueueListener( logQ ,fhdlr )
    logLstnr.start()

    return logger ,logLstnr

def __get_msgcomp( left: object ,right: object) -> str:
    if      left and right  and left == right:
        return '='
    elif    left is None  and right is not None:
        return '~'
    elif    left is None  or  left  <  right:
        return '<'
    else:
        return '>'

def _log_ops_msg(
        lvl: int,                   # Logging level
        opc: str,                   # Op Code
        sdr: str    | None = None,  # Sender
        tsm: int    | None = None,  # Timestamp
        nms: str    | None = None,  # Namespace
        key: object | None = None,  # Key
        crc: bytes  | None = None,  # Checksum (md5)
        msg: str    | None = None,  # Message to log.
        # In message replacement tokens.
        prvtsm: int | None = None,  # Previous Timestamp
        prvcrc: bytes|None = None,  # Previous Checksum (md5)
        tsmcmp: str | None = None,  # Timestamp comparator.
        crccmp: str | None = None,  # Checksum  comparator.
    ) -> None:  # Message
    """A standardize format to log out McCache operation messages making them easier to parse in the test.

    Args:
        lvl: int        Log level.
        opc: str        The operation code.
        sdr: str        Optional sender.
        tsm: int        Optional timestamp in nano seconds.
        nms: str        Optional cache namespace.
        key: object     Optional key object.
        crc: bytes      Optional checksum for the value.
        msg: str        Optional comment or description.
        #
        prvtsm: int     Optional previous Timestamp
        prvcrc: bytes   Optional previous Checksum (md5)
        tsmcmp: str     Optional Timestamp comparator.
        crccmp: str     Optional Checksum  comparator.
    Return:
        None
    """
    # TODO: Spawn it off in a thread. Too much processing here.
    # Use my own timestamp instead of what is provided by the logger via %(created) because I need chronological precision that is not buffered.
    now = PyCache.tsm_version_str()
    lno = getframeinfo(stack()[1][0]).lineno    # The line no where this method was called from.
    iam = SRC_IP_ADD
    md5 = crc

    if  sdr is None:
        sdr = f"   {FRM_IP_PAD}"
    else:
        sdr =  f"Fr:{sdr}"
    if  tsm is None:
        tsm =  f"T={' '*16}"    #   04:13:56.108051950
    else:
        tsm = f"{time.strftime('%H:%M:%S' ,time.gmtime( tsm // ONE_NS_SEC))}.{tsm % ONE_NS_SEC:0<9}"
    if  nms is None:
        nms =  f"N={' '* 5}"
    if  key is None:
        key =  f"K={' '* 6}"
    if  msg is None:
        msg = ''
    if  crc is None:
        crc =  \
        md5 =  f"C={' '*20}"
    elif isinstance( crc ,bytes ):
        crc =  \
        md5 =  base64.b64encode( crc ).decode()[:-2]    # NOTE: Without '==' padding.
    #   Additional in message replacement tokens.
    if  prvtsm is None:
        prvtsm =  f"T={' '*16}"
    else:
        prvtsm = f"{time.strftime('%H:%M:%S' ,time.gmtime( int(prvtsm // ONE_NS_SEC) ))}.{prvtsm % ONE_NS_SEC:0<9}"
    if  prvcrc is None:
        prvcrc = f"C={' '*22}"
    elif isinstance( prvcrc ,bytes ):
        prvcrc = base64.b64encode( prvcrc ).decode()[:-2]   # NOTE: Without '==' padding.

    # Cleanup the input message.
    if  isinstance( msg ,str ):
        msg = msg.format(   now=now ,iam=iam ,sdr=sdr ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,md5=md5,
                            # Following are the optional in message replacement.
                            prvtsm=prvtsm ,prvcrc=prvcrc ,tsmcmp=tsmcmp ,crccmp=crccmp )
    # Standardize the output format.
    txt =  _mcConfig.log_msgfmt.format( now=now ,lno=lno ,iam=iam ,sdr=sdr ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,md5=md5 ,msg=msg )

    logger.log( lvl ,txt )

def _get_local_metrics( name: str | None = None ) -> dict:
    """Return the metrics collected for the entire cache.

        SEE: https://psutil.readthedocs.io/en/latest/
        SEE: https://github.com/McCache/McCache-for-Python/blob/main/docs/BENCHMARK.md

    Args:
        name:   The case sensitive name of the cache.
    Return:
        Dictionary of cache statistics.
    """
    prc: dict = {}
    nms: dict = {}

    _mcQueueStats['ibq']['opc'] = dict(sorted(_mcQueueStats['ibq']['opc'].items()))
    _mcQueueStats['obq']['opc'] = dict(sorted(_mcQueueStats['obq']['opc'].items()))

    prc = { 'process': {
                'avgload':   f'{psutil.getloadavg()}',              # NOTE: Simulated on window platform.
                'cputimes':  f'{psutil.cpu_times()}',
                'meminfo':   f'{psutil.Process().memory_info()}',   # Memory info for current process.
                'netioinfo': f'{psutil.net_io_counters()}'
            },
            'mqueue':   _mcQueueStats
        }   # Process stats.
    nms =   {n: {   'count':    len(_mcCache[ n ]),
                    'size':     _mcCache[ n ].ttlSize,
                    'spikes':   _mcCache[ n ].spikes,
                    'spikeInt':
                        round(  _mcCache[ n ].spikeInt / ONE_NS_SEC ,4 ),
                    'misses':   _mcCache[ n ].misses,
                    'lookups':  _mcCache[ n ].lookups,
                    'inserts':  _mcCache[ n ].inserts,
                    'updates':  _mcCache[ n ].updates,
                    'deletes':  _mcCache[ n ].deletes,
                    'evicts':   _mcCache[ n ].evicts,   # Normal ttl or capacity evictions.
                }
                for n in _mcCache.keys() if n == name or name is None
        }   # Namespace stats.

    return prc | nms    # Python v3.9 way to merge multiple dictionaries.

def _get_local_checksum( arg: object | None = None ,key: str | None = None ) -> dict:
    """Get the local checksum for the cache.

    Args:
        arg:    Either the cache or the name of the cache.
    Return:
        Dictionary of cache keys with their checksums.
    """
    mcc: dict = None
    if  arg is  None:
        mcc = get_cache()
    elif  isinstance( arg ,str ):   # name of the cache is passed in.
        mcc = get_cache( arg )
    elif  isinstance( arg ,dict ):  # The cache dictionary is passed in.
        mcc = arg
    else:
        raise TypeError("Unsupported type")

    try:
        _lock.acquire()
        keys = [ key ] if key else sorted( mcc.keys() )
        # NOTE: Don't dump the raw data out for security reason.
        crcs = { k:{'crc': base64.b64encode( mcc.metadata[k]['crc'] ).decode()[:-2], # NOTE: Without '==' padding.
                    'tsm': f"{time.strftime('%H:%M:%S' ,time.gmtime( mcc.metadata[k]['tsm']//ONE_NS_SEC) )}.{mcc.metadata[k]['tsm']%ONE_NS_SEC:0<8}",
                    }
                    for k in keys if k in mcc.metadata}
    finally:
        _lock.release()

    return crcs

def _get_socket(is_sender: SocketWorker) -> socket.socket:
    """Get a configured socket for either the sender or receiver.

    Args:
        is_sender:  A switch to pick the socket to be configire for either sender or receiver.
    Return:
        A configured socket ready to be used.
    """
    # AF_INET:           IPv4
    # SOL_SOCKET:        The socket layer itself.
    # IPPROTO_IP:        Value is 0 which is the default and creates a socket that will receive only IP packet.
    # INADDR_ANY:        Binds the socket to all available local interfaces.
    # SO_REUSEADDR:      Tells the kernel to reuse a local socket in TIME_WAIT state ,without waiting for its natural timeout to expire.
    # SO_SNDBUF          Sets or gets the maximum socket send buffer in bytes.
    # IP_ADD_MEMBERSHIP: This tells the system to receive packets on the network whose destination is the group address (but not its own)

    addrinfo = socket.getaddrinfo( _mcConfig.multicast_ip ,None )[0]
    sock = socket.socket( addrinfo[0] ,socket.SOCK_DGRAM )

    # Default socket.SO_SNDBUF size:
    #   Windows:  64K
    #   MacOS:   128K
    #   Linux:   212K
    sock.setsockopt(  socket.SOL_SOCKET ,socket.SO_SNDBUF  ,256*1024 )
    sock.setsockopt(  socket.SOL_SOCKET ,socket.SO_RCVBUF  ,256*1024 )

    if  is_sender.value:
        # Set non-blocking send.
        sock.setblocking( False )

        # Set Time-to-live (optional)
        ttl_bin = struct.pack('@I' ,_mcConfig.multicast_hops)
        if  addrinfo[0] == socket.AF_INET:  # IPv4
            sock.setsockopt( socket.IPPROTO_IP  ,socket.IP_MULTICAST_TTL    ,ttl_bin )
        else:
            sock.setsockopt( socket.IPPROTO_IPV6,socket.IPV6_MULTICAST_HOPS ,ttl_bin )
    else:
        sock.setsockopt( socket.SOL_SOCKET ,socket.SO_REUSEADDR ,1 )
        sock.bind(('' ,_mcConfig.multicast_port))    # It need empty string or it will throw an "The requested address is not valid in its context" exception.

        group_bin = socket.inet_pton( addrinfo[0] ,addrinfo[4][0] )
        # Join multicast group
        if  addrinfo[0] == socket.AF_INET:  # IPv4
            mreq = group_bin + struct.pack('@I' ,socket.INADDR_ANY )
            sock.setsockopt( socket.IPPROTO_IP  ,socket.IP_ADD_MEMBERSHIP   ,mreq )
        else:
            mreq = group_bin + struct.pack('@I' ,0)
            sock.setsockopt( socket.IPPROTO_IPV6,socket.IPV6_JOIN_GROUP     ,mreq )

    return  sock

def _make_pending_ack( key_t: tuple ,val_t: tuple ,members: dict | str ,frame_size: int ) -> dict:
    """Make a dictionary entry for the management of acknowledgements.

    The input key and value shall be concatenated into a single out going binary message.
    The size of the out going message can be larger than the Ethernet MTU.
    The outgoing message shall be chunk out into fragments to be send out upto 255 chunks.
    Each fragment has a preceding fixed length header follow by fragment payload.

    Header:
        Magic:      5 bits +--  1 byte
        Version:    3 bits |
        Reserved:   1 byte      # Reserved bitmap for future needs.
        Sequence:   1 byte      # The zero based sequence number.
        Fragments:  1 byte      # The total number of fragments for the outgoing message.
        Key Length: 2 bytes     # The length of the serialized key tuple.
        Val Length: 2 bytes     # The length of the serialized value tuple.
        Timestamp:  8 bytes     # The initial timestamp in nano seconds from the input key tuple.
        Receiver:   2 byte      # The last octet of the receiver IP address.
                   -------
                   18 bytes
    Args:
        key_t:      Key tuple object made up of (namespace ,key ,timestamp).
        val_t:      Value tuple.  (opc ,crc ,val)
        members:    Set of members in the cluster or a specific member IP, excluding self.
        frame_size: The size of the usable Ethernet frame (minus the IP header).
    Return:
        A dictionary of the following structure:
        {
            'tsm':     int      # The time of the original message was queued in nano seconds.
            'opc':     str,     # The operation code.
            'crc':     str,     # The checksum for the entire message.
            'message': list(),  # Ordered list of fragments for re-send.
            'members': {
                ip: {           # IP address of the target node.
                    'unack':    set(),  # Set of unacknowledged fragments for the given IP key.
                    'backoff':  set()   # Backoff scale.
                }
            }
        }
    Raise:
        BufferError:    When the serialized key or value size is greater than unsigned two bytes.
        OverflowError:  When the serialized key or value resulted in more than 255 fragments.
    """
    # NOTE: An informal test of "pickling" out a large dictionary of 5000 patient objects
    #       to a file took less that 1.5 seconds.
    #       The output file size was 9,820,708 bytes.
    #       Encrypting this pickled object took approx 1.2 seconds of size of 13,094,372 approx 33% larger.

    tsm: int = key_t[ 2 ]                   # 8 bytes unsigned nanoseconds for timestamp.
    key_b: bytes = pickle.dumps( key_t )    # Serialized the key.
    key_s: int = len( key_b )
    if  key_s > UINT2:   # 2 bytes unsigned.
        raise BufferError(f"Pickled key for {key_t} size is {key_s}") # noqa: EM102

    val_b: bytes = pickle.dumps( val_t )    # Serialized the message.
    if  _mcCrypto:  # Cryptography is enabled.
        val_b = _mcCrypto.encrypt( val_b )

    val_s: int = len( val_b )
    if  val_s > UINT2:   # 2 bytes unsigned.
        raise BufferError(f"Pickled val for {key_t} size is {val_s}") # noqa: EM102

    bgn: int
    end: int
    rcv: int = 0    # The targeted specific receiving member.  Zero implies all.
    hdr_b: bytes
    frg_b: bytes
    pay_b: bytes = key_b + val_b    # Total binary payload to be send out.
    pay_s: int = len( pay_b )
    frg_m: int = frame_size - HEADER_SIZE # Max frame size.
    frg_c: int = int( pay_s / frg_m) +1

    if  frg_c > 255:
        # NOTE: Message too large resulted in more than 255 fragments.
        nms: str    = key_t[0] # Namespace
        key: object = key_t[1] # Key
        mcc: dict   = get_cache( nms )
        # Delete it locally and multicast it out.
        try:
            mcc.__delitem__( key ,tsm ,EnableMultiCast.YES )
        except  KeyError:
            #   Deep Tracing
            if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                opc: str = val_t[0] # Op Code
                crc: str = val_t[1] # Checksum
                _log_ops_msg( logging.DEBUG ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                            ,msg=f">   {key} no longer exist to be fragmented out for transmission!" )

        raise OverflowError(f"Message too large. {pay_b} bytes in {frg_c} fragments.")

    ack = { 'tsm': tsm,
            'opc': val_t[0],
            'crc': val_t[1],
            'message': [None] * frg_c,  # Pre-allocated the list.
            'members': {
                ip: {'unack': { f },
                     'backoff': BACKOFF.copy()
                    } for ip in members.keys() for f in range(0 ,frg_c) # TODO: Need to support targeting of individual member.
            }
        }

    # NOTE:  If only one entry, therefore targetting a specific node.
    if  len( members ) == 1:
        rcv  = int(next(iter( members )).split('.')[3]) # Last octet of the receiver IP.

    for seq in range( 0 ,frg_c ):
        bgn  = seq * frg_m
        end  = bgn + frg_m if (bgn + frg_m) < pay_s else pay_s +1
        frg_b= pay_b[ bgn : end ] # A fragment of the message.

        try:
            # NOTE: 'HH' MUST come after 'BBBB' for it impact the length.
            hdr_b =  struct.pack('@BBBBHHQH' ,MAGIC_BYTE ,0 ,seq ,frg_c ,key_s ,val_s ,tsm ,rcv)
            ack['message'][ seq ] = hdr_b + frg_b
        except struct.error as ex:
            raise(f"Failed to pack header for {key_t} due to {ex}. seq: {seq} ,frg_c: {frg_c} ,tsm: {tsm} ,rcv: {rcv} ,ack: {ack}")  from  ex
    return  ack

def _collect_fragment( pkt_b: bytes ,sender: str ) -> tuple:
    """Collect the arrived fragment to be later assembled back into an incoming key and value.

    The fragments are collected in the global `_mcArrived` dictionary of the following structure:
        {
            aky_t: {
                'tsm':      int,    # The time of the original message was queued in nano seconds.
                'message':  list(), # Ordered list of fragments for the message.
                'backoff':  set{}   # Backoff scale.
            }
        }

    Args:
        pkt_b: bytes    The received/input binary packet.
        sender: str     The sender/originator for the binary packet.
    Return:
        key tuple       The assembly key tuple if all fragments are received, else None
                        Key tuple is made up of the following segments:
                            - Sender
                            - Fragment Count
                            - Key Size
                            - Timestamp
    """
    mgc:   int      # Packet magic byte.
    seq:   int      # Fragment sequence.
    frg_c: int      # Fragment size/count.
    key_s: int      # Key size.
    tsm:   int      # Timestamp.
    rcv:   int      # Specific receiver.
    hdr_b: bytes    # Packet header.

    if  len( pkt_b ) <= HEADER_SIZE:
        logger.warning(f"Invalid packet header! Must be greater than {HEADER_SIZE}.")
        return  False

    hdr_b = pkt_b[ 0 : HEADER_SIZE ]
    mgc ,_ ,seq ,frg_c ,key_s ,_ ,tsm ,rcv = struct.unpack('@BBBBHHQH' ,hdr_b)    # Unpack the packet

    if  mgc != MAGIC_BYTE:
        logger.warning(f"Received a foreign non McCache packet from {sender}.")
        return  False

    #   Deep Tracing
    if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS + 2:
        _log_ops_msg( logging.DEBUG ,opc=OpCode.FYI ,sdr=sender ,tsm=tsm
                                    ,msg=f">>  Received fragment header from: {sender} ,seq={seq} ,frg_c={frg_c} ,key_s={key_s} ,rcv={rcv}" )

    if  rcv > 0 and rcv != SRC_IP_SEQ:
        # Packet is "unicast", but NOT to me.
        return  False

    # Packet is to be multicast to all members.
    aky_t: tuple = (sender ,frg_c ,key_s ,tsm)    # Pending assembly key.
    if  aky_t not in _mcArrived:
        _mcArrived[ aky_t ] = { 'tsm': tsm,
                                'message': [None] * frg_c,  # Pre-allocated the list.
                                'backoff': BACKOFF.copy()
                            }
    _mcArrived[ aky_t ]['message'][ seq ] = pkt_b

    return  aky_t if all([ f is not None for f in _mcArrived[ aky_t ]['message']]) else None  # noqa: C419

def _assemble_message( aky_t: tuple ) -> tuple[tuple ,object]:  # (tuple ,object):
    """Assemble the fragments back into the key and value tuple and delete the tracked fragments of the emsssage.

    Args:
        aky_t: tuple    The acknowledgment key for the message.
    Return:
        key: tuple      The key tuple.
        val: object     The value object
    """
    bgn: int
    end: int
    frg_b: bytes  = []  # Fragment bytes.
    frg_s: int    = 0   # Fragment size.
    hdr_b: bytes  = []  # Fixed packet Header bytes
    key_b: bytes  = []  # Serialized Key bytes.
    key_t: tuple  = None
    key_s: int    = 0
    val_b: bytes  = []  # Serialized Value bytes.
    val_o: object = None
    val_s: int    = 0   # Size of the value object.

    if  aky_t  not in _mcArrived:
        return None ,None

    # Assemble back the key and value object.
    for frg_b in _mcArrived[ aky_t ]['message']:
        # NOTE: Header bytes MUST come before Key bytes which MUST come before Value bytes.
        bgn   = HEADER_SIZE
        frg_s = len( frg_b )
        hdr_b = frg_b[ 0 : HEADER_SIZE ]    # Fix size 16 bytes of packet header.
        _ ,_ ,_ ,_ ,key_s ,val_s ,_ ,rcv = struct.unpack('@BBBBHHQH' ,hdr_b)    # Unpack the fragment header.

        if  not key_t:
            key_bal: int = ( key_s - len( key_b ))      # The size of the incomplete key.
            if  key_s > len( key_b ):
                # Not done assembling the key.
                end   = HEADER_SIZE + key_bal if key_bal < (frg_s - HEADER_SIZE) else frg_s
                key_b+= frg_b[ bgn : end ]
                bgn   = end

            if  key_s == len( key_b ):
                key_t =  pickle.loads(bytes( key_b ))    # noqa: S301    De-Serialized the key.

        if  key_t and bgn < frg_s:
            val_b +=  frg_b[ bgn : ]

    if  val_s == len( val_b ):
        # All fragments assembled back to the original message length.
        if  _mcCrypto:
            val_b = _mcCrypto.decrypt(bytes( val_b ))

        val_o =  pickle.loads(bytes( val_b ))   # noqa: S301    De-Serialized the value.
    
    # Delete the completely received message.
    del _mcArrived[ aky_t ]

    return  key_t ,val_o

def _send_fragment( sock:socket.socket ,fragment: bytes ) -> None:
    """Send a fragment out.

    The `TEST_MONKEY_TANTRUM` configuration greater than zero will enable the simulation of dropped packets.

    Args:
        socket:     A configured socket to send a fragment out of.
        fragment:   A fragment of binary data.
    Return:
        None
    """
    # The following is to assist with testing.
    # This Monkey should NOT throw a tantrum in a production environment.
    #
    if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA and _mcConfig.monkey_tantrum > 0 and _mcConfig.monkey_tantrum < HUNDRED:
        tantrum = random.randint(1 ,HUNDRED)    # noqa: S311    Between 1 and 99.
        if  tantrum >= (50.0 - _mcConfig.monkey_tantrum/2.0) and \
            tantrum <= (50.0 + _mcConfig.monkey_tantrum/2.0):
            # Either side of 50 by the tantrum percent.

            # DEBUG trace.
            if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                _log_ops_msg( logging.WARNING ,opc=OpCode.NOP ,msg="Monkey is angry!  NOT sending out packet." )
            return

    sock.sendto( fragment ,(_mcConfig.multicast_ip ,_mcConfig.multicast_port))

def _check_expr_pending() -> None:
    """Check the pending list of messages that are obsolete due to more recent update.

    Iterate through the pending list sorted by nsm ,key and tsm in descending order:
        If the namespace and key is the same as previous entry, delete it for it is not the latest.
    """
    prv_nms: str    = None
    prv_key: object = None
    prv_tsm: int    = None
    for pky_t in sorted(_mcPending.keys() ,reverse=True ):  # Descending key(nms ,key ,tsm) for this message pending acknowledgement.
        if  prv_nms and prv_nms == pky_t[0] and \
            prv_key and prv_key == pky_t[1] and \
            prv_tsm and(prv_tsm >  pky_t[2] or ((PyCache.tsm_version() - pky_t[2]) > (5*PyCache.ONE_NS_SEC))) and \
            pky_t   in _mcPending:
            # Will skip the first entry.
            #   1)  Same namespace.
            #   2)  Same key.
            #   3)  Previous timestamp is older than current timestamp OR current timestamp is older than 5 seconds.
            #   4)  The key is still in the list.

            # DEBUG trace.
            if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                _log_ops_msg( logging.DEBUG ,opc=OpCode.WRN ,tsm=pky_t[2] ,nms=pky_t[0] ,key=pky_t[1] ,crc=_mcPending[ pky_t ]['crc']
                                            ,msg=">   Newer acknowledgement is pending.  Delete expired change that is pending acknowledgement." )
            try:
                del _mcPending[ pky_t ]
                prv_tsm = None
            except  KeyError:
                pass

        prv_nms = pky_t[0]
        prv_key = pky_t[1]
        prv_tsm = pky_t[2]

def _check_sent_pending() -> None:
    """Check the pending list for messages that have NOT been acknowledge.

    Iterate through every entry in the pending list and each of its pending members (IP) do
        Check at least it have past the seasoning period.
        If all the members have not acknowledge, immediately re-multicast out the message.
        If some members have acknowledge, then request them to acknowledge.
    """
    for pky_t in list(_mcPending.keys()):   # Key for this message pending acknowledgement.
        if  pky_t in _mcPending:
            nms = pky_t[0]
            key = pky_t[1]
            tsm = pky_t[2]
            crc = _mcPending[ pky_t ]['crc']
            elps= (PyCache.tsm_version() - tsm) / ONE_NS_SEC    # Elapsed seconds since this key was queued.
            try:
                ips = {}
                ips = list(_mcPending[ pky_t ]['members'].keys())  # All members in the cluster for this key.
            except  KeyError:
                pass

            # NOTE: To lock or to trap?
            #       It is only under very high load that another thread can update the pending list.
            #       For most cases, maybe the lock is not required as long as I can handle the race condition.
            for ip in ips:
                try:
                    if  ip in  _mcPending[ pky_t ]['members'][ ip ] and _mcPending[ pky_t ]['members'][ ip ]['backoff']:
                        # NOTE: The following is NOT lock down and subjected to change.
                        # Get the head of the backoff pause second.
                        boff: int = next(iter(_mcPending[ pky_t ]['members'][ ip ]['backoff']))

                        # The minimum wait second before we consider message not acknowledged.  Need to be >= 0.8sec or too many RAK.
                        minw = max((boff * _mcConfig.multicast_hops) ,boff)
                        if  elps > minw:
                            if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS:
                                _log_ops_msg( logging.DEBUG ,opc=OpCode.RAK ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                            ,msg=f">>  UnAcknowledged. Elapsed: {elps} > {minw} ,Backoff: ({boff})" )
                            if  len(_mcPending[ pky_t ]['message']) == len(_mcPending[ pky_t ]['members'][ ip ]['unack']):
                                # No fragments for the entire message was acknowledged.
                                if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                                    _mcOBQueue.put((OpCode.INQ ,tsm ,nms ,key ,crc ,f"{ip}:" ,ip))   # Inquire member's cache checksum to debug.

                                # TODO: Just retransmit on the first detected unacknowledge packet that is < hops sec.
                                _mcOBQueue.put((OpCode.RAK ,tsm ,nms ,key ,crc ,f"{ip}:" ,ip))    # Request ACK for the entire message from an IP.
                            else:
                                # Partially unacknowledged.
                                s = len(_mcPending[ pky_t ]['message'])
                                for f in range( 0 ,s ):
                                    if  f in _mcPending[ pky_t ]['members'][ ip ]['unack']:
                                        _mcOBQueue.put((OpCode.RAK ,tsm ,nms ,key ,crc ,f"{ip}:{f}/{s}" ,ip))     # Request specific fragment ACK from an IP.

                            _ = _mcPending[ pky_t ]['members'][ ip ]['backoff'].pop()   # Pop off the head of the backoff pause.
                except  KeyError:
                    pass    # Was removed in the other thread.

        # NOTE: If all the members have NOT acknowledge this key, chances are the out going message was lost.
        #       Proactive re-multicast instead of waiting to time out.
        i = 0
        while i < RETRIES:
            i += 1
            try:
                if  pky_t in _mcPending:
                    uak = [ip for ip in _mcPending[ pky_t ]['members'].keys() if len(_mcPending[ pky_t ]['members'][ ip ]['backoff']) == 0]
                    mbr = len(_mcPending[ pky_t ]['members'])
                    # FIXME: Encountered "RuntimeError: dictionary changed size during iteration" inside this locked section.

                    if  mbr == len(_mcMember) and uak:
                        #   Deep Tracing
                        if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS:
                            _log_ops_msg( logging.DEBUG ,opc=OpCode.RSD ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                        ,msg=f">>  Proactive request ack from all members. all={len(_mcMember)} ,mbr={mbr} ,uak={len(uak)}" )

                        # Re-queue a full message transmission.  Proactive re-send has None value.
                        _mcOBQueue.put((OpCode.RSD ,tsm ,nms ,key ,crc ,None ,None))

                    for ip in uak:
                        # Re-start the timeout for
                        _mcPending[ pky_t ]['members'][ ip ]['backoff'] = BACKOFF.copy()    # Reset.
                break
            except (KeyError ,RuntimeError):
                if  i > RETRIES:
                    raise

def _check_recv_assembly() -> None:
    """Check the assembly list of fragments for a message.
    """
    bads = {}
    try:
        keys = list(_mcArrived.keys())  # aky_t: tuple = (sender ,frg_c ,key_s ,tsm)
    except  KeyError:
        keys = []

    for aky_t in keys:
        if  aky_t not in _mcArrived:
            continue  # Skip if the key was removed by another thread.

        try:
            # Calculate elapsed time since the fragment was last updated
            elps = (PyCache.tsm_version() - _mcArrived[ aky_t ]['tsm']) / ONE_NS_SEC

            # Handle backoff logic
            if  _mcArrived[ aky_t ]['backoff']:
                # Get the head of the backoff pause second.
                boff: int = next(iter(_mcArrived[ aky_t ]['backoff']))

                # The minimum wait second before we consider message not acknowledged.
                minw = max((boff * _mcConfig.multicast_hops) ,boff)
                if  elps > minw:
                    for seq in range( 0 ,len(_mcArrived[ aky_t ]['message'])):
                        if  _mcArrived[ aky_t ]['message'][ seq ] is None:
                            # NOTE:        (opc        ,tsm      ,nms  ,key   ,crc  ,val      ,rcv)
                            _mcOBQueue.put((OpCode.REQ ,aky_t[3] ,None ,aky_t ,None ,f"{seq}" ,aky_t[0]))

                    _ = _mcArrived[ aky_t ]['backoff'].pop()    # Pop off the head of the backoff pause.
            elif aky_t not in bads:
                # Ran out of backoff.
                bads[ aky_t ] = None
        except  KeyError:
            pass    # Was removed in the other thread.

    # Delete away the un-assemble fragments.
    for aky_t in bads:
        lst: list =  None
        try:
            if _mcArrived and aky_t in _mcArrived:
                lst = [ seq for seq in  range( 0, len(_mcArrived[ aky_t ])) \
                            if  seq in _mcArrived[ aky_t ] and _mcArrived[ aky_t ][ seq] is None
                    ]
        except  KeyError:
            pass    # Was removed in the other thread.

        if  lst:
            if  aky_t in _mcArrived:
                del _mcArrived[ aky_t ]
            logger.error(f"Key:{aky_t} message incomplete.  Missing fragments: {lst}" ,extra=LOG_EXTRA)

def _check_sync_metadata() -> None:
    """Sync-check the metadata.

    Send out a pulse heartbeat sync message to all members.
    The message is a copy of the metadata for the other members to validate their local cache against.
    """
    now = time.time()   # To get the time in seconds since epoch.
    i   = 1
    if (_mcConfig.cache_sync_on +(_mcConfig.cache_pulse *60)) < now:
        while i <= RETRIES:
            try:
                for nms in _mcCache:    # NOTE: Loop to give the receiver in between namespace break to process other request.
                    # TODO: Send out metadata that have been updated since two sync ago instead of everything.
                    val = get_cache( nms ).metadata.copy()
                    if  val:
                        _mcOBQueue.put((OpCode.SYC ,PyCache.tsm_version() ,nms ,None ,None ,val ,None))
                _mcConfig.cache_sync_on = now
                break
            except  KeyError:
                i += 1

        if  i > RETRIES:
            logger.warning(f"Encounter issue during metadata serialization for SYC operation after {RETRIES} retries." ,extra=LOG_EXTRA)

def _check_congestion() -> None:
    """Check the queue depth for congestion.
    """
    # DEBUG trace.
    if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
        ibs = _mcIBQueue.qsize()
        obs = _mcOBQueue.qsize()
        if  ibs >= _mcConfig.congestion or obs >= _mcConfig.congestion:
            msg = f"Internal message queue size. IB:{ibs:>6} ,OB:{obs:>4}"
            _log_ops_msg( logging.WARNING ,opc=OpCode.WRN ,tsm=PyCache.tsm_version() ,msg=msg )

def _get_local_value( key: object ,mcc: dict ) -> tuple:
    """Get the value from the local cache along with  its checksum and timestamp.

    Args:
        key: object     Key to the item to get.
        mcc: dict       Local cache dictionary.
    Return:
        (val ,crc ,tsm) Tuple of (value ,checksum ,timestamp).
    """
    i: int  = 0
    crc: bytes  = None
    tsm: int    = None
    val: object = None

    while key in mcc and key in mcc.metadata and (crc is None or tsm is None) and i < RETRIES:
        crc = None
        tsm = None
        val = None
        try:
            # NOTE: Another thread can be setting a new instance after the previous instance was deleted.
            val =  mcc[ key ]
            crc =  mcc.metadata[ key ]['crc']
            tsm =  mcc.metadata[ key ]['tsm']
        except  KeyError:
            i   =+ 1

    return (val ,crc ,tsm)

def _process_ACK( nms: str ,key: object ,tsm: int ,lts: int ,opc: str ,crc: str ,lcs: bytes ,val: object ,sdr: str ):    # noqa: N802
    """Process ACK message.
    """
    pky: tuple  = (nms ,key ,tsm)

    if  pky in _mcPending:
        if  sdr \
            in  _mcPending[ pky ]['members']:
            del _mcPending[ pky ]['members'][ sdr ]

        elif  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
            # Usually this node join the cluster after the other members self annoucement.
            _log_ops_msg( logging.WARNING   ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                            ,msg=f">   NOT expected from {sdr}." )

        if  len(_mcPending[ pky ]['members']) == 0:
            del _mcPending[ pky ]

            if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                _log_ops_msg( logging.DEBUG ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                            ,msg=">   Acknowledged by all members.  Delete tracking entry." )

    elif  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
        _log_ops_msg( logging.WARNING   ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">   {pky} NOT found for acknowledgment from {sdr}." )

def _process_BYE( nms: str ,key: object ,tsm: int ,lts: int ,opc: str ,crc: str ,lcs: bytes ,val: object ,sdr: str ):    # noqa: N802
    """Process BYE message.
    """
    if  sdr in _mcMember:
        del _mcMember[ sdr ]
        if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
            _log_ops_msg( logging.DEBUG ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">   Member {sdr} exited." )

    # Clear pending ack.
    for pky_t in list(_mcPending.keys()):   # Key for this message pending acknowledgement.
        if  pky_t in _mcPending:
            if  sdr \
                in  _mcPending[ pky_t ]['members']:
                del _mcPending[ pky_t ]['members'][ sdr ]

                if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS:
                    _log_ops_msg( logging.DEBUG ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                ,msg=f">>  Delete tracking entry {pky_t}." )

def _process_DEL( nms: str ,key: object ,tsm: int ,lts: int ,opc: str ,crc: str ,lcs: bytes ,val: object ,sdr: str ):    # noqa: N802
    """Process DEL message.
    """
    mcc: dict = get_cache( nms )

    if  key in mcc:
        #   Deep Tracing
        if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
            tsmcmp = __get_msgcomp( lts ,tsm )
            _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,prvtsm=lts ,tsmcmp=tsmcmp
                                        ,msg=">   Local tsm: {prvtsm} {tsmcmp} {tsm}" )

            if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS:
                _log_ops_msg( logging.DEBUG ,opc=OpCode.DEL ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                            ,msg=f">>  Calling: cache.__delitem__( {key} ,None )" )

        # Delete it locally and dont multicast it out.
        # TODO: Check for collision.  See: UPD.
        try:
            mcc.__delitem__( key ,tsm ,EnableMultiCast.NO )
        except  KeyError:
            #   Deep Tracing
            if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                            ,msg=f">   Requested key {key} is no longer in local cache." )
    # Acknowledge it.
    _mcOBQueue.put((OpCode.ACK ,tsm ,nms ,key ,crc ,None ,sdr))

    #   Deep Tracing
    if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS:
        if  key not in mcc:
            _log_ops_msg( logging.DEBUG ,opc=OpCode.DEL ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">>  OK: {key} deleted from local." )
        else:
            _log_ops_msg( logging.DEBUG ,opc=OpCode.DEL ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">>  ERR:{key} NOT deleted from local." )

def _process_NEW( nms: str ,key: object ,tsm: int ,lts: int ,opc: str ,crc: str ,lcs: bytes ,val: object ,sdr: str ):    # noqa: N802
    """Process NEW message.
    """
    if  sdr not in _mySelf and sdr not in _mcMember:
        _mcMember[ sdr ] = tsm   # Timestamp

def _process_RAK( nms: str ,key: object ,tsm: int ,lts: int ,opc: str ,crc: str ,lcs: bytes ,val: object ,sdr: str ,aky_t: tuple ):  # noqa: N802
    """Process RAK message.
    """
    mcc: dict = get_cache( nms )

     #   Deep Tracing
    if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS:
        if  aky_t in _mcArrived:
            _log_ops_msg( logging.DEBUG ,opc=OpCode.RAK ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">>  aky_t={aky_t} exist in _mcArrived." )
        else:
            _log_ops_msg( logging.DEBUG ,opc=OpCode.RAK ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">>  aky_t={aky_t} NOT exist in _mcArrived." )

        if  key in mcc:
            _log_ops_msg( logging.DEBUG ,opc=OpCode.RAK ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">>  {key} exist in _mcCache." )
        else:
            _log_ops_msg( logging.DEBUG ,opc=OpCode.RAK ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">>  {key} NOT exist in _mcCache." )

    if  aky_t in _mcArrived:
        # We keep the arrived messages around to be cleaned up by house keeping.
        _mcOBQueue.put((OpCode.ACK ,tsm ,nms ,key ,crc ,None ,sdr))
        #   Deep Tracing
        if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
            _log_ops_msg( logging.DEBUG ,opc=OpCode.RAK ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">   {key} Re-Acknowledge." )
    else:
        # Didn't receive message fragment and need sender to resend it.
        _mcOBQueue.put((OpCode.NAK ,tsm ,nms ,key ,crc ,None ,sdr))

def _process_REQ( nms: str ,key: object ,tsm: int ,lts: int ,opc: str ,crc: str ,lcs: bytes ,val: object ,sdr: str ):    # noqa: N802
    """Process REQ message.
    """
    mcc: dict = get_cache( nms )

    # TODO: Refactor this block into def process_REQ()
    if  val:
        # Pass the request over to outbound requesting a resend for the missing fragment.
        # TODO: Don't concatenate the sdr and val/seq.  We have the `sdr`.
        _mcOBQueue.put((OpCode.RSD ,tsm ,nms ,key ,crc ,f'{sdr}:{val}' ,sdr))
    elif  key in mcc:
        # Request from member processing a sync because they do not have this key.
        # Pass the request over to outbound requesting a resend for the entire message..
        try:
            tsm = mcc.metadata[ key ]['tsm']
            crc = mcc.metadata[ key ]['crc']
            val = mcc[ key ]
            _mcOBQueue.put((OpCode.UPD ,tsm ,nms ,key ,crc ,val ,sdr))
        except  KeyError:
            #   Deep Tracing
            if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                            ,msg=f">   Requested key {key} is no longer in local cache." )
            # TODO: NEG it.

def _process_RST( nms: str ,key: object ,tsm: int ,lts: int ,opc: str ,crc: str ,lcs: bytes ,val: object ,sdr: str ):    # noqa: N802
    """Process RST message.
    """
    # TODO: Refactor this block into def process_RST()
    for n in filter( lambda nk: nk == nms or nms is None ,_mcCache.keys() ):            # Namespace
        for k in filter( lambda kk: kk == key or key is None ,_mcCache[ n ].keys() ):   # Keys within namespace.
            _mcCache[ n ].__delitem__( k ,EnableMultiCast.NO )

def _process_SYC( nms: str ,_ky: object ,tsm: int ,lts: int ,opc: str ,crc: str ,lcs: bytes ,val: object ,sdr: str ):    # noqa: N802
    """Process SYC message.
    """
    mcc: dict = get_cache( nms )

    for key in  val:
        if  key in  mcc.metadata:
            frtsm = val[ key ]['tsm']           # Foreign tsm.
            frcrc = val[ key ]['crc']           # Foreign crc.
            mytsm = mcc.metadata[ key ]['tsm']  # Local   tsm.
            mycrc = mcc.metadata[ key ]['crc']  # Local   crc.
            if  frtsm < mytsm and frcrc != mycrc and key in mcc:
                # Incoming key/value is older than in local cache therefore send back to the sender my current local cache value.
                myval = mcc[ key ]

                # Send my latest value back to the sender thst has the older value.
                _mcOBQueue.put((OpCode.UPD ,mytsm ,nms ,key ,mycrc ,myval ,sdr))

                #   Deep Tracing
                if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                    _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=mytsm ,nms=nms ,key=key ,crc=mycrc
                                                ,msg=f">   Key from {sdr} is older.  Sending local cache entry back to sender." )
                if  mcc.callback:
                    # Let the user know that there is an incoherence event.
                    arg = {'typ': CallbackType.INCOHERENT ,'nms': mcc.name ,'key': key ,'lkp': frtsm ,'tsm': mytsm ,'elp': 0 ,'prvcrc': frcrc ,'newcrc': mycrc}
                    t1 = threading.Thread( target=mcc.callback ,args=[arg] ,name='McCache Sync' )
                    t1.start()  # NOTE: Launch and forget.
        else:
            # We don't have this entry.
            #   Deep Tracing
            if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                            ,msg=f">   {key} from {sdr} is not in local cache. Requesting sender for missing entry." )

            # Not in local cache therefore request the syncing sender to resend this key/value.
            _mcOBQueue.put((OpCode.REQ ,PyCache.tsm_version() ,nms ,key ,None ,None ,sdr))

def _process_UPD( nms: str ,key: object ,tsm: int ,lts: int ,opc: str ,crc: str ,lcs: bytes ,val: object ,sdr: str ):    # noqa: N802
    """Process UPD message.
    """
    mcc: dict = get_cache( nms )

    try:
        if  lts is None or  lts < tsm:  # NOTE: Local timestamp is older than the new arriving message timestamp.
            #   Deep Tracing
            if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                tsmcmp = __get_msgcomp( lts ,tsm )
                _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,prvtsm=lts ,tsmcmp=tsmcmp
                                            ,msg=">   Local tsm: {prvtsm} {tsmcmp} {tsm}. Updating local cache." )

                if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS:
                    _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                ,msg=">>  Calling: cache.__setitem__( {key} ,{crc} ,None ,{tsm} )" )

            # Update it locally and DONT multicast it out.
            # TODO: Implement "cache_sync_mode" == 0 to ONLY update existing local entry.
            mcc.__setitem__( key ,val ,tsm ,EnableMultiCast.NO )

            # NOTE: Invalidate pending acks for this key.  We got a newer entry.
            for pky_t in list(_mcPending.keys()):
                # pky_t(nms ,key ,tsm) is the Key for this message pending acknowledgement.
                try:
                    if  pky_t in _mcPending and pky_t[0] == nms and pky_t[1] == key and pky_t[2] < tsm:
                        lcs: bytes = '' # Local cache key's crc.
                        lts: int   = 0  # Local cache key's tsm.

                        lcs = _mcPending[ pky_t ]['crc']
                        lts = _mcPending[ pky_t ]['tsm']
                        del   _mcPending[ pky_t ]
                except  KeyError:   # NOTE: Got deleted in another thread.
                    #   Deep Tracing
                    if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA and lts:
                        crccmp = __get_msgcomp( lcs ,crc )
                        tsmcmp = __get_msgcomp( lts ,tsm )
                        _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,prvtsm=lts ,prvcrc=lcs ,tsmcmp=tsmcmp ,crccmp=crccmp
                                                    ,msg=">   Ack NOT needed. Newer value arrived.  Pending tsm: {prvtsm} {tsmcmp} {tsm} crc: {prvcrc} {crccmp} {crc}") # noqa: E501
            #   Deep Tracing
            if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS:
                try:
                    if  key in mcc and  mcc[ key ]:
                        lcs =  mcc.metadata[ key ]['crc']
                        lts =  mcc.metadata[ key ]['tsm']

                        if  lcs == crc and lts == tsm:
                            _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                        ,msg=">>  OK: {key} stored locally." )
                        else:
                            crccmp = __get_msgcomp( lcs ,crc )
                            tsmcmp = __get_msgcomp( lts ,tsm )
                            _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,prvtsm=lts ,prvcrc=lcs ,tsmcmp=tsmcmp ,crccmp=crccmp
                                                        ,msg=">>  ERR:{key} locally out of sync.  Local tsm: {prvtsm} {tsmcmp} {tsm} crc: {prvcrc} {crccmp} {crc}" )    # noqa: E501
                    else:
                        _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                    ,msg=">>  ERR:{key} NOT stored in local metadata." )
                except  KeyError:   # NOTE: Got deleted in another thread.
                    _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                ,msg=f">>  ERR:{key} NOT found in cache/metadata after calling __setitem__() with EnableMultiCast.NO." )
        elif lts >  tsm and crc != lcs and key in mcc and False:
            # TODO: Finish this.  An struct.error is thrown.
            # Send my latest value back to the sender that has the older value.
            val ,crc ,tsm = _get_local_value( key ,mcc )
            if   val is not None and crc is not None and tsm is not None:
                _mcOBQueue.put((OpCode.UPD ,crc ,tsm ,nms ,key ,crc ,val ,sdr))

                #   Deep Tracing
                if  _mcConfig.debug_level >= McCacheDebugLevel.SUPERFLUOUS:
                    _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                ,msg=f">>  Incoming message is older and local.  Send value of C={crc} T={tsm} to {sdr}" )

#       elif lts >  tsm and crc != lcs: # Incoherent?
#           # TODO: Think deeper on this eviction logic.  Maybe don't need to evict.
#           if  _mcConfig.debug_level >= McCacheDebugLevel.BASIC:
#               _log_ops_msg( logging.WARNING   ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,prvtsm=lts ,prvcrc=lcs
#                                               ,msg="Cache incoherent: Evict {key}! {prvtsm} > {tsm} and {prvcrc} <> {crc}" )
#           else:
#               logger.warning(f"Cache incoherent: {SRC_IP_ADD:11} to evict {key}.  CRC: {base64.b64encode( lcs ).decode()[:-2]} <> {base64.b64encode( crc ).decode()[:-2]}")
#
#           # NOTE: Cache in-consistent, evict this key from all members in the cluster.
#           # TODO: We need some congestion control.  Keep pounding the cache is making is worse.
#           if  key in mcc:
#               del mcc[ key ]
#       elif lts == tsm and crc == lcs:
#           # Re-transmitted message.
#           pass
    except  KeyError:   # NOTE: Got deleted in another thread.
        if  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
            _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                        ,msg=f">>  ERR:{key} NOT found in cache while processing {opc}." )

    val = None
    # Acknowledge it.
    _mcOBQueue.put((OpCode.ACK ,tsm ,nms ,key ,crc ,None ,sdr))

def _decode_message( aky_t: tuple ,key_t: tuple ,val_o: object ,sdr: str ) -> None:
    """Decode the message from the sender.

    A message is made up of key and value.

    Args:
        aky_t: tuple    Assembly key for incoming message.
        key_t: tuple    Message key.
        val_o: object   Message object. A tuple of (opc ,crc ,val).
        sdr: str        Sender of this message.
    Return:
        None
    """
    #pky: tuple  = key_t     # Pending key
    nms: str    = key_t[0]  # Namespace
    key: object = key_t[1]  # Key
    tsm: int    = key_t[2]  # Timestamp
    opc: str    = val_o[0]  # Op Code
    crc: str    = val_o[1]  # Checksum
    val: object = val_o[2]  # Value
    mcc: dict   = get_cache( nms )

    lcs: bytes  = None      # Local checksum
    lts: int    = None      # Local timestamp
    while key in mcc.metadata and (lcs is None or lts is None):
        try:
            # NOTE: PyCache can be setting a new instance after the previous instance was deleted.
            #lvl =  mcc[ key ]
            lcs =  mcc.metadata[ key ]['crc']
            lts =  mcc.metadata[ key ]['tsm']
        except  KeyError:
            pass

    # TODO: Deal with the concurrent deletion of the house keeping dictionaries.
    match opc:
        case OpCode.ACK:    # Acknowledgment.
            _process_ACK(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )

        case OpCode.BYE:    # Goodbye from member.
            _process_BYE(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )

        case OpCode.DEL | OpCode.EVT:   # Delete/Eviction.
            _process_DEL(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )
            val = None

        case OpCode.ERR:    # Error.
            pass    # TODO: How should we handle an error reported by the sender?

        case OpCode.INQ:    # Inquire.
            val = _get_local_checksum(  nms ,key )

        case OpCode.MET:    # Metrics.
            val = _get_local_metrics(   nms )

        case OpCode.NEW:    # New member.
            _process_NEW(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )

        case OpCode.RAK:    # Re-Acknowledgement.
            _process_RAK(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr ,aky_t )

        case OpCode.REQ:    # Request resend.
            _process_REQ(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )

        case OpCode.RST:    # Reset.
            _process_RST(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )

        case OpCode.SYC:    # Sync heart beat.
            _process_SYC(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )

        case OpCode.UPD | OpCode.INS:   # Insert and Update.
            _process_UPD(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )
            val = None

        case _:
            pass

    # Collect inbound operation code stats.
    if  opc not in  _mcQueueStats['ibq']['opc']:
        _mcQueueStats['ibq']['opc'][ str(opc) ] = 0
    _mcQueueStats['ibq']['opc'][ str(opc) ] += 1

    if  opc in ( OpCode.INQ ,OpCode.MET ):
        _log_ops_msg( logging.INFO  ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,msg=val )
    elif logger.level == logging.DEBUG:
        _log_ops_msg( logging.DEBUG ,opc=opc ,sdr=sdr ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,msg='In coming {opc} processed.' if val is None else val )

    return  val


# Private thread methods.
#
def _goodbye() -> None:
    """Shutting down of this Python process.

    Inform all the members in the cluster that this node is leaving the group.
    Output the current metrics of this local cache.

    SEE: https://docs.python.org/3.12/library/atexit.html#module-atexit

    Args:
    Return:
        None
    """
    _mcOBQueue.put((OpCode.BYE ,PyCache.tsm_version() ,None ,None ,None ,None ,None))

    # Stop the log listner.
    _mcLgLsnr.stop()

    time.sleep( 1 ) # Give enough time to send out the above ops to other cluster members.  Needed to output metrics.

def _multicaster() -> None:
    """Dequeue and multicast out the cache operation to all the members in the group.

    A dequeued message is constructed using the following format:
        OP Code:    Cache operation code.  SEE: OpCode enum.
        Timestamp:  When this request was generated in Python's nano seconds.
        Namespace:  Namespace of the cache.
        Key:        The key in the cache.
        CRC:        Checksum of the value identified by the key.
        Value:      The cached value.
        Receiver:   The receiving member to send message to.

    A pending set of un-acknowledge messages (key/value) is kept until acknowledge.
    SEE: _make_pending_value() for the structure.

    Args:
    Return:
        None
    """
    sock: socket.socket = _get_socket( SocketWorker.SENDER )    # Get an UDP socket for multicasting.

    # Keep the format consistent to make it easy for the test to parse.
    logger.debug('McCache broadcaster is ready.')

    opc: str = ''   # Op Code
    while opc != OpCode.BYE:
        try:
            msg = _mcOBQueue.get()  # Dequeue the local cache operation.
            qsz = _mcOBQueue.qsize()
            if  qsz > 0:
                _mcQueueStats['obq']['avgsize'] = ((_mcQueueStats['obq']['avgsize'] *_mcQueueStats['obq']['count']) + qsz) /(_mcQueueStats['obq']['count'] +1)
                _mcQueueStats['obq']['count']  += 1
                if  qsz > _mcQueueStats['obq']['maxsize']:
                    _mcQueueStats['obq']['maxsize'] = qsz

            opc         = msg[0]    # Op Code
            tsm: int    = msg[1]    # Timestamp
            nms: str    = msg[2]    # Namespace
            key: object = msg[3]    # Key
            crc: bytes  = msg[4]    # Checksum
            val: object = msg[5]    # Value
            rcv: str    = msg[6]    # Addressed to receiving member. None == multicast to all members.
            frgs: list  = []

            # TODO: Handle self targetting operation.  Check the "rcv" value for specifc MET operation.
            pky_t = (nms ,key ,tsm) # Key for this message pending acknowledgement.
            match opc:
                case OpCode.RSD:    # Request (from house keeping) resend of entire message.
                    if  pky_t in _mcPending:
                        if  not val:
                            # Timeout request to retransmit the entire message to all members.
                            frgs = _mcPending[ pky_t ]['message']
                        else:
                            # Request retransmit message fragment.
                            # NOTE: The fragment number is communicated in the value formatted as FromIP:Index
                            #       fr_ip: str     Who requested a re-transmit?
                            #       frg_i: int     Which fragment is requested?
                            # TODO: Use the `rcv` instead of splitting out from value.
                            fr_ip: str =     val.split(':')[0]
                            frg_i: int = int(val.split(':')[1])
                            if  pky_t in _mcPending and frg_i in _mcPending[ pky_t ]['message']:
                                frgs = [ _mcPending[ pky_t ]['message'][ frg_i ] ]
                            #   Deep Tracing
                            elif _mcConfig.debug_level >= McCacheDebugLevel.BASIC:
                                # Inform the requestor that we have an error on our side.
                                # _mcQueue.put((OpCode.ERR ,pky_t[3] ,pky_t[0] ,pky_t[1] ,None ,None ,None))
                                _log_ops_msg( logging.WARNING   ,opc=opc ,sdr=fr_ip ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                                ,msg=f"{fr_ip} requested fragment{frg_i:3} for {pky_t} doesn't exist!" )
                    #   Deep Tracing
                    elif  _mcConfig.debug_level >= McCacheDebugLevel.EXTRA:
                        _log_ops_msg( logging.WARNING   ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                                        ,msg=f">   {pky_t} no longer exist in pending!" )
                case _:
                    if  opc == OpCode.ACK and rcv is not None:  # TODO: Handle REQ from a spcific sender.
                        mbrs = { rcv: None }    #   Unicast, simulated.
                    else:
                        mbrs = _mcMember        #   Muticast.
                    #                             key_t ,val_t
                    ack: dict= _make_pending_ack( pky_t ,(opc ,crc ,val) ,mbrs ,_mcConfig.packet_mtu )

                    if  opc in {OpCode.DEL ,OpCode.INS ,OpCode.UPD}:
                        if  pky_t not in _mcPending:
                            # Acknowledgement is needed for Insert ,Update and Delete.
                            _mcPending[ pky_t ] = ack
                            frgs = _mcPending[ pky_t ]['message']
                    else:
                        # Acknowledgement is NOT needed for others.
                        frgs = ack['message']

            # Transmit the fragments out ASAP.
            for frg_b in frgs:
                _send_fragment( sock ,frg_b )

            # Collect outbound operation code stats.
            if  opc not in  _mcQueueStats['obq']['opc']:
                _mcQueueStats['obq']['opc'][ str(opc) ] = 0
            _mcQueueStats['obq']['opc'][ str(opc) ] += 1

            # DEBUG trace.
            if _mcConfig.debug_level >= McCacheDebugLevel.BASIC:
                _log_ops_msg( logging.DEBUG ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc
                                            ,msg=f"Out going to { rcv if rcv else 'members.'}" )

            if  opc == OpCode.MET:  # Metrics.
                # Query out the local metrics.
                val = _get_local_metrics( nms )

                if  _mcConfig.debug_level >= McCacheDebugLevel.BASIC:
                    _log_ops_msg( logging.INFO  ,opc=opc ,tsm=tsm ,nms=nms ,msg=val )
                else:
                    logger.info( val )
        except  Exception as ex:    # noqa: BLE001
            _log_ops_msg( logging.ERROR ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc  ,msg=f"Send failed due to {ex}" )
            logger.error( ex )
            traceback.print_exc()

    # NOTE: Congestion control?
    #       Holding back the multicast is not solving the problem for the timestamp is already fixed.
    #       The application should slow down its pounding of the cache.
    # SEE:  https://dzone.com/articles/the-role-of-rate-limiting-in-service-stability

def _housekeeper() -> None:
    """Background house keeping thread.

    Request acknowledgment for messages that was send.
    Request resent missing fragments of a message.

    Args:
    Return:
        None
    """
    # Keep the format consistent to make it easy for the test to parse.
    logger.debug('McCache housekeeper is ready.')

    while True:
        time.sleep( _mcConfig.daemon_sleep )
        try:
            # Check send messages that are expired.
            #
            _check_expr_pending()

            # Check sent messages that are pending acknowledgement.
            #
            _check_sent_pending()

            # Check receive fragments pending assembly into a message.
            #
            _check_recv_assembly()

            # Check cache synchronization.
            #
            _check_sync_metadata()

            # Monitor the internal message queues.
            #
            _check_congestion()
        except  Exception as ex:    # noqa: BLE001
            logger.error( ex )
            traceback.print_exc()

def _listener() -> None:
    """Listen in the group for new cache operation from all members.
    Queue up the incoming cache operation to be processed by a different tread.
    The intend here is not to let the incoming packets overwritten before it get processed.

    Args:
    Return:
        None
    """
    pkt_b: bytes    # Binary packet
    sender: tuple
    sock: socket.socket = _get_socket( SocketWorker.LISTEN )

    # Keep the format consistent to make it easy for the test to parse.
    logger.debug('McCache listener is ready.')

    while True:
        try:
            pkt_b ,sender = sock.recvfrom( _mcConfig.packet_mtu )
            _mcIBQueue.put((pkt_b ,sender))
        except  Exception as ex:    # noqa: BLE001
            logger.error( ex )
            traceback.print_exc()

def  _processor() -> None:
    """Processed the incoming cache operation from all members.

    Args:
    Return:
        None
    """
    pkt_b: bytes    # Binary packet
    key_t: tuple    # Key tuple of the message.
    val_o: object   # Value object of the message.
    aky_t: tuple    # Assembly key for the message.
    fr_ip: str      # Source of the message.
    sender: tuple

    # Keep the format consistent to make it easy for the test to parse.
    logger.debug('McCache processor is ready.')

    while True:
        try:
            pkt_b ,sender = _mcIBQueue.get()  # Dequeue the remote cache operation.
            fr_ip = sender[0]
            qsz = _mcIBQueue.qsize()
            if  qsz > 0:
                _mcQueueStats['ibq']['avgsize'] = ((_mcQueueStats['ibq']['avgsize'] *_mcQueueStats['ibq']['count']) +qsz) / (_mcQueueStats['ibq']['count'] +1)
                _mcQueueStats['ibq']['count']  += 1
                if  qsz > _mcQueueStats['ibq']['maxsize']:
                    _mcQueueStats['ibq']['maxsize'] = qsz

            # Maintain the cluster membership.
            if  fr_ip not in _mySelf and fr_ip not in _mcMember:
                _mcMember[ fr_ip ] = None

            # NOTE: Ignore our own messages.
            if  fr_ip not in _mySelf:   # TODO: and check the packet is directly address to me.
                aky_t = _collect_fragment( pkt_b ,fr_ip )

                if  aky_t:
                    # All the fragments are received and is ready to be assembled back into a message.
                    key_t ,val_o = _assemble_message( aky_t )
                    if  key_t:  # We have collected all the fragments for a message.
                        _ = _decode_message( aky_t ,key_t ,val_o ,fr_ip )
                        _mcMember[ fr_ip ] = key_t[ 2 ]   # Timestamp

                    # Update the member timestamp.
                    if  fr_ip in _mcMember:
                        _mcMember[ fr_ip ] = aky_t[ 3 ]   # aky_t = (sender ,frg_c ,key_s ,tsm)   # Pending assembly key.
        except  Exception as ex:    # noqa: BLE001
            logger.error( ex )
            traceback.print_exc()

# Initialization Section.
#
logger: logging.Logger = logging.getLogger()    # Initially use the root logger.
_mcConfig = _load_config()

logger ,_mcLgLsnr = _get_mccache_logger( _mcConfig.log_filename ) # Replace with the McCache logger.
if  _mcConfig.debug_level >= McCacheDebugLevel.BASIC:
    logger.setLevel( logging.DEBUG )
else:
    logger.setLevel( logging.INFO )
logger.debug( _mcConfig )

if  _mcConfig.crypto_key and len( _mcConfig.crypto_key.strip() ) > 0:
    _mcCrypto = Fernet( str(_mcConfig.crypto_key) )

# TODO: Need a better way to seperate out testing and production code.
if 'TEST_APERTURE'  in  os.environ:
    # Resize is to prevent run away memory consumption during stress test.
    _mcIBQueue = queue.Queue( 65536 )
    _mcOBQueue = queue.Queue( 65536 )

# Main section to start the background daemon threads.
#
atexit.register( _goodbye ) # SEE: https://docs.python.org/3.12/library/atexit.html#module-atexit

if  sys.platform == 'win32':
    _ = psutil.getloadavg() # Windows only simulate the load, so pre-warm it in the background.

t1 = threading.Thread( target=_listener    ,daemon=True ,name="McCache listener" )
t1.start()
t2 = threading.Thread( target=_multicaster ,daemon=True ,name="McCache multicaster" )
t2.start()
t3 = threading.Thread( target=_processor   ,daemon=True ,name="McCache processor" )
t3.start()
t4 = threading.Thread( target=_housekeeper ,daemon=True ,name="McCache housekeeper" )
t4.start()


# The MIT License (MIT)
# Copyright (c) 2023 McCache authors.
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
# OR OTHER DEALINGS IN THE  SOFTWARE.
