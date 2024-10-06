# See MIT license at the bottom of this script.
#
import base64
import hashlib
import logging
import os
import queue
import socket
import sys
import time
#
from collections import OrderedDict
from collections.abc import Iterable
from enum import Flag ,IntEnum
from inspect import getframeinfo, stack
from threading import Thread ,RLock #,Lock
from types import ModuleType, FunctionType
from typing import Any ,Callable

# If you are using VS Code, make sure your "cwd" and "PYTHONPATH" is set correctly in `launch.json`:
#   "cwd": "${workspaceFolder}",
#   "env": {"PYTHONPATH": "${workspaceFolder}${pathSeparator}src;${env:PYTHONPATH}"},
#
from  pycache.__about__ import __app__, __version__ # noqa

class EnableMultiCast( Flag ):
    YES = True      # Multicast out the change.
    NO  = False     # Do not multicast out the change.  This is the default.

    def __repr__(self):
        return self.value

    def __str__(self):
        return str( self.value )

class CallbackType( IntEnum ):
    DELETE      = 1
    UPDATE      = 2
    INCOHERENT  = 3

    def __repr__(self):
        return self.value

    def __str__(self):
        return str( self.value )


class Cache( OrderedDict ):
    """Cache based of the ordered dict object.
       ... "who says inheritance is bad" ...

    Functionality:
        - LRU (Least Recently Updated) cache.
        - Maintain usage metrics.
        - Maintain spike metrics.  Rapid updates within 5 seconds.
        - Support time-to-live (ttl) eviction.  Updated item will have its ttl reset.
        - Support telemetry communication with external via queue.
    Future:
        - LFU:  Least frequently used.
        - LRU:  Least recently used.  This is different from the above (Least Recently Updated)
    SEE:
        - https://dropbox.tech/infrastructure/caching-in-theory-and-practice
    """
    CACHE_LOCK  = RLock()           # Lock for serializing access to shared data.
    ONE_NS_SEC  = 1_000_000_000     # One second in nano seconds.
    ONE_NS_MIN  = 60 * ONE_NS_SEC   # One minute in nano seconds.
    TSM_VERSION = time.time_ns
    # NOTE: time.monotonic_ns() behave differently on different OS.  Different precision is returned.
    #       time.monotonic_ns()
    #       Win11:  828250000000
    #       WSL:    870533920929
    #       Mac:    526814061067827
    #
    #       time.time_ns()
    #       Win11:  1724447991929990900
    #       WSL:    1724448075183642631
    #       Mac:    1724447622073806000
    #
    IP4_ADDRESS = sorted(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET ))[0][4][0]

    # TODO: Refactor to use the following method instead of TSM_VERSION().
    @classmethod
    def tsm_version( clz ) -> int:
        return  time.time_ns()

    @classmethod
    def tsm_version_str( clz ,ver: int | None = None ) -> str:
        """
        Conversion the timestamp version from integer to displayable string.  If none is input, anew timestamp version is generated.

        Args:
            ver     Timestamp version in nano seconds.
        Return:
            String version of the timestamp.
        """
        if  not ver:
