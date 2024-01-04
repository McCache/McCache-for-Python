# See MIT license at the bottom of this script.
#
import base64
import hashlib
import logging
import queue
import re
import socket
import sys
import time
import threading

from collections import OrderedDict
from inspect import getframeinfo, stack
from typing import Any ,Iterable


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

    def __init__(self ,other=(), /, **kwargs) -> None:  # NOTE: The / as an argument marks the end of arguments that are positional.
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
        self.__touchon  :int    = Cache.TSM_VERSION()  # Last time the cache was touch on.
        self.__meta     :dict   = {}
        # Public instance metrics.
        self.__resetmetrics()

        for key ,val in kwargs.items():
            match key:
                case 'name':
                    self.__name = str( val )
                case 'max':
                    self.__maxlen = int( val )
                case 'size':
                    self.__maxsize = int( val )
                case 'ttl':
                    self.__ttl = int( val )
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

        if  self.__logger is None:
            self.__logger = logging.getLogger()
            # TODO: Flash out the output.

        # TODO: Figure out the other constructors
#       super().__init__( other ,**kwargs ) # Keep this here or the "self.__xxx" variable be NOT accessable.

    def __resetmetrics(self):
        self.evicts   :int    = 0   # Total number of evicts  since initialization.
        self.lookups  :int    = 0   # Total number of lookups since initialization.
        self.inserts  :int    = 0   # Total number of inserts since initialization.
        self.updates  :int    = 0   # Total number of updates since initialization.
        self.deletes  :int    = 0   # Total number of deletes since initialization.
        self.spikes   :int    = 0   # Total number of change to the cache where previous change was <= 5 seconds ago.
        self.spikeDur :float  = 0.0 # Average spike duration between changes.

    # Public instance properties in alphabetical order.
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
    def touchon(self) -> int:
        return  self.__touchon

    @property
    def ttl(self) -> int:
        return  self.__ttl

    @property
    def queue(self) -> queue.Queue:
        return  self.__queue

    # This class's private method section.
    #
    def _log_ops_msg(self,
            opc: str    | None = None,  # Op Code
            tsm: str    | None = None,  # Timestamp
            nms: str    | None = None,  # Namespace
            key: object | None = None,  # Key
            md5: bytes  | None = None,  # md5 checksum
            msg: str    | None = None,  # Message
        ) -> None:
        txt = self.__logmsg
        lno = getframeinfo(stack()[1][0]).lineno

        for pat in ['lno' ,'iam' ,'opc' ,'tsm' ,'nms' ,'key' ,'crc' ,'msg']:
            for frg in re.findall('{'+pat+'[:<>]*[\d]*}' ,txt):
                sub = None
                match pat:
                    case 'lno':
                        sub = frg.format(  lno = lno )
                    case 'opc':
                        sub = frg.format(  opc = opc if opc else f"O={' '*3}" )
                    case 'tsm':
                        sub = frg.format(  tsm = tsm if tsm else f"T={' '*16}")
                    case 'nms':
                        sub = frg.format(  nms = nms if nms else f"N={' '*6}" )
                    case 'key':
                        sub = frg.format(  key = key if key else f"K={' '*8}" )
                    case 'crc':
                        crc = base64.b64encode( md5 ).decode()  if md5 else None
                        sub = frg.format(  crc = crc if crc else f"C={' '*22}")
                    case 'msg':
                        sub = frg.format(  msg = msg if msg else '' )
                    case 'iam':
                        sub = frg.format(  iam = Cache.IP4_ADDRESS )
                txt = txt.replace( frg ,sub )
        self.__logger.debug( txt )

    def _need_eviction(self ,value: Any) -> bool:
        # NOTE: Very coarse way to check for eviction.  Not meant to be precise.
        return (super().__sizeof__() + sys.getsizeof( value ) > self.__maxsize) or (super().__len__() > self.__maxlen -1)

    def _evict_items(self ,tsm: int ,multicast: bool = True) -> None:
        if  tsm is None:
            tsm =  Cache.TSM_VERSION()
        evt: int = 0    # Evicted count
        if  self.__ttl > 0:
            now = Cache.TSM_VERSION()
            ttl = self.__ttl * Cache.ONE_NS_MIN     # Convert minutes in nano second.
            for key ,val in self.__meta.items():
                if  ttl < now - val['tsm']:
                    val = super().pop( key )
                    self._post_del( key ,tsm ,multicast ,eviction=True )
                    self.evt += 1
        if  evt == 0:
            val = super().pop( key )
            self._post_del(  key ,tsm ,multicast ,eviction=True )

    def _post_del(self ,key: Any ,tsm: int ,multicast: bool ,eviction: bool = False) -> None:
        if  tsm is None:
            tsm =  Cache.TSM_VERSION()
        # TODO: Flesh out how exactly do we do soft delete.  In the mean time we do hard delete.
        md5 = self.__meta[ key ]['crc']
        self.__meta[ key ]['del'] = True
        del self.__meta[ key ]
        #
        if  self.__queue and multicast:
            if  tsm is None:
                tsm = Cache.TSM_VERSION()
            opc = 'EVT' if eviction else 'DEL'
            self.__queue.put((opc ,tsm ,self.__name ,key ,md5 ,None))
            if  self.__debug:
                self._log_ops_msg( opc ,tsm ,self.__name ,key ,md5 ,f'Queued.')

        # Increment metrics.
        if  eviction:
            self.evicts  += 1
        else:
            self.deletes += 1
        self._set_spike()

        # TODO: Flesh out how exactly do we do soft delete.  In the mean time we do hard delete.
        # self.move_to_end( key ,last=True )    # FIFO

    def _post_set(self ,key: Any ,value: Any ,tsm: int ,update: bool , multicast: bool) -> None:
        if  tsm is None:
            tsm =  Cache.TSM_VERSION()
        md5 = hashlib.md5( bytearray(str( value ) ,encoding='utf-8') ).digest()    # Keep it small until we need to display it.
        met = {'tsm': tsm ,'crc': md5 ,'del': False}
        self.__meta[ key ] = met

        if  self.__queue and multicast:
            opc = 'UPD' if update else 'INS'
            self.__queue.put((opc ,tsm ,self.__name ,key ,md5 ,value))
            if  self.__debug:
                self._log_ops_msg( opc ,tsm ,self.__name ,key ,md5 ,f'Queued.')

        # Increment metrics.
        if  update:
            self.move_to_end( key ,last=True )    # FIFO
            self.updates += 1
        else:
            self.inserts += 1
        self._set_spike()

    def _set_spike(self ,now: int = None ) -> None:
        if  now is None:
            now = Cache.TSM_VERSION()
        span =  now - self.__touchon
        if  span > 0:
            # Monotonic.
            self.__touchon  = now
            if  span <= (5 * Cache.ONE_NS_SEC): # 5 seconds.
                self.spikeDur = ((self.spikeDur * self.spikes) + span) / (self.spikes + 1)
                self.spikes  += 1

    # Private dict magic/dunder methods overwrite section.
    #
    def __delitem__(self ,__key: Any ,__multicast: bool = True ,tsm: int = None) -> None:
        # TODO: Flesh out how exactly do we do soft delete.  In the mean time we do hard delete.
        self.move_to_end( __key ,last=True )    # FIFO
        super().__delitem__( __key )
        self._post_del( __key ,tsm ,__multicast )

    def __getitem__(self, __key: Any) -> Any:
        val = super().__getitem__( __key )
        self.lookups += 1
        return val

    def __setitem__(self, __key: Any, __value: Any ,__multicast: bool = True ,tsm: int = None) -> None:
        update: bool = self.__contains__( __key )   # If exist we are in UPD mode, else INS mode.

        if  self.__debug:
            opc = 'UPD' if update else 'INS'
            self._log_ops_msg( opc ,tsm ,self.__name ,__key ,None ,f'CurSize: {super().__sizeof__()} ,ValSize: {sys.getsizeof( __value )} ,MaxSize: {self.__maxsize} ,CurLen: {super().__len__()} ,MaxLen: {self.__maxlen -1}')

        # NOTE: Very coarse way to check for eviction.  Not meant to be precise.
        while self._need_eviction( __value ):
            self._evict_items( tsm=tsm ,multicast=__multicast )

        super().__setitem__(__key, __value)
        self._post_set( __key ,__value ,tsm ,update ,__multicast )

