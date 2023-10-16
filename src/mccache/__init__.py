# See MIT license at the bottom of this script.
#
"""
This is a distributed application cache build on top of the `cachetools` package.  SEE: https://pypi.org/project/cachetools/
It uses UDP multicasting is used as the transport hence the name "Multi-Cast Cache", playfully abbreviated to "McCache".


2023-09-10:
    To implement a peer-to-peer communication will be a big management overhead.
    As the cluster is coming online subsequent nodes could miss the prior annoucement.
    All the nodes need to setup their connections to connect to all the other cluster members.

    Instead, I am thinking of using the the same multi-cast infrasture to communicate among the members of the cluster.
    `ACK` packets are small and UDP is faster than TCP.  Modern switches are reliable managing ports thus reducing collision.
    Draft design:
        - New member multicast their presence but member that is coming online later will have missed this annoucemet.
            - Upon receiving any operations, we check the `members` collection for existance.  Add it, if it doesn't exist.
            - Upon receiving the `BYE` operation, remove it from the `members` collection.
        - `DEL`, `PUT`, `UPD` operations will require acknowledgment.
            - A `pending` dictionary shall be used to keep track of un-acknowledge keys.
                - We queue up a `ACK` operation to be multicast out.
            - All members in the cluster will receive other members acknowledgements.
                - If the received acknowledgment is not in one's `pending` collect, just ignore it.
                - The house keeping thread shall monitor the acknowledgement and request re-acknowledgement.
                    - Keys that have not received an acknowledgement in 1 sec, a re-acknowledgment `RAK` is initiated.
                    - If we haven't receive acknowledgement after 10 sec, we log a `warning` or `critical` message.
                        - Remove the key from the `pending` collection.
                        - Remove the key from the `member`  collection.
                            - The member node is down.

    Since we are going to implement a guarenteed protocol, the following feature to replace the optimistic level.
        1) Member only interested in what it have in cache.  Uses less memory.
        2) All members have the identical cache.  Will take up more memory per member.

    Competition:
    So far I have not able to seach for anything out on the internet that is doing what this project is doing.
    There is a Python project call `DistCache` but upon digging deeper it is a frontend to Redis.
        https://pypi.org/project/distcache/

    Are we so crazy to think of this design and implmentation?
    Surely, this is a solved problem or the herd mentality is on the client-server model.
"""
import atexit
import base64
import collections
import functools
import hashlib
import heapq
import logging
import os
import pickle
import psutil
import queue
import random
import socket
import struct
import sys
import threading
import time

from dataclasses import dataclass, fields
from enum import Enum, StrEnum
from logging.handlers import RotatingFileHandler
from statistics import mean

# TODO: Figure out how to setup this package.
try:
    # Not work from command line.
    from .__about__ import __app__, __version__ # noqa
except ImportError:
    # Work from VS Code.
    from  __about__ import __app__, __version__ # noqa


# Cachetools section.
#
# Classes copied from cachetools package version 5.3.1 by Thomas Kemmer.
# Licensed under The MIT License (MIT)
# I tried subclassing to overwrite:
#   __setitem__()
#   __delitem__()
#
# but encountered the issue where some of the value are set to None.
# Did not encounter this issue using a straight cachetools package.
# In the interest of time, I just copy cachetools classes over and tweaked them.
# When we have out test completed, we should try Monkey Patching it.
#
# We should also consider using other popular Python Cache implementation too.  Some candidates are:
#   1. https://pypi.org/project/cache3/
#   2. Write our own based of collection.UserDict


# fmt: off
class _DefaultSize:
    __slots__ = ()

    def __getitem__(self, _):
        return 1

    def __setitem__(self, _, value):
        assert value == 1   # noqa: S101

    def pop(self, _):
        return 1


class Cache(collections.abc.MutableMapping):
    """Mutable mapping to serve as a simple cache or cache base class."""

    __marker = object()

    __size = _DefaultSize()

    def __init__(self, maxsize, getsizeof=None):
        if getsizeof:
            self.getsizeof = getsizeof
        if self.getsizeof is not Cache.getsizeof:
            self.__size = dict()    # noqa: C408
        self.__data = dict()        # noqa: C408
        self.__currsize = 0
        self.__maxsize = maxsize
        # McCache addition.
        self.__name:str = None
        self.__initOn   = time.time_ns()    # The time the cache was initialized in nano seconds.
        self.__hitOn    = time.time_ns()    # Last time the cache was hit.
        self.__lookups  = 0                 # Total number of lookups since the cache initialization.
        self.__updates  = 0                 # Total number of updates since the cache initialization.
        self.__deletes  = 0                 # Total number of deletes since the cache initialization.
        self.__avgHits  = 0                 # Total number of hits to the cache for the average load in 1 minutes spike window.
        self.__avgSpan  = 0                 # The average load between calls that is within 10 minutes apart.

    def __setload__(self ,is_update: bool ) -> None:    # noqa: FBT001
        # Collect McCache metric and how rapid the cache being hit on.
        # Not interested in lookups.
        if  is_update:
            self.__updates += 1
        else:
            self.__deletes += 1

        _since  = time.time_ns() - self.__hitOn
        self.__hitOn   =  time.time_ns()
        self.__avgHits += 1

        if  _since <= (ONE_NS_SEC * 60):    # NOTE: Less than 1 minute
            self.__avgSpan = ((self.__avgSpan * self.__avgHits) + _since) / (self.__avgHits + 1)
            self.__avgHits += 1

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.__data)} ,maxsize={self.__maxsize} ,currsize={self.__currsize}))"

    def __getitem__(self, key):
        try:
            self.__lookups  += 1    # McCache
            return self.__data[key]
        except KeyError:
            return self.__missing__(key)

    def __setitem__(self, key, value, multicast = True):    # noqa: RUF100 FBT002  McCache
        maxsize = self.__maxsize
        size = self.getsizeof(value)
        if size > maxsize:
            raise ValueError("value too large")
        if key not in self.__data or self.__size[key] < size:
            while self.__currsize + size > maxsize:
                self.popitem()
        if key in self.__data:
            diffsize = size - self.__size[key]
        else:
            diffsize = size
        self.__data[key] = value
        self.__size[key] = size
        self.__currsize += diffsize

        # McCache addition.
        if  multicast:
            # TODO: Reconcile the format with the format that is send out.
            _mcQueue.put((OpCode.UPD ,time.time_ns() ,self.name ,key ,value))
            self.__setload__( is_update=True )

    def __delitem__(self, key, multicast = True):   # noqa: RUF100 FBT002  McCache
        size = self.__size.pop(key)
        del self.__data[key]
        self.__currsize -= size

        # McCache addition.
        if  multicast:
            # TODO: Reconcile the format with the format that is send out.
            _mcQueue.put((OpCode.DEL ,time.time_ns() ,self.name ,key ,None))
            self.__setload__( is_update=False )

    def __contains__(self, key):
        return key in self.__data

    def __missing__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(self.__data)

    def __len__(self):
        return len(self.__data)

    def get(self, key, default=None):
        if key in self:
            return self[key]
        else:
            return default

    def pop(self, key, default=__marker):
        if key in self:
            value = self[key]
            del self[key]
        elif default is self.__marker:
            raise KeyError(key)
        else:
            value = default
        return value

    def setdefault(self, key, default=None):
        if key in self:
            value = self[key]
        else:
            self[key] = value = default
        return value

    @property
    def maxsize(self):
        """The maximum size of the cache."""
        return self.__maxsize

    @property
    def currsize(self):
        """The current size of the cache."""
        return self.__currsize

    @staticmethod
    def getsizeof(value):   # noqa: ARG004
        """Return the size of a cache element's value."""
        return 1

    # McCache addition.
    def setname(self, name):
        """Set name of the cache."""
        self.__name = name

    @property
    def name(self) -> str:
        """The name of the cache."""
        return self.__name

    @property
    def hiton(self) -> int:
        """Last time the cache was hit."""
        return self.__hitOn

    @property
    def lookups(self) -> int:
        """The number of lookups count."""
        return self.__lookups

    @property
    def updates(self) -> int:
        """The number of insert/updates count."""
        return self.__updates

    @property
    def deletes(self) -> int:
        """The number of deletes count."""
        return self.__deletes

    @property
    def avghits(self) -> int:
        """The average hits of the cache."""
        return self.__avgHits

    @property
    def avgspan(self) -> int:
        """The average span since last hit of the cache."""
        return self.__avgSpan