#           ver = Cache.tsm_version()
            ver = Cache.TSM_VERSION()
        tsm = f"{time.strftime('%H:%M:%S' ,time.gmtime( (ver // Cache.ONE_NS_SEC) ))}.{ver % Cache.ONE_NS_SEC:0<9}"
        return  tsm

    def __init__(self ,other=() ,/ ,**kwargs) -> None:  # NOTE: The / as an argument marks the end of arguments that are positional.
        """Cache constructor.
        other:      SEE:    OrderedDict( dict ).__init__()
        kwargs:
            name    :str        Name for this instance of the cache.
            max     :int        Max entries threshold for triggering entries eviction. Default to `256`.
            size    :int        Max size in bytes threshold for triggering entries eviction. Default to `64K`.
            ttl     :int        Time to live in seconds. Default to `0`.
            msgbdy  :str        Custom log message format to log out.
            logger  :Logger     Custom logger to use internally.
            queue   :Queue      Output queue to broadcast internal changes out.
            callback:Callable   Your function to call if a value got updated just after you have read it.
                                The input parameter shall be a context dictionary of:
                                    {'key': key ,'lkp': lkp ,'tsm': tsm ,'prvcrc': old ,'newcrc': new}
                                        key:    The unique key for your object.
                                        lkp:    The last lookup timestamp for this key.
                                        tsm:    The current timestamp for this key.
                                        prvcrc: The CRC value for the previous value.
                                        newcrc: The CRC value for the new value.
                                If 'prvcrc' is None then it is a insertion.
                                If 'newcrc' is None then it is a deletion.
            cbwindow:int        The preceding number of seconds from the last value lookup to trigger a callback if it is updated.
            debug   :bool       Enable internal debugging.  Default to `False`.
        Raise:
            TypeError
        """
        # Private instance control.
        self.__name     :str    = 'default'
        self.__maxlen   :int    = 512       # Max entries threshold for triggering entries eviction.
        self.__maxsize  :int    = 512*1024  # Max size in bytes threshold for triggering entries eviction. Default= 256K.
        self.__ttl      :int    = 0         # Time to live in minutes.
        self.__msgbdy   :str    = 'L#{lno:>4}\tIm:{iam}\tOp:{opc}\tTs:{tsm:<18}\tNm:{nms}\tKy:{key}\tCk:{crc}\tMg:{msg}'
        self.__logger   :logging.Logger = None
        self.__queue    :queue.Queue    = None
        self.__callback :Callable       = None
        self.__cbwindow :int    = 3         # Callback window, in seconds, for changes in the cache since last looked up.
        self.__debug    :bool   = False     # Internal debug is disabled.
        self.__oldest   :int    = Cache.TSM_VERSION()  # Oldest entry in the cache.
        self.__latest   :int    = Cache.TSM_VERSION()  # Latest time the cache was touch on.
        self.__meta     :dict   = {}
        # Public instance metrics.
        self._reset_metrics()

        for key ,val in kwargs.items():
            if  val:
                match key:
                    case 'name':
                        if  not isinstance( val ,str ):
                            raise TypeError('The cache name must be a string!')
                        self.__name = str( val )
                    case 'max':
                        self.__maxlen = abs(int( val ))
                    case 'size':
                        self.__maxsize = abs(int( val ))
                    case 'ttl':
                        self.__ttl = abs(int( val ))
                    case 'msgbdy':
                        self.__msgbdy = str( val )
                    case 'logger':
                        if  not isinstance( val ,logging.Logger ):
                            raise TypeError('An instance of "logging.Logger" is required as a logger!')
                        self.__logger = val    # The logger object.
                    case 'queue':
                        if  not isinstance( val ,queue.Queue ):
                            raise TypeError('An instance of "queue.Queue" is required as a queue!')
                        self.__queue = val     # The queue object.
                    case 'callback':
                        if  not isinstance( val ,Callable ):
                            raise TypeError('An instance of "type.Callable" is required as a callback function!')
                        self.__callback = val   # The callback function.
                    case 'cbwindow':
                        if 'callback' not in kwargs:
                            raise TypeError('"cbwindow" can only be specify along with a callback function.')
                        self.__cbwindow = abs(int( val ))
                    case 'debug':
                        self.__debug = bool( val )

        # Setup the default logger.
        if  self.__logger is None:
            self._setup_logger()

        kwargs = { key: val for key ,val in kwargs.items()
                            if  key  not in {'name' ,'max' ,'size' ,'ttl' ,'msgbdy' ,'logger' ,'queue' ,'callback' ,'cbwindow' ,'debug'}}
        super().__init__( other ,**kwargs )

    # Public instance properties.
    #
    @property
    def logger(self) -> logging.Logger:
        return  self.__logger

    @property
    def maxlen(self) -> int:
        return  self.__maxlen

    @property
    def maxsize(self) -> int:
        return  self.__maxsize

    @property
    def metadata(self) -> dict:
        return  self.__meta

    @property
    def msgbdy(self) -> str:
        return  self.__msgbdy

    @property
    def name(self) -> str:
        return  self.__name

    @property
    def oldest(self) -> int:
        return  self.__oldest

    @property
    def latest(self) -> int:
        return  self.__latest

    @property
    def ttl(self) -> int:
        return  self.__ttl

    @property
    def queue(self) -> queue.Queue:
        return  self.__queue

    @property
    def callback(self) -> Callable:
        return  self.__callback

    # This class's private method section.
    #
    def _reset_metrics(self):
        """Reset the internal metrics.
        """
        self.__meta.clear()
        self.evicts   :int  = 0   # Total number of evicts  since initialization.
        self.deletes  :int  = 0   # Total number of deletes since initialization.
        self.misses   :int  = 0   # Total number of misses  since initialization.
        self.lookups  :int  = 0   # Total number of lookups since initialization.
        self.inserts  :int  = 0   # Total number of inserts since initialization.
        self.updates  :int  = 0   # Total number of updates since initialization.
        self.spikes   :int  = 0   # Total number of change to the cache where previous change was <= 5 seconds ago.
        self.spikeInt :float= 0.0 # Average spike interval between changes.
        self.ttlSize  :int  = sys.getsizeof( self ) # Total size of this cache object.

    def _setup_logger(self):
        """Setup the logger by checking the if we are in interactive terminal mode.
        """
        # Setup the default logger.
        self.__logger = logging.getLogger('pycache')
        if 'TERM' in os.environ or ('SESSIONNAME' in os.environ and os.environ['SESSIONNAME'] == 'Console'):
            # NOTE: In interactive terminal session.
            fmt = f"%(asctime)s.%(msecs)03d {__app__} %(levelname)s %(message)s"
            ftr = logging.Formatter(fmt=fmt ,datefmt='%Y%m%d%a %H%M%S')
            hdl = logging.StreamHandler()
            hdl.setFormatter( ftr )
            self.__logger.addHandler( hdl )
            self.__logger.setLevel( logging.DEBUG )

    def _log_ops_msg(self,
            opc: str    | None = None,    # Op Code
            tsm: str    | None = None,    # Timestamp
            nms: str    | None = None,    # Namespace
            key: object | None = None,    # Key
            crc: bytes  | None = None,    # Checksum (md5)
            msg: str    | None = None,    # Message
        ) -> None:
        """Standardize the output format with this object specifics.
        """
        txt = self.__msgbdy
        now = Cache.tsm_version_str()
        lno = getframeinfo(stack()[1][0]).lineno
        iam = Cache.IP4_ADDRESS if 'Im:' in txt else f'Im:{Cache.IP4_ADDRESS}'
        md5 = crc

        if  opc is None:
            opc =  f"O={' '* 4}"
        if  tsm is None:
            tsm =  f"T={' '*16}"
        else:
            tsm = f"{time.strftime('%H:%M:%S' ,time.gmtime(tsm // Cache.ONE_NS_SEC))}.{tsm % Cache.ONE_NS_SEC:0<9}"
        if  nms is None:
            nms =  f"N={' '* 5}"
        if  key is None:
            key =  f"K={' '* 6}"
        if  msg is None:
            msg =  ""
        if  crc is None:
            crc =  \
            md5 =  f"C={' '*20}"
        elif isinstance( crc ,bytes ):
            crc =  \
            md5 =  base64.b64encode( crc ).decode()[:-2]    # NOTE: Without '==' padding.

        txt =  txt.format( now=now ,lno=lno ,iam=iam ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,md5=md5 ,msg=msg )
        self.__logger.debug( txt )

    def _evict_items_by_ttl(self) -> int:
        """Evict cache time-to-live (ttl) based items.

        Return:
            Number of evictions.
        """
