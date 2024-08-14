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
|**`mccache`**||
| count      | The number of cache entries when the metrics was taken. |
| lookups    | The number of cache lookups. |
| inserts    | The number of cache inserts. |
| updates    | The number of cache updates. |
| deletes    | The number of cache deletes. |
| evicts     | The number of cache evicts.  |
| size       | The total memory used by the cache in bytes.<br>The example above, it is `42632` bytes. |
| spikes     | The number of `UPD/DEL` hits that contributed to the `spikeInt` metric.<br>The example above, `10489` operations that changes the data within a five seconds sliding window.|
|spikeInt| The average interval between two (`UPD/DEL`) operation that are within 5 seconds sliding window.<br>This is a spike gauge on how rapid the cache is materially changing.  The smaller the number the more rapid the cache is changing.<br>The example above, it is an average `0.0573` seconds apart. |

### Stress Testing
This stress test is intended to find the breaking point for `McCache` on a given class of machine.  The test script run for a certain duration pausing a faction of a second in each iteration in a loop.  Based on the sleep aperture, a snooze value is calculated to keep the value within the aperture precision up to ten times the aperture value.  e.g. If the aperture value is `0.01`, the snooze value shall be between `0.01` and `0.1`.
Next, a random operation, lookup, insert, update and delete, to be applied to the cache.  Currently, the distributions are:
* 55% are lookups.
* 05% are deletes.
* 20% are inserts.
* 20% are updates.

Cache in-coherence is when at least two nodes have different values for the same key.  To stress `McCache`, the following is some guidelines to keep it realistic:
* Keep the number of docker/podman containers to total number of cores on your machine minus one.
    * Our official stress test ran in **9** docker/podman containers cluster for **10** minutes.
* Missing cache entries is **not** bad.  The node that do not have the entry will need to re-process the work and insert it into its local cache.  This will trigger a multicast out to the other members in the cluster.
* Entries that are different must be validated against test done timestamp.  If the test done timestamp is older, this is **not** bad.


#### Command used
Bash shell:
```bash
$ tests/run_test  -c 9 -k 100 -p 3 -s 0.01 -d 10 -l 0
```
Windows Command Prompt:
```cmd
$ tests\run_test  -c 9 -k 100 -p 3 -s 0.01 -d 10 -l 0
```
The CLI parameters are:
|Flag  |Description     |Default|Unit    |Comment|
|------|----------------|------:|--------|-------|
|-c #  |Cluster size.   |      3|Nodes   |Max is 9.|
|-d #  |Run duration.   |      5|Minute  |Decrease run duration, decreases coverage.|
|-k #  |Max entries.    |    200|Key     |Decrease K/V entries, increases contention.|
|-l #  |Debug level.    |      0|Level   |0=Off ,1=Basic ,3=Extra ,5=Superfluous|
|-p #  |Sync pulse.     |      5|Minute  |Decrease pulse value, increases synchronization.|
|-s #  |Snooze aperture.|   0.01|Fraction|Decrease snooze aperture, increase contention. 0.01=10ms ,0.001=1ms ,0.0001=0.1ms/100us|
|-y #  |Monkey tantrum. |      0|Percent |0=Disabled. Artificially introduce some packet lost. e.g. `3 is 3% packet lost`.|
|-w #  |Callback window.|      0|Second  |0=Disabled. Callback window, in seconds, for changes in the cache since last looked up.|
* The test script that is used to pound the cache can be viewed [here](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py).

### Results of basic stress test
Result header caption:
* Avg Snooze    - The average pause plus processing time per loop iteration in the test script.
* Avg SpikeHits - The average number of inserts, updates, and deletes that are called with less than **3** seconds spike window..
* Avg SpikeInt  - The average interval in seconds between insert, update, and delete operation.
* Avg Misses    - The average lookups performed in the test.
* Avg LookUps   - The average lookups performed in the test.
* Avg Inserts   - The average inserts performed in the test.
* Avg Updates   - The average updates performed in the test.
* Avg Deletes   - The average deletes performed in the test.


|<br>Run|-c #<br>Nodes|-k #<br>Keys|-p #<br>Pulse|-s #<br>Aperture|-d #<br>Duration|<br>Result|<br>Hung|Fail<br>Test|Avg<br>Snooze|Avg<br>SpikeHits|Avg<br>SpikeInt|Avg<br>Misses|Avg<br>LookUps|Avg<br>Inserts|Avg<br>Updates|Avg<br>Deletes|<br>Comment|
|:------|---:|---:|--:|---:|---:|:----------------------------:|:-:|:-:|-----:|-----:|-----:|-----:|-----:|-----:|----:|-----:|:-|
|3.1    |   3| 100|  3| 0.1|  10|<font color="cyan">Pass</font>|   |   |0.5459|   325|1.1222|     0|   674|   106|  233|    38|Basic test with **3** nodes using **100** key/value pairs, sync every **5** minutes, running with **100**ms snooze aperture for **10** minutes.|
|3.1.1  |   3| 100|  3| 0.1|  15|<font color="cyan">Pass</font>|   |   |0.5423|   614|1.0357|     0|  1022|   161|  435|    82|Increase duration up to **15** minutes.|
|3.1.2  |   3| 100|  3| 0.1|  20|<font color="red" >Fail</font>|Yes|   |      |      |      |      |      |      |     |      |Increase duration up to **20** minutes.|
|3.1.2.1|   3| 100|  3| 0.5|  20|<font color="red" >Fail</font>|Yes|   |      |      |      |      |      |      |     |      |Increase aperture up to **0.5** second.|
|3.1.2.2|   3| 100|  3| 0.8|  20|<font color="red" >Fail</font>|   |   |      |      |      |      |      |      |     |      |Increase aperture up to **0.8** second.|
|3.1.2.3|   3| 100|  3| 2.0|  20|<font color="red" >Fail</font>|   |   |      |      |      |      |      |      |     |      |Increase aperture up to **2.0** second.|
|       |    |    |   |    |    |                              |   |   |      |      |      |      |      |      |     |      |   |

* The following may have influence over the above results:
    * Number of running containers.  CPU may throttle down when it is too hot.
    * Python version.  The latest version is mich faster than two versions ago.
    * Python `random.randrange()` and `time.sleep()` implementation.
    * The O/S scheduler.

### Observations
* The laptop is a freshly rebooted and is entirely dedicated to this stress test.  No other task were running on it.
* Some of my containers hang after running more than **15** minutes under load.
* Anecdotally, it does **not** look like `time.sleep( 0.0001 )` can yield accurate precision.
* We feel that `McCache` can handle very heavy update/delete against it.  `McCache` is **not** for you if you have a use case that pound the cache harder than `40000` changes within `0.01` second apart for `10` minutes.


### Cloud VM
TBD
