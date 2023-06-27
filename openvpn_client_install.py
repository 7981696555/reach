import os
os.system(f"sudo ip netns exec dataplane apt install -y openvpn")
os.system(f"sudo cp client.conf /etc/openvpn/client.conf")
os.system(f"sudo ip netns exec dataplane openvpn --config /etc/openvpn/client.conf")