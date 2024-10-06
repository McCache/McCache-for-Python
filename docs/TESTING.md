# Testing
The following is the stress testing performed on my laptop.

### Local Hardware
```
Lenovo P14s laptop
    O/S:    Windows 11 Pro
    CPU:    AMD Ryzen 7 Pro 6850U, 8 cores
    Clock:  2.7 GHz (Base)  4.7 GHz (Turbo)
    RAM:    32 Gib
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
This stress test is intended to find the breaking point for `McCache` on a given class of machine.  This is an edge case where in a normal usage the probability of two or more nodes updating the same key/value at the very same time is extremely low.

The test script run for a certain duration pausing a faction of a second in each iteration in a loop.  Based on the sleep aperture, a snooze value is calculated to keep the value within the aperture precision up to ten times the aperture value.  e.g. If the aperture value is `0.01`, the snooze value shall be between `0.01` and `0.1`.
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

The machine is rebooted before each set of test runs and is dedicated to run the test without any other programs running.

#### Command used
Bash shell:
```bash
$ tests/run_test  -t 7200 -L 0 -C 9 -K 100 -A 0.01 -R 10 -T 4
```
Windows Command Prompt:
```cmd
$ tests\run_test  -t 7200 -L 0 -C 9 -K 100 -A 0.01 -R 10 -T 4
```
The CLI parameters are:
|Flag  |Description             |Default|Unit   |Comment    |
|:-----|:-----------------------|------:|-------|:----------|
|`-D`  |Use Docker container.   |       |       |           |
|`-P`  |Use Podman container.   |       |       |           |
|`-L #`|Debug level.            |      0|Level  |0=Off ,1=Basic ,3=Extra ,5=Superfluous |
|`-C #`|Cluster size.           |      3|Nodes  |Max is 9.  |
|`-K #`|Max key entries to use. |    200|Entries|           |
|`-A #`|Sleep aperture.         |   0.05|Second |1=1s ,0.1=100ms ,0.01=10ms ,0.001=1ms ,0.0005=0.5ms ,0.0001=0.1ms/100us    |
|`-M #`|Data size mix.          |      1|       |1=Small ,2=Big ,3=Mix. |
|`-R #`|Run duration.           |      5|Minute |           |
|`-T #`|Monkey tantrum.         |      0|Percent|Percent of dropped packets. 0=Disabled.|
|`-t #`|Time-to-live.           |   3600|Second |           |
|`-e #`|Maximum cache entries.  |    256|Entries|           |
|`-s #`|Maximum cache storage.  |1048576|Bytes  |           |
|`-p #`|Cache sync pulse.       |      5|Second |           |
|`-w #`|Callback spike window.  |      0|Second |           |
* The test script that is used to pound the cache can be viewed [here](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py).

#### Container network latency
The following was obtain by login into a container and `ping` the another.
```
    root@843420eb1cf8:/home/mccache#  ping  172.18.0.4  -c 9
    PING 172.18.0.4 (172.18.0.4) 56(84) bytes of data.
    64 bytes from 172.18.0.4: icmp_seq=1 ttl=64 time=0.066 ms
    64 bytes from 172.18.0.4: icmp_seq=2 ttl=64 time=0.086 ms
    64 bytes from 172.18.0.4: icmp_seq=3 ttl=64 time=0.049 ms
    64 bytes from 172.18.0.4: icmp_seq=4 ttl=64 time=0.133 ms
    64 bytes from 172.18.0.4: icmp_seq=5 ttl=64 time=0.052 ms
    64 bytes from 172.18.0.4: icmp_seq=6 ttl=64 time=0.067 ms
    64 bytes from 172.18.0.4: icmp_seq=7 ttl=64 time=0.186 ms
    64 bytes from 172.18.0.4: icmp_seq=8 ttl=64 time=0.053 ms
    64 bytes from 172.18.0.4: icmp_seq=9 ttl=64 time=0.054 ms

    --- 172.18.0.4 ping statistics ---
    9 packets transmitted, 9 received, 0% packet loss, time 8357ms
    rtt min/avg/max/mdev = 0.049/0.082/0.186/0.044 ms
```
* The average round trip for a packet is `0.082`ms or `0.041`ms latency for single packet one way transmission.

#### Results of basic stress test
The results below are collected from testing output `result.txt` file and the `detail_xxx.log` files under the `.\log` sib-directory.

