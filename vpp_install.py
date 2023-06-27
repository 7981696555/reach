import os
os.system(f"sudo mkdir -p /var/log/vpp/vpp.log")
os.system(f"sudo dpkg -i *.deb")
os.system(f"sudo adduser $(id -un) vpp")
with open("/etc/sysctl.d/80-vpp.conf", "w") as f:
  f.write(f"\nvm.nr_hugepages=1024\nvm.max_map_count=3096\nvm.hugetlb_shm_group=0\nkernel.shmmax=2147483648")
with open("/etc/sysctl.d/81-vpp-netlink.conf", "w") as f:
  f.write(f"net.core.rmem_default=67108864\nnet.core.wmem_default=67108864\nnet.core.rmem_max=67108864\nnet.core.wmem_max=67108864")
os.system(f"sudo sysctl -p -f /etc/sysctl.d/80-vpp.conf ")
os.system(f"sudo sysctl -p -f /etc/sysctl.d/81-vpp-netlink.conf")
with open("dataplane_service.txt", "r") as f:
  data = f.read()
with open("/usr/lib/systemd/system/netns-dataplane.service", "w") as f:
  f.write(data)
os.system(f"sudo systemctl enable netns-dataplane")
os.system(f"sudo systemctl start netns-dataplane")
os.system(f"sudo cp /etc/vpp/startup.conf /etc/vpp/startup.conf.orig")
with open("vpp_startup.txt", "r") as f:
  data = f.read()
with open("/etc/vpp/startup.conf", "w") as f:
  f.write(data)
with open("/etc/vpp/bootstrap.vpp", "w") as f:
  f.write(f"create loopback interface\n")
os.system(f"sudo systemctl restart vpp")