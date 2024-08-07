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
from inspect import getframeinfo, stack
from threading import RLock #,Lock
from types import FunctionType
from typing import Any

# If you are using VS Code, make sure your "cwd" and "PYTHONPATH" is set correctly in `launch.json`:
#   "cwd": "${workspaceFolder}",
#   "env": {"PYTHONPATH": "${workspaceFolder}${pathSeparator}src;${env:PYTHONPATH}"},
#
from  pycache.__about__ import __app__, __version__ # noqa

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
    # CACHE_LOCK  = Lock()    # DEBUG
    ONE_NS_SEC  = 1_000_000_000     # One second in nano seconds.
    ONE_NS_MIN  = 60 * ONE_NS_SEC   # One minute in nano seconds.
    TSM_VERSION = time.monotonic_ns if sys.platform == 'darwin' else time.time_ns
    # NOTE: time.monotonic_ns() behave differently on different OS.  Different precision is returned.
    #       Win11:  13446437000000
    #       WSL:    11881976237028
    #
    #       time.time_ns()
    #       Win11:  1707278030313783400
    #       WSL:    1707276577346395597
    #
    IP4_ADDRESS = sorted(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET ))[0][4][0]

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
            callback:FunctionType   Your function to call if a value got updated just after you have read it.
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
        self.__maxlen   :int    = 256       # Max entries threshold for triggering entries eviction.
        self.__maxsize  :int    = 256*1024  # Max size in bytes threshold for triggering entries eviction. Default= 256K.
        self.__ttl      :int    = 0         # Time to live in minutes.
        self.__msgbdy   :str    = 'L#{lno:>4}\tIm:{iam}\tOp:{opc}\tTs:{tsm:<18}\tNm:{nms}\tKy:{key}\tCk:{crc}\tMg:{msg}'
        self.__logger   :logging.Logger = None
        self.__queue    :queue.Queue    = None
        self.__callback :FunctionType   = None
        self.__cbwindow :int    = 1
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
                        if  not isinstance( val ,FunctionType ):
                            raise TypeError('An instance of "type.FunctionType" is required as a callback function!')
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

    # This class's private method section.
    #
    def _reset_metrics(self):
        """Reset the internal metrics.
        """
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
        lno = getframeinfo(stack()[1][0]).lineno
        iam = Cache.IP4_ADDRESS if 'Im:' in txt else f'Im:{Cache.IP4_ADDRESS}'
        md5 = crc

        if  opc is None:
            opc =  f"O={' '* 4}"
        if  tsm is None:
            tsm =  f"T={' '*16}"    #   04:13:56.108051950
        else:
            tsm = f"{time.strftime('%H:%M:%S' ,time.gmtime(tsm // Cache.ONE_NS_SEC))}.{tsm % Cache.ONE_NS_SEC:0<8}"
        if  nms is None:
            nms =  f"N={' '* 6}"
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

        txt =  txt.format( lno=lno ,iam=iam ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,md5=md5 ,msg=msg )
        self.__logger.debug( txt )

    def _evict_ttl_items(self) -> int:
        """Evict cache time-to-live (ttl) based items.

        Return:
            Number of evictions.
        """
        now = Cache.TSM_VERSION()
        ttl = self.__ttl * Cache.ONE_NS_SEC     # Convert seconds in nanosecond.
        evt: int = 0

        if  ttl > now - self.__oldest:
            return  0   # NOTE: Nothing is old enough to evict.

        if  self.__debug:
            self._log_ops_msg( opc='EVT' ,tsm=now ,nms=self.__name ,key=None ,crc=None ,msg='Checking for eviction candidates.')

        oldest: int = Cache.TSM_VERSION()
        try:
            Cache.CACHE_LOCK.acquire()
            for key in self.__meta.copy():  # Make a shallow copy of the keys.
                val = self.__meta[ key ]
                if  ttl < now - val['tsm']:
                    _ = super().pop( key )
                    evt += 1
                    self._post_del( key=key ,tsm=now ,eviction=True ,queue_out=True )
                elif val['tsm'] < oldest:
                    oldest = val['tsm']
        finally:
            self.__oldest = oldest

        self.__oldest = oldest
        return  evt

    def _get_size(self ,obj: object ,seen: set | None = None) -> int:
        """Recursively finds size of nested objects.

        Credit goes to:
        https://goshippo.com/blog/measure-real-size-any-python-object

        Args:
            obj     Object, optionally with nested objects.
            seen    Set of seen objects as we recurse into the nesting.
        Return:
            size    Total size of the input object.
        """
        size = sys.getsizeof( obj ) # Size of the object with any additional overhead.
        if  seen is None:
            seen =  set()
        obj_id = id( obj )
        if  obj_id in seen:
            return 0
        # Important mark as seen *before* entering recursion to gracefully handle
        # self-referential objects
        seen.add( obj_id )
        if  isinstance( obj ,dict ):
            size += sum([self._get_size( v ,seen ) for v in obj.values()])
            size += sum([self._get_size( k ,seen ) for k in obj.keys()])
        elif hasattr( obj ,'__dict__' ):
            size += self._get_size( obj.__dict__ ,seen )
        elif hasattr( obj ,'__iter__' ) and not isinstance( obj ,str | bytes | bytearray ):
            size += sum([self._get_size( o ,seen ) for o in obj])
        return size


    def _evict_cap_items(self) -> int:
        """Evict cache capacity based items.

        Return:
            Number of evictions.
        """
        now    = Cache.TSM_VERSION()
        key ,_ = super().popitem( last=False )  # FIFO
        self._post_del(  key=key ,tsm=now ,eviction=True ,queue_out=True )
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
        if  tsm is None:
            tsm =  Cache.TSM_VERSION()
        try:
            crc = self.__meta[ key ]['crc'] # Old crc value.
            lkp = self.__meta[ key ]['lkp'] # Last looked up.
            elp = tsm - lkp                 # Elapsed nano seconds.
            del self.__meta[ key ]
            #
            if  self.__queue and queue_out:
                opc = 'EVT' if eviction else 'DEL'
                self.__queue.put((opc ,tsm ,self.__name ,key ,crc ,None ,None))
                if  self.__debug:
                    self._log_ops_msg( opc=opc ,tsm=tsm ,nms=self.__name ,key=key ,crc=crc ,msg='Queued.')

            # Increment metrics.
            if  eviction:
                self.evicts  += 1
            else:
                self.deletes += 1
            self._set_spike()
        except  KeyError:
            pass    # NOTE: Deleted from another thread.

        # Callback to notify a change in the cache.
        if  self.__callback and elp < (self.__cbwindow * Cache.ONE_NS_SEC):
            # The key/value got changed since last read.
            # We are still in a locked state so the callee method MUST NOT block!
            # TODO: Spin it off on a different thread?
            self.__callback({'typ': 1 ,'nms': self.__name ,'key': key ,'lkp': lkp ,'tsm': tsm ,'elp': elp ,'prvcrc': crc ,'newcrc': crc})

    def _post_get(self,
            key: Any    ) -> None:
        """Post lookup processing.  Update the metadata.
        """
        self.__meta[ key ]['lkp'] = Cache.TSM_VERSION() # Timestamp for the just lookup operation.

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
            tsm =  Cache.TSM_VERSION()
        if  key not in self.__meta:
            self.__meta[ key ] = {'tsm': None ,'crc': None ,'lkp': 0}

        crc = self.__meta[ key ]['crc'] # Old crc value.
        lkp = self.__meta[ key ]['lkp'] # Last looked up.
        elp = tsm - lkp                 # Elapsed nano seconds.
        md5 = hashlib.md5( bytearray(str( value ) ,encoding='utf-8') ).digest()  # noqa: S324   New crc value.
        self.__meta[ key ]['tsm'] = tsm
        self.__meta[ key ]['crc'] = md5

        if  self.__queue and queue_out:
            opc = 'UPD' if update else 'INS'
            self.__queue.put((opc ,tsm ,self.__name ,key ,md5 ,value ,None))
            if  self.__debug:
                self._log_ops_msg( opc=opc ,tsm=tsm ,nms=self.__name ,key=key ,crc=md5 ,msg=f'{opc} Queued out from _post_set()')

        # Increment metrics.
        if  update:
            self.move_to_end( key ,last=True )    # FIFO
            self.updates += 1
        else:
            self.inserts += 1
        self._set_spike()

        # Callback to notify a change in the cache.
        if  self.__callback and elp < (self.__cbwindow * Cache.ONE_NS_SEC):
            # The key/value got changed since last read.
            # We are still in a locked state so the callee method MUST NOT block!
            # TODO: Spin it off on a different thread?
            self.__callback({'typ': 2 ,'nms': self.__name ,'key': key ,'lkp': lkp ,'tsm': tsm ,'elp': elp ,'prvcrc': crc ,'newcrc': md5})

    def _set_spike(self,
            now: int | None = None ) -> None:
        """Update the internal spike metrics.
        A spikes are high frequency delete/insert/update that are within 5 seconds.

        Args:
            now     The current timestamp to determine a spike.  Default to present.
        """
        if  now is None:
            now =  Cache.TSM_VERSION()
        span =  now - self.__latest
        if  span > 0:
            # Monotonic.
            self.__latest  = now
            if  span <= (5 * Cache.ONE_NS_SEC): # 5 seconds.
                self.spikeInt = ((self.spikeInt * self.spikes) + span) / (self.spikes + 1)
                self.spikes  += 1

    # Private OrderedDict magic/dunder methods overwrite section.
    #
    def __delitem__(self,
            key: Any,
            tsm: int        | None = None,
            queue_out: bool | None = True ) -> None:
        """Dict __delitem__ dunder overwrite.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.__delitem__()
        Args:
            key         Key to the item to delete.
            tsm         Optional timestamp for the deletion.
            queue_out   Request queuing out operation info to external receiver.
        Raise:
            KeyError
        """
        try:
            Cache.CACHE_LOCK.acquire()
            if  tsm is None:
                tsm =  Cache.TSM_VERSION()
            if  self.__ttl > 0:
                _ = self._evict_ttl_items()

            if  self.__contains__( key ):   # NOTE: Added because encountered `KeyError` exception.
                size = self._get_size(super().__getitem__( key ))
                super().__delitem__( key )
                self.ttlSize -= size

            if  self.__debug:
                crc = self.__meta[ key ]['crc'] if key in self.__meta else None
                self._log_ops_msg( opc='DEL' ,tsm=tsm ,nms=self.__name ,key=key ,crc=crc ,msg='Deleted via __delitem__()')
            self._post_del( key=key ,tsm=tsm ,eviction=False ,queue_out=queue_out )
        finally:
            Cache.CACHE_LOCK.release()

    def __getitem__(self,
            key: Any ) -> Any:
        """Dict __getitem__ dunder overwrite.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.__getitem__()
        Args:
            key         Key to the item to get.
        Raise:
            KeyError
        """
        if  self.__ttl > 0:
            try:
                Cache.CACHE_LOCK.acquire()
                _ = self._evict_ttl_items()
            finally:
                Cache.CACHE_LOCK.release()

        val = super().__getitem__( key )
        self.lookups += 1
        self._post_get( key )
        return val

    def __iter__(self) -> Iterable:
        """Dict __iter__ dunder overwrite.
        Check for ttl evict then call the parent method.

        SEE:    dict.__iter__()
        """
        if  self.__ttl > 0:
            try:
                Cache.CACHE_LOCK.acquire()
                _ = self._evict_ttl_items()
            finally:
                Cache.CACHE_LOCK.release()

        return super().__iter__()

    def __setitem__(self,
            key: Any,
            value: Any,
            tsm: int        | None = None,
            queue_out: bool | None = True ) -> None:
        """Dict __setitem__ dunder overwrite.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.__setitem__()
        Args:
            key         Key to the item to set.
            value       Value of the item to set.
            tsm         Optional timestamp for the deletion.
            queue_out   Request queuing out operation info to external receiver.
        """
        try:
            Cache.CACHE_LOCK.acquire()
            if  tsm is None:
                tsm =  Cache.TSM_VERSION()
            if  self.__ttl > 0:
                _ = self._evict_ttl_items()

            # NOTE: Very coarse way to check for eviction.  Not meant to be precise.
            while super().__len__()     > 0 and \
                ((super().__len__() + 1 > self.__maxlen) or (self.ttlSize + sys.getsizeof( value ) > self.__maxsize)):
                    _ = self._evict_cap_items()

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
        finally:
            Cache.CACHE_LOCK.release()

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
        self.__meta.clear()
        self.__oldest = Cache.TSM_VERSION()
        self.__latest = Cache.TSM_VERSION()
        self._reset_metrics()

    def copy(self) -> OrderedDict:
        """Make a shallow copy of this cache instance.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.copy()
        """
        if  self.__ttl > 0:
            try:
                Cache.CACHE_LOCK.acquire()
                _ = self._evict_ttl_items()
            finally:
                Cache.CACHE_LOCK.release()

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
            try:
                Cache.CACHE_LOCK.acquire()
                _ = self._evict_ttl_items()
            finally:
                Cache.CACHE_LOCK.release()

        val = super().get( key ,default )
        self.lookups += 1
        return val

    def items(self) -> dict:
        """Return a set-like object providing a view on cache's items.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.items()
        """
        if  self.__ttl > 0:
            try:
                Cache.CACHE_LOCK.acquire()
                _ = self._evict_ttl_items()
            finally:
                Cache.CACHE_LOCK.release()

        return super().items()

    def keys(self) -> dict:
        """Return a set-like object providing a view on cache's keys.

        SEE:    OrderedDict.keys()
        """
        if  self.__ttl > 0:
            try:
                Cache.CACHE_LOCK.acquire()
                _ = self._evict_ttl_items()
            finally:
                Cache.CACHE_LOCK.release()

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
        try:
            Cache.CACHE_LOCK.acquire()
            if  self.__ttl > 0:
                _ = self._evict_ttl_items()

            if  self.__debug:
                crc = self.__meta['crc'] if 'crc' in self.__meta else None
                self._log_ops_msg( opc='POP' ,tsm=None ,nms=self.__name ,key=key ,crc=crc ,msg='In pop()')

            val = super().pop( key ,default )
            self._post_del( key=key ,eviction=False ,queue_out=True )
        finally:
            Cache.CACHE_LOCK.release()
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
        try:
            Cache.CACHE_LOCK.acquire()
            if  self.__ttl > 0:
                _ = self._evict_ttl_items()

            key ,val = super().popitem( last )
            if  self.__debug:
                crc = self.__meta['crc'] if 'crc' in self.__meta else None
                self._log_ops_msg( opc='POPI' ,tsm=None ,nms=self.__name ,key=key ,crc=crc ,msg='In popitem()')

            self._post_del( key=key ,eviction=False ,queue_out=True )
        finally:
            Cache.CACHE_LOCK.release()
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
            try:
                Cache.CACHE_LOCK.acquire()
                _ = self._evict_ttl_items()
            finally:
                Cache.CACHE_LOCK.release()

        if  self.__debug:
            crc = self.__meta['crc'] if 'crc' in self.__meta else None
            self._log_ops_msg( opc='SETD' ,tsm=None ,nms=self.__name ,key=key ,crc=crc ,msg='In setdefault()')

        return super().setdefault( key ,default )

    def update(self,
            iterable: Iterable ) -> None:
        """Update the cache with new values.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.update()
        Args:
            iterable    A list of key/value pairs to update the cache with.
        """
        try:
            Cache.CACHE_LOCK.acquire()
            if  self.__ttl > 0:
                _ = self._evict_ttl_items()

            updates = {}
            for key ,val in iterable.items():
                updates[ key ] = {'val': val ,'upd': self.__contains__( key )}    # If exist we are in UPD mode ,else INS mode.
            if  self.__debug:
                crc = self.__meta['crc'] if 'crc' in self.__meta else None
                self._log_ops_msg( opc='UPDT' ,tsm=None ,nms=self.__name ,key=key ,crc=crc ,msg='In update()')

            super().update( iterable )
            for key ,val in updates.items():
                self._post_set( key ,val['val'] ,update=val['upd'] ,queue_out=True )
        finally:
            Cache.CACHE_LOCK.release()

    def values(self) -> dict:
        """Return an object providing a view on cache's values.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.values()
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

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
