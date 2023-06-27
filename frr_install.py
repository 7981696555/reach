import os
os.system(f"sudo curl -s https://deb.frrouting.org/frr/keys.asc | sudo apt-key add -")
os.system(f"sudo echo deb https://deb.frrouting.org/frr $(lsb_release -s -c) frr-stable | sudo tee -a /etc/apt/sources.list.d/frr.list")
os.system(f"sudo apt update && sudo apt install frr frr-pythontools -y")
os.system(f"sudo adduser $(id -un) frr")
os.system(f"sudo adduser $(id -un) frrvty")
with open("daemons.txt","r") as f:
  data = f.read()
with open("/etc/frr/daemons", "w") as f:
  f.write(data)
with open("/etc/frr/frr.conf", "a") as f:
  f.write(f"\nlog file /var/log/frr/frr.log\nservice integrated-vtysh-config\n!\n!")
os.system(f"sudo service frr restart")