import psutil
import pymongo
from pymongo.server_api import ServerApi
import subprocess
import socket
from pyroute2 import IPRoute
from netaddr import IPAddress
ipr = IPRoute()
import requests

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["int_details"]
coll_route_info = db["ubuntu_route_info"]
coll_interface_info = db["ubuntu_interface_info"]


routes_protocol_map = {
    -1: '',
    0: 'unspec',
    1: 'redirect',
    2: 'kernel',
    3: 'boot',
    4: 'static',
    8: 'gated',
    9: 'ra',
    10: 'mrt',
    11: 'zebra',
    12: 'bird',
    13: 'dnrouted',
    14: 'xorp',
    15: 'ntk',
    16: 'dhcp',
    18: 'keepalived',
    42: 'babel',
    186: 'bgp',
    187: 'isis',
    188: 'ospf',
    189: 'rip',
    192: 'eigrp',
}

routes_protocol_id_map = { y:x for x, y in routes_protocol_map.items() }

response = requests.get("http://checkip.dyndns.org").text
    # Extract the public IP address from the response
public_ip = response.split("<body>")[1].split("</body>")[0].strip()
    

def store_ubuntu_routing_table():
 coll_route_info.delete_many({})
 ipr = IPRoute()
 routes = ipr.get_routes(family=socket.AF_INET)
 routing_table = []
 for route in routes:
  destination = "0.0.0.0/0"
  metric = 0
  gateway = "none"
  protocol = int(route['proto'])
  multipath = 0
  for attr in route['attrs']:
    if attr[0] == 'RTA_OIF':
      intfc_name = ipr.get_links(attr[1])[0].get_attr('IFLA_IFNAME')
    if attr[0] == 'RTA_GATEWAY':
      gateway = attr[1]
    if attr[0] == 'RTA_PRIORITY':
      metric = attr[1]
    if attr[0] == 'RTA_DST':
      destination = attr[1]
    if attr[0] == 'RTA_MULTIPATH':
      for elem in attr[1]:
        intfc_name = ipr.get_links(elem['oif'])[0].get_attr('IFLA_IFNAME')
        for attr2 in elem['attrs']:
          if attr2[0] == 'RTA_GATEWAY':
            gateway = attr2[1] 
            multipath = 1
            coll_route_info.insert_one({
                "interface_name":str(intfc_name),
                "gateway":str(gateway),
                "destination":str(destination),
                "metric":int(metric),
                "protocol":routes_protocol_map[protocol],
                })
  if multipath == 0:      
    coll_route_info.insert_one({
        "interface_name":str(intfc_name),
        "gateway":str(gateway),
        "destination":str(destination),
        "metric":int(metric),
        "protocol":routes_protocol_map[protocol],
        })
    		
	
  
  
def store_interface_details():
  coll_interface_info.delete_many({})
  interface = psutil.net_if_addrs()
  intfc_ubuntu = []
  for intfc_name in interface:
    colect = {"interface_name":intfc_name}
    addresses = interface[intfc_name]
    for address in addresses:
      
       if address.family == 2:
         pre_len = IPAddress(address.netmask).netmask_bits()
         ipaddr_prefix = str(address.address)+"/"+str(pre_len)
         colect.update({
            
            "IPv4address":ipaddr_prefix,
            "netmask":str(address.netmask),
            "broadcast":str(address.broadcast)
         })
       if address.family == 17:
         colect.update({
            "mac_address":str(address.address)
         })
       
         
    intfc_ubuntu.append(colect)
    coll_interface_info.insert_one(colect)
  pci_out = subprocess.check_output(["lspci"]).decode().split("\n")
  for line in pci_out:
    if "Ethernet controller" in line:
      pci_info = "0000:"+line.split()[0]
      lsh_out = subprocess.check_output(["lshw", "-c", "network", "-businfo"])
      lsh_out = lsh_out.decode().split("\n")
      lsh_out = lsh_out[2:-1]
      for line in lsh_out:
        li = line.split()
        lii = li[0].split("@")
        pci_addr = lii[1]
        if pci_info == pci_addr:
           for i in coll_interface_info.find():
             if i["interface_name"] == li[1]:
               query = {"interface_name": li[1]}
               update_data = {"$set": {"pci_address":pci_info+"0"}}
               coll_interface_info.update_many(query, update_data)
  default_route = ipr.get_default_routes(family = socket.AF_INET)
  for route in default_route:
        protocol = int(route['proto'])
        for attr in route['attrs']:
          if attr[0] == 'RTA_OIF':
            intfc_name = ipr.get_links(attr[1])[0].get_attr('IFLA_IFNAME')
          if attr[0] == 'RTA_GATEWAY':
            gateway = attr[1]
        for i in coll_interface_info.find():
          if i["interface_name"] == intfc_name:
               query = {"interface_name": intfc_name}
               update_data = {"$set": {"gateway":gateway}}
               coll_interface_info.update_many(query, update_data)
               query = {"interface_name": intfc_name}
               update_data2 = {"$set": {"public_ip":str(public_ip)}}
               coll_interface_info.update_many(query, update_data2)
               query = {"interface_name": intfc_name}
               update_data3 = {"$set": {"protocol":routes_protocol_map[protocol]}}
               coll_interface_info.update_many(query, update_data3)
               query = {"interface_name": intfc_name}
               update_data4 = {"$set": {"type":"wan"}}
               coll_interface_info.update_many(query, update_data4)
               
  for intfc in coll_interface_info.find():
    if "type" not in intfc:
      if "pci_address" in intfc:
        query = {"interface_name": intfc["interface_name"]}
        update_data = {"$set": {"type":"lan"}}
        coll_interface_info.update_many(query, update_data)
         
  
def get_ubuntu_routing_table():
  routing_table = []
  for route in coll_route_info.find({},{'_id':0}):
    routing_table.append(route)
    
  return routing_table


def get_interface_details():
  interface_details = []
  for interface in coll_interface_info.find({},{'_id':0}):
    interface_details.append(interface)
    
  return interface_details

    
  

store_ubuntu_routing_table()
store_interface_details()
print(get_ubuntu_routing_table())
print(get_interface_details())