class FIFOCache(Cache):
    """First In First Out (FIFO) cache implementation."""

    def __init__(self, maxsize, getsizeof=None):
        Cache.__init__(self, maxsize, getsizeof)
        self.__order = collections.OrderedDict()

    def __setitem__(self, key, value, multicast = True):    # noqa: RUF100 FBT002  McCache
        super().__setitem__(self, key, value, multicast)
        try:
            self.__order.move_to_end(key)
        except KeyError:
            self.__order[key] = None

    def __delitem__(self, key, multicast = True):  # noqa: RUF100 FBT002  McCache
        super().__delitem__(self, key, multicast)
        del self.__order[key]

    def popitem(self):
        """Remove and return the `(key, value)` pair first inserted."""
        try:
            key = next(iter(self.__order))
        except StopIteration:
            raise KeyError("%s is empty" % type(self).__name__) from None
        else:
            return (key, self.pop(key))


class LFUCache(Cache):
    """Least Frequently Used (LFU) cache implementation."""

    def __init__(self, maxsize, getsizeof=None):
        Cache.__init__(self, maxsize, getsizeof)
        self.__counter = collections.Counter()

    def __getitem__(self, key, cache_getitem=Cache.__getitem__):
        value = cache_getitem(self, key)
        if key in self:  # __missing__ may not store item
            self.__counter[key] -= 1
        return value

    def __setitem__(self, key, value, multicast = True):    # noqa: RUF100 FBT002  McCache
        super().__setitem__(self, key, value, multicast)
        self.__counter[key] -= 1

    def __delitem__(self, key, multicast = True):   # noqa: RUF100 FBT002  McCache
        super().__delitem__(self, key, multicast)
        del self.__counter[key]

    def popitem(self):
        """Remove and return the `(key, value)` pair least frequently used."""
        try:
            ((key, _),) = self.__counter.most_common(1)
        except ValueError:
            raise KeyError("%s is empty" % type(self).__name__) from None
        else:
            return (key, self.pop(key))


class LRUCache(Cache):
    """Least Recently Used (LRU) cache implementation."""

    def __init__(self, maxsize, getsizeof=None):
        Cache.__init__(self, maxsize, getsizeof)
        self.__order = collections.OrderedDict()

    def __getitem__(self, key, cache_getitem=Cache.__getitem__):
        value = cache_getitem(self, key)
        if key in self:  # __missing__ may not store item
            self.__update(key)
        return value

    def __setitem__(self, key, value, multicast = True):    # noqa: RUF100 FBT002  McCache
        super().__setitem__( key ,value ,multicast )
        self.__update(key)

    def __delitem__(self, key, multicast = True):   # noqa: RUF100 FBT002  McCache
        super().__delitem__(key, multicast)
        del self.__order[key]

    def popitem(self):
        """Remove and return the `(key, value)` pair least recently used."""
        try:
            key = next(iter(self.__order))
        except StopIteration:
            raise KeyError("%s is empty" % type(self).__name__) from None
        else:
            return (key, self.pop(key))

    def __update(self, key):
        try:
            self.__order.move_to_end(key)
        except KeyError:
            self.__order[key] = None


class MRUCache(Cache):
    """Most Recently Used (MRU) cache implementation."""

    def __init__(self, maxsize, getsizeof=None):
        Cache.__init__(self, maxsize, getsizeof)
        self.__order = collections.OrderedDict()

    def __getitem__(self, key, cache_getitem=Cache.__getitem__):
        value = cache_getitem(self, key)
        if key in self:  # __missing__ may not store item
            self.__update(key)
        return value

    def __setitem__(self, key, value, multicast = True):    # noqa: RUF100 FBT002  McCache
        super().__setitem__(self, key, value, multicast)
        self.__update(key)

    def __delitem__(self, key, multicast = True):   # noqa: RUF100 FBT002  McCache
        super().__delitem__(self, key, multicast)
        del self.__order[key]

    def popitem(self):
        """Remove and return the `(key, value)` pair most recently used."""
        try:
            key = next(iter(self.__order))
        except StopIteration:
            raise KeyError("%s is empty" % type(self).__name__) from None
        else:
            return (key, self.pop(key))

    def __update(self, key):
        try:
            self.__order.move_to_end(key, last=False)
        except KeyError:
            self.__order[key] = None


class RRCache(Cache):
    """Random Replacement (RR) cache implementation."""

    def __init__(self, maxsize, choice=random.choice, getsizeof=None):
        Cache.__init__(self, maxsize, getsizeof)
        self.__choice = choice

    @property
    def choice(self):
        """The `choice` function used by the cache."""
        return self.__choice

    def popitem(self):
        """Remove and return a random `(key, value)` pair."""
        try:
            key = self.__choice(list(self))
        except IndexError:
            raise KeyError("%s is empty" % type(self).__name__) from None
        else:
            return (key, self.pop(key))


class _TimedCache(Cache):
    """Base class for time aware cache implementations."""

    class _Timer:
        def __init__(self, timer):
            self.__timer = timer
            self.__nesting = 0

        def __call__(self):
            if self.__nesting == 0:
                return self.__timer()
            else:
                return self.__time

        def __enter__(self):
            if self.__nesting == 0:
                self.__time = time = self.__timer()
            else:
                time = self.__time
            self.__nesting += 1
            return time

        def __exit__(self, *exc):
            self.__nesting -= 1

        def __reduce__(self):
            return _TimedCache._Timer, (self.__timer,)

        def __getattr__(self, name):
            return getattr(self.__timer, name)

    def __init__(self, maxsize, timer=time.monotonic, getsizeof=None):
        Cache.__init__(self, maxsize, getsizeof)
        self.__timer = _TimedCache._Timer(timer)

    def __repr__(self, cache_repr=Cache.__repr__):
        with self.__timer as time:
            self.expire(time)
            return cache_repr(self)

    def __len__(self, cache_len=Cache.__len__):
        with self.__timer as time:
            self.expire(time)
            return cache_len(self)

    @property
    def currsize(self):
        with self.__timer as time:
            self.expire(time)
            return super().currsize

    @property
    def timer(self):
        """The timer function used by the cache."""
        return self.__timer

    def clear(self):
        with self.__timer as time:
            self.expire(time)
            Cache.clear(self)

    def get(self, *args, **kwargs):
        with self.__timer:
            return Cache.get(self, *args, **kwargs)

    def pop(self, *args, **kwargs):
        with self.__timer:
            return Cache.pop(self, *args, **kwargs)

    def setdefault(self, *args, **kwargs):
        with self.__timer:
            return Cache.setdefault(self, *args, **kwargs)


