# See MIT license at the bottom of this script.
#
import base64
import hashlib
import logging
import queue
import sys
import time
import threading

from collections import OrderedDict
#from collections.abc import dict_items, dict_keys ,dict_values
from inspect import getframeinfo, stack
from typing import Any ,Iterable


class Cache( OrderedDict ):
    """Cache based of the dict object.

    Functionality:
        - Maintain usage metrics.
        - Default as LFU cache.
        - Optionally with a time-to-live eviction.
        - Soft delete expired entries until eviction.
    """
    ONE_NS_SEC  = 10_000_000_000    # One Nano second.
    ONE_NS_MIN  = ONE_NS_SEC *60    # One Nano minute.
    TSM_VERSION = time.monotonic_ns if sys.platform == 'darwin' else time.time_ns

    def __init__(self ,*args ,**kwargs) -> None:
        """Cache constructor.

        Args:
            name    :str    Name for this instance of the cache.
            max     :int    Max entries threshold for triggering entries eviction. Default to `256`.
            size    :int    Max size in bytes threshold for triggering entries eviction. Default to `64K`.
            ttl     :int    Time to live in minutes. Default to `0`.
            debug   :bool   Enable internal debugging.  Default to `False`.
            logger  :Logger Custom logger to use internally.
            logmsg  :str    Custom log message format to log out.
            queue   :Queue  Output queue to broadcast internal changes out.
        """
        # Private instance control.
        self.__name     :str    = 'default'
        self.__ttl      :int    = 0     # Time to live in minutes.
        self.__maxlen   :int    = 256   # Max entries threshold for triggering entries eviction.
        self.__maxsize  :int    = 65536 # Max size in bytes threshold for triggering entries eviction. Default= 64K
        self.__touchon  :int    = Cache.TSM_VERSION()  # Last time the cache was touch on.
        self.__logger   :logging.Logger = None
        self.__queue    :queue.Queue    = None
        self.__debug    :bool   = False # Internal debug is disabled.
        self.__logmsg   :str    = 'L#{lno:>4}\tIm:{to}\tOp:{opc}\tTs:{tsm}\tNm:{nms}\tKy:{key}\tCk:{crc}\tMg:{msg}'
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

