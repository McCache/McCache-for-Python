# McCache for Python<br><sub>This package is still under development.</sub>
<!--  Not working in GitHub
<style scoped>
table {
  font-size: 12px;
}
</style>
-->
## Overview
McCache is a distributed in-memory write through caching library that is build on the [`cachetools`](https://pypi.org/project/cachetools/) package.
It uses UDP multicasting as the performant transport hence the name "Multi-Cast Cache", playfully abbreviated to "`McCache`".

The goals of this package are:
1. Reduce complexity by not be dependent on any external caching service such as `memcached`, `redis` or the likes.  We are guided by the principal of first scaling up before scaling out.

2. Keep the programming interface consistent with Python's dictionary.  The distributed nature of the cache is transparent to you.
3. Performance

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

## Saving
Removing an external dependency in your architecture reduces it's <strong>complexity</strong> and not to mention some cost saving.
SEE: [Cloud Savings](https://github.com/McCache/McCache-for-Python/blob/main/docs/SAVING.md)


## Guidelines
The following are some loose guidelines to help you assess if the `McCache` library is right for your project.

* You have a need to **not** depend on external caching service.
* You want to keep the programming **consistency** of Python.
* You have a **small** cluster of identically configured nodes.
* You have a **medium** size set of objects to cache.
* Your cached objects do not mutate **frequently**.
* Your cached objects size is **small**.
* Your cluster environment is secured by **other** means.

The adjectives used above have been intended to be loose and should be quantified to your environment and needs.
SEE: [Benchmark  Metrics](https://github.com/McCache/McCache-for-Python/blob/main/docs/BENCHMARK.md)

## Not convince yet?
You can review the script used in the test.<br>
**SEE**: https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py<br>
You should clone this repo down and run the test in a local `docker`/`podman` cluster.<br>
**SEE**: https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md#Tests

We suggest the following testing to collect metrics of your application running in your environment.
1. Import the `McCache` library into your project.
2. Use it in your data access layer by populating and updating the cache **but don't** use the cached values.
3. Configure to enable the debug logging by providing a path for your log file.
4. Run your application for an extended period and exit.  A metric summary will be logged out.
5. Review the metrics to quantify the fit to your application and environment.

## Configuration
The following are parameters you can tune to fit your needs.
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
    <td>Full</td>
    <td>The degree of keeping the cache coherent in the cluster.<br><b>Full</b>: All member cache shall be kept identical.<br><b>Part</b>: Only members that has the same key in their cache shall be updated.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_PACKET_MTU</sub></td>
    <td>1472</td>
    <td>The size of the smallest transfer unit of the network packet between all the network interfaces.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_MULTICAST_IP</sub></td>
    <td>224.0.0.3 [:4000]</td>
    <td>The multicast IP address and the optional port number for your group to multicast within.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_MULTICAST_HOPS</sub></td>
    <td>1</td>
    <td>The maxinum network hop. 1 is just within the local subnet. [1-9]</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_MONKEY_TANTRUM</sub></td>
    <td>0</td>
    <td>The percentage of packets the test monkey will drop. This should only be used in a test environment. [0-99]</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_DEAMON_SLEEP</sub></td>
    <td>2</td>
    <td>The snooze duration for the deamon housekeeper before waking up to check the state of the cache.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_RANDOM_SEED</sub></td>
    <td>4th IPv4 Octet</td>
    <td>The seed to assist with repeatable random stress testing.</td>
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
1. Multicaster. &nbsp;Whose job is to dequeue change operation messages and multicast them out into the cluster.
2. Listener. &nbsp;Whose job is to listen for change operation messages multicasted by other members in the cluster.
3. Housekeeper. &nbsp;Whose job is manage the acknowledgement of multicasted messages.

UPD is selected for its speed but unreliable.  We have to implement a guaranteed message transfer protocol over it.  A message may larger than the UDP payload size.  Regardless, we always chunk up the message into fragments plus a header that fully fit into the UPD payload.  Each UDP payload is made up of a fixed length header follow by a variable length message fragment.  The message is further broken up into the key and fragment section as depicted below:

Given the size of each field in the header, we have a limitation of a maximum 255 fragments per message.

The multicasting member will keep track of all the send fragments to all the member in the cluster.  Each member will re-assemble fragments back into a message.  Dropped fragment will be requested for a re-transmission.  Once each member have acknowledge receipt of all fragments, the message for that member is considered complete and be deleted from pending of acknowledgement.  Each member is always listening to traffic and maintaining its own members list.

## Miscellaneous
SEE: [Determine the size of the MTU in your network.](https://www.youtube.com/watch?v=Od5SEHEZnVU)

## Contribute
We welcome your contribution.  Please read [contributing](https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md) to learn how to contribute to this project.

Issues and feature request can be posted [here](https://github.com/McCache/McCache-for-Python/issues). Help us port this library to other languages.  The repos are setup under the [GitHub `McCache` organization](https://github.com/mccache).
You can reach me at `elau1004@netscape.net`.

## Releases
Releases are recorded [here](https://github.com/McCache/McCache-for-Python/issues).

## License
`McCache` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

# Rewrite everthing below ...
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
