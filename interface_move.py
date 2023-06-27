import os
import time
os.system("sudo python3 interface_details.py")
os.system(f"sudo apt-get install isc-dhcp-server -y")
os.system(f"sudo python3 dhcp-server-config.py")
os.system("sudo python3 bind_interface_vpp.py")
time.sleep(180)
with open("/etc/resolv.conf", "a") as f:
    f.write(f"nameserver 8.8.8.8\nnameserver 8.8.4.4\n")
os.system("sudo python3 vpp_int_config.py")
