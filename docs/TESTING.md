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

### Stress Testing
The test script run for a certain duration pausing a faction of a second in each iteration in a loop.  Based on the sleep aperture, a snooze value is calculated to keep the value within the aperture precision up to ten times the aperture value.  e.g. If the aperture value is `0.01`, the snooze value shall be between `0.01` and `0.1`.
Next, a random operation, lookup, insert, update and delete, to be applied to the cache.  Currently, the distributions are:
* 55% are lookups.
* 05% are deletes.
* 20% are inserts.
* 20% are updates.

Cache in-coherence is when at least two nodes have different values for the same key.  To stress `McCache`, the following is some guidelines to keep it realistic:
* Keep the number of docker/podman containers to total number of cores on your machine minus one.
    * Our official stress test ran in **9** docker/podman containers cluster.
* Missing cache entries is **not** bad.  The node that do not have the entry will need to re-process the work and insert it into its local cache.  This will trigger a multicast out to the other members in the cluster.
* Entries that are different must be validated against test done timestamp.  If the test done timestamp is older, this is **not** bad.


#### Command used
Bash shell:
```bash
$ tests/run_test  -c 9 -d 10 -k 100 -p 0.01 -s 1 -l 0
```
Windows Command Prompt:
```cmd
$ tests\run_test  -c 9 -d 10 -k 100 -p 0.01 -s 1 -l 0
```
The CLI parameters are:
|Flag  |Description         |Default|Unit    |Comment|
|------|--------------------|------:|--------|-------|
|-c #  |Cluster size.       |      3|Nodes   |Max is 9.|
|-d #  |Run duration.       |      5|Minute  |Decrease duration, decreases coverage.|
|-k #  |Max entries.        |    200|Key     |Decrease count, increases contention.|
|-l #  |Debug level.        |      0|Level   |0=Off ,1=Basic ,3=Extra ,5=Superfluous|
|-a #  |Sleep aperture.     |   0.01|Fraction|Decrease aperture, increase contention. 0.01=10ms ,0.001=1ms ,0.0001=0.1ms/100us|
|-y #  |Monkey tantrum.     |      0|Percent |0=Disabled. Artificially introduce some packet lost. e.g. `3 is 3% packet lost`.|
|-w #  |Callback window sec.|      0|Second  |0=Disabled. Callback window, in seconds, for changes in the cache since last looked up.|
* The test script that is used to pound the cache can be viewed [here](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py).