#       now = Cache.tsm_version()
        now = Cache.TSM_VERSION()
        ttl = self.__ttl * Cache.ONE_NS_SEC     # Convert seconds in nanosecond.
        evt: int = 0

        if  ttl > now - self.__oldest:
            return  0   # NOTE: Nothing is old enough to evict.

        if  self.__debug:
            self._log_ops_msg( opc='EVT' ,tsm=now ,nms=self.__name ,key=None ,crc=None ,msg='Checking for eviction candidates.')

#       oldest: int = Cache.tsm_version()
        oldest: int = Cache.TSM_VERSION()
        with  Cache.CACHE_LOCK: # TODO: Not working!
            for key in self.__meta.copy():  # Make a shallow copy of the keys.
                val = self.__meta[ key ]
                if  ttl < now - val['tsm']:
                    if  self.__contains__( key ):
                        _ = super().pop( key )
                    evt += 1
                    self._post_del( key=key ,tsm=now ,eviction=True ,queue_out=True )
                elif val['tsm'] < oldest:
                    oldest = val['tsm']
            self.__oldest = oldest
        return  evt

    def _get_size(self ,obj: object ,seen: set | None = None) -> int:
        """Recursively finds size of nested objects.

        Args:
            obj     Object, optionally with nested objects.
            seen    Set of seen objects as we recurse into the nesting.
        Return:
            size    Total size of the input object.
        """
        if seen is None:
            seen = set()

        obj_id = id( obj )
        if  obj_id in seen:
            return 0

        # Important mark as seen *before* entering recursion to gracefully handle self-referential objects.
        seen.add( obj_id )
        size = sys.getsizeof( obj )

        if isinstance( obj ,dict ):
            size += sum( self._get_size( k ,seen ) + self._get_size( v ,seen ) for k, v in obj.items())
        elif isinstance( obj ,(list ,tuple ,set ,frozenset)):
            size += sum( self._get_size( i ,seen ) for i in obj)
        elif isinstance( obj ,(ModuleType ,FunctionType)):
            pass  # Ignore modules and functions

        return size

    def _evict_items_by_capacity(self) -> int:
        """Evict cache capacity based items.
        To be called when we add an item to the cache.

        Return:
            Number of evictions.
        """
