import os

def net_ns_config():
  with open("/lib/systemd/system/mongodb.service", "r+") as f:
   data = f.readlines()
   data.insert(13, "NetworkNamespacePath=/var/run/netns/dataplane\n")
   data_new="".join(data)
   f.seek(0)
   f.write(data_new)
  with open("/lib/systemd/system/openvpn.service", "r+") as f:
   data = f.readlines()
   data.insert(10, "NetworkNamespacePath=/var/run/netns/dataplane\n")
   data_new="".join(data)
   f.seek(0)
   f.write(data_new)
  with open("/lib/systemd/system/openvpn@.service", "r+") as f:
   data = f.readlines()
   data.insert(14, "NetworkNamespacePath=/var/run/netns/dataplane\n")
   data_new="".join(data)
   f.seek(0)
   f.write(data_new)
  with open("/lib/systemd/system/isc-dhcp-server.service", "r+") as f:
   data = f.readlines()
   data.insert(14, "NetworkNamespacePath=/var/run/netns/dataplane\n")
   data_new="".join(data)
   f.seek(0)
   f.write(data_new)
  with open("/etc/netns/dataplane/resolv.conf", "a") as f:
    f.write(f"nameserver 8.8.8.8\nnameserver 8.8.4.4\n")
  os.system(f"sudo systemctl daemon-reload")
  os.system(f"sudo systemctl restart mongodb")
  os.system(f"sudo systemctl restart openvpn")
  

net_ns_config()