class TTLCache(_TimedCache):
    """LRU Cache implementation with per-item time-to-live (TTL) value."""

    class _Link:

        __slots__ = ("key", "expires", "next", "prev")

        def __init__(self, key=None, expires=None):
            self.key = key
            self.expires = expires

        def __reduce__(self):
            return TTLCache._Link, (self.key, self.expires)

        def unlink(self):
            next = self.next    # noqa: A001 RUF100
            prev = self.prev
            prev.next = next    # noqa: A001 RUF100
            next.prev = prev

    def __init__(self, maxsize, ttl, timer=time.monotonic, getsizeof=None):
        _TimedCache.__init__(self, maxsize, timer, getsizeof)
        self.__root = root = TTLCache._Link()
        root.prev = root.next = root
        self.__links = collections.OrderedDict()
        self.__ttl = ttl

    def __contains__(self, key):
        try:
            link = self.__links[key]  # no reordering
        except KeyError:
            return False
        else:
            return self.timer() < link.expires

    def __getitem__(self, key, cache_getitem=Cache.__getitem__):
        try:
            link = self.__getlink(key)
        except KeyError:
            expired = False
        else:
            expired = not (self.timer() < link.expires)
        if expired:
            return self.__missing__(key)
        else:
            return cache_getitem(self, key)

    def __setitem__(self, key, value, multicast = True):    # noqa: RUF100 FBT002  McCache
        with self.timer as time:
            self.expire(time)
            super().__setitem__(self, key, value, multicast)
        try:
            link = self.__getlink(key)
        except KeyError:
            self.__links[key] = link = TTLCache._Link(key)
        else:
            link.unlink()
        link.expires = time + self.__ttl
        link.next = root = self.__root
        link.prev = prev = root.prev
        prev.next = root.prev = link

    def __delitem__(self, key, multicast = True):  # noqa: RUF100 FBT002  McCache
        super().__delitem__(self, key, multicast)
        link = self.__links.pop(key)
        link.unlink()
        if not (self.timer() < link.expires):
            raise KeyError(key)

    def __iter__(self):
        root = self.__root
        curr = root.next
        while curr is not root:
            # "freeze" time for iterator access
            with self.timer as time:
                if time < curr.expires:
                    yield curr.key
            curr = curr.next

    def __setstate__(self, state):
        self.__dict__.update(state)
        root = self.__root
        root.prev = root.next = root
        for link in sorted(self.__links.values(), key=lambda obj: obj.expires):
            link.next = root
            link.prev = prev = root.prev
            prev.next = root.prev = link
        self.expire(self.timer())

    @property
    def ttl(self):
        """The time-to-live value of the cache's items."""
        return self.__ttl

    def expire(self, time=None):
        """Remove expired items from the cache."""
        if time is None:
            time = self.timer()
        root = self.__root
        curr = root.next
        links = self.__links
        cache_delitem = Cache.__delitem__
        while curr is not root and not (time < curr.expires):
            cache_delitem(self, curr.key)
            del links[curr.key]
            next = curr.next    # noqa: A001
            curr.unlink()
            curr = next

    def popitem(self):
        """Remove and return the `(key, value)` pair least recently used that
        has not already expired.

        """
        with self.timer as time:
            self.expire(time)
            try:
                key = next(iter(self.__links))
            except StopIteration:
                raise KeyError("%s is empty" % type(self).__name__) from None
            else:
                return (key, self.pop(key))

    def __getlink(self, key):
        value = self.__links[key]
        self.__links.move_to_end(key)
        return value


class TLRUCache(_TimedCache):
    """Time aware Least Recently Used (TLRU) cache implementation."""

    @functools.total_ordering
    class _Item:

        __slots__ = ("key", "expires", "removed")

        def __init__(self, key=None, expires=None):
            self.key = key
            self.expires = expires
            self.removed = False

        def __lt__(self, other):
            return self.expires < other.expires

    def __init__(self, maxsize, ttu, timer=time.monotonic, getsizeof=None):
        _TimedCache.__init__(self, maxsize, timer, getsizeof)
        self.__items = collections.OrderedDict()
        self.__order = []
        self.__ttu = ttu

    def __contains__(self, key):
        try:
            item = self.__items[key]  # no reordering
        except KeyError:
            return False
        else:
            return self.timer() < item.expires

    def __getitem__(self, key, cache_getitem=Cache.__getitem__):
        try:
            item = self.__getitem(key)
        except KeyError:
            expired = False
        else:
            expired = not (self.timer() < item.expires)
        if expired:
            return self.__missing__(key)
        else:
            return cache_getitem(self, key)

    def __setitem__(self, key, value, multicast = True):   # noqa: RUF100 FBT002  McCache
        with self.timer as time:
            expires = self.__ttu(key, value, time)
            if not (time < expires):
                return  # skip expired items
            self.expire(time)
            super().__setitem__(self, key, value, multicast)    # McCache
        # removing an existing item would break the heap structure, so
        # only mark it as removed for now
        try:
            self.__getitem(key).removed = True
        except KeyError:
            pass
        self.__items[key] = item = TLRUCache._Item(key, expires)
        heapq.heappush(self.__order, item)

    def __delitem__(self, key, multicast = True):  # noqa: RUF100 FBT002  McCache
        with self.timer as time:
            # no self.expire() for performance reasons, e.g. self.clear() [#67]
            super().__delitem__(self, key, multicast)   # McCache
        item = self.__items.pop(key)
        item.removed = True
        if not (time < item.expires):
            raise KeyError(key)

    def __iter__(self):
        for curr in self.__order:
            # "freeze" time for iterator access
            with self.timer as time:
                if time < curr.expires and not curr.removed:
                    yield curr.key

    @property
    def ttu(self):
        """The local time-to-use function used by the cache."""
        return self.__ttu

    def expire(self, time=None):
        """Remove expired items from the cache."""
        if time is None:
            time = self.timer()
        items = self.__items
        order = self.__order
        # clean up the heap if too many items are marked as removed
        if len(order) > len(items) * 2:
            self.__order = order = [item for item in order if not item.removed]
            heapq.heapify(order)
        cache_delitem = Cache.__delitem__
        while order and (order[0].removed or not (time < order[0].expires)):
            item = heapq.heappop(order)
            if not item.removed:
                cache_delitem(self, item.key)
                del items[item.key]

    def popitem(self):
        """Remove and return the `(key, value)` pair least recently used that
        has not already expired.

        """
        with self.timer as time:
            self.expire(time)
            try:
                key = next(iter(self.__items))
            except StopIteration:
                raise KeyError("%s is empty" % self.__class__.__name__) from None
            else:
                return (key, self.pop(key))

    def __getitem(self, key):
        value = self.__items[key]
        self.__items.move_to_end(key)
        return value
# fmt: on


# McCache Section.

ONE_MIB     = 1_048_576             # 1 Mib
ONE_NS_SEC  = 10_000_000_000        # One Nano second.
MAGIC_BYTE  = 0b11111001            # 241 (Pattern + Version)
HEADER_SIZE = 16                    # The fixed length header for each fragment packet.
SEASON_TIME = 0.6                   # Seasoning time (seconds) to wait before considering a retry.
HUNDRED     = 100                   # Hundred percent.
UINT2       = 65535                 # Unsigned 2 bytes.

class EnableMultiCast(Enum):
    YES = True      # Multicast out the change.
    NO  = False     # Do not multicast out the change.  This is the default.


class SocketWorker(Enum):
    SENDER = True   # The sender of a message.
    LISTEN = False  # The listener for messages.


class McCacheOption(StrEnum):
    # Constants for linter to catch typos instead of at runtime.
    # TODO: Drop the TTL feature.
    MCCACHE_CACHE_TTL       = 'MCCACHE_CACHE_TTL'
    MCCACHE_CACHE_SIZE      = 'MCCACHE_CACHE_SIZE'
    MCCACHE_CACHE_SYNC      = 'MCCACHE_CACHE_SYNC'
    MCCACHE_PACKET_MTU      = 'MCCACHE_PACKET_MTU'
    MCCACHE_MULTICAST_IP    = 'MCCACHE_MULTICAST_IP'
    MCCACHE_MULTICAST_PORT  = 'MCCACHE_MULTICAST_PORT'
    MCCACHE_MULTICAST_HOPS  = 'MCCACHE_MULTICAST_HOPS'
    MCCACHE_MONKEY_TANTRUM  = 'MCCACHE_MONKEY_TANTRUM'
    MCCACHE_DEAMON_SLEEP    = 'MCCACHE_DEAMON_SLEEP'
    MCCACHE_RANDOM_SEED     = 'MCCACHE_RANDOM_SEED'
    MCCACHE_DEBUG_LOGFILE   = 'MCCACHE_DEBUG_LOGFILE'
    MCCACHE_LOG_FORMAT      = 'MCCACHE_LOG_FORMAT'

    def __repr__(self):
        return self.value

    def __str__(self):
        return str(self.value)


