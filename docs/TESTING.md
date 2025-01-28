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
#  Bash shell
$  pipenv   shell
$  podman-compose  up  --build  -d
```
or the test script with the following CLI parameters:
```bash
$  pipenv   shell
$  tests/run_test  -C 9 -R 10 -L 1
```
```cmd
:: Windows terminal
$  pipenv   shell
$  tests\run_test.bat  -C 9 -R 10 -L 1
```

Since the test is running locally on my laptop in a container environment, there is no physical wired network between the nodes.  We almost have a near zero communication latency between the nodes.  Lost packets does occur when the cache is highly stress.

### Logs
The log file was deposited in `./log/` sub-directory.  The following command:
```bash
$ grep  MET ./log/mccache_debug*log  |  head -1
```
 extracted the following metric from my test run.
 ```python
15:46:19.928452860 L#1535 Im:172.18.0.4  MET  15:46:19.917445670  N=  K=  C=
{   'process': {
        'avgload':  '(0.29345703125, 0.40478515625, 0.22216796875)',
        'cputimes': 'scputimes(user=532.02, nice=1.07, system=556.2, idle=494926.47, iowait=53.06, irq=0.0, softirq=67.45, steal=0.0, guest=0.0, guest_nice=0.0)',
        'meminfo':  'pmem(rss=30359552, vms=413962240, shared=10969088, text=4096, lib=0, data=63111168, dirty=0)',
        'netioinfo':'snetio(bytes_sent=225880, bytes_recv=1130502, packets_sent=1247, packets_recv=6236, errin=0, errout=0, dropin=0, dropout=0)'
    }
    'mccache': {
        'count':    227,
        'deletes':  172,
        'evicts':   0,
        'inserts':  399,
        'lookups':  664,
        'misses':   0,
        'size':     38264,
        'spikeInt': 0.0484,
        'spikes':   1239,
        'updates':  668
    },
    'mqueue': {
        'ibq': {'avgsize': 1.76 ,'count': 3095  ,'maxsize': 3,
                'opc': {'ACK': 1002 ,'DEL': 133 ,'INS': 327 ,'REQ': 18 ,'SYC': 4 ,'UPD': 529}
        },
        'obq': {'avgsize': 5.30 ,'count': 33    ,'maxsize': 15,
                'opc': {'ACK': 989  ,'DEL': 39  ,'INS': 75  ,'REQ': 3  ,'SYC': 1 ,'UPD': 157}
        }
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
|**`mqueue`**||
| ibq.count  | In-bound arrived message count.|
| ibq.avgsize| In-bound average queue depth inferred from `queue.qsize()`.|
| ibq.maxsize| In-bound deepest queue depth inferred from `queue.qsize()`.|
| obq.count  | Out-bound arrived message count.|
| obq.avgsize| Out-bound average queue depth inferred from `queue.qsize()`.|
| obq.maxsize| Out-bound deepest queue depth inferred from `queue.qsize()`.|
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
#  Bash shell
$  tests/run_test  -t 7200 -L 0 -C 9 -K 100 -A 0.01 -R 10 -T 4 -s 1048576
```
Windows Command Prompt:
```cmd
:: Windows terminal
$  tests\run_test  -t 7200 -L 0 -C 9 -K 100 -A 0.01 -R 10 -T 4 -s 1048576
```
The CLI parameters are:
|Flag&nbsp;&nbsp;&nbsp;|Description             |Default|Unit   |Comment    |
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
|`-s #`|Maximum cache storage.  |8388608|Bytes  |           |
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
* You need to take this into consideration interpreting the stress test result.

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
|<sub><br>Run</sub>|<sub>-C #<br>Nodes</sub>|<sub>-K #<br>Keys</sub>|<sub>-A #<br>Aperture</sub>|<sub>-R #<br>Duration</sub>|<sub><br>Result</sub>|<sub>Avg<br>Snooze</sub>|<sub>Avg<br>SpikeHits</sub>|<sub>Avg<br>SpikeInt</sub>|<sub>Avg&nbsp;InQ<br>avg&nbsp;/&nbsp;max</sub>|<sub>Avg&nbsp;OutQ<br>avg&nbsp;/&nbsp;max</sub>|<sub>Avg<br>LookUps</sub>|<sub>Avg<br>Inserts</sub>|<sub>Avg<br>Updates</sub>|<sub>Avg<br>Deletes</sub>|<sub>Avg<br>Evicts</sub>|<sub><br>Comment</sub>|
|:------|---:|---:|-----:|---:|:----------------------------:|-----:|-----:|-----:|:-----------:|:-----------:|------:|------:|------:|------:|---:|:--|
|3.1    |   3| 100|   0.1|  10|<font color="cyan">Pass</font>|0.1419|  2802|0.2142|    1 / 2    |   1 / 2     |   5154|    607|   1758|    437|   0|   |
|3.2    |   3| 100|  0.01|  10|<font color="cyan">Pass</font>|0.0146| 27316|0.0220|    1 / 5    |   1 / 5     |  50064|   4872|  17819|   4505| 120|   |
|3.2.1  |   3| 100| 0.005|  10|<font color="cyan">Pass</font>|0.0052| 72131|0.0083|    1 / 7    | 333 / 834   | 135213|  12888|  46599|  12083| 563|5 ms aperture.|
|3.3    |   3| 100| 0.001|  10|<font color="cyan">Pass</font>|0.0017|198865|0.0030|    1 / 9    | 967 / 7207  | 379863|  35167| 128785|  33886|1027|1 ms aperture.|
|3.3.1  |   3| 100|0.0005|  10|<font color="cyan">Pass</font>|0.0010|341951|0.0018|    2 / 22   | 488 / 16383 | 640322|  60186| 221833|  58510|1424|   |
|3.3.2  |   3| 100|0.0001|  10|<font color="cyan">Pass</font>|0.0009|336611|0.0018|    5 / 57   | 312 / 15699 | 568502|  59249| 218371|  57333|1667|   |
|       |    |    |      |    |                              |      |      |      |             |             |       |       |       |       |    |   |
|5.1    |   5| 100|   0.1|  10|<font color="cyan">Pass</font>|0.1439|  4534|0.1323|    2 / 11   |    3 / 10   |   7925|    949|   2846|    739|   0|   |
|5.2    |   5| 100|  0.01|  10|<font color="cyan">Pass</font>|0.0145| 44875|0.0134|    2 / 13   |    1 / 9    |  78551|   8230|  28659|   7927|  59|   |
|5.2.1  |   5| 100| 0.005|  10|<font color="cyan">Pass</font>|0.0053|114206|0.0053|    2 / 40   |  831 / 2763 | 201024|  21428|  71603|  20613| 564|5 ms aperture.|
|5.3    |   5| 100| 0.001|  10|<font color="cyan">Pass</font>|0.0017|337663|0.0018|    2 / 24   | 1216 /10716 | 611913|  62652| 212611|  60213|2190|1 ms aperture.|
|5.3.1  |   5| 100|0.0005|  10|<font color="cyan">Pass</font>|0.0012|522466|0.0011|  113 / 11710|  357 /16383 | 853127|  96983| 328757|  92861|3877|Took an average of ` 3.5` minutes to dequeue after the testing have stop.|
|5.3.2  |   5| 100|0.0001|  10|<font color="cyan">Pass</font>|0.0007|625592|0.0010|  114 / 32767|   454 / 16383|1387929| 148397| 328811|  84700|5540|Took an average of ` 4.5` minutes to dequeue after the testing have stop.|
|       |    |    |      |    |                              |      |      |      |             |             |       |       |       |       |    |   |
|7.1    |   7| 100|   0.1|  10|<font color="cyan">Pass</font>|0.1414|  6459|0.0929|    2 / 9    |    1 / 2    |  11030|   1284|   4139|   1036|   0|   |
|7.2    |   7| 100|  0.01|  10|<font color="cyan">Pass</font>|0.0145| 64547|0.0093|    2 / 26   |    1 / 11   | 109398|  11842|  41115|  11361| 230|   |
|7.2.1  |   7| 100| 0.005|  10|<font color="cyan">Pass</font>|0.0053|158618|0.0038|    2 / 54   |  706 / 4237 | 274852|  30035|  98801|  28845| 940|Took an average of ` 2.0` minutes to dequeue after the testing have stop.|
|7.3    |   7| 100| 0.001|  10|<font color="cyan">Pass</font>|0.0022|341254|0.0018|    6 / 559  |  285 / 12653| 612992|  63390| 214733|  59933|3203|Took an average of ` 5.0` minutes to dequeue after the testing have stop.|
|7.3.1  |   7| 100|0.0005|  10|<font color="cyan">Pass</font>|0.0020|280724|0.0021|30196 / 32768|  197 / 21330| 569234|  67248| 146481|  63954|3043|Took an average of ` 7.5` minutes to dequeue after the testing have stop.|
|7.3.2  |   7| 100|0.0001|  10|<font color="cyan">Pass</font>|0.0009|672400|0.0009| 5069 / 32768|10829 / 32767|1405468|207267| 256967| 128248|79927|Took an average of `11.5` minutes to dequeue after the testing have stop.|
|       |    |    |      |    |                              |      |      |      |             |             |       |       |       |       |    |   |
|9.1    |   9| 100|   0.1|  10|<font color="cyan">Pass</font>|0.1430|  8277|0.0725|    3 / 17   |    2 / 6    |  13550|   1679|   5173|   1417|   8|   |
|9.2    |   9| 100|  0.01|  10|<font color="cyan">Pass</font>|0.0146| 81552|0.0074|    3 / 92   |    7 / 53   | 134950|  15127|  51548|  14446| 431|   |
|9.2.1  |   9| 100| 0.005|  10|<font color="cyan">Pass</font>|0.0056|194818|0.0031|    6 / 389  |  739 / 6485 | 325658|  37229| 120615|  35254|1720|Took an average of ` 2.0` minutes to dequeue after the testing have stop.|
|9.3    |   9| 100| 0.001|  10|<font color="cyan">Pass</font>|0.0028|291969|0.0021| 6830 / 23602|  198 / 14222| 583991|  63727| 164765|  58680|4800|Took an average of ` 9.0` minutes to dequeue after the testing have stop.|
|9.3.1  |   9| 100|0.0005|  10|<font color="cyan">Pass</font>|0.0017|394400|0.0015| 5482 / 32768|10050 / 32767| 650617| 128083| 138478| 126198|1648|Took an average of ` 8.5` minutes to dequeue after the testing have stop.|
|9.3.2  |   9| 100|0.0001|  10|<font color="cyan">Pass</font>|0.0012|424483|0.0014|62875 / 65536|  262 / 35467| 680510| 162123| 100481| 159182|2706|Took an average of `17.0` minutes to dequeue after the testing have stop.|
|       |    |    |      |    |                              |      |      |      |             |             |       |       |       |       |    |   |
* 9 nodes are more than the 8 cores on the test machine.

### Duration Stress Test Result
```bash
$ tests/run_test  -t 7200 -L 0 -C 9 -K 100 -A 0.01 -R 480 -T 4 -s 1048576
```
|<sub><br>Run</sub>|<sub>-C #<br>Nodes</sub>|<sub>-K #<br>Keys</sub>|<sub>-A #<br>Aperture</sub>|<sub>-R #<br>Duration</sub>|<sub><br>Result</sub>|<sub>Avg<br>Snooze</sub>|<sub>Avg<br>SpikeHits</sub>|<sub>Avg<br>SpikeInt</sub>|<sub>Avg&nbsp;InQ<br>avg&nbsp;/&nbsp;max</sub>|<sub>Avg&nbsp;OutQ<br>avg&nbsp;/&nbsp;max</sub>|<sub>Avg<br>LookUps</sub>|<sub>Avg<br>Inserts</sub>|<sub>Avg<br>Updates</sub>|<sub>Avg<br>Deletes</sub>|<sub>Avg<br>Evicts</sub>|<sub><br>Comment</sub>|
|:------|---:|---:| ----:|---:|:----------------------------:|-----:|------:|-----:|:---------:|:---------:|--------:|----------:|----------:|----------:|---:|:-|
|9.2.1  |   9| 100|  0.01| 480|<font color="cyan">Pass</font>|0.0145| 5700951|0.0051| 4 / 653  |  12 / 2621|  6783081|    2482802|     735515|    2477708|4981|Took an average of `17.0` minutes to dequeue after the testing have stop.|
|9.2.2  |   9| 100|  0.01|1440|<font color="cyan">Pass</font>|0.0155|17089517|0.0047| 4 / 802  |   8 / 322 | 19551763|    8010656|    1068399|    8005235|5350|  |

* Interpreting the results.
    1. Watch the average snooze (pause plus processing) time per iteration.  This number is an indicator of the latency between cache updates.
    2. Watch the average number of spike count and how close they are with the average spike interval.  These 2 number are indicators of how hard the cache is pounded.
    3. Watch the average queues depth.  This number is an indicator if the cache is keeping up with processing.
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
    4c5533635d8c   mccache01   56.15%    52.36MiB / 5.702GiB   0.90%     1.01GB / 113MB   0B / 0B     8
    be4b289503fe   mccache02   57.19%    52.48MiB / 5.702GiB   0.90%     1.01GB / 112MB   0B / 0B     8
    00625aade927   mccache03   68.43%    54.36MiB / 5.702GiB   0.93%     1.01GB / 111MB   0B / 0B     8
    45e610a0b89c   mccache04   69.92%    54.73MiB / 5.702GiB   0.94%     1.01GB / 110MB   0B / 0B     10
    100e4b98692f   mccache05  102.07%    53.37MiB / 5.702GiB   0.91%     1.01GB / 111MB   0B / 0B     8
    b7493e0d19a9   mccache06   56.91%    51.79MiB / 5.702GiB   0.89%     1.01GB / 112MB   0B / 0B     8
    1c49b8530f65   mccache08   56.25%    52.8 MiB / 5.702GiB   0.90%     1.01GB / 111MB   0B / 0B     8
    d260c6822812   mccache07   57.23%    55.74MiB / 5.702GiB   0.95%     1.01GB / 113MB   0B / 0B     8
    d3806d9b2f75   mccache09   69.69%    54.82MiB / 5.702GiB   0.94%     1.01GB / 112MB   0B / 0B     8
```

### Observations
* As more stress is applied to the cache, the outbound queue starts to back up.  This is by designed as long as it is not too deep and only you can decided how deep is acceptable.
    * Stress is generated from the increased number of nodes plus a higher update frequency (aperture < **0.01** seconds, **10** ms).
    * The local outbound queue starts backing up as we pound the local cache at a frequency with an aperture of < **0.005** seconds or **5** ms.  Anecdotally, this suggested that the current implementation or Python is not able to keep.
* The larger the object to cache, the higher the latency to sync the other members in the cluster.  Many more packets need to be transmitted plus the processing overhead.
* More detail logging will require more processing.  The tests disable logging with the `-L 0` CLI option.
* The more nodes, the longer it takes to for the other nodes to receive message.  **5** nodes have about **8** seconds latency when tested with very high frequency updates (<= `0.005` ms snooze).
* Anecdotally, it does **not** look like `time.sleep( 0.0001 )` can yield accurate precision for the stress test.
* Python is not known for it performance and we should **not** expect `McCache` to out performance Python's inherent limitation.
* `McCache` can handle heavy update/delete against it.
    * If you do **not** have an use case where the cache is pounded **less** than once every **10**ms, sustained for **10** minutes, `McCache` may be suitable for you.


### Cloud VM
TBD
