# McCache for Python
<style scoped>
table {
  font-size: 12px;
}
</style>

## Overview
McCache is a distributed in-memory caching library that is build on the [`cachetools`](https://pypi.org/project/cachetools/) package.
It uses UDP multicasting as the performant transport hence the name "Multi-Cast Cache", playfully abbreviated to "`McCache`".

The goals of this package are:
1. Reduce complexity by not be dependent on any external caching service such as `memcached`, `redis` or the likes.
2. Keep the programming interface consistent with Python's dictionary.  The distributed nature of the cache is transparent to you.
3. ~~Not dependent on external library.~~ (_Work in progress_.)

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
In the above example, there is **nothing** different in the usage `McCache` from a regular Python dictionary.  However, the benefit is in a clustered environment where the other member's cache are kept coherent with the changes to your local cache.

## Saving
Removing an external dependency in your architecture reduces in complexity and not to mention a tangible cost saving.  The following are some cloud compute instance pricing comparison on September 16th, 2023.

<table>
<thead>
  <tr>
    <th>Instance pricing</td>
    <th>Smallest cluster size and cost</td>
  </tr>
</thead>
<tbody>
  <tr>
    <td valign="top">
      <table>
      <thead>
        <tr><th>Instance Name</th><th>Term</th><th>vCPU</th><th>RAM</th><th align="right">$/Hour</th><th align="right">$/30days</th></tr>
      </thead>
      <tbody>
        <tr><td colspan=6><a href="https://aws.amazon.com/ec2/pricing/reserved-instances/pricing/">Compute instances</a><td>
        <tr><td>t3a.small       </td><td>One Year </td><td align="center"> 2 </td><td>2 Gb</td><td align="right">0.011</td><td align="right"><b> 7.92</b></td><tr>
        <tr><td>t3a.small       </td><td>On Demand</td><td align="center"> 2 </td><td>2 Gb</td><td align="right">0.019</td><td align="right">   13.68</td><tr>
        <tr><td>t3a.medium      </td><td>One Year </td><td align="center"> 2 </td><td>4 Gb</td><td align="right">0.024</td><td align="right"><b>17.28</b></td><tr>
        <tr><td>t3a.medium      </td><td>On Demand</td><td align="center"> 2 </td><td>4 Gb</td><td align="right">0.037</td><td align="right">   26.64</td><tr>
        <tr><td colspan=6><a href="https://aws.amazon.com/elasticache/pricing/?nc2=type_a/">Managed Redis or Memcached instances</a><td>
        <tr><td>cache.t4g.medium</td><td>One Year </td><td align="center"> 2 </td><td>3 Gb</td><td align="right">0.041</td><td align="right"><b>29.52</b></td><tr>
        <tr><td>cache.t4g.medium</td><td>On Demand</td><td align="center"> 2 </td><td>3 Gb</td><td align="right">0.065</td><td align="right">   46.80</td><tr>
        <tr><td>cache.m6g.large </td><td>One Year </td><td align="center"> 2 </td><td>6 Gb</td><td align="right">0.094</td><td align="right"><b> 7.68</b></td><tr>
        <tr><td>cache.m6g.large </td><td>On Demand</td><td align="center"> 2 </td><td>6 Gb</td><td align="right">0.149</td><td align="right">  107.28</td><tr>
      </tbody>
      </table>
    </td>
    <td valign="top">
      <table>
      <thead>
        <tr>
          <th>Instance Name</th><th>Term</th><th>Count</th><th>RAM</th><th align="right">$/30days</th></tr>
      </thead>
      <tbody>
        <tr><td>t3a.medium      </td><td>One Year</td>   <td align="center"> 2</td><td>8 Gb</td><td align="right">   34.56</td></tr>
        <tr><td colspan=2 align="right"><b>Total</b></td><td align="center"> 2</td><td>8 Gb</td><td align="right"><b>$34.56</b></td></tr>
        <tr><td colspan=5/>
        <tr><td>t3a.small       </td><td>One Year</td>   <td align="center"> 2</td><td>4 Gb</td><td align="right">   15.84</td></tr>
        <tr><td>cache.t4g.medium</td><td>One Year</td>   <td align="center"> 1</td><td>3 Gb</td><td align="right">   29.52</td></tr>
        <tr><td colspan=2 align="right"><b>Total</b></td><td align="center"> 3</td><td>7 Gb</td><td align="right"><b>$45.36</b></td></tr>
      </tbody>
      </table>
    </td>
  </tr>
</tbody>
</table>


For example, a small cluster of three `t3a.medium` instances should have plenty of available memory for caching as compared to a dedicated one `cache.m6g.large` instance.

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

## Not convince yet?
You can review the script used in the test.<br>
**SEE**: https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py<br>
You should clone this repo down and run the test in a local `docker`/`podman` cluster.<br>
**SEE**: https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md#Tests

## Configuration
The following are parameters you can tune to fit your needs.
|Name                  |Default          |Comment|
|----------------------|-----------------|-------|
|MCCACHE_TTL           |900              |The number of seconds a cached entry will live without activity.  This is use by the default `TLRUCache`.<br><b>SEE</b>: https://cachetools.readthedocs.io/en/latest/|
|MCCACHE_MTU           |1472             |The size of the smallest transfer unit of the network packet between all the network interfaces.|
|MCCACHE_MAXSIZE       |512              |The maximum entries per cache.|
|MCCACHE_MULTICAST_IP  |224.0.0.3 [:4000]|The multicast IP address and the optional port number for your group to multicast within.|
|MCCACHE_MULTICAST_HOPS|1                |The maxinum network hop. 1 is just within the local subnet. [1-8]|
|MCCACHE_MONKEY_TANTRUM|0                |The percentage of packets the test monkey will drop.  This should only be used in a test environment. [0-99]|
|MCCACHE_RANDOM_SEED   |4th IPv4 Octet   |The seed to assist with **repeatable** random stress testing.|
|MCCACHE_DEBUG_FILE    |None             |The local filename where output log messages are appended to.|
|MCCACHE_LOG_FORMAT    |None             |The custom logging format for your project.|

### pyproject.toml
```toml
[tool.mccache]
ttl = 900
mtu = 1472
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
```
1) Header                       2) Message
                                    Key section                     Fragment section
    # Field             Size        # Field            Type         # Field             Type
    - ---------------- ------       - ---------------- -------      - ----------------  -------
    1 Magic number     1 Byte       1 Cache namespace  String       1 Operation code    String
      1.1 Pattern      4 Bits       
      1.2 Version      4 Bits       
    2 Sequence number  1 Byte       2 Key              Object       2 Checksum          String
    3 Fragments count  1 Byte       3 Timestamp        Integer      3 Message fragment  Bytes
    4 Key size         2 Byte       4 Sequence number  Integer
    5 Fragment size    2 Byte       5 Fragments count  Integer
    6 Reserved         1 Byte
```
Given the size of each field in the header, we have a limitation of a maximum 255 fragments per message.

The multicasting member will keep track of all the send fragments to all the member in the cluster.  Each member will re-assemble fragments back into a message.  Dropped fragment will be requested for a re-transmission.  Once each member have acknowledge receipt of all fragments, the message for that member is considered complete and be deleted from pending of acknowledgement.  Each member is always listening to traffic and maintaining its own members list.

## Miscellaneous
SEE: [Determine the size of the MTU in your network.](https://www.youtube.com/watch?v=Od5SEHEZnVU)

## Contribute
Issues and feature request can be posted [here](https://github.com/McCache/McCache-for-Python/issues).  We welcome your contribution too.  Help us port this library to other languages.  The repos are setup under the [GitHub `McCache` organization](https://github.com/mccache).
You can reach me at `elau1004@netscape.net`.


## Releases - Maybe move it into RELEASES.md?
#### YYYY-MM-DD &nbsp;&nbsp; v1.0.1
* Second release.
#### YYYY-MM-DD &nbsp;&nbsp; v1.0.0
* Initial release.

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

