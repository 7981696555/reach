import os
import pymongo
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["int_details"]
coll_route_info = db["ubuntu_route_info"]
coll_interface_info = db["ubuntu_interface_info"]

# Install dhcpd package
for intfc in coll_interface_info.find():
  if intfc["type"] == "lan":
    if "pci_address" in intfc:
      static_ip = intfc["IPv4address"]   
      dhcp_netmask = intfc["netmask"]
      interface_name = intfc["interface_name"]
lanip = static_ip.split(".")
lan_address = lanip[0]+"."+lanip[1]+"."+lanip[2]+"."+"0"
dhcp_start_address = lanip[0]+"."+lanip[1]+"."+lanip[2]+"."+"100"
dhcp_end_address = lanip[0]+"."+lanip[1]+"."+lanip[2]+"."+"200"
dhcp_gateway = lanip[0]+"."+lanip[1]+"."+lanip[2]+"."+"1"
domain_name = "8.8.8.8"
optional_dns = "8.8.4.4"
bracket = "{"
closebracket ="}"
#Configure dhcpd.conf file
with open("/etc/dhcp/dhcpd.conf", "w") as f:

 f.write(f"default-lease-time 600;\nmax-lease-time 7200;\nauthoritative;\nsubnet {lan_address} netmask {dhcp_netmask} {bracket} \n range {dhcp_start_address} {dhcp_end_address}; \n option routers {dhcp_gateway}; \n option subnet-mask {dhcp_netmask}; \n option domain-name-servers {domain_name}, {optional_dns}; \n{closebracket}")

# Configure network interface
#network_interface = # The primary network interface
with open("/etc/network/interfaces", "w") as w:
 w.write(f"auto {interface_name} \n iface {interface_name} inet static \n \t address {static_ip} netmask {dhcp_netmask} \n \t gateway {dhcp_gateway}")
# Start the dhcpd service
with open("/etc/default/isc-dhcp-server", "w") as f:
  f.write(f'INTERFACESv4="{interface_name}"')

print(os.system(f"sudo systemctl enable isc-dhcp-server"))
print(os.system(f"sudo systemctl start isc-dhcp-server"))

