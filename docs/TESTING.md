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
$ pipenv   shell
$ podman-compose  up  --build  -d
```
or the default test script located `.\tests\run_test.bat` with the following CLI parameters:
```bash
$ pipenv   shell
$ tests/run_test  -c 9 -d 10 -l 1
```

Since the test is running locally on my laptop in a container environment, there is no physical wired network between the nodes.  We almost have a near zero communication latency between the nodes.  Lost packets does occur when the cache is highly stress.

### Logs
The log file was deposited in `./log/` sub-directory.  The following command:
```bash
$ grep  MET  ./log/mccache_debug*log  |  head -1
```
 extracted the following metric from my test run.
 ```python
15:46:19.928452860 L#1535 Im:172.18.0.4  MET  15:46:19.917445670  N=  K=  C=
{   '_process_': {
         'avgload': (3.35546875 ,3.2646484375 ,3.109375)
        ,'cputimes': scputimes(user=113111.88 ,nice=4.06 ,system=11364.92 ,idle=1635278.66 ,iowait=137.96 ,irq=0.0 ,softirq=9945.58 ,steal=0.0 ,guest=0.0 ,guest_nice=0.0)
        ,'meminfo': pmem(rss=709353472 ,vms=949870592 ,shared=10891264 ,text=4096 ,lib=0 ,data=775802880 ,dirty=0)
        ,'netioinfo': snetio(bytes_sent=56425244 ,bytes_recv=396178095 ,packets_sent=314250 ,packets_recv=2206571 ,errin=0 ,errout=0 ,dropin=0 ,dropout=0)
    },
    'mccache': {
         'count': 119
        ,'size': 49520
        ,'spikes': 99094
        ,'spikeInt': 0.0727
        ,'misses': 0
        ,'lookups': 83114
        ,'inserts': 12978
        ,'updates': 73257
        ,'deletes': 12684
        ,'evicts': 175
    }
}
```
The above have been manually formatted for readability.  For stress testing purposes, the `spike` and `spikeInt` numbers are of interest for they indicate how hard the cache was stressed with changes.  The `spikeInt`, in seconds, shows how rapid the cache was updated in a sliding five seconds window.  In the above sample, the cache was stressed with  `99094` changes and all within an average of `0.0727` seconds apart.

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
| size       | The total memory used by the cache in bytes.<br>The example above, it is `49520` bytes. |
| spikes     | The number of `INS/UPD/DEL` hits that contributed to the `spikeInt` metric.<br>The example above, `99094` operations that changes the data within a five seconds sliding window.|
| spikeInt   | The average interval between two (`UPD/DEL`) operation that are within 5 seconds sliding window.<br>This is a spike gauge on how rapid the cache is materially changing.  The smaller the number the more rapid the cache is changing.<br>The example above, it is an average `0.0727` seconds apart. |

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
|-l #  |Debug level.    |      1|        |0=Off ,1=Basic ,3=Extra ,5=Superfluous|
|-m #  |Data size mix.  |      1|        |Value message size stored in cache.  1=Small (< mtu) ,2=Large (> mtu) ,3=Mixed.|
|-p #  |Sync pulse.     |      5|Minute  |Decrease pulse value, increases synchronization.|
|-s #  |Snooze aperture.|   0.01|Fraction|Decrease snooze aperture, increase contention. 0.01=10ms ,0.001=1ms ,0.0001=0.1ms/100us|
|-y #  |Monkey tantrum. |      0|Percent |0=Disabled. Artificially introduce some packet lost. e.g. `3 is 3% packet lost`.|
|-w #  |Callback window.|      0|Second  |0=Disabled. Callback window, in seconds, for changes in the cache since last looked up.|
* The test script that is used to pound the cache can be viewed [here](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py).


#### Results of basic stress test
The results below are collected from testing output `result.txt` file and the `detail_xxx.log` files under the `.\log` sib-directory.

|Result<br>Caption|<br>Description|
|-|-|
|Avg Snooze     |The average pause plus processing time per loop iteration in the test script.|
|Avg SpikeHits  |The average number of inserts, updates, and deletes that are called with less than **5** seconds spike window.|
|Avg SpikeInt   |The average interval in seconds between insert, update, and delete operation.|
|Avg SpikeQue   |The average messages in the internal in-bound message queue.|
|Avg SpikeEvcs  |The average evictions due to cache detected cache incoherence in the cluster.
|Avg LookUps    |The average lookups performed in the test.|
|Avg Inserts    |The average inserts performed in the test.|
|Avg Updates    |The average updates performed in the test.|
|Avg Deletes    |The average deletes performed in the test.|

### Frequency Stress Test Result
|<sub><br>Run</sub>|<sub>-c #<br>Nodes</sub>|<sub>-k #<br>Keys</sub>|<sub>-p #<br>Pulse</sub>|<sub>-s #<br>Aperture</sub>|<sub>-d #<br>Duration</sub>|<sub><br>Result</sub>|<sub>Avg<br>Snooze</sub>|<sub>Avg<br>SpikeHits</sub>|<sub>Avg<br>SpikeInt</sub>|<sub>Avg<br>SpikeQue</sub>|<sub>Avg<br>SpikeEvcs</sub>|<sub>Avg<br>LookUps</sub>|<sub>Avg<br>Inserts</sub>|<sub>Avg<br>Updates</sub>|<sub>Avg<br>Deletes</sub>|<sub><br>Comment</sub>|
|:------|---:|---:|--:|-----:|---:|:----------------------------:|-----:|-----:|-----:|-----:| ----:|-----:|-----:|-----:|-----:|:-|
|3.1    |   3| 100|  3|   0.1|  10|<font color="cyan">Pass</font>|0.5459|   325|1.1222|      |      |   674|   106|   233|    38|Basic test with **3** nodes using **100** key/value pairs, sync every **5** minutes, running with **100**ms snooze aperture for **10** minutes.|
|3.1.1  |   3| 100|  3|  0.05|  10|<font color="cyan">Pass</font>|0.2750|   777|0.4024|      |      |  1238|   197|   635|   123|Decrease snooze aperture down to **0.05** second, **50**ms.|
|3.2    |   3| 100|  3|  0.01|  10|<font color="cyan">Pass</font>|0.0552|  4937|0.1215|      |      |  5907|   856|  3346|   735|Decrease snooze aperture down to **0.01** second, **10**ms.|
|3.2.1  |   3| 100|  3| 0.005|  10|<font color="cyan">Pass</font>|0.0277| 10155|0.0591|     0|     4| 11239|  1606|  7080|  1469|Decrease snooze aperture down to **0.005** second, **5**ms.|
|3.3    |   3| 100|  3| 0.001|  10|<font color="cyan">Pass</font>|0.0062| 46061|0.0130|   101|    85| 50266|  6993| 32198|  6848|Decrease snooze aperture down to **0.001** second, **1**ms.|
|3.3.1  |   3| 100|  3|0.0005|  10|<font color="cyan">Pass</font>|0.0037| 47259|0.0128|   448|   527| 82944| 17215| 12917| 17127|Decrease snooze aperture down to **0.0005** second, **0.5**ms.|
|3.3.2  |   3| 100|  3|0.0001|  10|<font color="cyan">Pass</font>|0.0015|172779|0.0035| 30877| 54420|217931| 42692| 87511| 42578|Decrease snooze aperture down to **0.0001** second, **0.1**ms.|
|       |    |    |   |      |    |                              |      |      |      |      |      |      |      |      |      |   |
|5.1    |   5| 100|  3|   0.1|  10|<font color="cyan">Pass</font>|0.5363|   519|1.0306|      |      |   664|   114|   358|    57|Increase cluster size to **5**.|
|5.1.1  |   5| 100|  3|  0.05|  10|<font color="cyan">Pass</font>|0.2754|  1355|0.4429|      |      |  1229|   241|   939|   175|Decrease snooze aperture down to **0.05** second, **50**ms.|
|5.2    |   5| 100|  3|  0.01|  10|<font color="cyan">Pass</font>|0.0552|  7362|0.0815|      |      |  5806|  1099|  5293|   970|Decrease snooze aperture down to **0.01** second, **10**ms.|
|5.2.1  |   5| 100|  3| 0.005|  10|<font color="cyan">Pass</font>|0.0281| 13673|0.0439|     0|    12| 11309|  1997|  9801|  1875|Decrease snooze aperture down to **0.005** second, **5**ms.|
|5.3    |   5| 100|  3| 0.001|  10|<font color="cyan">Pass</font>|0.0064| 30765|0.0196|   104|   715| 48831| 13142|  4571| 13052|Decrease snooze aperture down to **0.001** second, **1**ms.|
|5.3.1  |   5| 100|  3|0.0005|  10|<font color="cyan">Pass</font>|0.0036| 51547|0.0117|   412|  9518| 85916| 20593| 10445| 20510|Decrease snooze aperture down to **0.0005** second, **0.5**ms.|
|5.3.2  |   5| 100|  3|0.0001|  10|<font color="cyan">Pass</font>|0.0017|146044|0.0041|112288| 94543|183693| 44623| 67638| 44542|Decrease snooze aperture down to **0.0001** second, **0.1**ms.|
|       |    |    |   |      |    |                              |      |      |      |      |      |      |      |      |      |   |
|7.1    |   7| 100|  3|   0.1|  10|<font color="cyan">Pass</font>|0.5362|   659|0.8528|      |      |   656|   120|   474|    70|Increase cluster size to **7**.|
|7.1.1  |   7| 100|  3|  0.05|  10|<font color="cyan">Pass</font>|0.2747|  1586|0.3783|      |      |  1293|   247|  1162|   179|Decrease snooze aperture down to **0.05** second, **50**ms.|
|7.2    |   7| 100|  3|  0.01|  10|<font color="cyan">Pass</font>|0.0554|  8791|0.0683|     0|    11|  5787|  1231|  6442|  1118|Decrease snooze aperture down to **0.01** second, **10**ms.|
|7.2.1  |   7| 100|  3| 0.005|  10|<font color="cyan">Pass</font>|0.0278| 15914|0.0378|    16|    25| 11514|  2257| 11523|  2134|Decrease snooze aperture down to **0.005** second, **5**ms.|
|7.3    |   7| 100|  3| 0.001|  10|<font color="cyan">Pass</font>|0.0066| 29807|0.0202|   483|  5104| 47055| 12914|  4060| 12833|Decrease snooze aperture down to **0.001** second, **1**ms.|
|7.3.1  |   7| 100|  3|0.0005|  10|<font color="cyan">Pass</font>|0.0039| 48349|0.0125|  1193| 24343| 79999| 19323|  9785| 19241|Decrease snooze aperture down to **0.0005** second, **0.5**ms.|
|7.3.2  |   7| 100|  3|0.0001|  10|<font color="cyan">Pass</font>|0.0023|101683|0.0059|141098| 45527|135183| 37688| 26391| 37605|Decrease snooze aperture down to **0.0001** second, **0.1**ms.|
|       |    |    |   |      |    |                              |      |      |      |      |      |      |      |      |      |   |
|9.1    |   9| 100|  3|   0.1|  10|<font color="cyan">Pass</font>|0.5362|   864|0.6747|      |      |   683|   142|   632|    93|Increase cluster size to **9**.|
|9.1.1  |   9| 100|  3|  0.05|  10|<font color="cyan">Pass</font>|0.2753|  1862|0.3224|      |      |  1257|   275|  1374|   213|Decrease snooze aperture down to **0.05** second, **50**ms.|
|9.2    |   9| 100|  3|  0.01|  10|<font color="cyan">Pass</font>|0.0550|  9002|0.0667|     0|     5|  5744|  1248|  6620|  1134|Decrease snooze aperture down to **0.01** second, **10**ms.|
|9.2.1  |   9| 100|  3| 0.005|  10|<font color="cyan">Pass</font>|0.0283| 12338|0.0488|  1283|    78| 10633|  2733|  6937|  2668|Decrease snooze aperture down to **0.005** second, **5**ms.|
|9.3    |   9| 100|  3| 0.001|  10|<font color="cyan">Pass</font>|0.0072| 57628|0.0104|   719| 19994| 43410| 10724| 36278| 10626|Decrease snooze aperture down to **0.001** second, **1**ms.|
|9.3.1  |   9| 100|  3|0.0005|  10|<font color="cyan">Pass</font>|0.0050| 66906|0.0090|  4518| 55600| 62784| 16763| 33464| 16679|Decrease snooze aperture down to **0.0005** second, **0.5**ms.|
|9.3.2  |   9| 100|  3|0.0001|  10|<font color="pink">Fail</font>|0.0026| 85840|0.0070| 32104| 117686|18570| 33675| 18570| 33595|Decrease snooze aperture down to **0.0001** second, **0.1**ms.|
|       |    |    |   |      |    |                              |      |      |      |      |      |      |      |      |      |   |

### Duration Stress Test Result
|<sub><br>Run</sub>|<sub>-c #<br>Nodes</sub>|<sub>-k #<br>Keys</sub>|<sub>-p #<br>Pulse</sub>|<sub>-s #<br>Aperture</sub>|<sub>-d #<br>Duration</sub>|<sub><br>Result</sub>|<sub>Avg<br>Snooze</sub>|<sub>Avg<br>SpikeHits</sub>|<sub>Avg<br>SpikeInt</sub>|<sub>Avg<br>SpikeQue</sub>|<sub>Avg<br>SpikeEvcs</sub>|<sub>Avg<br>LookUps</sub>|<sub>Avg<br>Inserts</sub>|<sub>Avg<br>Updates</sub>|<sub>Avg<br>Deletes</sub>|<sub><br>Comment</sub>|
|:------|---:|---:|--:|-----:|---:|:----------------------------:|-----:|-----:|-----:|-----:| ----:|-----:|-----:|-----:|-----:|:-|
|3.2.1  |   3| 100|  3|  0.01|  20|<font color="cyan">Pass</font>|0.0550| 10242|0.1172|     0|     2| 11852|  1660|  7056|  1515|Basic test with **3** nodes using **100** key/value pairs, sync every **3** minutes, running for **20** minutes with **0.01** second (**10**ms) snooze aperture.|
|3.2.2  |   3| 100|  3|  0.01|  40|<font color="cyan">Pass</font>|0.0555| 20831|0.1152|     0|     4| 23795|  3269| 14427|  3092|Increase run duration to **40** minutes.|
|3.2.3  |   3| 100|  3|  0.01|  60|<font color="cyan">Pass</font>|0.0554| 31025|0.1160|     0|    11| 35772|  4822| 21507|  4618|Increase run duration to **60** minutes, **1** hour.|
|3.2.4  |   3| 100|  3|  0.01| 120|<font color="cyan">Pass</font>|0.0558| 62462|0.1153|     0|    24| 71425|  9498| 43591|  9195|Increase run duration to **120** minutes, **2** hours.|
|3.2.5  |   3| 100|  3|  0.01| 480|<font color="cyan">Pass</font>|      |      |      |      |      |      |      |      |      |Increase run duration to **480** minutes, **8** hours.|
|       |    |    |   |      |    |                              |      |      |      |      |      |      |      |      |      |  |
|5.2.1  |   5| 100|  3|  0.01|  20|<font color="cyan">Pass</font>|0.0557| 14261|0.0841|     0|    44| 12628|  2045| 10297|  1907|Increase the basic (`3.2.1`) test to **5** nodes.|
|5.2.2  |   5| 100|  3|  0.01|  40|<font color="cyan">Pass</font>|0.0559| 27646|0.0868|     0|   131| 25425|  3937| 19891|  3774|Increase run duration to **40** minutes.|
|5.2.3  |   5| 100|  3|  0.01|  60|<font color="cyan">Pass</font>|0.0561| 41403|0.0869|     0|   191| 38352|  5845| 29825|  5660|Increase run duration to **60** minutes, **1** hour.|
|5.2.4  |   5| 100|  3|  0.01| 120|<font color="cyan">Pass</font>|0.0562| 82895|0.0869|     0|   374| 76837| 11478| 60055| 11198|Increase run duration to **120** minutes, **2** hours.|
|5.2.5  |   5| 100|  3|  0.01| 480|<font color="cyan">Pass</font>|      |      |      |      |      |      |      |      |      |Increase run duration to **480** minutes, **8** hours.|
|       |    |    |   |      |    |                              |      |      |      |      |      |      |      |      |      |  |
|7.1.1  |   7| 100|  3|  0.01|  20|<font color="cyan">Pass</font>|0.0554| 16674|0.0720|     0|   114| 13388|  2252| 12287|  2126|Increase the basic (`3.2.1`) test to **7** nodes.|
|7.1.2  |   7| 100|  3|  0.01|  40|<font color="cyan">Pass</font>|0.0564| 32818|0.0731|     0|   673| 27458|  4376| 24192|  4212|Increase run duration to **40** minutes.|
|7.1.3  |   7| 100|  3|  0.01|  60|<font color="cyan">Pass</font>|0.0564| 48733|0.0739|     0|   827| 41329|  6488| 35870|  6304|Increase run duration to **60** minutes, **1** hour.|
|7.1.4  |   7| 100|  3|  0.01| 120|<font color="cyan">Pass</font>|0.0567| 99094|0.0727|     0|  2007| 83114| 12978| 73257| 12684|Increase run duration to **120** minutes, **2** hours.|
|7.1.5  |   7| 100|  3|  0.01| 480|<font color="cyan">Pass</font>|      |      |      |      |      |      |      |      |      |Increase run duration to **480** minutes, **8** hours.|
|       |    |    |   |      |    |                              |      |      |      |      |      |      |      |      |      |  |
|9.1.1  |   9| 100|  3|  0.01|  20|<font color="cyan">Pass</font>|0.0559| 18970|0.0633|     0|   598| 13863|  2407| 14280|  2272|Increase the basic (`3.2.1`) test to **9** nodes.|
|9.1.2  |   9| 100|  3|  0.01|  40|<font color="cyan">Pass</font>|0.0568| 38011|0.0631|     0|  1624| 29986|  4776| 28570|  4619|Increase run duration to **40** minutes.|
|9.1.3  |   9| 100|  3|  0.01|  60|<font color="cyan">Pass</font>|0.0564| 56825|0.0634|     0|  1776| 43593|  7052| 42831|  6861|Increase run duration to **60** minutes, **1** hour.|
|9.1.4  |   9| 100|  3|  0.01| 120|<font color="cyan">Pass</font>|0.0572|111328|0.0647|     0|  5191| 84487| 13947| 83544| 13668|Increase run duration to **120** minutes, **2** hours.|
|9.1.5  |   9| 100|  3|  0.01| 480|<font color="cyan">Pass</font>|      |      |      |      |      |      |      |      |      |Increase run duration to **480** minutes, **8** hours.|
|       |    |    |   |      |    |                              |      |      |      |      |      |      |      |      |      |  |

* To be completely transparent, some failures was encountered running the above regression stress tests and upon rebooting the tests passes.
* Interpreting the results.
    1. Watch the average snooze (pause plus processing) time per iteration.  This number is an indicator of the latency between cache updates.
    2. Watch the average number of spike count and how close they are with the average spike interval.  These 2 number are indicators of how hard the cache is pounded.
    3. Watch the average spike queue depth.  This number is an indicator if the cache is keeping up with inbound changes.
    4. Watch the average spike eviction.  This number is an indicator of the test randomness of generating an update to the same key at the "same" time by at different nodes.
* The following may have influence over the above results:
    * The class of machine the test was ran on.
    * Number of running containers and load on them.  CPU may throttle down when it is too hot.
    * Python version.  The latest version is much faster than two versions ago.  This test was ran using Python version `3.12.5`.
    * Python `random.randrange()` and `time.sleep()` implementation.
    * The O/S scheduler.

### Observations
* As more stress is applied to the cache, the inbound queue starts to back up.  This is by designed as long as it is not too deep and only you  can decided how deep is acceptable.
    * Stress is generated from the increased number of nodes plus a high frequency (snooze < **0.005** second, **5** ms).
* More detail logging will require more processing and do fail the tests.  The tests disable logging with the `-l 0` CLI option.
* The more nodes, the longer it takes to for the other nodes to receive message.  **5** nodes have about **8** seconds latency when tested with very high frequency updates (<= `0.005` ms snooze).
* Some of my containers hang after running more than **15** minutes under load.
* Anecdotally, it does **not** look like `time.sleep( 0.0001 )` can yield accurate precision.
* `McCache` can handle very heavy update/delete against it.
    * If you have an use case where the cache is pounded **less** than once every **50**ms, sustained for **10** minutes, `McCache` may be suitable for you.


### Cloud VM
TBD