#   Python dict class dunder methods.
#
#   def __add__(self, __value: list[_T]) -> list[_T]: ...
#   def __add__(self, __value: list[_S]) -> list[_S | _T]: ...
#   def __delitem__(self, __key: SupportsIndex | slice) -> None: ...
#   def __getitem__(self, __i: SupportsIndex) -> _T: ...
#   def __getitem__(self, __s: slice) -> list[_T]: ...
#   def __setitem__(self, __key: SupportsIndex, __value: _T) -> None: ...
#   def __setitem__(self, __key: slice, __value: Iterable[_T]) -> None: ...

    # Public dictionary methods section.
    #
    # SEE: https://www.programiz.com/python-programming/methods/dictionary/copy
    # SEE: https://www.geeksforgeeks.org/ordereddict-in-python/
    #

#   Python dict class public methods.
#
#   def append(self, __object: _T) -> None: ...
#   def clear(self) -> None: ...
#   def copy(self) -> list[_T]: ...
#   def copy(self) -> dict[_KT, _VT]: ...
#   def extend(self, __iterable: Iterable[_T]) -> None: ...
#   def fromkeys(cls ,__iterable: Iterable ,__value: None = None) -> dict: ...
#   def items(self) -> dict_items[_KT, _VT]: ...
#   def keys(self) -> dict_keys[_KT, _VT]: ...
#   def pop(self, __index: SupportsIndex = -1) -> _T: ...
#   def pop(self, __key: _KT, __default: _T) -> _VT | _T: ...
#   def values(self) -> dict_values[_KT, _VT]: ...

    def get(self ,__key: Any ,__default: Any | None=None ) -> dict:
        val = super().get( __key ,__default )
        self.lookups += 1
        return val

    def pop(self ,__key: Any ,__default: Any | None=None ) -> Any:
        val = super().pop( __key ,__default )
        # TODO: Flesh out how exactly do we do soft delete.  In the mean time we do hard delete.
        self.__meta[ __key ]['del'] = True
        del self.__meta[ __key ]
        self.deletes += 1
        self._set_spike()
        return val

    def popitem(self ,last=True) -> tuple:
        key ,val = super().popitem( last )
        # TODO: Flesh out how exactly do we do soft delete.  In the mean time we do hard delete.
        self.__meta[ key ]['del'] = True
        del self.__meta[ key ]
        self.deletes += 1
        self._set_spike()
        return (key ,val)

    def setdefault(self, __key: Any ,__default: Any | None=None ) -> Any:
        if __key in self:
            return self[__key]
        self.__setitem__( __key ,__default )
        return __default

    def update(self ,__iterable: Iterable ) -> None:
        upd = {}
        for key ,val in __iterable.items():
            upd[ key ] = {'val': val ,'upd': self.__contains__( key )}    # If exist we are in UPD mode, else INS mode.
        super().update( __iterable )
        for key ,val in upd.items():
            self._post_set( key ,val['val'] ,tsm=None ,update=val['upd'] ,multicast=True )


if __name__ == "__main__":
    # SEE: https://phoenixnap.com/kb/python-initialize-dictionary
    k = ['key1' ,'key2' ,'key3']
    v = ['val1' ,'val2' ,'val3']

    # Test.
    c = Cache()
    c = Cache(name='mccache' ,ttl=15 ,max=100 ,size=1024*1024 ,debug=True)
    try:
        _ = c['k']
    except KeyError:
        pass
    try:
        del c['k']
    except KeyError:
        pass

    c['k'] = 123
    c['k'] = 'The quick brown fox jump over the lazy dog and sat on a tack.'
    c['d'] = time.time_ns()
    v = c['k']
    v = c.get('k')

    for e in c: print(e)
    for k in c.keys( ):
        print(f"key={k}")
    for v in c.values( ):
        print(f"        val={v}")
    for k ,v in c.items( ):
        print(f"key={k}   val={v}")

    del c['k']
    v = c.pop('d' ,678)
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