#       now = Cache.tsm_version()
        now = Cache.TSM_VERSION()
        with  Cache.CACHE_LOCK: # TODO: Not working!
            try:
                key ,_ = super().popitem( last=False )  # FIFO
                self._post_del(  key=key ,tsm=now ,eviction=True ,queue_out=True )
            except  KeyError:
                # Someone else deleted the last item.  We are good.
                pass
        return  1

    def _post_del(self,
            key: Any,
            tsm: int        | None = None,
            eviction: bool  | None = False,
            queue_out: bool | None = True ) -> None:
        """Post deletion processing.  Update the metadata and internal metrics.
        Queue out the details if required.

        Args:
            key         Post delete processing of metrics for this key.
            tsm         Optional timestamp for the deletion.
            eviction    Originated from a cache eviction or deletion.
            queue_out   Request queuing out operation info to external receiver.
        """
        crc = None
        lkp = None
        elp = None
        if  tsm is None:
#           tsm =  Cache.tsm_version()
            tsm =  Cache.TSM_VERSION()
        try:
            crc = self.__meta[ key ]['crc'] # Old crc value.
            lkp = self.__meta[ key ]['lkp'] # Last looked up.
            elp = tsm - lkp                 # Elapsed nano seconds.

            # Get the change out to members ASAP.
            if  self.__queue and queue_out:
                opc = 'EVT' if eviction else 'DEL'
                self.__queue.put((opc ,tsm ,self.__name ,key ,crc ,None ,None))
                if  self.__debug:
                    self._log_ops_msg( opc=opc ,tsm=tsm ,nms=self.__name ,key=key ,crc=crc ,msg='Queued.')

            del self.__meta[ key ]

            # Increment metrics.
            if  eviction:
                self.evicts  += 1
            else:
                self.deletes += 1
            self._set_spike()
        except  KeyError:
            # NOTE: Deleted from another thread.
            if  self.__debug:
                self.__logger.warning( f"Key '{key}' not found in cache '{self.__name}'.")

        # Callback to notify a change in the cache.
        if  self.__callback and elp and elp < (self.__cbwindow * Cache.ONE_NS_SEC):
            # Type: 1=Deletion ,2=Update ,3=Incoherent
            # The key/value got changed since last read.
            arg = {'typ': CallbackType.DELETE ,'nms': self.__name ,'key': key ,'lkp': lkp ,'tsm': tsm ,'elp': elp ,'prvcrc': crc ,'newcrc': crc}
            t1 = Thread( target=self.__callback ,args=[arg] ,name='PyCache' )
            t1.start()  # NOTE: Launch and forget.

    def _post_get(self,
            key: Any    ) -> None:
        """Post lookup processing.  Update the metadata.
        """
        try:
