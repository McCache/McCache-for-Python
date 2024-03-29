# Testing
The following is the stress testing performed on my laptop.

### Local Hardware
```
Lenovo P14s laptop                              Acer Nitro 5 laptop
    O/S:    Windows 11 Pro                          O/S:    Windows 11 Home
    CPU:    AMD Ryzen 7 Pro 6850U, 8 cores          CPU:    Intel Core i7-12700H, 14 cores
    Clock:  2.7 GHz (Base)  4.7 GHz (Turbo)         Clock:  2.7 GHz (Base) 4.7 GHz (Turbo)
    RAM:    32 Gib                                  RAM:    16 Gib
```

### Container
**Podman** v4.5.1.  The cluster was spun up via `docker-compose.yml` with the following command:
```
podman-compose  up  --build  -d
```
or the default test script located under `.\tests\run_test.bat` with the following CLI parameters:
```
.\tests\run_test -c 9 -d 10 -l 1
```

Since the test is running locally on my laptop in acontainer environment, there is no physical wired network between the nodes.  We almost have a near zero communication latency between the nodes.  Lost packets does occur when the cache is highly stress.

### Logs
The log file was deposited in `./log/` sub-directory.  The following command:
```
grep  MET  ./log/debug*log  |  head -1
```
 extracted the following metric from my test run.
 ```
 1706587615.712198 L#1167 Im:10.89.2.72  Fr:10.89.2.73   MET     17065876156.695839
{   '_process_': {
        'avgload': (2.74658203125, 3.5654296875, 3.08642578125),
        'cputimes': scputimes(user=3909.73, nice=0.96, system=7038.32, idle=65431.12, iowait=20.6, irq=0.0, softirq=567.77, steal=0.0, guest=0.0, guest_nice=0.0),
        'meminfo': pmem(rss=60022784, vms=276606976, shared=11001856, text=4096, lib=0, data=75644928, dirty=0),
        'netioinfo': snetio(bytes_sent=1938965, bytes_recv=15485462, packets_sent=11018, packets_recv=88105, errin=0, errout=0, dropin=0, dropout=0)
    },
    'mccache': {
        'count': 249,
        'lookups': 1768,
        'inserts': 2543,
        'updates': 5652,
        'deletes': 2212,
        'evicts': 82,
        'size': 55736,
        'spikes': 10489,
        'spikeduration': 0.0573
    }
}
```
The above have been manully formatted for readability.  For stress testing purposes, the `spike` and `spikeduration` numbers are of interest for they indicate how hard the cache was stressed with changes.  The `spikeduration`, in seconds, shows how rapid the cache was updated in a sliding five seconds window.  In the above sample, the cache was stressed with  `10489` changes and all within an average of `0.0573` seconds apart.

### Glossary
|`_process_` | The process detail can be found [here](https://psutil.readthedocs.io/en/latest).|
|------------|--------------------------------------|
| avgload    | Return the average system load over the last 1, 5 and 15 minutes as a tuple.<br>The “load” represents the processes which are in a runnable state, either using the CPU or waiting to use the CPU. |
| cputimes   | Return system CPU times as a named tuple.<br>Every attribute represents the seconds the CPU has spent in the given mode. |
| meminfo    | Return memory information about the process as a named tuple. |
| netioinfo  | Return system-wide network I/O statistics as a named tuple. |
| `mccache`  ||
| count      | The number of cache entries when the metrics was taken. |
| lookups    | The number of cache lookups. |
| inserts    | The number of cache inserts. |
| updates    | The number of cache updates. |
| deletes    | The number of cache deletes. |
| evicts     | The number of cache evicts.  |
| size       | The total memory used by the cache in bytes.<br>The example above, it is `42632` bytes. |
| spikes     | The number of `UPD/DEL` hits that contributed to the `spikeduration` metric.<br>The example above, `10489` operations that changes the data within a five seconds sliding window.|
|spikeduration| The average span between two (`UPD/DEL`) operation that are within 5 seconds.<br>This is a spike gauge on how rapid the cache is materially changing.  The smaller the number the more rapid the cache is changing.<br>The example above, it is an average `0.0573` seconds apart. |

### Cloud VM
TBD

### Testing Parameters
Cache in-coherence is when at least two nodes have different values for the same key.  To stress `McCache`, the following is some guidelines to keep it realistic:
* Keep the number of docker/podman containers to total number of cores on your machine minus one.
    * Our official stress ran in **9** docker/podman containers cluster.
* Missing entries is **not** bad.  The node that do not have the entry will need to re-process the work and insert it into its local cache.  This will trigger a multicast out to the other members in the cluster.
* Entries that are different must be validated against test exiting timestamp.  If the test exiting timestamp is older, this is **not** bad.

The following testing parameters that did **not** produce any cache in-coherence after five consecutive runs among the nodes in my local docker/podman cluster.  The three main knobs to tune the stress test are: 1) `MAX_ENTRIES` ,2) `SLEEP_SPAN` and 3) `SLEEP_UNIT`.  Increasing the mentioned parameters have the following affects:

