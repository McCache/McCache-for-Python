# McCache for Python
<!--  Not working in GitHub
<style scoped>
table {
  font-size: 12px;
}
</style>
-->
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
Removing an external dependency in your architecture reduces it's <strong>complexity</strong> and not to mention some cost saving.  The following are some cloud compute instance pricing comparison on September 16th, 2023.

<table>
<thead>
  <tr>
    <th align="left">Instance pricing</th>
    <th align="left">Smallest cluster size and cost</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td valign="top">
      <table>
      <thead>
        <tr><th align="left"><sub>Instance Name</sub></th><th><sub>Term</sub></th><th><sub>vCPU</sub></th><th><sub>RAM</sub></th><th align="right"><sub>$/Hour</sub></th><th align="right"><sub>$/30days</sub></th></tr>
      </thead>
      <tbody>
        <tr><td colspan=5><a href="https://aws.amazon.com/ec2/pricing/reserved-instances/pricing/"><sub>Compute instances</sub></a></td></tr>
        <tr><td><sub>t3a.small       </sub></td><td><sub>One Year </sub></td><td align="center"><sub> 2 </sub></td><td><sub>2 Gb</sub></td><td align="right"><sub>0.011</sub></td><td align="right"><sub><b> 7.92</b></sub></td></tr>
        <tr><td><sub>t3a.small       </sub></td><td><sub>On Demand</sub></td><td align="center"><sub> 2 </sub></td><td><sub>2 Gb</sub></td><td align="right"><sub>0.019</sub></td><td align="right"><sub>   13.68</sub></td></tr>
        <tr><td><sub>t3a.medium      </sub></td><td><sub>One Year </sub></td><td align="center"><sub> 2 </sub></td><td><sub>4 Gb</sub></td><td align="right"><sub>0.024</sub></td><td align="right"><sub><b>17.28</b></sub></td></tr>
        <tr><td><sub>t3a.medium      </sub></td><td><sub>On Demand</sub></td><td align="center"><sub> 2 </sub></td><td><sub>4 Gb</sub></td><td align="right"><sub>0.037</sub></td><td align="right"><sub>   26.64</sub></td></tr>
        <tr><td colspan=5><a href="https://aws.amazon.com/elasticache/pricing/?nc2=type_a/"><sub>Managed Redis or Memcached instances</sub></a><td><sub></tr>
        <tr><td><sub>cache.t4g.medium</sub></td><td><sub>One Year </sub></td><td align="center"><sub> 2 </sub></td><td><sub>3 Gb</sub></td><td align="right"><sub>0.041</sub></td><td align="right"><sub><b>29.52</b></sub></td></tr>
        <tr><td><sub>cache.t4g.medium</sub></td><td><sub>On Demand</sub></td><td align="center"><sub> 2 </sub></td><td><sub>3 Gb</sub></td><td align="right"><sub>0.065</sub></td><td align="right"><sub>   46.80</sub></td></tr>
        <tr><td><sub>cache.m6g.large </sub></td><td><sub>One Year </sub></td><td align="center"><sub> 2 </sub></td><td><sub>6 Gb</sub></td><td align="right"><sub>0.094</sub></td><td align="right"><sub><b>67.68</b></sub></td></tr>
        <tr><td><sub>cache.m6g.large </sub></td><td><sub>On Demand</sub></td><td align="center"><sub> 2 </sub></td><td><sub>6 Gb</sub></td><td align="right"><sub>0.149</sub></td><td align="right"><sub>  107.28</sub></td></tr>
      </tbody>
      </table>
    </sub></td>
    <td valign="top">
      <table>
      <thead>
        <tr>
          <th><sub>Instance Name</sub></th><th><sub>Term</sub></th><th><sub>Count</sub></th><th><sub>RAM</sub></th><th align="right"><sub>$/30days</sub></th></tr>
      </thead>
      <tbody>
        <tr><td><sub>t3a.small       </sub></td><td><sub>One Year</sub></td>   <td align="center"><sub> 4</sub></td><td><sub>8 Gb</sub></td><td align="right"><sub>    31.68</sub></td></tr>
        <tr><td colspan=2 align="right"><b>Total</b></sub></td><td align="center"><sub> 4</sub></td><td><sub>8 Gb</sub></td><td align="right"><sub><b>$31.68</b></sub></td></tr>
        <tr><td colspan=5/>
        <tr><td><sub>t3a.medium      </sub></td><td><sub>One Year</sub></td>   <td align="center"><sub> 2</sub></td><td><sub>8 Gb</sub></td><td align="right"><sub>    34.56</sub></td></tr>
        <tr><td colspan=2 align="right"><sub><b>Total</b></sub></td><td align="center"><sub> 2</sub></td><td><sub>8 Gb</sub></td><td align="right"><sub><b>$34.56</b></sub></td></tr>
        <tr><td colspan=5/>
        <tr><td><sub>t3a.small       </sub></td><td><sub>One Year</sub></td>   <td align="center"><sub> 2</sub></td><td><sub>4 Gb</sub></td><td align="right"><sub>    15.84</sub></td></tr>
        <tr><td><sub>cache.t4g.medium</sub></td><td><sub>One Year</sub></td>   <td align="center"><sub> 1</sub></td><td><sub>3 Gb</sub></td><td align="right"><sub>    29.52</sub></td></tr>
        <tr><td colspan=2 align="right"><sub><b>Total</b></sub></td><td align="center"><sub> 3</sub></td><td><sub>7 Gb</sub></td><td align="right"><sub><b>$45.36</b></sub></td></tr>
      </tbody>
      </table>
    </sub></td>
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
We welcome your contribution.  Please read [contributing](https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md) to learn how to contribute to this project.

Issues and feature request can be posted [here](https://github.com/McCache/McCache-for-Python/issues). Help us port this library to other languages.  The repos are setup under the [GitHub `McCache` organization](https://github.com/mccache).
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