#           self.__meta[ key ]['lkp'] = Cache.tsm_version()
            self.__meta[ key ]['lkp'] = Cache.TSM_VERSION() # Timestamp for the just lookup operation.
        except  KeyError:
            # NOTE: Deleted from another thread.
            if  self.__debug:
                self.__logger.warning( f"Key '{key}' not found in cache '{self.__name}'.")

    def _post_set(self,
            key: Any,
            value: Any,
            tsm: int        | None = None,
            update: bool    | None = True,
            queue_out: bool | None = True ) -> None:
        """Post insert/update processing.  Update the metadata and internal metrics.
        Queue out the details if required.

        Args:
            key         Post setting processing of metrics for this key.
            value       Value that was set.
            tsm         Optional timestamp for the deletion.
            update      Originated from a cache update or insert.
            queue_out   Request queuing out operation info to external receiver.
        """
        if  tsm is None:
#           tsm =  Cache.tsm_version()
            tsm =  Cache.TSM_VERSION()
        try:
            if  key not in self.__meta:
                self.__meta[ key ] = {'tsm': tsm ,'crc': None ,'lkp': 0}

            crc = self.__meta[ key ]['crc'] # Old crc value.
            lkp = self.__meta[ key ]['lkp'] # Last looked up.
            elp = tsm - lkp                 # Elapsed nano seconds.
            md5 = hashlib.md5( bytearray(str( value ) ,encoding='utf-8') ).digest()  # noqa: S324   New crc value.

            # Get the change out to members ASAP.
            if  self.__queue and queue_out:
                opc = 'UPD' if update else 'INS'
                self.__queue.put((opc ,tsm ,self.__name ,key ,md5 ,value ,None))
                if  self.__debug:
                    self._log_ops_msg( opc=opc ,tsm=tsm ,nms=self.__name ,key=key ,crc=md5 ,msg=f'{opc} Queued out from _post_set()')

            self.__meta[ key ]['tsm'] = tsm
            self.__meta[ key ]['crc'] = md5

            # Increment metrics.
            if  update:
                with  Cache.CACHE_LOCK: # TODO: Not working!
                    try:
                        self.move_to_end( key ,last=True )    # FIFO
                    except  KeyError:
                        # Someone else deleted the last item.  We are good.
                        pass
                self.updates += 1
            else:
                self.inserts += 1
            self._set_spike()
        except  KeyError:
            # NOTE: Deleted from another thread.
            if  self.__debug:
                self.__logger.warning( f"Key '{key}' not found in cache '{self.__name}'.")

        # Callback to notify a change in the cache.
        if  self.__callback and elp and elp < (self.__cbwindow * Cache.ONE_NS_SEC):
            # Type: 1=Deletion ,2=Update ,3=Incoherent
            # The key/value got changed since last read.
            arg = {'typ': CallbackType.UPDATE ,'nms': self.__name ,'key': key ,'lkp': lkp ,'tsm': tsm ,'elp': elp ,'prvcrc': crc ,'newcrc': crc}
            t1 = Thread( target=self.__callback ,args=[arg] ,name='PyCache' )
            t1.start()  # NOTE: Launch and forget.

    def _set_spike(self,
            now: int | None = None ) -> None:
        """Update the internal spike metrics.
        A spikes are high frequency delete/insert/update that are within 5 seconds.

        Args:
            now     The current timestamp to determine a spike.  Default to present.
        """
        if  now is None:
#           now =  Cache.tsm_version()
            now =  Cache.TSM_VERSION()
        span =  now - self.__latest
        if  span > 0:
            # Monotonic.
            self.__latest  = now
            if  span <= (self.__cbwindow * Cache.ONE_NS_SEC):
                self.spikeInt = ((self.spikeInt * self.spikes) + span) / (self.spikes + 1)
                self.spikes  += 1

    # Private OrderedDict magic/dunder methods overwrite section.
    #
    def __delitem__(self,
            key: Any,
            tsm: int        | None = None,
            queue_out: bool | None = True ) -> None:
        """Dict __delitem__() dunder overwrite.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.__delitem__()
        Args:
            key         Key to the item to delete.
            tsm         Optional timestamp for the deletion.
            queue_out   Request queuing out operation info to external receiver.
        Raise:
            KeyError
        """
        if  tsm is None:
