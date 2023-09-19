# McCache for Python

## Overview
McCache is a distributed in-memory caching library that is build on [`cachetools`](https://pypi.org/project/cachetools/) package.
It uses UDP multicasting as the performant transport hence the name "Multi-Cast Cache", playfully abbreviated to "McCache".

The goals of this package are:
1. Not for your application to be dependent on an external caching service such as `memcached`, `redis` and the likes.
2. Keep the programming interface consistent with Python's dictionary.  The distributed nature of the cache is transparent to you.

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
if k'key' not in c:
    l.info(f'"key" is not in the cache.')
```
In the above example, there is **nothing** different in the usage `McCache` from a regular Python dictionary.  However, the benefit is in a clustered environment where the other member's cache are kept coherent with the changes to your local cache.

## Saving
If an external dependency is remove your architecture, there is a immediate reduction in complexity and not to mention a cost saving too.  The following are some cloud compute instance pricing comparison on September 16th, 2023.

|<sub>Instance Name   </sub>|<sub>Term     </sub>|<sub>vCPU</sub>|<sub>RAM </sub>|<sub>$/Hour</sub>|<sub>$/30 Days</sub>|
|----------------           |---------           |:--:           |---:           |-------:         |------:             |
|<sub>t3a.small       </sub>|<sub>One Year </sub>|<sub>2   </sub>|<sub>2 Gb</sub>|<sub> 0.011</sub>|<sub>     7.92</sub>|
|<sub>t3a.small       </sub>|<sub>On Demand</sub>|<sub>2   </sub>|<sub>2 Gb</sub>|<sub> 0.019</sub>|<sub>    13.68</sub>|
|<sub>t3a.medium      </sub>|<sub>One Year </sub>|<sub>2   </sub>|<sub>4 Gb</sub>|<sub> 0.024</sub>|<sub>    17.28</sub>|
|<sub>t3a.medium      </sub>|<sub>On Demand</sub>|<sub>2   </sub>|<sub>4 Gb</sub>|<sub> 0.037</sub>|<sub>    26.64</sub>|
|                           |                    |               |               |                 |                    |
|<sub>cache.t4g.medium</sub>|<sub>One Year </sub>|<sub>2   </sub>|<sub>3 Gb</sub>|<sub> 0.041</sub>|<sub>    29.52</sub>|
|<sub>cache.t4g.medium</sub>|<sub>On Demand</sub>|<sub>2   </sub>|<sub>3 Gb</sub>|<sub> 0.065</sub>|<sub>    46.80</sub>|
|<sub>cache.m6g.large </sub>|<sub>One Year </sub>|<sub>2   </sub>|<sub>6 Gb</sub>|<sub> 0.094</sub>|<sub>    67.68</sub>|
|<sub>cache.m6g.large </sub>|<sub>On Demand</sub>|<sub>2   </sub>|<sub>6 Gb</sub>|<sub> 0.149</sub>|<sub>   107.28</sub>|

Top: [Compute instances](https://aws.amazon.com/ec2/pricing/reserved-instances/pricing/)<br>
Bottom: [Managed Redis or Memcached instances](https://aws.amazon.com/elasticache/pricing/?nc2=type_a)

For example, a small cluster of three `t3.medium` instances should have plenty of available memory for caching as compared to a dedicated one `cache.m6g.large` instance.

## Guidelines
The following are some loose guidelines to help you assess if the `McCache` library is right for your project.

* You have a need to **not** to depend on external caching services.
* You want to keep the programming **consistency** of Python.
* You have a **small** cluster of identically configured nodes.
* You have a **medium** size set of objects to cache.
* Your cached objects do **not** mutate frequently.
* Your cluster environment is secured by **other** means.

The adjectives used above have been intended to be loose and should be quantified to your environment and needs.

## Not convince yet?
You can review the script used in the test.<br>
**SEE**: https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py<br>
You should clone this repo down and run the test in a local `docker`/`podman` cluster.<br>
**SEE**: https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md#Tests

## Releases
#### YYYY-MM-DD &nbsp;&nbsp; v1.0.1
* Second release.
#### YYYY-MM-DD &nbsp;&nbsp; v1.0.0
* Initial release.

## License 
`mccache` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

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

