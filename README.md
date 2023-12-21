# McCache for Python<br><sub>This package is still under development.</sub>
<!--  Not working in GitHub
<style scoped>
table {
  font-size: 12px;
}
</style>
-->
## Overview
`McCache` is a distributed in-memory write through caching library that is build on the [`cachetools`](https://pypi.org/project/cachetools/) package.
It uses **UDP** multicasting as the performant transport hence the name "Multi-Cast Cache", playfully abbreviated to "`McCache`".

The goals of this package are:
1. Reduce complexity by not be dependent on any external caching service such as `memcached`, `redis` or the likes.  We are guided by the principal of first scaling up before scaling out.

2. Keep the programming interface consistent with Python's dictionary.  The distributed nature of the cache is transparent to you.
3. Performant

## Installation
```console
pip install mccache
```

## Example
```python
import datetime
import logging
import mccache

l = logging.getLogger('mccache')
c = mccache.get_cache()

c['key'] = datetime.datetime.utcnow()  # Insert a cache entry
l.info(f'Started at {c['key']}')

c['key'] = datetime.datetime.utcnow()  # Update a cache entry
l.info(f'Ended at {c['key']}')

del c['key']  # Delete a cache entry
if 'key' not in c:
    l.info(f'"key" is not in the cache.')
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
* Your all nodes clock are **well** synchronized.
* Your cluster environment is secured by **other** means.

The adjectives used above have been intended to be loose and should be quantified to your environment and needs.
SEE: [Benchmark](https://github.com/McCache/McCache-for-Python/blob/main/docs/BENCHMARK.md)

## Not convince yet?
You can review the script used in the test.<br>
**SEE**: [Test script](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py)<br>

You should clone this repo down and run the test in a local `docker`/`podman` cluster.<br>
**SEE**: [Contributing](https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md#Tests)

We suggest the following testing to collect metrics of your application running in your environment.
1. Import the `McCache` library into your project.
2. Use it in your data access layer by populating and updating the cache but **don't** use the cached values.
3. Configure to enable the debug logging by providing a path for your log file.
4. Run your application for an extended period and exit.  A metric summary will be logged out.
5. Review the metrics to quantify the fit to your application and environment.  **SEE**: [Benchmark](https://github.com/McCache/McCache-for-Python/blob/main/BENCHMARK.md#Container)

## Saving
Removing an external dependency in your architecture reduces it's <strong>complexity</strong> and not to mention some cost saving.
SEE: [Cloud Savings](https://github.com/McCache/McCache-for-Python/blob/main/docs/SAVING.md)

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
    <td>900</td>
    <td>Maximum number of seconds a cached entry can live before eviction.<br><b>TLRUCache</b> is the default cache use by McCache.
SEE: <a href="https://cachetools.readthedocs.io/en/latest/">cachetools</a></td>
  </tr>
  <tr>
    <td><sub>MCCACHE_CACHE_SIZE</sub></td>
    <td>512</td>
    <td>The maximum entries per cache.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_CACHE_SYNC</sub></td>
    <td>FULL</td>
    <td>The degree of keeping the cache coherent in the cluster.<br><b>FULL</b>: All member cache shall be kept fully coherent and synchronized.<br><b>PART</b>: Only members that has the same key in their cache shall be updated.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_PACKET_MTU</sub></td>
    <td>1472</td>
    <td>The size of the smallest transfer unit of the network packet between all the network interfaces.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_MULTICAST_IP</sub></td>
    <td>224.0.0.3 [:4000]</td>
    <td>The multicast IP address and the optional port number for your group to multicast within.
    <br><b>SEE</b>: https://www.iana.org/assignments/multicast-addresses/multicast-addresses.xhtml</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_SEND_LATENCY</sub></td>
    <td>0.01</td>
    <td>The pause second between each send message. A congestion control value to slow down the rapid sending out of messages.
    <br>0.01 = 10 ms</td>
  </tr>
  send_latency
  <tr>
    <td><sub>MCCACHE_MULTICAST_HOPS</sub></td>
    <td>1</td>
    <td>The maxinum network hop. 1 is just within the local subnet. [1-9]</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_DEAMON_SLEEP</sub></td>
    <td>0.75</td>
    <td>The snooze duration for the deamon housekeeper before waking up to check the state of the cache.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_DEBUG_LOGFILE</sub></td>
    <td>./log/debug.log</td>
    <td>The local filename where output log messages are appended to.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_LOG_FORMAT</sub></td>
    <td></td>
    <td>The custom logging format for your project.</td>
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
    <td><sub>TEST_SLEEP_SPAN</sub></td>
    <td>100</td>
    <td>The range span where a randomly generated to pause in between cache test operation.
      The range of random number is between 1 and 100.<br>
      The smaller the number, the tighter/rapid the operation applied to the cache.
      Tune this number down to add stress to the test.</td>
  </tr>
  <tr>
    <td><sub>TEST_SLEEP_UNIT</sub></td>
    <td>100</td>
    <td>The factoring scale to apply to the above <b>TEST_SLEEP_SPAN</b>.<br>
        1000 = 0.001 sec ,100 = 0.01 sec ,10 = 0.1 sec ,1 = 1 sec<br>
        The larger the number, the tighter/rapid the operation applied to the cache.
        Tune this number up to add stress to the test.</td>
  </tr>
  <tr>
    <td><sub>TEST_MAX_ENTRIES</sub></td>
    <td>100</td>
    <td>The maximum of randomly generated keys.<br>
        The smaller the number, the higher the chance of cache collision.
        Tune this number down to add stress to the test.</td>
  </tr>
  <tr>
    <td><sub>TEST_RUN_DURATION</sub></td>
    <td>5</td>
    <td>The duration in minutes of the testing run. <br>
        The larger the number, the longer the test run/duration.
        Tune this number up to add stress to the test.</td>
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
```toml
[tool.mccache]
cache_ttl = 900
packet_mtu = 1472
```
### Environment variables
```bash
export MCCACHE_TTL=900
export MCCACHE_MTU=1472
```

## Design
`McCache` overwrite both the `__setitem__()` and `__delitem__()` dunder methods of `cachetool` to shim in the communication sub-layer to sync-up the other members in the cluster.  All changes to the cache dictonary are captured and queued up to be multicasted out.

Three deamon threads are started when this package is initialized.  They are:
1. **Multicaster**. &nbsp;Whose job is to dequeue change operation messages and multicast them out into the cluster.
2. **Listener**. &nbsp;Whose job is to listen for change operation messages multicasted by other members in the cluster.
3. **Housekeeper**. &nbsp;Whose job is manage the acknowledgement of multicasted messages.

**UPD** is unreliable.  We have to implement a guaranteed message transfer protocol over it.  We did consider TCP but will have to implement management of peer-to-peer connection manager.  Multi-casting is implmented on top of UDP and we selected it.  In the future as our knowledge expand, we can return to re-evaluate this decision.

A message may be larger than the UDP payload size.  Regardless, we always chunk up the message into fragments plus a header that fully fit into the UPD payload.  Each UDP payload is made up of a fixed length header follow by a variable length message fragment.  The message is further broken up into the key and fragment section as depicted below:

Given the size of each field in the header, we have a limitation of a maximum 255 fragments per message.

The multicasting member will keep track of all the send fragments to all the member in the cluster.  Each member will re-assemble fragments back into a message.  Dropped fragment will be requested for a re-transmission.  Once each member have acknowledge receipt of all fragments, the message for that member is considered complete and be deleted from pending of acknowledgement.  Each member is always listening to traffic and maintaining its own members list.

Collision happens when two or more nodes make a change to a same key at the same time.  The timestamp that is attached to the update is not granular enough to serialize the operation.  In this case, a warning is log and multi-cast out the eviction of this key to prevent the cache from becoming in-coherent.

## Limitation
* Even though the latency is low, it is still **eventually** be consistent.  There is a very micro chance that an event can split in just before the cache is updated.
* The clocks in a distributed environment is never as accurate (due to clock drift) as we want it to be in a high update environment.  On a Local Area Network, the accuracy could go down to 1ms but 10ms is a safer assumption.  SEE: [NTP](https://timetoolsltd.com/ntp/ntp-timing-accuracy/)

## Miscellaneous
* SEE: [Determine the size of the MTU in your network.](https://www.youtube.com/watch?v=Od5SEHEZnVU)
* SEE: [Network maximum transmission unit (MTU) for your EC2 instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/network_mtu.html)
Different cloud provider uses different size.

## Background Story
This project started as a forum for a diverse bunch of experience colleagues to learn `Python`.  Very soon we decided that we need a more  challenging and real project to implement.  We wanted to learn network and threading programming.  We seach for sample code and ended up with some mutli-casting chat server example as our starting point.  We also talked about all the external services used in some application architecture and wonder if they could be removed to reduce complexity and cost.

Finally, we decided on implementing a distributed cache that do **not** introduce any new ways but keep the same `Python` dictionary usage experience.

First we kept it simple to fit our understanding and to deliver working code.  We limit the size of the cached object small.  Each member maintain their owe cache and do not share it.  Any updates to each local cache will be broadcast out an eviction so that the next lookup shall be reprocessed thus be the freshest.  If there is no changes to the underneath platform, they should have the same processed result.

Very soon, we realized that it is a fun academic learning but not functional enough to use it in our own project.  `McCache` functional requirements are:
* Reliable and guaranteed delivery
* Performant

Other non-functional technical requirements are:
* Handle large message
* Small code base
* Not "complex" beyond our skillset and understanding

Building a simple distributed system is more challenging than we originally thought.  You may question some design decision but we arrive here from a collection of wrong and right turns on a long learning journey but we agreed to delivering a good enough working software is the most important compromise.  In the future if we still feel strongly for a re-factoring or a re-design, this option is always available to us.  We are still on this journey of learning and hopefully contribute something of value back into the community.  (circa Oct-2023)

## Contribute
We welcome your contribution.  Please read [contributing](https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md) to learn how to contribute to this project.

Issues and feature request can be posted [here](https://github.com/McCache/McCache-for-Python/issues). Help us port this library to other languages.  The repos are setup under the [GitHub `McCache` organization](https://github.com/mccache).
You can reach me at `elau1004@netscape.net`.

## Releases
Releases are recorded [here](https://github.com/McCache/McCache-for-Python/issues).

## License
`McCache` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.


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