|Result<br>Caption|<br>Description|
|-----------------|---------------|
|Avg Snooze       |The average pause plus processing time per loop iteration in the test script.|
|Avg SpikeHits    |The average number of inserts, updates, and deletes that are called with less than **5** seconds spike window.|
|Avg SpikeInt     |The average interval in seconds between insert, update, and delete operation.|
|Avg SpikeQue     |The average messages in both the internal in/out bound message queue.|
|Avg SpikeEvcs    |The average evictions due to cache detected cache incoherence in the cluster.
|Avg LookUps      |The average lookups performed in the test.|
|Avg Inserts      |The average inserts performed in the test.|
|Avg Updates      |The average updates performed in the test.|
|Avg Deletes      |The average deletes performed in the test.|

### Frequency Stress Test Result
|<sub><br>Run</sub>|<sub>-C #<br>Nodes</sub>|<sub>-K #<br>Keys</sub>|<sub>-A #<br>Aperture</sub>|<sub>-R #<br>Duration</sub>|<sub><br>Result</sub>|<sub>Avg<br>Snooze</sub>|<sub>Avg<br>SpikeHits</sub>|<sub>Avg<br>SpikeInt</sub>|<sub>Avg&nbsp;InQ<br>avg&nbsp;/&nbsp;max</sub>|<sub>Avg&nbsp;OutQ<br>avg&nbsp;/&nbsp;max</sub>|<sub>Avg<br>LookUps</sub>|<sub>Avg<br>Inserts</sub>|<sub>Avg<br>Updates</sub>|<sub>Avg<br>Deletes</sub>|<sub><br>Comment</sub>|
|:------|---:|---:|-----:|---:|:----------------------------:|-----:|-----:|-----:|:--------:|:---------:|------:|------:|------:|------:|:--|
|3.1    |   3| 100|   0.1|  10|<font color="cyan">Pass</font>|0.5362|   392|1.0754|  2 / 18  |  89 / 189 |    849|    123|    263|     47|   |
|3.2    |   3| 100|  0.01|  10|<font color="cyan">Pass</font>|0.0553|  5094|0.1178|  2 / 37  |  85 / 190 |   6051|    874|   3467|    753|   |
|3.2.1  |   3| 100| 0.005|  10|<font color="cyan">Pass</font>|0.0281| 10230|0.0586|  2 / 41  |  55 / 128 |  11543|   1619|   7129|   1482|   |
|3.3    |   3| 100| 0.001|  10|<font color="cyan">Pass</font>|0.0059| 48129|0.0125|  1 / 49  |  49 / 427 |  53169|   7318|  33641|   7170|   |
|3.3.1  |   3| 100|0.0005|  10|<font color="cyan">Pass</font>|0.0033| 86822|0.0069|  2 / 31  |  12 / 141 |  95255|  13059|  60844|  12919|   |
|3.3.2  |   3| 100|0.0001|  10|<font color="cyan">Pass</font>|0.0011|247783|0.0032|  4 / 412 |  48 / 526 | 280336|  41755| 164428|  41600|   |
|       |    |    |      |    |                              |      |      |      |          |           |       |       |       |       |   |
|5.1    |   5| 100|   0.1|  10|<font color="cyan">Pass</font>|0.5361|   496|0.9102|  4 / 41  | 273 / 691 |   1182|    114|    356|     57|   |
|5.2    |   5| 100|  0.01|  10|<font color="cyan">Pass</font>|0.0553|  6795|0.0883|  3 / 49  | 124 / 326 |   6777|   1032|   4843|    920|   |
|5.2.1  |   5| 100| 0.005|  10|<font color="cyan">Pass</font>|0.0278| 13705|0.0438|  2 / 64  | 127 / 440 |  12518|   1970|  10150|   1857|   |
|5.3    |   5| 100| 0.001|  10|<font color="cyan">Pass</font>|0.0062| 61914|0.0097|  3 / 430 | 141 / 833 |  51688|   8682|  44677|   8555|   |
|5.3.1  |   5| 100|0.0005|  10|<font color="cyan">Pass</font>|0.0035|104876|0.0057|  4 / 473 |  74 / 861 |  88751|  15848|  73310|  15718|   |
|5.3.2  |   5| 100|0.0001|  10|<font color="cyan">Pass</font>|0.0015|180155|0.0033| 11 / 1747|  24 / 421 | 204686|  46191|  87858|  46107|   |
|       |    |    |      |    |                              |      |      |      |          |           |       |       |       |       |   |
|7.1    |   7| 100|   0.1|  10|<font color="cyan">Pass</font>|0.5438|   721|0.7391| 93 / 1962| 429 / 1570|   1933|    130|    528|     78|   |
|7.2    |   7| 100|  0.01|  10|<font color="cyan">Pass</font>|0.0549|  8154|0.0736| 49 / 1669| 272 / 1116|   7465|   1185|   5882|   1087|   |
|7.2.1  |   7| 100| 0.005|  10|<font color="cyan">Pass</font>|0.0281| 16016|0.0375| 44 / 1533| 264 / 1280|  13235|   2193|  11751|   2072|   |
|7.3    |   7| 100| 0.001|  10|<font color="cyan">Pass</font>|0.0064| 67556|0.0089| 11 / 1231|  45 / 478 |  50473|  10055|  47564|   9937|   |
|7.3.1  |   7| 100|0.0005|  10|<font color="cyan">Pass</font>|0.0039| 99322|0.0060| 13 / 1478|  34 / 818 |  81542|  18389|  62639|  18294|   |
|7.3.2  |   7| 100|0.0001|  10|<font color="pink">Fail</font>|0.0025| 82234|0.0073| 71 / 2993|  76 / 1909| 122789|  35774|  10773|  35687|   |
|7.3.2.1|   7| 500|0.0001|  10|<font color="cyan">Pass</font>|0.0019|153891|0.0039| 45 / 2770| 115 / 5123| 160715|  46753|  60387|  28012|   |
|       |    |    |      |    |                              |      |      |      |          |           |       |       |       |       |   |
|9.1    |   9| 100|   0.1|  10|<font color="cyan">Pass</font>|0.5454|   833|0.6524|462 / 4282| 691 / 1859|   2606|    139|    621|     86|   |
|9.2    |   9| 100|  0.01|  10|<font color="cyan">Pass</font>|0.0556|  9476|0.0633|258 / 3047| 631 / 2007|   7930|   1240|   7102|   1134|   |
|9.2.1  |   9| 100| 0.005|  10|<font color="cyan">Pass</font>|0.0279| 19146|0.0314|210 / 3003| 780 / 2199|  13549|   2361|  14536|   2249|   |
|9.3    |   9| 100| 0.001|  10|<font color="cyan">Pass</font>|0.0068| 65166|0.0092| 39 / 2174|  97 / 1172|  46928|  11023|  43215|  10928|   |
|9.3.1  |   9| 100|0.0005|  10|<font color="cyan">Pass</font>|0.0048| 66477|0.0090| 73 / 2887|  97 / 1521|  65900|  17500|  31562|  17415|   |
|9.3.2  |   9| 100|0.0001|  10|<font color="pink">Fail</font>|0.0029| 70108|0.0086|210 / 4243|1136 / 5495| 103436|  30736|   8713|  30660|   |
|9.3.2.1|   9| 500|0.0001|  10|<font color="pink">Fail</font>|0.0030| 76544|0.0079|210 / 4243|1136 / 5495|  99775|  29904|  16951|  28654|   |
|       |    |    |      |    |                              |      |      |      |          |           |       |       |       |       |   |
* 9 nodes are more than the 8 cores on the test machine.