### Results
|<br>Run|-c #<br>Nodes|-k #<br>Keys|-d #<br>Duration|-a #<br>Aperture|<br>Status|Avg<br>Snooze|Avg<br>SpikeHits|Avg<br>SpikeInt|Avg<br>LookUps|Avg<br>Inserts|Avg<br>Updates|Avg<br>Deletes|<br>Comment|
|:------|---:|---:|------:|-------:|:--:|-----:|-----:|-----:|----:|----:|----:|----:|:-|
|1.1    | 3  | 200|      5|  `0.01`|    |0.0550|  3392|0.0887| 2757|  584| 2382|  426|Basic test with **3** nodes using **200** unique key/value pairs running for **5** minutes with **10**ms snooze aperture.|
|1.2    | 3  | 100|      5|  `0.01`|    |0.0558|  3343|0.0899| 2868|  537| 2356|  450|Decrease key/value pairs down to **100** from 200.|
|       |    |    |       |        |    |      |      |      |     |     |     |     |  |
|2.1    | 3  | 100|      5| `0.001`|    |0.0059| 32640|0.0092|26373| 4538|23708| 4394|Decrease aperture down to **1**ms from 10ms.|
|2.2    | 3  | 100|      5|`0.0008`|    |0.0048| 40050|0.0075|31982| 5531|29112| 5407|Decrease aperture down to **0.8**ms from 1ms.|
|2.3    | 3  | 100|      5|`0.0006`|    |0.0032| 58308|0.0051|48056| 8416|41621| 8271|Decrease aperture down to **0.6**ms from 1ms.|
|2.4    | 3  | 100|      5|`0.0005`|Fail|0.0032| 58984|0.0051|47903| 8427|42251| 8306|Decrease aperture down to **0.5**ms from 1ms.|
|2.4.1  | 3  | 500|      5|`0.0005`|Fail|0.0035| 50143|0.0060|44549| 9319|31759| 8009|Increase unique key/value pairs up to **500**.|
|2.4.2  | 3  |1000|      5|`0.0005`|    |0.0036| 33640|0.0089|42509|14996| 3649| 1180|Increase unique key/value pairs up to **1000**.<br>**Some cache incoherences evictions**.|
|       |    |    |       |        |    |      |      |      |     |     |     |     |  |
|3.1    | 3  | 100|     10| `0.001`|    |0.0062| 46061|0.0130|50337| 6974|32249| 6838|Increase run duration to **10** minutes starting with **1**ms snooze aperture.|
|3.2    | 3  | 100|     10|`0.0008`|    |0.0051| 56293|0.0107|61341| 8475|39487| 8331|Decrease aperture down to **0.8**ms from 1ms.|
|3.3    | 3  | 100|     10|`0.0006`|    |0.0034| 82159|0.0073|89312|12516|57280|12363|Decrease aperture down to **0.6**ms from 1ms.<br>**Some cache incoherences evictions**.|
|3.4    | 3  | 100|     10|`0.0005`|    |0.0035| 82098|0.0073|88885|12338|57564|12196|Decrease aperture down to **0.5**ms from 1ms.|
|3.5    | 3  | 100|     10|`0.0001`|    |0.0010|      |      |     |     |     |     |Decrease aperture down to **0.1**ms from 1ms.<br>**Reached saturation. Metrics not output.**|
|       |    |    |       |        |    |      |      |      |     |     |     |     |  |
|5.1    | 5  | 100|     10|  `0.01`|    |0.0554|  6750|0.0890| 5638| 1016| 4831|  903|Increase to **5** nodes using **100** unique key/value pairs running for **5** minutes with **10**ms snooze aperture.|
|5.2    | 5  | 100|     10| `0.001`|    |0.0062| 62579|0.0096|50682| 8705|45288| 8586|Decrease aperture down to **1**ms.|
|5.3    | 5  | 100|     10|`0.0008`|    |0.0051| 74492|0.0081|60398|10537|53540|10415|Decrease aperture down to **0.8**ms.|
|5.4    | 5  | 100|     10|`0.0007`|    |0.0046| 82029|0.0073|67678|11985|58193|11851|Decrease aperture down to **0.7**ms.|
|5.5    | 5  | 100|     10|`0.0006`|Fail|0.0036|102973|0.0058|87202|15489|72115|15369|Decrease aperture down to **0.6**ms.|
|5.5.1  | 5  | 500|     10|`0.0006`|    |0.0036| 78822|0.0076|85545|25854|27115| 5670|Increase unique key/value pairs up to **500**.<br>**Lots of cache incoherences evictions**.|
|5.5.2  | 5  |1000|     10|`0.0006`|    |0.0038| 63063|0.0095|82462|29006| 5052| 2161|Increase unique key/value pairs up to **1000**.<br>**Lots of cache incoherences evictions**.|
|5.6    | 5  | 100|     10|`0.0005`|Fail|0.0035|103872|0.0058|87793|15619|72754|15499|Decrease aperture down to **0.5**ms.<br>**Reached saturation.  Not much difference from the run 5.5**.|
|       |    |    |       |        |    |      |      |      |     |     |     |     |  |
|7.1    | 7  | 100|     10|  `0.01`|    |0.0554|  8322|0.0722| 5638| 1125| 6173| 1024|Increase to **7** nodes using **100** unique key/value pairs running for **10** minutes with **10**ms snooze aperture.|
|7.2    | 7  | 100|     10| `0.008`|    |0.0445| 10559|0.0569| 7014| 1394| 7882| 1283|Decrease aperture down to **8**ms.|
|7.3    | 7  | 100|     10| `0.005`|    |0.0278| 17102|0.0351|11255| 2194|12825| 2083|Decrease aperture down to **5**ms.|
|7.4    | 7  | 100|     10| `0.002`|    |0.0117| 40385|0.0149|26959| 5232|30057| 5096|Decrease aperture down to **2**ms.<br>**Some cache incoherences evictions**.|
|7.5    | 7  | 100|     10| `0.001`|Fail|0.0063| 69338|0.0087|49150| 9721|50009| 9608|Decrease aperture down to **1**ms.|
|7.5.1  | 7  | 500|     10| `0.001`|Fail|0.0064| 70389|0.0085|48822|10093|50444| 8814|Increase unique key/value pairs up to **500**.|
|7.5.2  | 7  |1000|     10| `0.001`|    |0.0064| 46548|0.0129|48225|14954|16641| 8574|Increase unique key/value pairs up to **1000**.<br>**Lots of cache incoherences evictions**.|
|       |    |    |       |        |    |      |      |      |     |     |     |     |  |
|9.1    | 9  | 100|     10|  `0.01`|    |0.0553|  9641|0.0623| 5676| 1236| 7270| 1135|Increase to **9** nodes using **100** unique key/value pairs running for **10** minutes with **10**ms snooze aperture.|
|9.2    | 9  | 100|     10| `0.008`|    |0.0442| 11915|0.0504| 7100| 1486| 9054| 1375|Decrease aperture down to **8**ms.|
|9.3    | 9  | 100|     10| `0.005`|    |0.0279| 19153|0.0314|11021| 2356|14546| 2251|Decrease aperture down to **5**ms.|
|9.4    | 9  | 100|     10| `0.004`|    |0.0229| 23430|0.0257|13570| 2866|17827| 2737|Decrease aperture down to **4**ms.|
|9.5    | 9  | 100|     10| `0.003`|    |0.0175| 30269|0.0198|17863| 3805|22780| 3684|Decrease aperture down to **3**ms.|
|9.5.1  | 9  | 500|     10| `0.002`|Fail|0.0118| 43218|0.0139|26516| 5618|32098| 5502|Increase unique key/value pairs up to **500**.|
|9.5.2  | 9  |1000|     10| `0.002`|Fail|0.0118| 44909|0.0134|26350| 5810|33538| 5212|Increase unique key/value pairs up to **1000**.|
|       |    |    |       |        |    |      |      |      |     |     |     |     |  |
|10.1   | 9  | 100|     60|  `0.01`|Fail|0.0279| 19153|0.0314|11021| 2356|14546| 2251|Extreme test with **9** nodes using **100** unique key/value pairs running for **60** minutes with **10**ms snooze aperture.<br>**Some containers hung and didn't exit.**|
|10.2   | 9  | 100|     30|  `0.01`|Fail|      |      |      |     |     |     |     |Reduce run duration to **30** minutes.<br>**Some containers hung and didn't exit.**|
|10.3   | 9  | 100|     20|  `0.01`|Fail|      |      |      |     |     |     |     |Reduce run duration to **20** minutes.|
|       |    |    |       |        |    |      |      |      |     |     |     |     |  |
|       |    |    |       |        |    |      |      |      |     |     |     |     |  |
* Result header caption:
    * Avg Snooze      - The average pause plus processing per loop iteration in the test script.
    * Avg SpikeHits   - The average number of inserts, updates, and deletes that are called with less than **3** seconds apart.
    * Avg SpikeInt    - The average interval in seconds between insert, update, and delete operation.
    * Avg LookUps     - The average lookups performed in the test.
    * Avg Inserts     - The average inserts performed in the test.
    * Avg Updates     - The average updates performed in the test.
    * Avg Deletes     - The average deletes performed in the test.

* The following may have influence over the above results:
    * Number of running containers.  CPU may throttle down when it is too hot.
    * Python version.  The lastest version is mich faster than two versions ago.
    * Python `random.randrange()` and `time.sleep()` implementation.
    * The O/S scheduler.

### Observations
* The laptop is a freshly rebooted and is entirely dedicated to this stress test.  No other task were running on it.
  Maybe trying testing it in the cloud instead local on my laptop.
* Anecdotally, it does **not** look like `time.sleep( 0.0001 )` can yield accurate precision.
* We feel that `McCache` can handle very heavy update/delete against it.  `McCache` is **not** for you if you have a use case that pound the cache harder than `40000` changes within `0.01` second apart for `10` minutes.


### Cloud VM
TBD
