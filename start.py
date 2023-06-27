import os
import time
os.system(f"sudo apt install net-tools")
os.system(f"sudo python3 vpp_install.py")
os.system(f"sudo apt --fix-broken install -y")
os.system(f"sudo python3 frr_install.py")
os.system(f"sudo python3 mongoinstall.py")
os.system(f"sudo apt install pip -y")
os.system(f"sudo pip install pymongo")
os.system(f"sudo pip install flask")
os.system(f"sudo pip install flask-cors")
os.system(f"sudo pip install pyufw")
os.system(f"sudo pip install vpp-papi")
os.system(f"sudo pip install psutil")
os.system(f"sudo pip install netaddr")
os.system(f"sudo pip install pyroute2")
os.system(f"sudo apt install -y openvpn")
os.system(f"sudo cp client.conf /etc/openvpn/client.conf")
os.system(f"sudo python3 inst_db.py") 
os.system(f"sudo python3 interface_move.py")
time.sleep(180)
os.system(f"sudo systemctl start openvpn@client")
os.system(f"sudo systemctl daemon-reload")
os.system(f"sudo systemctl restart openvpn")
os.system(f"sudo systemctl restart isc-dhcp-server")
time.sleep(180)
#to allow openvpn
os.system(f"sudo ufw allow 1194/udp")
#to connect with reachManage
os.system(f"sudo ufw allow 5000")
#to allow ipsec
os.system(f"sudo ufw allow 500/esp")
#to allow vxlan
os.system(f"sudo ufw allow 4789/udp")
#to allow mongodb
os.system(f"sudo ufw allow 27017/tcp")
#to allow ospf
os.system(f"sudo ufw allow 89")
#to open dns port
os.system(f"sudo ufw allow 53")
#to open ssh port
os.system(f"sudo ufw allow 22")
#to open dhcp port
os.system(f"sudo ufw allow 67/udp")

os.system(f"sudo python3 vxlan_rtt.py")