### Duration Stress Test Result
```bash
$ tests/run_test  -t 7200 -L 0 -C 9 -K 100 -A 0.01 -R 60 -T 4
```
|<sub><br>Run</sub>|<sub>-C #<br>Nodes</sub>|<sub>-K #<br>Keys</sub>|<sub>-A #<br>Aperture</sub>|<sub>-R #<br>Duration</sub>|<sub><br>Result</sub>|<sub>Avg<br>Snooze</sub>|<sub>Avg<br>SpikeHits</sub>|<sub>Avg<br>SpikeInt</sub>|<sub>Avg&nbsp;InQ<br>avg&nbsp;/&nbsp;max</sub>|<sub>Avg&nbsp;OutQ<br>avg&nbsp;/&nbsp;max</sub>|<sub>Avg<br>LookUps</sub>|<sub>Avg<br>Inserts</sub>|<sub>Avg<br>Updates</sub>|<sub>Avg<br>Deletes</sub>|<sub><br>Comment</sub>|
|:------|---:|---:| ----:|---:|:----------------------------:|-----:|------:|-----:|:--------:|:---------:|--------:|----------:|----------:|----------:|:-|
|9.2.1  |   9| 100|  0.01| 480|<font color="cyan">Pass</font>|0.0162|5497602|0.0047|  4 /1556 | 15 / 1432 |  6516186|    2472578|     552526|    2466800|  |
|9.2.2  |   9| 100| 0.005| 480|<font color="cyan">Pass</font>|      |       |      |          |           |         |           |           |           |  |
|9.2.3  |   9| 100| 0.001| 480|<font color="cyan">Pass</font>|      |       |      |          |           |         |           |           |           |  |
|9.2.4  |   9| 100|0.0005| 480|<font color="cyan">Pass</font>|      |       |      |          |           |         |           |           |           |  |
|9.2.5  |   9| 100|0.0001| 480|<font color="cyan">Pass</font>|      |       |      |          |           |         |           |           |           |  |
|       |    |    |      |    |                              |      |       |      |          |           |         |           |           |           |  |
|9.2.6  |   9| 100| 0.005|1440|<font color="cyan">Pass</font>|      |       |      |          |           |         |           |           |           |  |
|9.2.7  |   9| 100| 0.001|1440|<font color="cyan">Pass</font>|      |       |      |          |           |         |           |           |           |  |
|9.2.8  |   9| 100|0.0005|1440|<font color="cyan">Pass</font>|      |       |      |          |           |         |           |           |           |  |
|9.2.9  |   9| 100|0.0001|1440|<font color="cyan">Pass</font>|      |       |      |          |           |         |           |           |           |  |