class OpCode(StrEnum):
    # Keep everything here as 3 character fixed length strings.
    ACK = 'ACK'     # Acknowledgement of a received message.
    BYE = 'BYE'     # Member announcing it is leaving the group.
    DEL = 'DEL'     # Member requesting the group to evict the cache entry.
    ERR = 'ERR'     # Member announcing an error to the group.
    FYI = 'FYI'     # Member communicating information.
    INQ = 'INQ'     # Member inquiring about a cache entry from the group.
    MET = 'MET'     # Member inquiring about the cache metrics metrics from the group.
    NEW = 'NEW'     # New member annoucement to join the group.
    NAK = 'NAK'     # Negative acknowledgement.  Didn't receive the key/value.
    NOP = 'NOP'     # No operation.
    RAK = 'RAK'     # Request acknowledgment for a message.
    REQ = 'REQ'     # Member requesting resend message fragment.
    RST = 'RST'     # Member requesting reset of the cache.
    UPD = 'UPD'     # Update an existing cache entry (Insert/Updatre).

    def __repr__(self):
        return self.value

    def __str__(self):
        return str(self.value)


@dataclass
class McCacheConfig:
    cache_ttl: int = 900            # Total Time to Live in seconds for a cached entry.
    cache_size: int = 512           # Max entries.
    cache_sync: str = 'FULL'        # Cache coherence syncing level. [Full ,Part]
    packet_mtu: int = 1472          # Maximum Transmission Unit of your network packet payload.  Ethernet frame is 1500 minus header.
                                    # SEE: https://www.youtube.com/watch?v=Od5SEHEZnVU and https://www.youtube.com/watch?v=GjiDmU6cqyA
    multicast_ip: str = '224.0.0.3' # Unassigned multi-cast IP.
    multicast_port: int = 4000      # Unofficial port.  Was for Diablo II game.
    multicast_hops: int = 1         # Only local subnet.
    monkey_tantrum: int = 0         # Chaos monkey tantrum % level (0 - 99).
    deamon_sleep: int = SEASON_TIME # House keeping snooze seconds (0.33 - 3.0).
    random_seed: int = int(str(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET )[0][4][0]).split(".")[3])
    debug_logfile: str = 'log/debug.log'
    log_format: str = f"%(asctime)s.%(msecs)03d (%(ipV4)s.%(process)d.%(thread)05d)[%(levelname)s {__app__}@%(lineno)d] %(message)s"

# Module initialization.
#
_lock = threading.RLock()           # Module-level lock for serializing access to shared data.
_mySelf:    dict[str]               # All my IP address.
_mcConfig:  McCacheConfig()         # Private McCache configuration.
_mcCache:   dict[str   ,dict] = {}  # Private dictionary to segregate the cache namespace.
_mcArrived: dict[tuple ,dict] = {}  # Private dictionary to manage arriving fragments to be assemble into a value message.
_mcPending: dict[tuple ,dict] = {}  # Private dictionary to manage send fragment needing acknowledgements.
_mcMember:  dict[str   ,int]  = {}  # Private dictionary to manage members in the group.  IP: Timestamp.
_mcQueue:   queue.Queue = queue.Queue()

# Setup normal and short IP addresses for logging and other use.
_mySelf = { me[4][0] for me in socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET ) }

LOG_EXTRA: dict   = {'ipv4': None ,'ipV4': None ,'ipv6': None ,'ipV6': None }    # Extra fields for the logger message.
LOG_EXTRA['ipv4'] = sorted(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET ))[0][4][0]
LOG_EXTRA['ipV4'] = ''.join([hex(int(g)).removeprefix("0x").zfill(2) for g in LOG_EXTRA['ipv4'].split(".")])
try:
    LOG_EXTRA['ipv6'] = socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET6)[0][4][0]
    LOG_EXTRA['ipV6'] = LOG_EXTRA['ipv6'].replace(':' ,'')
except socket.gaierror:
    pass
LOG_FORMAT: str = McCacheConfig.log_format
SRC_IP_ADD: str = f"{LOG_EXTRA['ipv4']}:{os.getpid()}"   # Source IP address.
FRM_IP_PAD: str = ' '*len(LOG_EXTRA['ipv4'])
logger: logging.Logger = logging.getLogger()    # Root logger.


# Public methods.
#
def get_cache( name: str | None = None ,cache: Cache | None = None ) -> Cache:
    """
    Return a cache with the specified name ,creating it if necessary.
    If no name is specified ,return the default TLRUCache or LRUCache cache depending on the optimism setting.
    SEE: https://dropbox.tech/infrastructure/caching-in-theory-and-practice

    Args:
        name:   Name to isolate different caches.  Namespace dot notation is suggested.
        cache:  Optional cache instance to override the default cache type.
    Return:
        Cache instance to use with given name.
    """
    if  name:
        if  not isinstance( name ,str ):
            raise TypeError('The cache name must be a string!')
    else:
        name = 'default'
    if  cache:
        if  not isinstance( cache ,Cache ):
            raise TypeError(f"Cache name '{name}' is not of type McCache.Cache!")   # noqa: EM102
    try:
        _lock.acquire()
        if  name in _mcCache:
            cache = _mcCache[ name ]

        if  not cache:
#           cache = TTLCache( maxsize=_mcConfig.cache_size ,ttl=_mcConfig.cache_ttl )
            cache = LRUCache( maxsize=_mcConfig.cache_size )
            _mcCache[ name ] = cache

        if  not cache.name:
            cache.setname( name )
    finally:
        _lock.release()

    return cache

def clear_cache( name: str | None = None ) -> None:
    """Clear all the distributed caches.

    Request all the members in the cluster to clear their cache without rebooting their instance.
    This method is intended to be used from a node that is not participating in the cluster.

    Args:
        name:   Name of the cache.  If none is provided, all caches shall be cleared.
    Return:
        None
    """
    _mcQueue.put((OpCode.RST ,time.time_ns() ,name ,None ,None))

def get_cluster_metrics( name: str | None = None ) -> None:
    """Inquire the metrics for all the distributed caches.
    """
    _mcQueue.put((OpCode.MET ,time.time_ns() ,name ,None ,None))

def get_cache_checksum( name: str | None = None ,key: str | None = None ) -> None:
    """Inquire the checksum for all the distributed caches.
    """
    _mcQueue.put((OpCode.INQ ,time.time_ns() ,name ,key ,None))

# Public utility methods.
#
def checksum(val: bytes) -> str:
    """Generate a checksum for the input value.

    The checksum can be displayed as a representation of the raw value.
    One should not display the raw value for it may be a security violation.

    Args:
        val:    Input bytes to create a checksum for.
    Return:
        A checksum string in encoded in base64.
    """
    pkl: bytes  = pickle.dumps( val )
    crc: str    = base64.b64encode( hashlib.md5( pkl ).digest() ).decode()  # noqa: S324

    # NOTE: 'None' value for base64.b64encode() is 'fR5VZQAU4htFaO0+PR/FMQ=='
    return  crc

