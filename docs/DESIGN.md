# Design
## Architecture Diagram
### Centralized implementation
A centralize caching architecture shall be a remote server providing the caching service.
![Centralized Architecture](Centralize%20Architecture.png)
* <sub>This diagram is generated at https://www.eraser.io/diagramgpt.  I am in need of some help in the art department</sub>.

### McCache implementation
`McCache` attempt to keep the cache in the other members in the cluster in sync with each other.
![McCache Architecture](McCache%20Architecture.png)
* <sub>This diagram is generated at https://www.eraser.io/diagramgpt.  I am in need of some help in the art department</sub>.

## Design Gist
`McCache` overwrite both the `__setitem__()` and `__delitem__()` dunder methods of `OrderedDict` to shim in the communication sub-layer to sync-up the other members' cache in the cluster.  All changes to the local cache are captured and queued up to be multicast out.  The cache in all nodes will eventually be consistent.

Four daemon threads are started when this package is initialized.  They are:
1. **Multicaster**. &nbsp;Whose job is to dequeue local change operation messages and multicast them out into the cluster.
2. **Listener**. &nbsp;Whose job is to listen for change operation messages multicast by other members in the cluster and immediately queue them up for processing.
3. **Processor**. &nbsp;Whose job is to process the incoming changes.
4. **Housekeeper**. &nbsp;Whose job is manage the acknowledgement of the messages.

UDP is unreliable.  We implemented a guaranteed message transfer protocol over UDP in `McCache`.
The nature of `McCache` is to broadcast out changes and this align well with multicast service offered by UDP and we selected it.  Furthermore, `McCache` prioritize operation that mutates the cache and only acknowledged these operations.  We did consider TCP but will have to implement management of peer-to-peer connection manager.

A message may be larger than the UDP payload size.  Regardless, we always chunk up the message into fragments plus a header that fully fit into the UDP payload.  Each UDP payload is made up of a fixed length header follow by a variable length message fragment.  The message is further broken up into the key and fragment section as depicted below:

Given the size of each field in the header, we have a limitation of a maximum 255 fragments per message.  The maximum size of your message shall be 255 multiple by the `packet_mtu` size set in the configuration.

The multicasting member will keep track of all the send fragments to all the member in the cluster.  Each member will re-assemble fragments back into a message.  Dropped fragment will be requested for a re-transmission.  Once each member have acknowledge receipt of all fragments, the message for that member is considered complete and be deleted from pending of acknowledgement.  Each member is always listening to traffic and maintaining its own members list.

Collision happens when two or more nodes make a change to a same key at nearly the same time.  The received message timestamp and checksum of the arriving object shall be compared to the local object timestamp and checksum.  If the local object is more current, based on the timestamp, the local object shall be send back to the original sender to be updated.

There are **no** remote locks.  Synchronization is implemented using a **monotonic** timestamp that is tagged to every cache entry.  This helps serialized the update operation on every node in the cluster.  An arrived change operation has a timestamp which will be compared to the timestamp of the local cache entry.  Only remote operation with the timestamp that is more recent shall be applied to local cache.

Furthermore, we are experimenting with a lockless design.  Locks are needed when the data is being mutated.  For read operation, the data is read without a lock applied to it.  If the entry doesn't exist the `keyError` exception is throw and be handled appropriately.  This is a very edge case and is the reason we decided on trapping the exception instead of locking the region of code.


## Concerns
* Multicast could saturate the network.  We don't think this is a big issue, with a future outlook, for the following reasons:
  1. Modern network do **not** run in a bus topology.  Bus topology is exposed to more packet collisions that requires backoff and retransmit.  Modern network uses a star topology implemented with high speed switches.  This hardware reduces packet collision and are virtually point-to-point connection between nodes in the cluster.
  2. Modern network can signal at a rate of **100** Gb, which is use for uplink aggregation.  Normal NIC rate is **10** Gb.  According to [this article](https://www.fmad.io/blog/what-is-10g-line-rate), the maximum theoretical limit to saturate a **10** Gb wire with **1500** byte packets is **820,209**.  If we reach this edge case in a spike, it will only for a very brief moment before the traffic volume ebbs away.

* Eventual consistent.  This is a tradeoff we made for a remote lockless implementation.  We address this issue as follows:
  1. With less network protocol overhead, messages arrive sooner to keep the cache fresh.
  2. Have inconsistency detection to evict the key/value from all caches.
  3. Cache **time-to-live** expiration will eventually flush the entire cache down to empty is an inactive environment.
  4. Sync heart beat to check for cache consistency.  In an edge case, a race condition could result in a new inconsistent just after a sync up but the latest entry should have been multicast out tho the members in cluster.

## Load balancer
* We recommend to use sticky session load balancer.
* <b>SEE</b>: <a href="https://www.youtube.com/watch?v=hTp4czOrvOY">Enabling Sticky Sessions</a>

## Limitation
* Even though the latency is low, it will **eventually** be consistent.  There is a very micro chance that an event can slip in just after the cache is read with the old value.  You have the option to pass in callback function to `McCache` for it to invoke if a change to the value of your cached object have changed within one second ago.  The other possibility is to perform a manual check.  The following is a code snippet that illustrate both approaches:

```python
import mcache as mc

def change(ctx: dict):
    """Callback method to be informed of changes to your local cache from a remote update.
    """
    print('Cache got change 1 second ago.  Context "ctx" have more details.')

c = mc.get_cache( callback=change )
c['k'] = False
time.sleep( 0.9 )
c['k'] = True   # The change() method will be invoked.

e = c.metadata['k']['lkp']
time.sleep( 10 )
if 'k' in c.metadata:
    a = c.metadata['k']['tsm']
    if  a > e:  # Actual is greater than expected.
        print('Cache got change since you previously read it.')
```

* The clocks in a distributed environment is never as accurate (due to clock drift) as we want it to be in a high update environment.  On a Local Area Network, the accuracy could go down to 1ms but 10ms is a safer assumption.  SEE: [NTP](https://timetoolsltd.com/ntp/ntp-timing-accuracy/) and [PTP](https://en.wikipedia.org/wiki/Precision_Time_Protocol)

* The maximum size of your message shall be **255** multiple by the `packet_mtu` size set in the configuration.  If your object to be cached span more than 255 fragments, it will be evicted from your local cache and the eviction shall be propagated to the rest of the members in the cluster.
