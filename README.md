# McCache for Python

**Table of Contents**

- [Overview](#overview)
- [Example](#example)
- [Saving](#saving)
- [Guidelines](#guidelines)
- [Installation](#installation)
- [Saving](#saving)
- [License](#license)

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

c = mccache.get_cache()
c['key'] =  datetime.datetime.utcnow()  # Insert

l = logging.getLogger('mccache')
l.info(f'Started at {c['key']}')

c['key'] =  datetime.datetime.utcnow()  # Update
l.info(f'Ended at {c['key']}')

del c['key']  # Delete
if k'key' not in c:
    l.info(f'"key" is not in the cache.')
```
In the above example, there is **nothing** different in the usage `mccache` from a regular Python dictionary.  However, the benefit is in a clustered environment where the other member's cache are kept coherent with the changes to your local cache.

## Saving
If an external dependency is remove your architecture, there is a immediate reduction in complexity and not to mention a cost saving too.  The following are some cloud compute instance pricing comparison on September 16th, 2023.

|Instance Name   |Term     |vCPU|RAM |Price/Hr|30 Days|
|----------------|---------|:--:|---:|-------:|------:|
|t3.medium       |On Demand|2   |4 Gb|   0.052|  37.44|
|t3.medium       |1 year   |2   |4 Gb|   0.037|  26.64|
|cache.t4g.medium|On Demand|2   |3 Gb|   0.065|  46.80|
|cache.t4g.medium|1 year   |2   |3 Gb|   0.041|  29.52|
|cache.m6g.large |On Demand|2   |6 Gb|   0.149| 107.28|
|cache.m6g.large |1 year   |2   |6 Gb|   0.094|  67.68|

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
SEE: https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py<br>
You should clone this repo down and run the test in a local `docker`/`podman` cluster.<br>
SEE: https://github.com/McCache/McCache-for-Python/blob/main/CONTRIBUTING.md

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

## License

`mccache` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