# Private utilities methods.
#
def _is_valid_multicast_ip( ip: str ) -> bool:
    """Validate the inputis a valid multicast ip address.

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

def _load_config():
    """Load the McCache configuration.

    Configuration will loaded in the following order over writting the prevously set values.
    1) `pyproject.toml`
    2) Environment variables.

    Data type validation is performed.

    Args:
    Return:
        Dataclass   A new configuration.
    """
    tmlcfg = {}
    config = McCacheConfig()
    config.random_seed = int(str(socket.getaddrinfo(socket.gethostname() ,0 ,socket.AF_INET )[0][4][0]).split(".")[3])

    try:
        import tomllib  # Introduced in Python 3.11.
        with open("pyproject.toml" ,encoding="utf-8") as fp:
            tmlcfg = tomllib.loads( fp.read() )
    except  ModuleNotFoundError:
        pass

    fldtyp = { f.name: f.type for f in fields( config )}
    for envar in McCacheOption:
        cfvar = str( envar ).replace('MCCACHE_' ,'').lower()

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
            if   fldtyp[ cfvar ] is int   and     str(os.environ[ envar ]).isnumeric():
                setattr( config ,cfvar           ,int(os.environ[ envar ]))
            elif fldtyp[ cfvar ] is float and not str(os.environ[ envar ]).isnumeric() and str(os.environ[ envar ]).replace('.' ,'').isnumeric():
                setattr( config ,cfvar         ,float(os.environ[ envar ]))
            if   fldtyp[ cfvar ] is int   and     str(os.environ[ envar ]).isnumeric():
                setattr( config ,cfvar           ,int(os.environ[ envar ]))
            elif fldtyp[ cfvar ] is float and not str(os.environ[ envar ]).isnumeric() and str(os.environ[ envar ]).replace('.' ,'').isnumeric():
                setattr( config ,cfvar         ,float(os.environ[ envar ]))
            else:
                setattr( config ,cfvar           ,str(os.environ[ envar ]))
                setattr( config ,cfvar           ,str(os.environ[ envar ]))

        if  cfvar == 'cache_sync':
            config.cache_sync = str(config.cache_sync).upper()

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
    """Setup the McCache specifc logger.

    Args:
    Return:
        A logger specific to the module.
    """
    logger: logging.Logger = logging.getLogger('mccache')   # McCache specific logger.
    logger.propagate = False
    logger.handlers.clear() # This is strictly a McCache logger.

    if 'TERM' in os.environ or ('SESSIONNAME' in os.environ and os.environ['SESSIONNAME'] == 'Console'):
        hdlr = logging.StreamHandler()
        fmtr = logging.Formatter(fmt=LOG_FORMAT ,datefmt='%Y%m%d%a %H%M%S' ,defaults=LOG_EXTRA)
        hdlr.setFormatter( fmtr )
        logger.addHandler( hdlr )
        logger.setLevel( logging.INFO )
    if  debug_log:
        hdlr = RotatingFileHandler( debug_log ,mode="a" ,maxBytes=(2*1024*1024*1024), backupCount=99)   # 2Gib with 99 backups.
        hdlr.setFormatter( fmtr )
        logger.addHandler( hdlr )
        logger.setLevel( logging.DEBUG )
    # TODO: Make it cloud ready for AWS ,Azure ,GPC ,OCI.

    return logger

def _log_debug_msg( opc: str,
                    tsm: int    | None = None,
                    nms: str    | None = None,
                    key: object | None = None,
                    crc: str    | None = None,
                    val: object | None = None,
                    frm: str    | None = None ) -> None:
    """A standardize the format to log out McCache DEBUG messages.

    The standardized format makes parsing them easier.

    Args:
        opc: str    The operation code.
        tsm: int    Optional timestamp in nano seconds.
        nms: str    Optional cache namespace.
        key: object Optional key object.
        crc: str    Optional checksum for the value.
        val: object Optional value object.
        frm: str    Optional sender.
    Return:
        None
    """
    msg = (opc ,tsm ,nms ,key ,crc ,val)
    logger.debug(f"Im:{SRC_IP_ADD}\tFr:{frm}\tMsg:{msg}" ,extra=LOG_EXTRA)

def _get_size( obj: object, seen: set | None = None ):
    """Recursively finds size of objects.

    Credit goes to:
    https://goshippo.com/blog/measure-real-size-any-python-object

    Args:
        seen:   A collection of seen objets.
    Return:
    """
    size = sys.getsizeof( obj )
    if  seen is None:
        seen =  set()
    obj_id = id( obj )
    if  obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add( obj_id )
    if  isinstance( obj ,dict ):
        size += sum([_get_size( v ,seen ) for v in obj.values()])
        size += sum([_get_size( k ,seen ) for k in obj.keys()])
    elif hasattr( obj ,'__dict__' ):
        size += _get_size( obj.__dict__ ,seen )
    elif hasattr( obj ,'__iter__' ) and not isinstance( obj ,str | bytes | bytearray ):
        size += sum([_get_size( i ,seen ) for i in obj])
    return size

def _get_cache_metrics( name: str | None = None ) -> dict:
    """Return the metrics collected for the entire cache.

        SEE: https://psutil.readthedocs.io/en/latest/
        SEE: https://github.com/McCache/McCache-for-Python/blob/main/docs/BENCHMARK.md

    Args:
        name:   The case sensitive name of the cache.
    Return:
        Dictionary of cache statistics.
    """
    prc: dict = {}
    gbl: dict = {}
    nms: dict = {}

    prc = { '_process_': {
                'avgload':      psutil.getloadavg(),    # NOTE: Simulated on window platform.
                'cputimes':     psutil.cpu_times(),
                'meminfo':      psutil.Process().memory_info(), # Memory info for current process.
                'netioinfo':    psutil.net_io_counters()
            }
        }   # Process stats.
    nms =   {n: {   'count':    len( _mcCache[ n ]),
                    'size':     round(_get_size(_mcCache[ n ])        / ONE_MIB    ,4),
                    'avgspan':  round(          _mcCache[ n ].avgspan / ONE_NS_SEC ,4),
                    'avghits':  _mcCache[ n ].avghits,
                    'lookups':  _mcCache[ n ].lookups,
                    'updates':  _mcCache[ n ].updates,
                    'deletes':  _mcCache[ n ].deletes,
                }
                for n in _mcCache.keys() if n == name or name is None
        }   # Namespace stats.
    if  not name:
        gbl = { '_mccache_': {
                    'count':    len( _mcCache),
                    'size':     round(_get_size(_mcCache  ) / ONE_MIB ,4),
                    'avgspan':  round(    mean([_mcCache[ n ].avgspan for n in _mcCache.keys()]) / ONE_NS_SEC ,4),
                    'avghits':  sum([_mcCache[ n ].avghits for n in _mcCache.keys()]),
                    'lookups':  sum([_mcCache[ n ].lookups for n in _mcCache.keys()]),
                    'updates':  sum([_mcCache[ n ].updates for n in _mcCache.keys()]),
                    'deletes':  sum([_mcCache[ n ].deletes for n in _mcCache.keys()]),
                },
            }   # Global stats.

    return prc | gbl | nms  # Python v3.9 way to merge multiple dictionaries.

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
    # IP_ADD_MEMBERSHIP: This tells the system to receive packets on the network whose destination is the group address (but not its own)

    addrinfo = socket.getaddrinfo( _mcConfig.multicast_ip ,None )[0]
    sock = socket.socket( addrinfo[0] ,socket.SOCK_DGRAM )
    if  is_sender.value:
        # Set Time-to-live (optional)
        ttl_bin = struct.pack('@I' ,_mcConfig.multicast_hops)
        if  addrinfo[0] == socket.AF_INET:  # IPv4
            sock.setsockopt( socket.IPPROTO_IP   ,socket.IP_MULTICAST_TTL ,ttl_bin )
        else:
            sock.setsockopt( socket.IPPROTO_IPV6 ,socket.IPV6_MULTICAST_HOPS ,ttl_bin )
    else:
        sock.setsockopt( socket.SOL_SOCKET ,socket.SO_REUSEADDR ,1 )
        sock.bind(('' ,_mcConfig.multicast_port))    # It need empty string or it will throw an "The requested address is not valid in its context" exception.

        group_bin = socket.inet_pton( addrinfo[0] ,addrinfo[4][0] )
        # Join multicast group
        if  addrinfo[0] == socket.AF_INET:  # IPv4
            mreq = group_bin + struct.pack('@I' ,socket.INADDR_ANY )
            sock.setsockopt( socket.IPPROTO_IP  ,socket.IP_ADD_MEMBERSHIP ,mreq )
        else:
            mreq = group_bin + struct.pack('@I' ,0)
            sock.setsockopt( socket.IPPROTO_IPV6 ,socket.IPV6_JOIN_GROUP ,mreq )

    return  sock

def _make_pending_ack( key_t: tuple ,val_o: object ,members: dict ,frame_size: int ) -> dict:
    """Make a dictionary entry for the management of acknowledgements.

    The input key and value shall be concatenated into a single out going binary message.
    The size of the out going message can be larger than the Ethernet MTU.
    The outgoing message shall be chunk out into fragments to be send out upto 255 chunks.
    Each fragment has a preceeding fixed length header follow by fragment payload.

    Header:
        Magic:      5 bits +--  1 byte
        Version:    3 bits |
        Reserved:   1 byte      #   Reserved bitmap for future needs.
        Sequence:   1 byte      #   The zero based sequence number.
        Fragments:  1 byte      #   The total number of fragments for the outgoing message.
        Key Length: 2 bytes     #   The length of the serialized key tuple.
        Val Length: 2 bytes     #   The length of the serialized value tuple.
        Timestamp:  8 bytes     #   The initiaing timestamp in nano seconds from the input key tuple.

    Args:
        key:        Key tuple object made up of (namespace ,key ,timestamp).
        val:        Value object.
        member:     Set of members in the cluster.
        frame_size: The size of the usable Ethernet frame (minus the IP header).
    Return:
        A dictionary of the following structure:
        {
            'initon':  int          # The time of the original message was queued in nano seconds.
            'message': list(),      # Ordered list of fragments for re-send.
            'members': {
                ip: {
                    'unack': set(), # Set of unacknowledge fragments for the given IP key.
                    'tries': int,   # Count the number of retries.
                }
            }
        }
    Raise:
        BufferError:    When the serialized key or value size is greater than unsigned two bytes.
    """
    tsm: int = key_t[ 2 ]                   # 8 bytes unsigned nanoseconds for timestamp.
    key_b: bytes = pickle.dumps( key_t )    # Serialized the key.
    key_s: int = len( key_b )
    if  key_s > UINT2:   # 2 bytes unsigned.
        raise BufferError(f"Pickled key for {key_t} size is {key_s}") # noqa: EM102

    val_b: bytes = pickle.dumps( val_o )    # Serialized the message.
    val_s: int = len( val_b )
    if  val_s > UINT2:   # 2 bytes unsigned.
        raise BufferError(f"Pickled val for {key_t} size is {val_s}") # noqa: EM102

    bgn: int
    end: int
    hdr_b: bytes
    frg_b: bytes
    pay_b: bytes  = key_b + val_b  # Total binary payload to be send out.
    pay_s: int = len( pay_b )
    frg_m: int = frame_size - HEADER_SIZE # Max frame size.
    frg_c:int = int( pay_s / frg_m) +1

    ack = { 'initon':  tsm,
            'message': [None] * frg_c,  # Pre-allocated the list.
            'members': {
                ip: {'unack': { f } ,'tries': 3}
                    for ip in members.keys() for f in range(0 ,frg_c)
            }
        }

    for seq in range( 0 ,frg_c ):
        bgn  = seq * frg_m
        end  = bgn + frg_m if (bgn + frg_m) < pay_s else pay_s +1
        frg_b= pay_b[ bgn : end ] # A fragment of the message.

        # NOTE: 'HH' MUST come after 'BBBB' for it impact the length.
        hdr_b =  struct.pack('@BBBBHHQ' ,MAGIC_BYTE ,0 ,seq ,frg_c ,key_s ,val_s ,tsm)
        ack['message'][ seq ] = hdr_b + frg_b
    return  ack

def _collect_fragment( pkt_b: bytes ,sender: str ) -> bool:
    """Collect the arrived fragment to be later assembled back into an incoming key and value.

    The fragments are collected in the global `_mcArrived` dictionary of the following structure:
        {
            aky_t: {
                'initon': int,      # The time of the original message was queued in nano seconds.
                'message': list(),  # Ordered list of fragments for the message.
                'tries': int        # Number of retries left.  Default is 3.
            }
        }

    Args:
        pkt_b: bytes    The received/input binary packet.
        sender: str     The sender/originator for the binary packet.
    Return:
        tuple           The assembly key tuple if all fragments are received, else None
    """
    mgc:   int      # Packet magic byte.
    seq:   int      # Fragment sequence
    frg_c: int      # Fragment size/count.
    key_s: int      # Key size
    tsm:   int      # Timestamp
    hdr_b: bytes    # Packet header

    if  len( pkt_b ) <= HEADER_SIZE:
        logger.warn(f"Invalid packet header! Must be greater than {HEADER_SIZE}.")
        return  False

    hdr_b = pkt_b[ 0 : HEADER_SIZE ]
    mgc ,_ ,seq ,frg_c ,key_s ,_ ,tsm = struct.unpack('@BBBBHHQ' ,hdr_b)    # Unpack the packet

    if  mgc != MAGIC_BYTE:
        logger.warn(f"Received a foreign packet from {sender}.")
        return  False

    aky_t: tuple = (sender ,frg_c ,key_s ,tsm)    # Pending assembly key.
    if  aky_t not in _mcArrived:
        _mcArrived[ aky_t ] = { 'initon':  tsm,
                                'message': [None] * frg_c,  # Pre-allocated the list.
                                'tries': 3
                            }
    _mcArrived[ aky_t ]['message'][ seq ] = pkt_b

    return  aky_t if all([ f is not None for f in _mcArrived[ aky_t ]['message']]) else None  # noqa: C419

def _assemble_message( aky_t: tuple ) -> (tuple ,object):
    """Assemble the fragments back into the key and value tuple.

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
        _ ,_ ,_ ,_ ,key_s ,val_s ,_ = struct.unpack('@BBBBHHQ' ,hdr_b)    # Unpack the fragment header.

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
        val_o =  pickle.loads(bytes( val_b ))    # noqa: S301    De-Serialized the value.

    return  key_t ,val_o

