#!/bin/bash

if [[ $# -lt 1 ]]; then
    echo $'\033[1;31mError:\033[0m  You should specify the path to directory with run.sh in it!' 
    exit 1
fi

# problem with root for cgroups https://unix.stackexchange.com/questions/197718/does-managing-cgroups-require-root-access

cpu_set=0

sudo cgcreate -g cpuset,memory:ailimitgroup
sudo cgset -r cpuset.cpus=${cpu_set} ailimitgroup              # CPU number, can be define as a set, for ex. 0-3,15 => 0,1,2,3,15
sudo cgset -r cpuset.mems=0 ailimitgroup
sudo cgset -r cpuset.cpu_exclusive=1 ailimitgroup
sudo cgset -r memory.limit_in_bytes=6m ailimitgroup            # 6G => 6 GiB (gibibytes) = 6442450944 bytes
# !!! After taking all the memory process will use SWAP, probably we need to limit both of them together example:
# sudo cgset -r memory.memsw.limit_in_bytes=6m ailimitgroup 

# cgget -a ailimitgroup  # to list configuration

cd $1
sudo cgexec -g cpuset,memory:ailimitgroup bash ./run.sh

sudo cgdelete -g cpuset,memory:ailimitgroup