#           tsm =  Cache.tsm_version()
            tsm =  Cache.TSM_VERSION()
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        if  self.__debug:
            crc = self.__meta[ key ]['crc'] if key in self.__meta else None
            self._log_ops_msg( opc='DEL' ,tsm=tsm ,nms=self.__name ,key=key ,crc=crc ,msg='Deleted via __delitem__()')

        with  Cache.CACHE_LOCK: # TODO: Not working!
            if  self.__contains__( key ):
                size = self._get_size(super().__getitem__( key ))
                super().__delitem__( key )
                self.ttlSize -= size
        self._post_del( key=key ,tsm=tsm ,eviction=False ,queue_out=queue_out )

    def __getitem__(self,
            key: Any ) -> Any:
        """Dict __getitem__() dunder overwrite.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.__getitem__()
        Args:
            key         Key to the item to get.
        Raise:
            KeyError
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()
        try:
            val = super().__getitem__( key )
        except:
            self.misses += 1
            raise

        self.lookups += 1
        self._post_get( key )
        return val

    def __iter__(self) -> Iterable:
        """Dict __iter__() dunder overwrite.
        Check for ttl evict then call the parent method.

        SEE:    dict.__iter__()
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        return super().__iter__()

    def __setitem__(self,
            key: Any,
            value: Any,
            tsm: int        | None = None,
            queue_out: bool | None = True ) -> None:
        """Dict __setitem__() dunder overwrite.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.__setitem__()
        Args:
            key         Key to the item to set.
            value       Value of the item to set.
            tsm         Optional timestamp for the deletion.
            queue_out   Request queuing out operation info to external receiver.
        """
        if  tsm is None:
#           tsm =  Cache.tsm_version()
            tsm =  Cache.TSM_VERSION()
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        # NOTE: Very coarse way to check for eviction.  Not meant to be precise.
        while super().__len__()     > 0 and \
            ((super().__len__() + 1 > self.__maxlen) or (self.ttlSize + sys.getsizeof( value ) > self.__maxsize)):
                _ = self._evict_items_by_capacity()

        with  Cache.CACHE_LOCK: # TODO: Not working!
            updmode: bool = self.__contains__( key )   # If exist we are in UPD mode ,else INS mode.
            if  updmode:
                self.ttlSize -= self._get_size( super().__getitem__( key )) # Decrement the previous object size.
            super().__setitem__( key ,value )
            self.ttlSize += self._get_size( super().__getitem__( key ))     # Increment the current  object size.

        if  self.__debug:
            opc = f"{'UPD' if updmode else 'INS'}"
            msg = f"{'Updated' if updmode else 'Inserted'} via __setitem__()."
            crc = self.__meta[ key ]['crc'] if key in self.__meta else None
            self._log_ops_msg( opc=opc ,tsm=tsm ,nms=self.__name ,key=key ,crc=crc ,msg=msg)

        self._post_set( key=key ,value=value ,tsm=tsm ,update=updmode ,queue_out=queue_out )

    # Public dictionary methods section.
    #
    # SEE: https://www.programiz.com/python-programming/methods/dictionary/copy
    # SEE: https://www.geeksforgeeks.org/ordereddict-in-python/
    #
    def clear(self) -> None:
        """Clear the entire cache and update the internal metrics.
        Call the parent method and then do some house keeping.
        """
        super().clear()
#       self.__oldest =  Cache.tsm_version()
        self.__oldest = Cache.TSM_VERSION()