#       super().__init__( *args ,**kwargs ) # Keep this here or the "self.__xxx" variable be NOT accessable.

    def __resetmetrics(self):
        self.lookups  :int    = 0   # Total number of lookups since initialization.
        self.inserts  :int    = 0   # Total number of inserts since initialization.
        self.updates  :int    = 0   # Total number of updates since initialization.
        self.deletes  :int    = 0   # Total number of deletes since initialization.
        self.spikes   :int    = 0   # Total number of hits to the cache where previous hit was <= 5 seconds ago.
        self.spikeDur :float  = 0.0 # Average spike duration between updates.

    # Public instance properits.
    #
    @property
    def name(self) -> str:
        return  self.__name

    @property
    def maxlen(self) -> int:
        return  self.__maxlen

    @property
    def maxsize(self) -> int:
        return  self.__maxsize

    @property
    def ttl(self) -> int:
        return  self.__ttl

    @property
    def touchon(self) -> int:
        return  self.__touchon

    @property
    def logger(self) -> logging.Logger:
        return  self.__logger

    @property
    def queue(self) -> queue.Queue:
        return  self.__queue

    @property
    def logmsg(self) -> str:
        return  self.__logmsg

    # Private dictionary magic/dunder methods section.
    #
    def __getitem__(self ,__key: Any ) -> Any:
        if  self.__contains__( __key ):
            val = super().__getitem__( __key )
            if  not val['_del']:    # Active ,not soft deleted.
                self.lookups += 1
                return val['_val']  # Unwrap the value.
        raise KeyError( __key )

    def __delitem__(self ,__key: Any ,__multicast: bool = True ,tsm: int = None) -> None:
        if  tsm is None:
            tsm = Cache.TSM_VERSION()
        if  self.__contains__( __key ):
             val = super().__getitem__( __key )
             val['_del'] = True
             self.move_to_end( __key ,last=True )    # FIFO
             # TODO: Flesh out how exactly do we do soft delete.  In the mean time we do hard delete.
             if  self.__queue and __multicast:
                 self.__queue.put(('DEL' ,tsm ,self.__name ,__key ,val['_crc'] ,None))
             self._setspike()
        super().__delitem__( __key )

    def __setitem__(self ,__key: Any ,__value: Any ,__multicast: bool = True ,tsm: int = None) -> None:
        t = self.__name
        update  :bool = self.__contains__( __key )
        if  tsm is None:
            tsm =  Cache.TSM_VERSION()
        md5 = hashlib.md5( bytearray(str( __value) ,encoding='utf-8') ).digest()    # Keep it small until we need to display it.
        val = {'_tsm': tsm ,'_del': False ,'_crc': md5 ,'_val': __value}            # Wrap the value with metadata.

        # NOTE: Very coarse way to check for eviction.  Not meant to be precise.
        #if (super().__sizeof__() + sys.getsizeof( val ) > self.__maxsize) or (super().__len__() > self.__maxlen -1):
        #    self._evictitems( tsm=tsm ,multicast=__multicast )

        super().__setitem__( __key ,val )
        if  self.__queue and __multicast:
            self.__queue.put(('UPD' if update else 'INS' ,tsm ,self.__name ,__key ,md5 ,__value))
        self._setspike()

        # Increment metrics.
        if  update:
            self.updates += 1
            self.move_to_end( __key ,last=True )    # FIFO
        else:
            self.inserts += 1

    # This class private method section.
    #
    def _evictitems(self ,tsm: int ,multicast: bool = True) -> None:
        evt: int = 0    # Evicted count
        if  self.__ttl > 0:
            now = Cache.TSM_VERSION()
            ttl = self.__ttl * Cache.ONE_NS_MIN     # Convert minutes in nano second.
            for key ,val in super().items():
                if  now - val['_tsm'] > ttl:
                    val = self._pop( key )
                    if  self.__queue and multicast and not val['_del']: # Not soft delete.:
                        md5 =  val['_crc'] if isinstance( val ,dict ) and '_val' in val else None
                        self.__queue.put(('EVT' ,tsm ,self.__name ,key ,md5 ,None))
        if  evt == 0:
            key ,val = self._popitem( last=False )  # FIFO.
            md5 =  val['_crc'] if isinstance( val ,dict ) and '_val' in val else None
            if  self.__queue and multicast:
                self.__queue.put(('EVT' ,tsm ,self.__name ,key ,md5 ,None))

    def _setspike(self ,now: int = None ) -> None:
        if  now is None:
            now = Cache.TSM_VERSION()
        span =  now - self.__touchon
        if  span > 0:
            # Monotonic.
            self.__touchon  = now
            if  span <= (5 * Cache.ONE_NS_SEC): # 5 seconds.
                self.spikeDur = ((self.spikeDur * self.spikes) + span) / (self.spikes + 1)
                self.spikes  += 1

    def _log_ops_msg(self,
            opc: str    | None = None,
            tsm: str    | None = None,
            nms: str    | None = None,
            key: object | None = None,
            crc: str    | None = None,
            msg: str    | None = None) -> None:
        txt = self.__logmsg
        lno = getframeinfo(stack()[1][0]).lineno

        if '{lno' in txt:
            txt = txt.format( lno = lno )
        if '{opc' in txt:
            txt = txt.format( opc = opc if opc else 'O= ')
        if '{tsm' in txt:
            txt = txt.format( tsm = tsm if tsm else 'T=                 ')
        if '{nms' in txt:
            txt = txt.format( nsm = nms if nms else 'N=    ')
        if '{key' in txt:
            txt = txt.format( key = key if key else 'K=        ')
        if '{crc' in txt:
            crc = base64.b64encode( crc ).decode()  if crc else None
            txt = txt.format( crc = crc if crc else 'C=                      ')
        if '{msg' in txt:
            txt = txt.format( msg = msg if msg else '')

        self.__logger.debug( txt )

    # Public dictionary methods section.
    #
    # SEE: https://www.programiz.com/python-programming/methods/dictionary/copy
    # SEE: https://www.geeksforgeeks.org/ordereddict-in-python/
    #
    def clear(self) -> None:
        self.__resetmetrics()
        return super().clear()

    def copy(self) -> dict:
        raise NotImplementedError("Cache should NOT be shallow copied.")

    @classmethod
    def fromkeys(cls ,__iterable: Iterable ,__value: None = None) -> dict:
        self = cls()
        for key in __iterable:
            self[ key ] = __value
#       return self
        raise NotImplementedError("Use dict.fromkeys method instead.")

    def get(self ,__key: Any ,__default: Any | None=None ) -> dict:
        vl = super().get( __key ,__default )
        if  isinstance( vl ,dict ) and '_val' in vl:
            return ['_val']    # Unwrap the value.
        else:
            return vl

    def _items(self):
        return super().items()  # Raw wrapped data with metadata.

    def items(self):
        # TODO: Figure out a better way to return the items in the expected "dict_items" view.
        return OrderedDict([(e[0] ,e[1]['_val']) for e in super().items()]).items()

    def _pop(self ,__key: Any ,__default: Any | None=None ) -> Any:
        # NOTE: OrderedDict.pop() doesn't call internal dunder method.
        val = super().pop( __key ,__default)
        self.deletes -= 1
        self._setspike()
        return  val

    def pop(self ,__key: Any ,__default: Any | None=None ) -> Any:
        val = self._pop( __key ,__default )
        if  isinstance( val ,dict ) and '_val' in val:
            return val['_val']    # Unwrap the value.
        else:
            return val

    def _popitem(self ,last=True) -> tuple:
        # NOTE: OrderedDict.popitem() doesn't call internal dunder method.
        key ,val = super().popitem( last )
        self.deletes -= 1
        self._setspike()
        return (key ,val)

    def popitem(self ,last=True) -> tuple:
        key ,val = self._popitem( last )
        return (key ,val['_val']  if isinstance( val ,dict ) and '_val' in val else val)

    def setdefault(self, __key ,__default: Any | None=None ):
        if  __key   in  self:
            return  self[ __key ]['_val']
        self[ __key ] = __default
        return __default

    def update(self ,s: Iterable):
        # TODO: Finish this up.
        raise NotImplementedError("Cache entry cannot be set this way.")

    def values(self):
        # TODO: Figure out a better way to return the items in the expected "odict_values" view.
        return OrderedDict([(e[0] ,e[1]['_val']) for e in super().items()]).values()


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
