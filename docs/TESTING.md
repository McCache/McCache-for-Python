# Testing
The following is the stress testing performed on my laptop.

### Local Hardware
```
Lenovo P14s laptop                              Acer Nitro 5 laptop
    O/S:    Windows 11 Pro                          O/S:    Windows 11 Home
    CPU:    AMD Ryzen 7 Pro 6850U, 8 cores          CPU:    Intel Core i7-12700H, 14 cores
    Clock:  2.7 GHz (Base)  4.7 GHz (Turbo)         Clock:  2.3 GHz (Base) 4.7 GHz (Turbo)
    RAM:    32 Gib                                  RAM:    16 Gib
```

### Container
**Podman** v4.5.1.  The cluster was spun up via `docker-compose.yml` with the following command:
```bash
$ podman-compose  up  --build  -d
```
or the default test script located `.\tests\run_test.bat` with the following CLI parameters:
```bash
$ tests/run_test  -c 9 -d 10 -l 1
```

Since the test is running locally on my laptop in a container environment, there is no physical wired network between the nodes.  We almost have a near zero communication latency between the nodes.  Lost packets does occur when the cache is highly stress.

### Logs
The log file was deposited in `./log/` sub-directory.  The following command:
```bash
$ grep  MET  ./log/debug*log  |  head -1
```
 extracted the following metric from my test run.
 ```json
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
        'spikeInt': 0.0573
    }
}
```
The above have been manully formatted for readability.  For stress testing purposes, the `spike` and `spikeInt` numbers are of interest for they indicate how hard the cache was stressed with changes.  The `spikeInt`, in seconds, shows how rapid the cache was updated in a sliding five seconds window.  In the above sample, the cache was stressed with  `10489` changes and all within an average of `0.0573` seconds apart.

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
| spikes     | The number of `UPD/DEL` hits that contributed to the `spikeInt` metric.<br>The example above, `10489` operations that changes the data within a five seconds sliding window.|
|spikeInt| The average interval between two (`UPD/DEL`) operation that are within 5 seconds sliding window.<br>This is a spike gauge on how rapid the cache is materially changing.  The smaller the number the more rapid the cache is changing.<br>The example above, it is an average `0.0573` seconds apart. |

### Testing Parameters
Cache in-coherence is when at least two nodes have different values for the same key.  To stress `McCache`, the following is some guidelines to keep it realistic:
* Keep the number of docker/podman containers to total number of cores on your machine minus one.
    * Our official stress ran in **9** docker/podman containers cluster.
* Missing entries is **not** bad.  The node that do not have the entry will need to re-process the work and insert it into its local cache.  This will trigger a multicast out to the other members in the cluster.
* Entries that are different must be validated against test exiting timestamp.  If the test exiting timestamp is older, this is **not** bad.

The following testing parameters that did **not** produce any cache in-coherence after three consecutive runs among the nodes in my local docker/podman cluster.  The three main knobs to tune the stress test are: 1) `MAX_ENTRIES` ,2) `SLEEP_SPAN` and 3) `SLEEP_UNIT`.  Increasing the mentioned parameters have the following affects:

|Parameter  |Decription|
|:----------|:---------|
|MAX_ENTRIES|Increasing/decreasing this value spread out the number of entries thus reduces/increases contention.|
|SLEEP_SPAN |Increasing/decreasing this value provide a wider/narrower window range for a random event to be generated within. Tune down the number to stress the system.  This parameter is to be used with `SLEEP_UNIT`.|
|SLEEP_UNIT |Increasing/decreasing this value provide a finer/coarser fraction time increment for a random event to be generated within.  Tune up the number to stress the system.  This parameter is to be used with `SLEEP_SPAN`.|

Each batch of test consist of **5** independent runs in a cluster of **9** nodes for a duration of **10** minutes with the set of parameters listed below.  All **5** runs must pass consecutively to be considered successful.

#### Command used
Bash shell:
```bash
$ tests/run_test  -c 9 -d 10 -k 100 -s 100 -u 100 -l 0
```
Windows Command Prompt:
```cmd
$ tests\run_test  -c 9 -d 10 -k 100 -s 100 -u 100 -l 0
```

### Results

|<br>Run|<br>Nodes|MAX<br>ENTRIES|SLEEP<br>SPAN|SLEEP<br>UNIT|<br>Status|Average<br>SpikeHits|Average<br>SpikeLoad|Average<br>LookUps|Average<br>Inserts|Average<br>Updates|Average<br>Deletes|<br>Comment|
|:--  |:---:|------:|----:|-----:|:------:|---:|----:|---:|---:|---:|---:|:-|
|1    |  9  |  100  | 100 |  100 |  PASS  |2529|0.237| 592| 799|1184| 518|Time between changes range from `0.05 to 1.0` second of `0.01` sec increment. |
|5    |  9  |  100  |  50 |  100 |**FAIL**|    |     |    |    |    |    |Time between changes range from `0.05 to 0.5` second of `0.01` sec increment. |
|5.1.1|**4**|  100  |  50 |  100 |**FAIL**|    |     |    |    |    |    |Encountered cache incoherence. |
|5.1.2|**3**|  100  |  50 |  100 |**FAIL**|    |     |    |    |    |    |Encountered cache incoherence. |
|5.2.1|  9  |**150**|  50 |  100 |        |    |     |    |    |    |    |  |
|5.2.2|  9  |  200  |  50 |  100 |        |4414|0.163|1243|1026|2615| 763|  |
|5.2.3|  9  |  250  |  50 |  100 |        |4449|0.135|1243|1058|2586| 787|  |
|6    |  9  |  100  |  40 |  100 |  PASS  |    |     |    |    |    |    |  |
|7    |  9  |  100  |  30 |  100 |  PASS  |    |     |    |    |    |    |  |
|8    |  9  |  100  |  20 |  100 |  PASS  |    |     |    |    |    |    |  |
|9    |  9  |  100  |  10 |  100 |  PASS  |    |     |    |    |    |    |  |


### Observations
* The laptop is a freshly rebooted and is entirely dedicated to this stress test.  No other task were running on it.
* We feel that `McCache` can handle very heavy update/delete against it.  Unless you have a workload that can pound `McCache` with an average of `32378` changes with `0.0187` second apart for `10` minutes, then `McCache` is **not** for you.
* Once we stress `McCache` beyond `test#` **8**, we observed some cache in-coherent and the entries are evicted.

### Cloud VM
TBD