|Parameter  |Decription|
|:----------|:---------|
|MAX_ENTRIES|Increasing/decreasing this value spread out the number of entries thus reduces/increases contention.|
|SLEEP_SPAN |Increasing/decreasing this value provide a wider/narrower window range for a random event to be generated within. Tune down the number to stress the system.  This parameter is to be used with `SLEEP_UNIT`.|
|SLEEP_UNIT |Increasing/decreasing this value provide a finer/coarser fraction time increment for a random event to be generated within.  Tune up the number to stress the system.  This parameter is to be used with `SLEEP_SPAN`.|

Each batch of test consist of **5** independent runs in a cluster of **9** nodes for a duration of **10** minutes with the set of parameters listed below.  All **5** runs must pass consecutively to be considered successful.

#### Command used
```bash
tests/run_test  -c 9 -d 10 -s 100 -u 1000 -l 0
```

### Results

|SLEEP<br>SPAN|SLEEP<br>UNIT|MAX<br>ENTRIES|<br>Status|<br>Comment|Spike<br>AvgHits|Spike<br>AvgLoad|
|----:|-----:|----:|:------:|--------------------------------------------------------------------------------|----:|------:|
|1000 | 1000 | 100 |  PASS  |Cache change within `0s - 1.00s` window of `.001s ` increment for `100` entries.| 3090|0.1938s|
| 700 | 1000 | 100 |  PASS  |Cache change within `0s - 0.70s` window of `.001s ` increment for `100` entries.| 4485|0.1341s|
| 600 | 1000 | 100 |  PASS  |Cache change within `0s - 0.60s` window of `.001s ` increment for `100` entries.| 5338|0.1124s|
| 500 | 1000 | 100 |  PASS  |Cache change within `0s - 0.50s` window of `.001s ` increment for `100` entries.| 6406|0.0934s|
| 400 | 1000 | 100 |  PASS  |Cache change within `0s - 0.40s` window of `.001s ` increment for `100` entries.| 7974|0.0753s|
| 300 | 1000 | 100 |  PASS  |Cache change within `0s - 0.30s` window of `.001s ` increment for `100` entries.|10628|0.0564s|
| 200 | 1000 | 100 |  PASS  |Cache change within `0s - 0.20s` window of `.001s ` increment for `100` entries.|16429|0.0368s|
| 100 | 1000 | 100 |  PASS  |Cache change within `0s - 0.10s` window of `.001s ` increment for `100` entries.|32378|0.0187s|
| 100 | 2000 | 100 |  PASS  |Cache change within `0s - 0.05s` window of `.0005s` increment for `100` entries.|63771|0.0096s|
| 100 | 5000 | 100 |        |Cache change within `0s - 0.02s` window of `.0002s` increment for `100` entries.|||
| 100 |10000 | 100 |        |Cache change within `0s - 0.01s` window of `.0001s` increment for `100` entries.|||
