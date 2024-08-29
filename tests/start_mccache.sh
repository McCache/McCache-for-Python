
# Increase network buffer for McCache high traffic stress testing.
# Need to run as root or with sudo priviledge but sudo will prompt for password.
#
sysctl -w net.ipv4.udp_rmem_min=16777216    # Min UDP read  buffer.
sysctl -w net.ipv4.udp_wmem_min=16777216    # Min UDP write buffer.
{
    echo    Increase network buffer size on ${HOSTNAME} to:
    sysctl -a |grep -E [_.][rw]mem
    echo
}   >>  /home/mccache/log/start_mccache.log

python  /home/mccache/tests/unit/start_mccache.py