#       self.__latest =  Cache.tsm_version()
        self.__latest = Cache.TSM_VERSION()
        self._reset_metrics()

    def copy(self) -> OrderedDict:
        """Make a shallow copy of this cache instance.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.copy()
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        with Cache.CACHE_LOCK:
            return super().copy()

#   @classmethod
#   def fromkeys(cls, iterable, value=None):
#       ...
#       No need to overwrite.

    def get(self,
            key: Any,
            default: Any | None = None ) -> Any|None:
        """Get an item.  If doesn't exist return the default.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.get()
        Args:
            key         Key to the item to get.
            default     Default value to return if the key doesn't exist in the cache.
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        with Cache.CACHE_LOCK:
            val = super().get( key ,default )
        self.lookups += 1
        return val

    def items(self) -> dict:
        """Return a set-like object providing a view on cache's items.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.items()
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        with Cache.CACHE_LOCK:
            return super().items()

    def keys(self) -> dict:
        """Return a set-like object providing a view on cache's keys.

        SEE:    OrderedDict.keys()
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        with Cache.CACHE_LOCK:
            return super().keys()

    def pop(self,
            key: Any,
            default: Any | None = None ) -> Any:
        """Remove specified key and return the corresponding value.
        If key is not found, default is returned if given, otherwise KeyError is raised.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    OrdredDict.pop()
        Args:
            key         Key to the item to get.
            default     Default value to return if the key doesn't exist in the cache.
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        if  self.__debug:
            crc = self.__meta[ key ]['crc'] if  key in self.__meta  and 'crc' in self.__meta[ key ] else None
            self._log_ops_msg( opc='POP' ,tsm=None ,nms=self.__name ,key=key ,crc=crc ,msg='In pop()')

        with  Cache.CACHE_LOCK: # TODO: Not working!
            val = super().pop( key ,default )

        self._post_del( key=key ,eviction=False ,queue_out=True )
        return val

    def popitem(self,
            last: bool | None = False ) -> tuple:
        """Remove and return a (key, value) pair from the dictionary.
        Pairs are returned in LIFO order if last is true or FIFO order if false.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    OrderedDict.popitem()
        Args:
            last        True is LIFO ,False is FIFO
            default     Default value to return if the key doesn't exist in the cache.
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        if  self.__debug:
            crc = self.__meta[ key ]['crc'] if  key in self.__meta  and 'crc' in self.__meta[ key ] else None
            self._log_ops_msg( opc='POPI' ,tsm=None ,nms=self.__name ,key=key ,crc=crc ,msg='In popitem()')

        with  Cache.CACHE_LOCK: # TODO: Not working!
            key ,val = super().popitem( last )

        self._post_del( key=key ,eviction=False ,queue_out=True )
        return (key ,val)

    def setdefault(self,
            key: Any,
            default: Any | None = None ) -> Any:
        """Insert key with a value of default if key is not in the cache.
        Return the value for key if key is in the dictionary, else default.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    OrderedDict.setdefault()
        Args:
            key         Key to the item to get.
            default     Default value to return if the key doesn't exist in the cache.
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        if  self.__debug:
            crc = self.__meta[ key ]['crc'] if key in self.__meta and 'crc' in self.__meta[ key ] else None
            self._log_ops_msg( opc='SETD' ,tsm=None ,nms=self.__name ,key=key ,crc=crc ,msg='In setdefault()')

        with Cache.CACHE_LOCK:
            return super().setdefault( key ,default )

    def update(self,
            iterable: Iterable ) -> None:
        """Update the cache with new values.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.update()
        Args:
            iterable    A list of key/value pairs to update the cache with.
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        with  Cache.CACHE_LOCK: # TODO: Not working!
            updates = {}
            for key ,val in iterable.items():
                updates[ key ] = {'val': val ,'upd': self.__contains__( key )}    # If exist we are in UPD mode ,else INS mode.
                if  self.__debug:
                    crc = self.__meta[ key ]['crc'] if  key in self.__meta  and 'crc' in self.__meta[ key ] else None
                    self._log_ops_msg( opc='UPDT' ,tsm=None ,nms=self.__name ,key=key ,crc=crc ,msg='In update()')

            super().update( iterable )
            for key ,val in updates.items():
                self._post_set( key ,val['val'] ,update=val['upd'] ,queue_out=True )

    def values(self) -> dict:
        """Return an object providing a view on cache's values.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.values()
        """
        if  self.__ttl > 0:
            _ = self._evict_items_by_ttl()

        with Cache.CACHE_LOCK:
            return super().values()


# The MIT License (MIT)
# Copyright (c) 2023 McCache authors.
#
# Permission is hereby granted ,free of charge ,to Any person obtaining a copy
# of this software and associated documentation files (the "Software") ,to deal
# in the Software without restriction ,including without limitation the rights
# to use ,copy ,modify ,merge ,publish ,distribute ,sublicense ,and/or sell
# copies of the Software ,and to permit persons to whom the Software is
# furnished to do so ,subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS" ,WITHOUT WARRANTY OF Any KIND,
# EXPRESS OR IMPLIED ,INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY ,FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR Any CLAIM,
# DAMAGES OR OTHER LIABILITY ,WHETHER IN AN ACTION OF CONTRACT ,TORT OR
# OTHERWISE ,ARISING FROM ,OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
# OR OTHER DEALINGS IN THE SOFTWARE.
