# Benchmark
The following is an informal testing I did on my development laptop.

### Local Hardware
Lenovo P14s laptop
```
O/S:    Windows 11 Pro
CPU:    AMD Ryzen 7 Pro 6850U, 8 cores
Clock:  2.7 GHz
RAM:    32 Gib
```

### Container
**Podman** v4.5.1.  Five nodes are spun up via `docker-compose.yml` with the following command:
```
podman-compose  up  --build  -d
```

The log file was deposited in `./log/` sub-directory.  The following command:
```
grep  MET  ./log/debug*log  |  head -1
```
 extracted the following metric from my test run.
 ```
 20231010Tue 180946.903 Im:10.89.2.7:6     Fr:             Msg:(MET, 1696961386903262942, None, None, None,
 {
    '_process_': {
        'avgload': (0.04443359375, 0.08642578125, 0.08349609375),
        'cputimes': scputimes(user=34.63, nice=0.0, system=36.81, idle=16529.84, iowait=5.98, irq=0.0, softirq=15.32, steal=0.0, guest=0.0, guest_nice=0.0),
        'meminfo': pmem(rss=26808320, vms=256716800, shared=10379264, text=4096, lib=0, data=41074688, dirty=0),
        'netioinfo': snetio(bytes_sent=420635, bytes_recv=2191, packets_sent=1845, packets_recv=28, errin=0, errout=0, dropin=0, dropout=0)
    },
    '_mccache_': {
        'count': 1,
        'size': 0.0051, 'avgspan': 0.011, 'avghits': 3660,
        'lookups': 1850, 'updates': 1567, 'deletes': 263
    },
    'default': {
        'count': 11,
        'size': 0.0049, 'avgspan': 0.011, 'avghits': 3660,
        'lookups': 1850, 'updates': 1567, 'deletes': 263
    }
})
```
The above have been manully formatted for readability.

### Glossary
|`_process_` | The process detail can be found [here](https://psutil.readthedocs.io/en/latest).|
|------------|--------------------------------------|
| avgload    | Return the average system load over the last 1, 5 and 15 minutes as a tuple.<br>The “load” represents the processes which are in a runnable state, either using the CPU or waiting to use the CPU. |
| cputimes   | Return system CPU times as a named tuple.<br>Every attribute represents the seconds the CPU has spent in the given mode. |
| meminfo    | Return memory information about the process as a named tuple. |
| netioinfo  | Return system-wide network I/O statistics as a named tuple. |
| `default`  | `_mccache_` is the total aggregated metrics for all the caches managed by `McCache`. |
| count      | The number of cache entries when the metrics was taken. |
| size       | The total memory size (Mib) used by the cache.<br>The example above, it is `0.0049` Mib or `5,138` bytes. |
| avgspan    | The average span between two (`UPD/DEL`) operation that are within 60 seconds.<br>This is a spike gauge on how rapid the cache is materially changing.  The smaller the number the more rapid the cache is changing.<br>The example above, it is `0.011` seconds apart. |
| avghits    | The number of `UPD/DEL` hits that contributed to the `avgspan` metric. |
| lookups    | The number of cache lookups. |
| updates    | The number of cache updates. |
| deletes    | The number of cache deletes. |

### Cloud VM
TBD
