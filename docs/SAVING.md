# Saving
Removing an external dependency in your architecture reduces it's <strong>complexity</strong> and not to mention some cost saving.  The following are some cloud compute instance pricing comparison on September 16th, 2023.

<table>
<thead>
  <tr>
    <th align="left">Instance pricing</th>
    <th align="left">Small cluster size and cost</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td valign="top">
      <table>
      <thead>
        <tr><th align="left"><sub>Instance Name</sub></th><th><sub>Term</sub></th><th><sub>vCPU</sub></th><th><sub>RAM</sub></th><th align="right"><sub>$/Hour</sub></th><th align="right"><sub>30 days</sub></th></tr>
      </thead>
      <tbody>
        <tr><td colspan=5><a href="https://aws.amazon.com/ec2/pricing/reserved-instances/pricing/"><sub>Compute instances</sub></a></td></tr>
        <tr><td><sub>t3a.small       </sub></td><td><sub>One Year </sub></td><td align="center"><sub> 2 </sub></td><td><sub>2 Gb</sub></td><td align="right"><sub>0.011</sub></td><td align="right"><sub><b> $7.92</b></sub></td></tr>
        <tr><td><sub>t3a.small       </sub></td><td><sub>On Demand</sub></td><td align="center"><sub> 2 </sub></td><td><sub>2 Gb</sub></td><td align="right"><sub>0.019</sub></td><td align="right"><sub>   $13.68</sub></td></tr>
        <tr><td><sub>t3a.medium      </sub></td><td><sub>One Year </sub></td><td align="center"><sub> 2 </sub></td><td><sub>4 Gb</sub></td><td align="right"><sub>0.024</sub></td><td align="right"><sub><b>$17.28</b></sub></td></tr>
        <tr><td><sub>t3a.medium      </sub></td><td><sub>On Demand</sub></td><td align="center"><sub> 2 </sub></td><td><sub>4 Gb</sub></td><td align="right"><sub>0.037</sub></td><td align="right"><sub>   $26.64</sub></td></tr>
        <tr><td colspan=5><a href="https://aws.amazon.com/elasticache/pricing/?nc2=type_a/"><sub>Managed Redis or Memcached instances</sub></a><td><sub></tr>
        <tr><td><sub>cache.t4g.medium</sub></td><td><sub>One Year </sub></td><td align="center"><sub> 2 </sub></td><td><sub>3 Gb</sub></td><td align="right"><sub>0.041</sub></td><td align="right"><sub><b>$29.52</b></sub></td></tr>
        <tr><td><sub>cache.t4g.medium</sub></td><td><sub>On Demand</sub></td><td align="center"><sub> 2 </sub></td><td><sub>3 Gb</sub></td><td align="right"><sub>0.065</sub></td><td align="right"><sub>   $46.80</sub></td></tr>
        <tr><td><sub>cache.m6g.large </sub></td><td><sub>One Year </sub></td><td align="center"><sub> 2 </sub></td><td><sub>6 Gb</sub></td><td align="right"><sub>0.094</sub></td><td align="right"><sub><b>$67.68</b></sub></td></tr>
        <tr><td><sub>cache.m6g.large </sub></td><td><sub>On Demand</sub></td><td align="center"><sub> 2 </sub></td><td><sub>6 Gb</sub></td><td align="right"><sub>0.149</sub></td><td align="right"><sub>  $107.28</sub></td></tr>
      </tbody>
      </table>
    </sub></td>
    <td valign="top">
      <table>
      <thead>
        <tr>
          <th align="left"><sub>Instance Name</sub></th><th><sub>Term</sub></th><th><sub>Servers</sub></th><th><sub>RAM</sub></th><th align="right"><sub>30 days</sub></th></tr>
      </thead>
      <tbody>
        <tr><td colspan=5><sub>Compute instances with McCache</sub></td></tr>
        <tr><td><sub>t3a.small       </sub></td><td><sub>One Year</sub></td>   <td align="center"><sub> 4</sub></td><td><sub>8 Gb</sub></td><td align="right"><sub>    $31.68</sub></td></tr>
        <tr><td colspan=2 align="right"><sub><b>Total</b></sub></td><td align="center"><sub> 4</sub></td><td><sub>8 Gb</sub></td><td align="right"><sub><b>$31.68</b></sub></td></tr>
        <tr><td colspan=5/></tr>
        <tr><td><sub>t3a.medium      </sub></td><td><sub>One Year</sub></td>   <td align="center"><sub> 2</sub></td><td><sub>8 Gb</sub></td><td align="right"><sub>    $34.56</sub></td></tr>
        <tr><td colspan=2 align="right"><sub><b>Total</b></sub></td><td align="center"><sub> 2</sub></td><td><sub>8 Gb</sub></td><td align="right"><sub><b>$34.56</b></sub></td></tr>
        <tr><td colspan=5><sub>Compute instances with External Cache</sub></td></tr>
        <tr><td><sub>t3a.small       </sub></td><td><sub>One Year</sub></td>   <td align="center"><sub> 2</sub></td><td><sub>4 Gb</sub></td><td align="right"><sub>    $15.84</sub></td></tr>
        <tr><td><sub>cache.t4g.medium</sub></td><td><sub>One Year</sub></td>   <td align="center"><sub> 2</sub></td><td><sub>6 Gb</sub></td><td align="right"><sub>    $59.04</sub></td></tr>
        <tr><td colspan=2 align="right"><sub><b>Total</b></sub></td><td align="center"><sub> 4</sub></td><td><sub>10 Gb</sub></td><td align="right"><sub><b>$74.88</b></sub></td></tr>
      </tbody>
      </table>
    </sub></td>
  </tr>
  </tbody>
</table>

##### Single Python 3.12 memory footprint (RSS) while idling:
```bash
$ python -c 'import time; time.sleep(60)' &
$ sleep  20
$ ps aux |grep python \
 |awk '{sum=sum+$6}; END {print "\n" sum/1024 " MB"}'

10.054 MB
```
##### Single Python 3.12 memory footprint (RSS) while running the stress test caching `datetime` object:
```
$ ps aux |grep python \
 |awk '{sum=sum+$6}; END {print "\n" sum/1024 " MB"}'

37.445 MB
```

For example, a minimum small cluster of two `t3a.medium` instances, for your backend application, should have plenty of available memory for caching as compared to having an additional dedicated cluster of `cache.m6g.medium` instances for caching.