* Interpreting the results.
    1. Watch the average snooze (pause plus processing) time per iteration.  This number is an indicator of the latency between cache updates.
    2. Watch the average number of spike count and how close they are with the average spike interval.  These 2 number are indicators of how hard the cache is pounded.
    3. Watch the average queues depth.  This number is an indicator if the cache is keeping up with processing.
    4. Watch the average spike eviction.  This number is an indicator of the test randomness of generating an update to the same key at the "same" time by at different nodes.
* The following may have subtle influence over the above results:
    * The class of machine the test was ran on.
    * Number of running containers and load from them.  CPU may throttle down when it is too hot.
    * Python version.  The latest version is much faster than two versions ago.  This test was ran using Python version `3.12.5`.
    * Python `random.randrange()` and `time.sleep()` implementation.
    * The O/S scheduler.
    * Simulated 4% packet drop.

### Docker stats
The following is a snapshot of the Docker containers running a stress test.  SEE: [Docker stats](https://docs.docker.com/reference/cli/docker/container/stats/) for detail.
```bash
    $ docker stats
    CONTAINER ID   NAME        CPU %     MEM USAGE / LIMIT     MEM %     NET I/O          BLOCK I/O   PIDS
    16bf2f64db6a   mccache01   82.33%    26.52MiB / 5.702GiB   0.45%     5.19GB / 547MB   0B / 0B     8
    b18882fbd621   mccache02   76.60%    27.11MiB / 5.702GiB   0.46%     5.19GB / 581MB   0B / 0B     8
    cceb8e046682   mccache03   74.43%    28.16MiB / 5.702GiB   0.48%     5.19GB / 581MB   0B / 0B     8
    4b8a1429f4af   mccache04   76.94%    28.28MiB / 5.702GiB   0.48%     5.19GB / 581MB   0B / 0B     8
    c6c59a509fcd   mccache05   77.35%    28.25MiB / 5.702GiB   0.48%     5.19GB / 581MB   0B / 0B     8
    631d4a11b17c   mccache06   75.97%    28.30MiB / 5.702GiB   0.48%     5.19GB / 581MB   0B / 0B     8
    455363b958dc   mccache07   78.28%    25.37MiB / 5.702GiB   0.43%     5.19GB / 581MB   0B / 0B     8
    7d31d9244b92   mccache08   87.03%    29.87MiB / 5.702GiB   0.51%     5.19GB / 580MB   0B / 0B     8
    f53abde9fdeb   mccache09   76.87%    27.14MiB / 5.702GiB   0.46%     5.19GB / 581MB   0B / 0B     8
```

### Observations
* As more stress is applied to the cache, the outbound queue starts to back up.  This is by designed as long as it is not too deep and only you can decided how deep is acceptable.
    * Stress is generated from the increased number of nodes plus a high frequency (snooze < **0.05** second, **50** ms).
* More detail logging will require more processing.  The tests disable logging with the `-L 0` CLI option.
* The more nodes, the longer it takes to for the other nodes to receive message.  **5** nodes have about **8** seconds latency when tested with very high frequency updates (<= `0.005` ms snooze).
* Anecdotally, it does **not** look like `time.sleep( 0.0001 )` can yield accurate precision.
* `McCache` can handle very heavy update/delete against it.
    * If you do **not** have an use case where the cache is pounded **less** than once every **50**ms, sustained for **10** minutes, `McCache` may be suitable for you.


### Cloud VM
TBD
