<h1><a href="https://github.com/McCache/McCache-for-Python/blob/main/README.md">
<!--
<img src="https://github.com/McCache/McCache-for-Python/blob/main/docs/McCache%20Logo.png?raw=true" width="200" height="200" alt="McCache for Python">
-->
<img src="https://github.com/McCache/McCache-for-Python/blob/main/docs/McCache%20Logo%20-%20Rectangle.png?raw=true" width="200" height="150" alt="McCache for Python">
</a>
</h1>

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
2. Keep the same Python programming experience.  It is the same Python's dictionary interface.  The distributed nature of the cache is transparent to you.
    * This is an in process cache.
3. Performant
    * Need to handle rapid updates that are 0.01sec (10 ms) or faster.
4. Secure
    * All transmissions across the network are encrypted.

`McCache` is **not** a replacement for your persistent or search data.  It is intended to be used to cache your most expensive work.  You can consider the Pareto Principle [**80/20**](https://en.wikipedia.org/wiki/Pareto_principle) rule, which states that caching **20%** of the most frequently accessed **80%** data can improve performance for most requests.  This principle offers you the option to reduce your hardware requirement.  Only you can decide how much to cache.

## Installation
```console
pip  install  mccache
```

## Example
```python
import  mccache
from    datetime  import  datetime  as  dt
from    datetime  import  UTC
from    pprint    import  pprint    as  pp

c = mccache.get_cache( 'demo' )
k = 'k1'

c[ k ] = dt.now( UTC )   # Insert a cache entry
print(f"Inserted on {c[ k ]}")

c[ k ] = dt.now( UTC )   # Update a cache entry
print(f"Updated  on {c[ k ]}")
print(f"Metadata for key '{k}' is {c.metadata[ k ]}")

del c[ k ] # Delete a cache entry
if  k  not in c:
    print(f" {k}  is not in the cache.")

k = 'k2'
c[ k ] = dt.now( UTC )   # Insert another cache entry
print(f"Inserted on {c[ k ]}")

# At this point all the cache with namespace 'demo' in the cluster are identical with just one entry with key 'k2'.

# Query the local cache checksum and metrics.
pp( mccache.get_local_checksum( 'demo' ))
pp( mccache.get_local_metrics(  'demo' ))

# Request the other members in the cluster to log out their local cache metrics.
mccache.get_cluster_metrics()
```

In the above example, there is **nothing** different in the usage of `McCache` from a regular Python dictionary.  However, the benefit is in a clustered environment where the other subscribed member's cache are kept coherent with the changes to your local cache.

## Guidelines
The following are some loose guidelines to help you assess if the `McCache` library is right for your project.

* You have a need to **not** depend on external caching service.
* You want to keep the programming **consistency** of a Python dictionary.
* You have a **small** cluster of identically configured nodes.
* You have a **medium** size set of objects to cache.
* Your cached objects do not mutate **frequently**.
* Your cached objects size is **small**.
* Your cluster environment is secured by **other** means.
* Your nodes clock in the cluster are **well** synchronized.

The adjectives used above have been intended to be loose and should be quantified to your environment and needs.<br>
**SEE**: [Testing](https://github.com/McCache/McCache-for-Python/blob/main/docs/TESTING.md)

You can review the script used in the stress test.<br>
**SEE**: [Test script](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py)

You should clone this repo down and run the test in a local `docker`/`podman` cluster.<br>
**SEE**: [Contributing](https://github.com/McCache/McCache-for-Python/blob/main/docs/CONTRIBUTING.md#Tests)

We suggest the following testing to collect metrics of your application running in your environment.
1. Import the `McCache` library into your project.
2. Use it in your data access layer by populating and updating the cache but **don't** use the cached values.
3. Configure to enable the debug logging by providing a path for your log file.
4. Compare the retrieved values between your existing cache and from `McCache`.
5. Run your application for an extended period and exit.
6. Log the summary metric out for more extended analysis.
7. Review the metrics to quantify the fit to your application and environment.  **SEE**: [Testing](https://github.com/McCache/McCache-for-Python/blob/main/docs/TESTING.md#container)

## Saving
Removing an external dependency in your architecture reduces it's <strong>complexity</strong> and not to mention some capital cost saving.<br>
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
    <td>3600 secs (1 hour)</td>
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
    <td>8,388,608&nbsp;bytes&nbsp;(8Mb)</td>
    <td>The maximum in-memory size per cache.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_CACHE_PULSE</sub></td>
    <td>300 secs (5 min)</td>
    <td>The interval to send out a synchronization pulse operation to the other members in the cluster.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_CRYPTO_KEY</sub></td>
    <td></td>
    <td>The encryption/decryption key.  Cryptography shall be enabled if presence of a key value.  Generate the key as follows:
    <code><br>
    &nbsp;&nbsp;from  cryptography.fernet  import  Fernet<br>
    &nbsp;&nbsp;print( Fernet.generate_key() )
    </code><br>Enabling this will increase the payload size by at least 30% and also increase CPU processing.  
    </td>
  </tr>
  <tr>
    <td><sub>MCCACHE_PACKET_MTU</sub></td>
    <td>1472 bytes</td>
    <td>The size of the smallest transfer unit of the network packet between all the network interfaces.<br>Generally, ethernet frame is <b>1500</b> without the static <b>20</b> bytes IP and <b>8</b> bytes ICMP headers.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_MULTICAST_IP</sub></td>
    <td>224.0.0.3 [ :4000 ]</td>
    <td>The multicast IP address and the optional port number for your group to multicast within.
    <br><b>SEE</b>: <a href="https://www.iana.org/assignments/multicast-addresses/multicast-addresses.xhtml">IANA multicast addresses</a>.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_MULTICAST_HOPS</sub></td>
    <td>3 hops</td>
    <td>The maximum network hops. 1 is just within the same switch/router. [>=1]</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_CALLBACK_WIN</sub></td>
    <td>5 secs</td>
    <td>The window, in seconds, where the last lookup and the current change falls in to trigger a callback to a function provided by you. </td>
  </tr>
  <tr>
    <td><sub>MCCACHE_DAEMON_SLEEP</sub></td>
    <td>1 sec</td>
    <td>The snooze duration for the daemon housekeeper before waking up to check the state of the cache.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_LOG_FILENAME</sub></td>
    <td>./log/mccache.log</td>
    <td>The local filename where output log messages are appended to.</td>
  </tr>
  <tr>
    <td><sub>MCCACHE_LOG_FORMAT</sub></td>
    <td></td>
    <td>The custom logging format for your project.
    <br><b>SEE</b>: Variables <code>log_format</code> and <code>log_msgfmt</code> in <code>__init__.py</code></td>
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
    <td><sub>TEST_DATA_SIZE_MIX</sub></td>
    <td>1</td>
    <td>The data packet size mix.<br>
    <b>1</b>: Cache small objects where size < 1Kb.<br>
    <b>2</b>: Cache large objects where size > 9Kb.<br>
    <b>3</b>: Random mix of small and large objects.<br>
    Tune this number to 2 to add stress to the test.</td>
  </tr>
  <tr>
    <td><sub>TEST_RUN_DURATION</sub></td>
    <td>5 mins</td>
    <td>The duration in minutes of the testing run. <br>
        The larger the number, the longer the test run/duration.
        Tune this number up to add stress to the test.</td>
  </tr>
  <tr>
    <td><sub>TEST_APERTURE</sub></td>
    <td>0.01 sec</td>
    <td>The centerpoint of a range of durations to snooze within.
        e.g. For the value of 0.01, 10ms, the snooze range shall be between 6.5ms and 13.5ms.
        Tune this number down to add stress to the test.</td>
  </tr>
  <tr>
    <td><sub>TEST_MONKEY_TANTRUM</sub></td>
    <td>0</td>
    <td>The percentage of drop packets. <br>
        The larger the number, the more unsent packets.
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
```bat
::  Windows
SET MCCACHE_TTL=900
SET MCCACHE_MTU=1472
```
Environment variables supersede the setting in the `pyproject.toml` file.

## Design
* SEE: [Design gist](https://github.com/McCache/McCache-for-Python/blob/main/docs/DESIGN.md).

## Background Story
* SEE: [Background story](https://github.com/McCache/McCache-for-Python/blob/main/docs/BACKGROUND.md).

## Releases
Releases are recorded [here](https://github.com/McCache/McCache-for-Python/issues).

## License
`McCache` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Contribute
We welcome your contribution.  Please read [contributing](https://github.com/McCache/McCache-for-Python/blob/main/docs/CONTRIBUTING.md) to learn how to get setup to contribute to this project.

`McCache` is still a young project. With that said, please try it out in your applications: We need your feedback to fix the bugs and file down the rough edges.

Issues and feature request can be posted [here](https://github.com/McCache/McCache-for-Python/issues). Help us port this library to other languages.  The repos are setup under the [GitHub `McCache` organization](https://github.com/mccache).
You can reach our administrator at `elau1004@netscape.net`.

## Support
For any inquiries, bug reports, or feature requests, please open an issue in the [GitHub repository](https://github.com/McCache/McCache-for-Python/issues).

## Miscellaneous
* SEE: [Latency Numbers](https://gist.github.com/hellerbarde/2843375)
* SEE: [Determine the size of the MTU in your network.](https://www.youtube.com/watch?v=Od5SEHEZnVU)
* SEE: [Network maximum transmission unit (MTU) for your EC2 instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/network_mtu.html)
* SEE: [Setting MTU size for jumbo frames on OCI instance interfaces](https://support.checkpoint.com/results/sk/sk167534)
Different cloud provider uses different size.
* SEE: [Enabling Sticky Sessions](https://www.youtube.com/watch?v=hTp4czOrvOY")
* SEE: [In-Process vs Distributed](https://dzone.com/articles/process-caching-vs-distributed)
