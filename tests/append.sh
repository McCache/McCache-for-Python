#!/usr/bin/bash
for ((i=1;i<=10000;i++))
do
echo "$(hostname) $(date '+%T %N')" >> ${MCCACHE_DEBUG_FILE}
done