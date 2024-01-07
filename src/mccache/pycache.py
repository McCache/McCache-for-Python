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
from typing import Any ,Iterable

# TODO: Figure out how to setup this package.
try:
    # Not work from command line.
    from .__about__ import __app__, __version__ # noqa
except ImportError:
    # Work from VS Code.
    from  __about__ import __app__, __version__ # noqa


class Cache( OrderedDict ):
    """Cache based of the dict object.

    Functionality:
        - Default as LFU cache.
        - Maintain usage metrics.
        - Support time-to-live eviction.  Updated item will have its ttl reset.
        - Support communicating with external via queue.

    """
    ONE_NS_SEC  = 10_000_000_000    # One second in nano seconds.
    ONE_NS_MIN  = ONE_NS_SEC *60    # One minute in nano seconds.
    TSM_VERSION = time.monotonic_ns if sys.platform == 'darwin' else time.time_ns
    IP4_ADDRESS = sorted(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET ))[0][4][0]

    def __init__(self ,other=() ,/ ,**kwargs) -> None:  # NOTE: The / as an argument marks the end of arguments that are positional.
        """Cache constructor.
        other:      SEE:    OrderedDict( dict ).__init__()
        kwargs:
            name    :str    Name for this instance of the cache.
            max     :int    Max entries threshold for triggering entries eviction. Default to `256`.
            size    :int    Max size in bytes threshold for triggering entries eviction. Default to `64K`.
            ttl     :float  Time to live in minutes. Default to `0`.
            logmsg  :str    Custom log message format to log out.
            logger  :Logger Custom logger to use internally.
            queue   :Queue  Output queue to broadcast internal changes out.
            debug   :bool   Enable internal debugging.  Default to `False`.
        """
        # Private instance control.
        self.__name     :str    = 'default'
        self.__maxlen   :int    = 256       # Max entries threshold for triggering entries eviction.
        self.__maxsize  :int    = 256*1024  # Max size in bytes threshold for triggering entries eviction. Default= 256K.
        self.__ttl      :float  = 0.0       # Time to live in minutes.
        self.__logmsg   :str    = 'L#{lno:>4}\tIm:{iam}\tOp:{opc}\tTs:{tsm}\tNm:{nms}\tKy:{key}\tCk:{crc}\tMg:{msg}'
        self.__logger   :logging.Logger = None
        self.__queue    :queue.Queue    = None
        self.__debug    :bool   = False     # Internal debug is disabled.
        self.__oldest   :int    = Cache.TSM_VERSION()  # oldest entry in the cache.
        self.__latest   :int    = Cache.TSM_VERSION()  # Latest time the cache was touch on.
        self.__meta     :dict   = {}
        # Public instance metrics.
        self._reset_metrics()

        for key ,val in kwargs.items():
            match key:
                case 'name':
                    self.__name = str( val )
                case 'max':
                    self.__maxlen = int( val )
                case 'size':
                    self.__maxsize = int( val )
                case 'ttl':
                    self.__ttl = float( val )
                case 'logmsg':
                    self.__logmsg = str( val )
                case 'logger':
                    if  not isinstance( val ,logging.Logger ):
                        raise TypeError('An instance of "logging.Logger" is required!')
                    self.__logger = val    # The logger object.
                case 'queue':
                    if  not isinstance( val ,queue.Queue ):
                        raise TypeError('An instance of "queue.Queue" is required!')
                    self.__queue = val     # The queue object.
                case 'debug':
                    self.__debug = bool( val )

        # Setup the default logger.
        if  self.__logger is None:
            self._setup_logger()

        # TODO: Figure out the other constructors
        kwargs = { key: val for key ,val in kwargs.items()
                            if  key  not in {'name' ,'max' ,'size' ,'ttl' ,'logmsg' ,'logger' ,'queue' ,'debug'}}
        super().__init__( other ,**kwargs )

    # Public instance properties.
    #
    @property
    def logger(self) -> logging.Logger:
        return  self.__logger

    @property
    def logmsg(self) -> str:
        return  self.__logmsg

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
        self.evicts   :int    = 0   # Total number of evicts  since initialization.
        self.lookups  :int    = 0   # Total number of lookups since initialization.
        self.inserts  :int    = 0   # Total number of inserts since initialization.
        self.updates  :int    = 0   # Total number of updates since initialization.
        self.deletes  :int    = 0   # Total number of deletes since initialization.
        self.spikes   :int    = 0   # Total number of change to the cache where previous change was <= 5 seconds ago.
        self.spikeDur :float  = 0.0 # Average spike duration between changes.

    def _setup_logger(self):
        """Setup the logger by checking the if we are in interactive terminal mode.
        """
        # Setup the default logger.
        self.__logger = logging.getLogger('pycache')
        if 'TERM' in os.environ or ('SESSIONNAME' in os.environ and os.environ['SESSIONNAME'] == 'Console'):
            fmt = f"%(asctime)s.%(msecs)03d {__app__} %(levelname)s %(message)s"
            ftr = logging.Formatter(fmt=fmt ,datefmt='%Y%m%d%a %H%M%S')
            hdl = logging.StreamHandler()
            hdl.setFormatter( ftr )
            self.__logger.addHandler( hdl )
            self.__logger.setLevel( logging.DEBUG )

    def _log_ops_msg(self,
            opc: str    | None=None,    # Op Code
            tsm: str    | None=None,    # Timestamp
            nms: str    | None=None,    # Namespace
            key: object | None=None,    # Key
            md5: bytes  | None=None,    # md5 checksum
            msg: str    | None=None,    # Message
        ) -> None:
        """Standardize the output format with this object specifics.
        """
        txt = self.__logmsg
        lno = getframeinfo(stack()[1][0]).lineno
        iam = Cache.IP4_ADDRESS if 'Im:' in txt else f"Im:{Cache.IP4_ADDRESS}"
        if  opc is None:
            opc = ' '* 3
        if  tsm is None:
            tsm = ' '*16
        if  nms is None:
            nms = ' '* 6
        if  key is None:
            key = ' '* 8
        if  msg is None:
            msg = ""
        if  md5 is None:
            md5 = \
            crc = ' '*22
        elif  isinstance( md5 ,bytes ):
            md5 = \
            crc = base64.b64encode( md5 ).decode()

        txt =  txt.format( lno=lno ,iam=iam ,opc=opc ,tsm=tsm ,nms=nms ,key=key ,crc=crc ,md5=md5 ,msg=msg )
        self.__logger.debug( txt )

    def _evict_ttl_items(self) -> int:
        """Evict cache time-to-live (ttl) based items.

        Return:
            Number of evictions.
        """
        now = Cache.TSM_VERSION()
        ttl = self.__ttl * Cache.ONE_NS_MIN     # Convert minutes in nano second.
        evt: int = 0
        if  ttl > now - self.__oldest:
            return  0   # NOTE: Nothing is old enough to evict.

        for key ,val in [(k ,v) for k ,v in self.__meta.items() if ttl < now - val['tsm']]:
            _ = super().pop( key )
            evt += 1
            self._post_del( key=key ,tsm=now ,eviction=True ,multicast=True )

        self.__oldest = min( self.__meta.values() )
        return  evt

    def _evict_cap_items(self) -> int:
        """Evict cache capacity based items.

        Return:
            Number of evictions.
        """
        now    = Cache.TSM_VERSION()
        key ,_ = super().popitem( last=False )  # FIFO
        self._post_del(  key=key ,tsm=now ,eviction=True ,multicast=True )
        return  1

    def _post_del(self,
            key: Any,
            tsm: int        | None=None,
            eviction:  bool | None=False,
            multicast: bool | None=True ) -> None:
        """Post deletion processing.  Update the meatadata and internal metrics.
        Queue out the details if required.

        Args:
            key         Post delete processing of metrics for this key.
            tsm         Optional timestamp for the deletion.
            eviction    Originated from a cache eviction or deletion.
            multicast   Request queing out opeartion info to external receiver.
        """
        if  tsm is None:
            tsm =  Cache.TSM_VERSION()
        # TODO: Flesh out how exactly do we do soft delete.  In the mean time we do hard delete.
        md5 = self.__meta[ key ]['crc']
        self.__meta[ key ]['del'] = True
        self.__meta[ key ]['tsm'] = tsm
        del self.__meta[ key ]
        #
        if  self.__queue and multicast:
            opc = 'EVT' if eviction else 'DEL'
            self.__queue.put((opc ,tsm ,self.__name ,key ,md5 ,None))
            if  self.__debug:
                self._log_ops_msg( opc ,tsm ,self.__name ,key ,md5 ,'Queued.')

        # Increment metrics.
        if  eviction:
            self.evicts  += 1
        else:
            self.deletes += 1
        self._set_spike()

        # TODO: Flesh out how exactly do we do soft delete.  In the mean time we do hard delete.
        # self.move_to_end( key ,last=True )    # FIFO

    def _post_set(self,
            key: Any,
            value: Any,
            tsm: int        | None=None,
            update: bool    | None=True,
            multicast: bool | None=True ) -> None:
        """Post insert/update processing.  Update the meatadata and internal metrics.
        Queue out the details if required.

        Args:
            key         Post setting processing of metrics for this key.
            value       Value that was set.
            tsm         Optional timestamp for the deletion.
            update      Originated from a cache update or insert.
            multicast   Request queing out opeartion info to external receiver.
        """
        if  tsm is None:
            tsm =  Cache.TSM_VERSION()
        md5 = hashlib.md5( bytearray(str( value ) ,encoding='utf-8') ).digest() # noqa: S324    Keep it small until we need to display it.
        met = {'tsm': tsm ,'crc': md5 ,'del': False}
        self.__meta[ key ] = met

        if  self.__queue and multicast:
            opc = 'UPD' if update else 'INS'
            self.__queue.put((opc ,tsm ,self.__name ,key ,md5 ,value))
            if  self.__debug:
                self._log_ops_msg( opc ,tsm ,self.__name ,key ,md5 ,'Queued.')

        # Increment metrics.
        if  update:
            self.move_to_end( key ,last=True )    # FIFO
            self.updates += 1
        else:
            self.inserts += 1
        self._set_spike()

    def _set_spike(self,
            now: int | None=None ) -> None:
        """Update the internal spike metrics.
        A spikes are high frequncy delete/insert/update that are within 5 seconds.

        Args:
            now     The current timestamp to dtermine a spike.  Default to present.
        """
        if  now is None:
            now = Cache.TSM_VERSION()
        span =  now - self.__latest
        if  span > 0:
            # Monotonic.
            self.__latest  = now
            if  span <= (5 * Cache.ONE_NS_SEC): # 5 seconds.
                self.spikeDur = ((self.spikeDur * self.spikes) + span) / (self.spikes + 1)
                self.spikes  += 1

    # Private OrderedDict magic/dunder methods overwrite section.
    #
    def __delitem__(self,
            key: Any,
            tsm: int        | None=None,
            multicast: bool | None=True ) -> None:
        """Dict dunder overwrite.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.__delitem__()
        Args:
            key         Key to the item to delete.
            tsm         Optional timestamp for the deletion.
            multicast   Request queing out opeartion info to external receiver.
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        super().__delitem__( key )
        if  self.__debug:
            crc = self.__meta['crc'] if 'crc' in self.__meta else None
            self._log_ops_msg( 'DEL' ,tsm ,self.__name ,key ,crc ,f'Deleted via __delitem__()')
        self._post_del( key=key ,tsm=tsm ,eviction=False ,multicast=multicast )

    def __getitem__(self,
            key: Any ) -> Any:
        """Dict dunder overwrite.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.__getitem__()
        Args:
            key         Key to the item to get.
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        val = super().__getitem__( key )
        self.lookups += 1
        return val

    # TODO: Finish this implementation.
    def __iter__(self) -> Iterable:
        """Dict dunder overwrite.
        Check for ttl evict then call the parent method.

        SEE:    dict.__iter__()
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        return super().__iter__()

    def __setitem__(self,
            key: Any,
            value: Any,
            tsm: int        | None=None,
            multicast: bool | None=True ) -> None:
        """Dict dunder overwrite.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.__setitem__()
        Args:
            key         Key to the item to set.
            value       Value of the item to set.
            tsm         Optional timestamp for the deletion.
            multicast   Request queing out opeartion info to external receiver.
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        # NOTE: Very coarse way to check for eviction.  Not meant to be precise.
        while super().__len__()     > 0 and \
            ((super().__len__() + 1 > self.__maxlen) or (super().__sizeof__() + sys.getsizeof( value ) > self.__maxsize)):
                _ = self._evict_cap_items()

        updmode: bool = self.__contains__( key )   # If exist we are in UPD mode ,else INS mode.
        super().__setitem__( key ,value )

        if  self.__debug:
            crc = self.__meta['crc'] if 'crc' in self.__meta else None
            self._log_ops_msg( f"{'UPD' if updmode else 'INS'}" ,tsm ,self.__name ,key ,crc ,f"{'Updated' if updmode else 'Inserted'} via __setitem__()")
        self._post_set( key=key ,value=value ,tsm=tsm ,update=updmode ,multicast=multicast )

    # Public dictionary methods section.
    #
    # SEE: https://www.programiz.com/python-programming/methods/dictionary/copy
    # SEE: https://www.geeksforgeeks.org/ordereddict-in-python/
    #
    def clear(self) -> None:
        """Clear the entire cache and update the internal metrices.
        Call the parent method and then do some house keeping.
        """
        super().clear()
        self.__meta.clear()
        self.__oldest   = Cache.TSM_VERSION()
        self.__latest  = Cache.TSM_VERSION()
        self._reset_metrics()

    # TODO: Finish this implementation.
    def copy(self) -> OrderedDict:
        """Make a shallow copy of this cacge instance.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.copy()
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        return super().copy()

    # TODO: Finish this implementation.
    @classmethod
    def fromkeys(cls, iterable, value=None):
        """Create a new ordered dictionary with keys from iterable and values set to value.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.fromkeys()
        """
        self = cls()
        for key in iterable:
            self[key] = value   # Calls __setitem__()
        return self

    def get(self,
            key: Any,
            default: Any = None ) -> Any|None:
        """Get an item.  If doesn't exist return the default.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    dict.get()
        Args:
            key         Key to the item to get.
            default     Default value to return if the key doesn't exist in the cache.
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        val = super().get( key ,default )
        self.lookups += 1
        return val

    def items(self) -> dict:
        """Return a set-like object providing a view on cache's items.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.items()
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()
        return super().items()

    def keys(self) -> dict:
        """Return a set-like object providing a view on cache's keys.

        SEE:    OrderedDict.keys()
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()
        return super().keys()

    def pop(self,
            key: Any,
            default: Any = None ) -> Any:
        """Remove specified key and return the corresponding value.
        If key is not found, default is returned if given, otherwise KeyError is raised.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    OrdredDict.pop()
        Args:
            key         Key to the item to get.
            default     Default value to return if the key doesn't exist in the cache.
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        if  self.__debug:
            crc = self.__meta['crc'] if 'crc' in self.__meta else None
            self._log_ops_msg( 'POP' ,None ,self.__name ,key ,crc ,f'In pop()')

        val = super().pop( key ,default )
        self._post_del( key=key ,eviction=False ,multicast=True )
        return val

    def popitem(self,
            last: bool | None=False ) -> tuple:
        """Remove and return a (key, value) pair from the dictionary.
        Pairs are returned in LIFO order if last is true or FIFO order if false.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    OrderedDict.popitem()
        Args:
            last        True is LIFO ,False is FIFO
            default     Default value to return if the key doesn't exist in the cache.
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        if  self.__debug:
            crc = self.__meta['crc'] if 'crc' in self.__meta else None
            self._log_ops_msg( 'POPI' ,None ,self.__name ,key ,crc ,f'In popitem()')

        key ,val = super().popitem( last )
        self._post_del( key=key ,eviction=False ,multicast=True )
        return (key ,val)

    def setdefault(self,
            key: Any,
            default: Any = None ) -> Any:
        """Insert key with a value of default if key is not in the cache.
        Return the value for key if key is in the dictionary, else default.
        Check for ttl evict then call the parent method and then do some house keeping.

        SEE:    OrderedDict.setdefault()
        Args:
            key         Key to the item to get.
            default     Default value to return if the key doesn't exist in the cache.
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        if  self.__debug:
            crc = self.__meta['crc'] if 'crc' in self.__meta else None
            self._log_ops_msg( 'SETD' ,None ,self.__name ,key ,crc ,f'In setdefault()')

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
            _ = self._evict_ttl_items()

        updates = {}
        for key ,val in iterable.items():
            updates[ key ] = {'val': val ,'upd': self.__contains__( key )}    # If exist we are in UPD mode ,else INS mode.
        if  self.__debug:
            crc = self.__meta['crc'] if 'crc' in self.__meta else None
            self._log_ops_msg( 'UPDT' ,None ,self.__name ,key ,crc ,f'In update()')

        super().update( iterable )
        for key ,val in updates.items():
            self._post_set( key ,val['val'] ,update=val['upd'] ,multicast=True )

    def values(self) -> dict:
        """Return an object providing a view on cache's values.
        Check for ttl evict then call the parent method.

        SEE:    OrderedDict.values()
        """
        if  self.__ttl > 0:
            _ = self._evict_ttl_items()

        return super().values()

if __name__ == "__main__":
    # SEE: https://phoenixnap.com/kb/python-initialize-dictionary
    k = ['key1' ,'key2' ,'key3']
    v = ['val1' ,'val2' ,'val3']

    # Test.
    c = Cache()
    pass


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