def _send_fragment( sock:socket.socket ,fragment: bytes ) -> None:
    """Send a fragment out.

    The `MCCACHE_MONKEY_TANTRUM` configuration greater than zero will enable the simulation of dropped packets.

    Args:
        socket:     A configured socket to send a fragment out of.
        fragment:   A fragment of binary data.
    Return:
        None
    """
    # The following is to assist with testing.
    # This Monkey should NOT throw a tantrum in a production environment.
    #
    if _mcConfig.monkey_tantrum > 0 and _mcConfig.monkey_tantrum < HUNDRED:
        _trantrum = random.randint(1 ,100)  # noqa: S311    Between 1 and 99.
        if  _trantrum >= (50 - _mcConfig.monkey_tantrum/2) and \
            _trantrum <= (50 + _mcConfig.monkey_tantrum/2):
            msg = (OpCode.NOP.value ,None ,None ,None ,None ,'Monkey is angry!  NOT sending out packet.')
            logger.warning(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)
            return

    sock.sendto( fragment ,(_mcConfig.multicast_ip ,_mcConfig.multicast_port))

def _check_sent_pending() -> None:
    """Check the pending list for messages that have not been acknowledge.
    """
    bads = {}   # A bad list of unacknowledge packets to delete outside of the iteration.
    for pky_t in _mcPending.keys(): # pky_t = (nms ,key ,tsm)   # Key for this message pending acknowledgement.
        elps = (time.time_ns() - _mcPending[ pky_t ]['initon']) / ONE_NS_SEC

        if  elps > SEASON_TIME:     # At least 2/3 of a second old.
            for ip in _mcPending[ pky_t ]['members'].keys():
                if  _mcPending[ pky_t ]['members'][ ip ]['tries'] > 0:
                    # DEBUG:
                    if  _mcPending[ pky_t ]['members'][ ip ]['tries'] == 1: # Down to 1 last try.
                        msg = (OpCode.FYI ,None ,None ,None ,None ,f"{pky_t} need ack. {_mcPending[ pky_t ]}")
                        logger.debug(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

                    if  len(_mcPending[ pky_t ]['message']) == len(_mcPending[ pky_t ]['members'][ ip ]['unack']):
                        # Nothing was acknowledged.
                        # Format: ( OpCode ,Timestamp ,Namespace ,Key ,Value )
                        _mcQueue.put((OpCode.RAK ,pky_t[2] ,pky_t[0] ,pky_t[1] ,f"{ip}:"))   # Request ACK for the entire message from an IP.
                    else:
                        # Partially acknowledged.
                        s = len(_mcPending[ pky_t ]['message'] )
                        for f in range( 0 ,s ):
                            if  f in _mcPending[ pky_t ]['members'][ ip ]['unack']:
                                _mcQueue.put((OpCode.RAK ,pky_t[2] ,pky_t[0] ,pky_t[1] ,f"{ip}:{f}/{s}"))  # Request specific fragment ACK from an IP.
                elif  _mcPending[ pky_t ]['members'][ ip ]['tries'] < 0:
                    # NOTE: Wait for another cycle to let things settle.
                    if  pky_t not in bads:
                        bads[ pky_t ] = {'members': []}
                    if  ip  not in bads[ pky_t ]['members']:
                        bads[ pky_t ]['members'].append( ip )
                _mcPending[ pky_t ]['members'][ ip ]['tries'] -= 1

    # Delete away the unacknowledge packets.
    for pky_t in bads:
        for ip in bads[ pky_t ]['members']:
            del _mcPending[ pky_t ]['members'][ ip ]
            logger.error(f"Key:{pky_t} have NOT be acknowledge by {ip}" ,extra=LOG_EXTRA)

        if  len(_mcPending[ pky_t ]['members']) == 0:
            del _mcPending[ pky_t ]

def _check_recv_assembly() -> None:
    """Check the assembly list of fragments for a message.
    """
    bads = {}
    for aky_t in _mcArrived.keys(): # aky_t: tuple = (sender ,frg_c ,key_s ,tsm)
        elps = (time.time_ns() - _mcArrived[ aky_t ]['initon']) / ONE_NS_SEC

        if  elps > SEASON_TIME: # At least 2/3 of a second old.
            if  _mcArrived[ aky_t ]['tries'] > 0:
                for seq in range( 0 ,len(_mcArrived[ aky_t ]['message'])):
                    if  _mcArrived[ aky_t ]['message'][ seq ] is None:
                        _mcQueue.put((OpCode.REQ ,time.time_ns() ,aky_t[1] ,aky_t[0] ,f"{SRC_IP_ADD[0]}:{seq}"))
            elif  _mcArrived[ aky_t ]['tries'] < 0:
                # NOTE: Wait for another cycle to let things settle.
                if  aky_t not in bads:
                    bads[ aky_t ] = None
            _mcArrived[ aky_t ]['tries'] -= 1

    # Delete away the unassemble fragments.
    for aky_t in bads:
        try:
            lst: list = None
            _lock.acquire()
            lst = [ seq for seq in range( 0, len(_mcArrived[ aky_t ])) \
                        if  _mcArrived and aky_t in _mcArrived and seq in _mcArrived[ aky_t ] and _mcArrived[ aky_t ][ seq] is None
                ]
        finally:
            _lock.release()

        if  lst:
            logger.error(f"Key:{aky_t} message incomplete.  Missing fragments: {lst}" ,extra=LOG_EXTRA)
            del _mcArrived[ aky_t ]

def _decode_message( aky_t: tuple ,key_t: tuple ,val_o: object ,sender: str ) -> None:
    """Decode the message from the sender.

    A message is made up of key and value.

    Args:
        aky_t: tuple    Assembly key for incoming message.
        key_t: tuple    Message key.
        val_o: object   Message object.
        sender: str     The sender of this message.
    Return:
        None
    """
    pky: tuple  = key_t     # Pending key.
    nms: str    = key_t[0]  # Namespace
    key: object = key_t[1]  # Key
    tsm: int    = key_t[2]  # Timestamp
    opc: str    = val_o[0]  # Op Code
    crc: str    = val_o[1]  # Checksum
    val: object = val_o[2]  # Value
    mcc: object = get_cache( nms )

    match opc:
        case OpCode.ACK:    # Acknowledgment.
            if  pky in _mcPending:
                if  sender \
                    in  _mcPending[ pky ]['members']:
                    del _mcPending[ pky ]['members'][ sender ]

                    msg = (opc ,tsm ,nms ,None ,None ,f"{pky} is acknowledged by {sender}.")
                    logger.debug(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)
                else:
                    msg = (opc ,tsm ,nms ,None ,None ,f"{pky} is NOT expected from {sender}.")
                    logger.info(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

                if  len(_mcPending[ pky ]['members']) == 0:
                    del _mcPending[ pky ]

                    msg = (opc ,tsm ,nms ,None ,None ,f"{pky} is fully acknowledged.")
                    logger.debug(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)
            else:
                msg = (opc ,tsm ,nms ,None ,None ,f"{pky} NOT found for acknowledgment from {sender}.")
                logger.warn(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

        case OpCode.BYE:    # Goobye from member.
            if  sender in _mcMember:
                del _mcMember[ sender ]

        case OpCode.DEL:   # Delete.
            if  key in mcc:
                mcc.__delitem__( key ,EnableMultiCast.NO )
            # Acknowledge it.
            _mcQueue.put( (OpCode.ACK ,tsm ,nms ,key ,None))

        case OpCode.ERR:   # Error.
            pass    # TODO: How should we handle an error reported by the sender?

        case OpCode.INQ:    # Inquire.
            if  logger.level == logging.DEBUG:
                # NOTE: Don't dump the raw data out for security reason.
                _ks = [ key ] if key else sorted( mcc.keys() )
                _mc = {k: checksum( mcc[ k ]) for k in _ks}
                msg = (opc ,tsm ,nms ,None ,None ,_mc)
                logger.info(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

        case OpCode.MET:    # Metrics.
            if  logger.level == logging.DEBUG:
                _mc = _get_cache_metrics( nms )
                msg = (opc ,tsm ,nms ,None ,None ,_mc)
                logger.info(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

        case OpCode.NEW:    # New member.
            if  sender not in _mcMember:
                _mcMember[ sender ] = tsm   # Timestamp

        case OpCode.RAK:    # Re-Acknowledgement
            if  aky_t not in _mcArrived and key in mcc:
                _mcQueue.put((OpCode.ACK ,tsm ,nms ,key ,None))

        case OpCode.RST:    # Reset.
            for n in filter( lambda k: k == nms or nms is None ,_mcCache.keys() ):
                for k in _mcCache[ n ].keys():
                    _mcCache[ n ].__delitem__( k ,EnableMultiCast.NO )

        case OpCode.UPD:    # Insert and Update.
            if  key in mcc:
                mcc.__setitem__( key ,val ,EnableMultiCast.NO )
            # Acknowledge it.
            _mcQueue.put( (OpCode.ACK ,tsm ,nms ,key ,None))

        case _:
            pass

    if  logger.level == logging.DEBUG:
        msg = (opc ,tsm ,nms ,key ,crc ,None)
        logger.debug(f"Im:{SRC_IP_ADD}\tFr:{sender}\tMsg:{msg}" ,extra=LOG_EXTRA)

# Private thread methods.
#
def _goodbye() -> None:
    """Shutting down of this Python process.

    Inform all the members in the cluster that this node is leaving the group.
    Output the current metrics of this local cache.

    SEE: https://docs.python.org/3.8/library/atexit.html#module-atexit

    Args:
    Return:
        None
    """
    _mcQueue.put((OpCode.MET ,time.time_ns() ,None ,None ,None))
    _mcQueue.put((OpCode.BYE ,time.time_ns() ,None ,None ,None))
    time.sleep( 1 )

def _multicaster() -> None:
    """Dequeue and multicast out the cache operation to all the members in the group.

    A dequeued message is constructed using the following format:
        OP Code:    Cache operation code.  SEE: OpCode enum.
        Timestamp:  When this request was generated in Python's nano seconds.
        Namespace:  Namespace of the cache.
        Key:        The key in the cache.
        CRC:        Checksum of the value identified by the key.
        Value:      The cached value.

    A pending set of un-acknowledge messages (key/value) is kept until acknowledge.
    SEE: _make_pending_value() for the structure.

    Args:
    Return:
        None
    """
    sock: socket.socket = _get_socket( SocketWorker.SENDER )

    # Keep the format consistent to make it easy for the test to parse.
    msg = (OpCode.NEW ,None ,None ,None ,None ,'McCache broadcaster is ready.')
    logger.debug(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

    opc: str = ''   # Op Code
    while opc != OpCode.BYE:
        try:
            msg = _mcQueue.get()    # Dequeue the cache operation.
            opc         = msg[0]    # Op Code
            tsm: int    = msg[1]    # Timestamp
            nms: str    = msg[2]    # Namespace
            key: object = msg[3]    # Key
            val: object = msg[4]    # Value
            crc: str    = None      # Checksum

            # TODO: Reconcile the format with the format that is queued up.
            pky_t = (nms ,key ,tsm)   # Key for this message pending acknowledgement.
            match opc:
                case OpCode.REQ:    # Request retransmit of a single fragment.
                    # NOTE: The fragment number is communicated in the value formatted as FromIP:Index
                    #       fr_ip: str     Who requested a re-transmit?
                    #       frg_i: int     Which fragment is requested?
                    #
                    fr_ip: str =     val.split(':')[0]
                    frg_i: int = int(val.split(':')[1])
                    if  pky_t in _mcPending[ pky_t ] and frg_i in _mcPending[ pky_t ]['value']:
                        # Send an individual fragment out.
                        _send_fragment( sock ,_mcPending[ pky_t ]['value'][ frg_i ] )
                    else:
                        # Inform the requestor that we have an error on our side.
                        _mcQueue.put((OpCode.ERR ,pky_t[3] ,pky_t[0] ,pky_t[1] ,None))
                        logger.error(f"{fr_ip} requested fragment{frg_i:3} for {pky_t} doesn't exist!")

                case _:
                    crc = checksum( val )
                    if  logger.level == logging.DEBUG:
                        msg = (opc ,tsm ,nms ,key ,crc ,None)
                        logger.debug(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

                    if  opc == OpCode.MET:  # Metrics.
                        _mc = _get_cache_metrics( nms )
                        msg = (opc ,tsm ,nms ,None ,None ,_mc)
                        logger.info(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

                    frg: list
                    ack: dict = _make_pending_ack( pky_t ,(opc ,crc ,val) ,_mcMember ,_mcConfig.packet_mtu )
                    if  opc in {OpCode.DEL ,OpCode.UPD}:
                        if  pky_t not in _mcPending:
                            # Acknowledgement is needed for Insert ,Update and Delete.
                            _mcPending[ pky_t ] = ack
                        frg = _mcPending[ pky_t ]['message']
                    else:
                        # Acknowledgement is NOT needed for others.
                        frg = ack['message']

                    for frg_b in frg:
                        _send_fragment( sock ,frg_b )

        except  Exception as ex:    # noqa: BLE001
            logger.error( ex )

def _housekeeper() -> None:
    """Background house keeping thread.

    Request acknowledgment for messages that was send.
    Request resent missing fragments of a message.

    Args:
    Return:
        None
    """
    # Keep the format consistent to make it easy for the test to parse.
    msg = (OpCode.NEW ,None ,None ,None ,None ,'McCache housekeeper is ready.')
    logger.debug(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

    while True:
        time.sleep( _mcConfig.deamon_sleep )
        # Check sent messages that are pending acknowledgement.
        #
        _check_sent_pending()

        # Check receive fragments pending assembly into a message.
        #
        _check_recv_assembly()

def _listener() -> None:
    """Listen in the group for new cache operation from all members.

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
    sock: socket.socket = _get_socket( SocketWorker.LISTEN )

    # Keep the format consistent to make it easy for the test to parse.
    msg = (OpCode.NEW ,None ,None ,None ,None ,'McCache listener is ready.')
    logger.debug(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tMsg:{msg}" ,extra=LOG_EXTRA)

    while True:
        try:
            pkt_b ,sender = sock.recvfrom( _mcConfig.packet_mtu )
            fr_ip = sender[0]
            # Maintain the cluster membership.
            if  fr_ip not in _mcMember:
                _mcMember[ fr_ip ] = None

            # NOTE: Ignore our own messages and we have collected all the fragments for a message.
            if  fr_ip not in _mySelf:
                aky_t = _collect_fragment( pkt_b ,fr_ip )

                if  aky_t:
                    # All the fragments are received and is ready to be assembled back into a message.
                    key_t ,val_o = _assemble_message( aky_t )
                    if  key_t:
                        try:
                            _lock.acquire()
                            _decode_message( aky_t ,key_t ,val_o ,fr_ip )
                        finally:
                            _lock.release()
                        _mcMember[ fr_ip ] = key_t[ 2 ]   # Timestamp

                    # Update the member timestamp.
                    if  fr_ip in _mcMember:
                        _mcMember[ fr_ip ] = aky_t[3]   # aky_t = (sender ,frg_c ,key_s ,tsm)   # Pending assembly key.
        except  Exception as ex:    # noqa: BLE001
            logger.error( ex )


# Main Initialization Section.
#
logger: logging.Logger = logging.getLogger()    # Root logger.
_mcConfig = _load_config()
if  _mcConfig.log_format and _mcConfig.log_format != LOG_FORMAT:
    LOG_FORMAT = _mcConfig.log_format
logger = _get_mccache_logger(_mcConfig.debug_logfile)
logger.debug(f"Im:{SRC_IP_ADD}\tFr:{FRM_IP_PAD}\tCfg:{_mcConfig}" ,extra=LOG_EXTRA)

random.seed( _mcConfig.random_seed )

# Main section to start the background daemon threads.
#
atexit.register( _goodbye ) # SEE: https://docs.python.org/3.8/library/atexit.html#module-atexit

if  sys.platform == 'win32':
    psutil.getloadavg()     # Windows only simulate the load, so pre-warm it the background.

t1 = threading.Thread(target=_multicaster ,daemon=True ,name="McCache multicaster")
t1.start()
t2 = threading.Thread(target=_housekeeper ,daemon=True ,name="McCache housekeeper")
t2.start()
t3 = threading.Thread(target=_listener    ,daemon=True ,name="McCache listener")
t3.start()

if __name__ == "__main__":
    # ONLY used during development testing.
    # TODO: Get unit test working.
    import sys
    sys.path.append(__file__[:__file__.find('src')-1])
    sys.path.append(__file__[:__file__.find('src')+3])
    import tests.unit.start_mccache # noqa: F401 I001


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
# OR OTHER DEALINGS IN THE SOFTWARE.
