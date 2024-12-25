# McCache for Python<br><sub>This package is still under development.</sub>
<!--  Not working in GitHub
<style scoped>
table {
  font-size: 12px;
}
</style>
-->
## Overview
`McCache` is a, write through cluster aware, local in-memory caching library that is build on Python's [`OrderedDict`](https://docs.python.org/3/library/collections.html#collections.OrderedDict) package.  A local cache lookup is faster than retrieving it across a network.
It uses **UDP** multicast as the transport hence the name "Multi-Cast Cache", playfully abbreviated to "`McCache`".

The goals of this package are:
1. Reduce complexity by **not** be dependent on any external caching service such as `memcached`, `redis` or the likes.  SEE: [Distributed Cache](https://en.wikipedia.org/wiki/Distributed_cache)
    * We are guided by the principal of first scaling up before scaling out.
2. Keep the programming interface consistent with Python's dictionary.  The distributed nature of the cache is transparent to you.
    * This is an in process cache.
3. Performant
    * Need to handle rapid updates that are 0.01sec (10 ms) or faster.

`McCache` is **not** a replacement for your persistent or search data.  It is intended to be used to cache your most expensive work.  You can consider the Pareto Principle [**80/20**](https://en.wikipedia.org/wiki/Pareto_principle) rule, which states that caching **20%** of the most frequently accessed **80%** data can improve performance for most requests.

## Installation
```console
pip install mccache
```

## Example
```python
import  mccache
from    datetime  import  datetime  as  dt
from    pprint    import  pprint    as  pp

c = mccache.get_cache( 'demo' )

c['key'] = dt.utcnow()  # Insert a cache entry
print(f"Started at {c['key']}")

c['key'] = dt.utcnow()  # Update a cache entry
print(f"Ended at {c['key']}")
print(f"Metadata for key is {c.metadata['key']}")

del c['key']  # Delete a cache entry
if 'key' not in c:
    print(f"'key' is not in the cache.")

print("At this point all the cache with namespace "demo" in the cluster are identical.")

# Query the local cache metrics and checksum.
mccache.get_local_metrics( 'demo' ).replace(')' ,')\n')
pp( mccache.get_local_checksum( 'demo' ))
```

In the above example, there is **nothing** different in the usage of `McCache` from a regular Python dictionary.  However, the benefit is in a clustered environment where the other member's cache are kept coherent with the changes to your local cache.

## Guidelines
The following are some loose guidelines to help you assess if the `McCache` library is right for your project.

* You have a need to **not** depend on external caching service.
* You want to keep the programming **consistency** of Python.
* You have a **small** cluster of identically configured nodes.
* You have a **medium** size set of objects to cache.
* Your cached objects do not mutate **frequently**.
* Your cached objects size is **small**.
* Your cluster environment is secured by **other** means.
* Your nodes clock in the cluster are **well** synchronized.

The adjectives used above have been intended to be loose and should be quantified to your environment and needs.<br>
**SEE**: [Testing](https://github.com/McCache/McCache-for-Python/blob/main/docs/TESTING.md)

## Not convince yet?
You can review the script used in the stress test.<br>
**SEE**: [Test script](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py)<br>

You should clone this repo down and run the test in a local `docker`/`podman` cluster.<br>
**SEE**: [Contributing](https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md#Tests)

We suggest the following testing to collect metrics of your application running in your environment.
1. Import the `McCache` library into your project.
2. Use it in your data access layer by populating and updating the cache but **don't** use the cached values.
3. Configure to enable the debug logging by providing a path for your log file.
4. Run your application for an extended period and exit.
5. Log the summary metric out to be analyze.
5. Review the metrics to quantify the fit to your application and environment.  **SEE**: [Testing](https://github.com/McCache/McCache-for-Python/blob/main/TESTING.md#Container)

## Saving
Removing an external dependency in your architecture reduces it's <strong>complexity</strong> and not to mention some cost saving.<br>
**SEE**: [Cloud Savings](https://github.com/McCache/McCache-for-Python/blob/main/docs/SAVING.md)

## Configuration
The following are environment variables you can tune to fit your production environment needs.
<table>
<thead>
  <tr>
    <th align="left">Name</th>
    <th align="left">Default</th>
    <th align="left">Comment</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td><sub>MCCACHE_CACHE_TTL</sub></td>
    <td>3600 sec</td>
    <td>Maximum number of seconds a cached entry can live before eviction.  Update operations shall reset the timer.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_CACHE_MAX</sub></td>
    <td>256 entries</td>
    <td>The maximum entries per cache.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_CACHE_MODE</sub></td>
    <td>1</td>
    <td>The degree of keeping the cache coherent in the cluster.<br>
    <b>0</b>: Only members that has the same key in their cache shall be updated.<br>
    <b>1</b>: All members cache shall be kept fully coherent and synchronized.<br></td>
  </tr>
  <tr>
    <td><sub>MCCACHE_CACHE_SIZE</sub></td>
    <td>1,048,576 bytes</td>
    <td>The maximum size for the cache.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_SYNC_PULSE</sub></td>
    <td>300 sec</td>
    <td>The interval to send out a synchronization pulse operation to the other members in the cluster.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_PACKET_MTU</sub></td>
    <td>1472 bytes</td>
    <td>The size of the smallest transfer unit of the network packet between all the network interfaces.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_MULTICAST_IP</sub></td>
    <td>224.0.0.3 [ :4000 ]</td>
    <td>The multicast IP address and the optional port number for your group to multicast within.
    <br><b>SEE</b>: https://www.iana.org/assignments/multicast-addresses/multicast-addresses.xhtml</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_MULTICAST_HOPS</sub></td>
    <td>1 hop</td>
    <td>The maxinum network hop. 1 is just within the local subnet. [1-9]</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_CALLBACK_WIN</sub></td>
    <td>5 sec</td>
    <td>The window, in seconds, where the last lookup and the current change falls in to trigger a callback to a function provided by you. </td>
  </tr>
  <tr>
    <td><sub>MCCACHE_DAEMON_SLEEP</sub></td>
    <td>1 sec</td>
    <td>The snooze duration for the daemon housekeeper before waking up to check the state of the cache.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_DEBUG_LOGFILE</sub></td>
    <td>./log/debug.log</td>
    <td>The local filename where output log messages are appended to.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_LOG_FORMAT</sub></td>
    <td></td>
    <td>The custom logging format for your project.
    <br><b>SEE</b>: Line# <b>229</b> in __init__.py</td>
  </tr>
  <tr>
    <td colspan=3><b>The following are parameters you can tune to fit your stress testing needs.</b></td>
  <tr>
  <tr>
    <td><sub>TEST_RANDOM_SEED</sub></td>
    <td>4th octet of the IP address</td>
    <td>The random seed for each different node in the test cluster.</td>
  </tr>
  <tr>
    <td><sub>TEST_KEY_ENTRIES</sub></td>
    <td>200 key/values</td>
    <td>The maximum of randomly generated keys.<br>
        The smaller the number, the higher the chance of cache collision.
        Tune this number down to add stress to the test.</td>
  </tr>
  <tr>
    <td><sub>TEST_RUN_DURATION</sub></td>
    <td>5 min</td>
    <td>The duration in minutes of the testing run. <br>
        The larger the number, the longer the test run/duration.
        Tune this number up to add stress to the test.</td>
  </tr>
  <tr>
    <td><sub>TEST_APERTURE</sub></td>
    <td>0.01 sec</td>
    <td>The time scale to keep the randomly generated value to snooze within.
        The value of 0.01, 10ms, a random snooze shall be between 6.5ms and 45ms.
        Tune this number down to add stress to the test.</td>
  </tr>
  <tr>
    <td><sub>TEST_MONKEY_TANTRUM</sub></td>
    <td>0</td>
    <td>The percentage of drop packets. <br>
        The larger the number, the more unsend packets.
        Tune this number up to add stress to the test.</td>
  </tr>
</tbody>
</table>

### pyproject.toml
Specifying tuning parameters via `pyproject.toml` file.
```toml
[tool.mccache]
cache_ttl = 900
packet_mtu = 1472
```
### Environment variables
Specifying tuning parameters via environment variables.
```bash
#  Unix
export MCCACHE_TTL=900
export MCCACHE_MTU=1472
```
```command
::  Windows
SET MCCACHE_TTL=900
SET MCCACHE_MTU=1472
```

## Architecture Diagram
### Centralized implementation
A centralize caching architecture shall be a remote server providing the caching service.
![Centralized Architecture](docs/Centralize%20Architecture.png)
* This diagram is generated at https://www.eraser.io/diagramgpt.  I am in need of some help in the art department.

### McCache implementation
`McCache` attempt to keep the cache in the other members in the cluster in sync with each other.
![McCache Architecture](docs/McCache%20Architecture.png)
* This diagram is generated at https://www.eraser.io/diagramgpt.  I am in need of some help in the art department.

## Design Gist
`McCache` overwrite both the `__setitem__()` and `__delitem__()` dunder methods of `OrderedDict` to shim in the communication sub-layer to sync-up the other members' cache in the cluster.  All changes to the local cache are captured and queued up to be multicast out.  The cache in all nodes will eventually be consistent.

Four daemon threads are started when this package is initialized.  They are:
1. **Multicaster**. &nbsp;Whose job is to dequeue local change operation messages and multicast them out into the cluster.
2. **Listener**. &nbsp;Whose job is to listen for change operation messages multicast by other members in the cluster and immediately queue them up for processing.
3. **Processor**. &nbsp;Whose job is to process the incoming changes.
4. **Housekeeper**. &nbsp;Whose job is manage the acknowledgement of the messages.

UDP is unreliable.  We have to implement a guaranteed message transfer protocol over it in `McCache`.  We did consider TCP but will have to implement management of peer-to-peer connection manager.  Multi-casting is implemented on top of UDP and we selected it.  Furthermore, the nature of `McCache` is to broadcast out changes and this align well with multicasting.  `McCache` prioritize operation that mutates the cache and only acknowledged these operations.  In the future as our knowledge expand, we can return to re-evaluate this decision.

UDP is unreliable.  We  implemented a guaranteed message transfer protocol over UDP in `McCache`.
The nature of `McCache` is to broadcast out changes and this align well with multicast service offered by UDP and we selected it.  Furthermore, `McCache` prioritize operation that mutates the cache and only acknowledged these operations.  We did consider TCP but will have to implement management of peer-to-peer connection manager.

A message may be larger than the UDP payload size.  Regardless, we always chunk up the message into fragments plus a header that fully fit into the UDP payload.  Each UDP payload is made up of a fixed length header follow by a variable length message fragment.  The message is further broken up into the key and fragment section as depicted below:

Given the size of each field in the header, we have a limitation of a maximum 255 fragments per message.  The maximum size of your message shall be 255 multiple by the `packet_mtu` size set in the configuration.

The multicasting member will keep track of all the send fragments to all the member in the cluster.  Each member will re-assemble fragments back into a message.  Dropped fragment will be requested for a re-transmission.  Once each member have acknowledge receipt of all fragments, the message for that member is considered complete and be deleted from pending of acknowledgement.  Each member is always listening to traffic and maintaining its own members list.

Collision happens when two or more nodes make a change to a same key at nearly the same time.  The received message timestamp and checksum of the arriving object shall be compared to the local object timestamp and checksum.  If the local object is more current, based on the timestamp, the local object shall be send back to the original sender to be updated.

There are **no** remote locks.  Synchronization is implemented using a **monotonic** timestamp that is tagged to every cache entry.  This helps serialized the update operation on every node in the cluster.  An arrived change operation has a timestamp which will be compared to the timestamp of the local cache entry.  Only remote operation with the timestamp that is more recent shall be applied to local cache.

Furthermore, we are experimenting with a lockless design.  Locks are needed when the data is being mutated.  For read operation, the data is read without a lock applied to it.  If the entry doesn't exist the `keyError` exception is throw and be handled appropriately.  This is a very edge case and is the reason we decided on trapping the exception instead of locking the region of code.


## Concern
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
* SEE https://www.youtube.com/watch?v=hTp4czOrvOY

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

* The maximum size of your message shall be **255** multiple by the `packet_mtu` size set in the configuration.

## Miscellaneous
* SEE: [Latency Numbers](https://gist.github.com/hellerbarde/2843375)
* SEE: [Determine the size of the MTU in your network.](https://www.youtube.com/watch?v=Od5SEHEZnVU)
* SEE: [Network maximum transmission unit (MTU) for your EC2 instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/network_mtu.html)
* SEE: [Setting MTU size for jumbo frames on OCI instance interfaces](https://support.checkpoint.com/results/sk/sk167534)
Different cloud provider uses different size.

## Background Story
* SEE: [Background story](https://github.com/McCache/McCache-for-Python/blob/main/BACKGROUND.md).

## Releases
Releases are recorded [here](https://github.com/McCache/McCache-for-Python/issues).

## License
`McCache` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Contribute
We welcome your contribution.  Please read [contributing](https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md) to learn how to get setup to contribute to this project.

Issues and feature request can be posted [here](https://github.com/McCache/McCache-for-Python/issues). Help us port this library to other languages.  The repos are setup under the [GitHub `McCache` organization](https://github.com/mccache).
You can reach our administrator at `elau1004@netscape.net`.

## Support
For any inquiries, bug reports, or feature requests, please open an issue in the [GitHub repository](https://github.com/McCache/McCache-for-Python/issues). See the McCache contributor guide for guidelines on filing good bugs.

# Rewrite or remove everthing below ...
## Installation

```console
pip install mccache
```

## How to build?
`hatch -e .`

## How to upload?
`python -m twine upload dist/*`

## Package in Test PypI
https://test.pypi.org/project/McCache/0.0.1/

## Package in PyPI
_Coming soon_
