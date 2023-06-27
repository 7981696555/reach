from flask import Flask, request, jsonify
import pyufw as ufw
from flask_cors import CORS
from vpp_papi import VPPApiClient
import os
import subprocess
import json
import fnmatch
import sys
import pymongo
from pymongo.server_api import ServerApi
import secrets
import random
import binascii
import ipaddress
import requests
import time
from ipaddress import IPv4Interface
import netaddr
from netaddr import IPAddress
from pyroute2 import IPRoute
import socket
import psutil

ipr = IPRoute()

routes_protocol_map = {
    -1: '',
    196:'vpn',
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

#--------------------------------------------------------------------------------------------------------------
#Local Database to store interface details of Ubuntu
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["wan_details"]
coll = db["wan_info"]
coll.delete_many({})
db1 = client["int_details"]
coll_route_info = db1["ubuntu_route_info"]
coll_interface_info  = db1["ubuntu_interface_info"]

coll_netns_route_info = db["netns_route_info"]
coll_netns_interface_info = db["netns_interface_info"]

#-----------------------------------------------------------------------------------------------------------------
#Local Database to maintain iteration variable user for instance creation in VPP
db = client["iteration_variable"]
col = db["instance_list"]
client1 = pymongo.MongoClient("mongodb://10.8.0.1:27017/")
#client1 = pymongo.MongoClient("mongodb+srv://bavya:bavya23@cluster0.xxummtw.mongodb.net/?retryWrites=true&w=majority", server_api=ServerApi('1')) 

#-----------------------------------------------------------------------------------------------------------------
#local database for vxlan details
db_vxlan = client["vxlan"]
col_vxlan_details = db_vxlan ["vxlan_details"]

#Cloud Database to store Ipsec sa 
db_ipsec = client1["ipsec_key"]
col_ipsec_sa = db_ipsec["sa_table"]
#-----------------------------------------------------------------------------------------------------------------
#Cloud Database for MAC address of Loopback Interface
db_mac = client1["mac_address"]
col_mac = db_mac["mac_list"]
#-----------------------------------------------------------------------------------------------------------------
#Cloud Database for Ipsec Keys 
col_cryptokeys = db_ipsec["crypto_keys"]
col_integkeys = db_ipsec["integ_keys"]
#----------------------------------------------------------------------------------------------------------------
#Cloud Database to maintain Loopback IP Addresses
db_loopback = client1["loopback_address"]
col_vxlan_loopaddr = db_loopback["vxlan_loop_addr"]
col_gre_loopaddr = db_loopback["gre_loop_addr"]
#----------------------------------------------------------------------------------------------------------
#VPP Api Block
vpp_json_dir = '/usr/share/vpp/api/'
jsonfiles = []
for root, dirnames, filenames in os.walk(vpp_json_dir):
  for filename in fnmatch.filter(filenames, '*.api.json'):
    jsonfiles.append(os.path.join(root, filename))

vpp = VPPApiClient(apifiles=jsonfiles, server_address='/run/vpp/api.sock')
vpp.connect("test-client")

v = vpp.api.show_version()
print('VPP version is %s' % v.version)
#---------------------------------------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)
#--------------------------------------------------------------------------------------------------------------
# Machine INFO
@app.route('/')  
def get_machine_info():
    data=[]
    with open('/etc/machine-id', 'r') as f:
      machine_id = f.read().strip()
    with open("/etc/hostname", "r") as f:
      host_name = f.read().strip()
    for intfc in coll_interface_info.find():
      if "gateway" in intfc:
        collect = {"machine_id":machine_id, "host_name":host_name, "wan_ip":intfc["IPv4address"]}
        data.append(collect)
    return data

     
#-----------------------------------------
def store_netns_routing_table():
 coll_netns_route_info.delete_many({})
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
            coll_netns_route_info.insert_one({
                "interface_name":str(intfc_name),
                "gateway":str(gateway),
                "destination":str(destination),
                "metric":int(metric),
                "protocol":routes_protocol_map[protocol],
                })
  if multipath == 0:      
    coll_netns_route_info.insert_one({
        "interface_name":str(intfc_name),
        "gateway":str(gateway),
        "destination":str(destination),
        "metric":int(metric),
        "protocol":routes_protocol_map[protocol],
        })
    		

#--------------------------------------------------------------------------------------------------------
#Ubuntu Interface - INFO
@app.route('/routing_table')
def get_netns_routing_table():
  store_netns_routing_table()
  routing_table = []
  for route in coll_netns_route_info.find({},{'_id':0}):
    routing_table.append(route)
  return routing_table
  
#----------------------------------------------------------------------
def store_netns_interface_details():
  coll_netns_interface_info.delete_many({})
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
            "IPv4address_noprefix":str(address.address),
            "IPv4address":ipaddr_prefix,
            "netmask":str(address.netmask),
            "broadcast":str(address.broadcast)
         })
       if address.family == 17:
         colect.update({
            "mac_address":str(address.address)
         })
       
         
    intfc_ubuntu.append(colect)
    coll_netns_interface_info.insert_one(colect)
  
  default_route = ipr.get_default_routes(family = socket.AF_INET)
  for route in default_route:
        multipath = 0
        for attr in route['attrs']:
          if attr[0] == 'RTA_OIF':
            intfc_name = ipr.get_links(attr[1])[0].get_attr('IFLA_IFNAME')
          if attr[0] == 'RTA_GATEWAY':
            gateway = attr[1]
          if attr[0] == 'RTA_MULTIPATH':
            multipath = 1
            for elem in attr[1]:
              intfc_name = ipr.get_links(elem['oif'])[0].get_attr('IFLA_IFNAME')
              for attr2 in elem['attrs']:
                if attr2[0] == 'RTA_GATEWAY':
                  gateway = attr2[1] 
                  for i in coll_netns_interface_info.find():
                    if i["interface_name"] == intfc_name:
                      query = {"interface_name": intfc_name}
                      update_data = {"$set": {"gateway":gateway}}
                      coll_netns_interface_info.update_many(query, update_data)
                      query = {"interface_name": intfc_name}
                      update_data1 = {"$set": {"type":"wan"}}
                      coll_netns_interface_info.update_many(query, update_data1)
        if multipath == 0:
          for i in coll_netns_interface_info.find():
            if i["interface_name"] == intfc_name:
               query = {"interface_name": intfc_name}
               update_data = {"$set": {"gateway":gateway}}
               coll_netns_interface_info.update_many(query, update_data)
               query = {"interface_name": intfc_name}
               update_data1 = {"$set": {"type":"wan"}}
               coll_netns_interface_info.update_many(query, update_data1)
               
  for intfc in coll_netns_interface_info.find():
    if "IPv4address_noprefix" in intfc:
     if "type" not in intfc:
      subnet_addr = subprocess.check_output(["awk", "/subnet/ {print $2}", "/etc/dhcp/dhcpd.conf"]).decode()
      net_mask = subprocess.check_output(["awk", "/netmask/ {print $4}", "/etc/dhcp/dhcpd.conf"]).decode()
      pre_len = str(IPAddress(net_mask).netmask_bits())
      sub_addr = subnet_addr.split("\n")[0]+"/"+pre_len
      if ipaddress.ip_address(intfc["IPv4address_noprefix"]) in ipaddress.ip_network(sub_addr):
        query = {"interface_name": intfc["interface_name"]}
        update_data = {"$set": {"type":"lan"}}
        coll_netns_interface_info.update_many(query, update_data)
         

@app.route('/netns_interface_details')    
def get_netns_interface_details():
  store_netns_interface_details()
  interface_details = []
  for interface in coll_netns_interface_info.find({},{'_id':0}):
    interface_details.append(interface)
    
  return interface_details

#-----------------------------------------------------------------------------------------------------------
#Get ubuntu interface info. 
@app.route('/ubuntu_interface_details')   
def get_ubuntu_interface_details():
  interface_details = []
  for interface in coll_interface_info.find({},{'_id':0}):
    interface_details.append(interface)
    
  return interface_details
#------------------------------------------------------------------------------------------------------------
#Ubuntu Routing-info
@app.route('/ubuntu_routing_table')   
def get_ubuntu_routing_table():
  routing_table = []
  for route in coll_route_info.find({},{'_id':0}):
    routing_table.append(route)
    
  return routing_table

#------------------------------------------------------------------------------------------------------------


#-----------------------------------------------------------------------------------------------------------------
#VXLAN Tunnel Setup
   
@app.route('/tunnel_data', methods = ['POST'])  
def vxlan_setup():
    data = request.json
    response = {"message":"successfull"}
    x = col.find_one()
    loopback_instance = x["loopback_instance"]
    bridge_instance = x["bridge_instance"]
    vxlan_instance = x["vxlan_instance"]
    gre_instance = x["gre_instance"]
    
    loop1_addr = data["loop1_addr"]
    loop2_addr = data["loop2_addr"]
    loop1_mac = data["loop1_mac"]
    loop2_mac = data["loop2_mac"]
    loop1_remote_addr = data["loop1_remote_addr"]
    loop2_remote_addr = data["loop2_remote_addr"]
    vxlan_src_ip = data["vxlan_src_ip"]
    vxlan_dst_ip = data["vxlan_dst_ip"]
    sa_in = int(data["sa_in"])
    sa_out = int(data["sa_out"])
    sa_in_pro = int(data["sa_in_pro"])
    sa_out_pro = int(data["sa_out_pro"])
    ck1 = bytes.fromhex(data["encry_key1"])
    ck2 = bytes.fromhex(data["encry_key2"])
    ik1 = bytes.fromhex(data["integ_key1"])
    ik2 = bytes.fromhex(data["integ_key2"])
    spi_in = int(data["spi_in"])
    spi_out = int(data["spi_out"])
    
    vxlan_loopback_addr = loop1_addr.split("/")[0]
    gre_loopback_addr = loop2_addr.split("/")[0]
    gre_remote_looopback_addr = loop2_remote_addr.split("/")[0]
    
         
    
    
   
      

    vpp.api.ipsec_sad_entry_add_del_v2( entry = {   "sad_id":sa_in,
                                                    "spi":int(spi_in), 
                                                    "protocol":50,
                                                    "crypto_algorithm":1,
                                                    "crypto_key":{ "length":16, 
                                                                    "data":ck1
                                                                  },
                                                    "integrity_algorithm":2, 
                                                    "integrity_key":{ "length":20,
                                                                      "data":ik1 
                                                                    }
                                                },
                                        is_add=1
                                      )
    vpp.api.ipsec_sad_entry_add_del_v2(entry = {"sad_id":sa_out, "spi":int(spi_out), "protocol":50, "crypto-algorithm":1, "crypto_key":{"length":16, "data":ck2}, "integrity_algorithm":2, "integrity_key":{"length":20, "data":ik2}}, is_add=1)

   
    
    
    loop1_ip = IPv4Interface(loop1_addr)
    gre_src_addr = loop1_ip.ip
  #----------------------------------------------------------------------------------------------------------  
    loop1_remote_ip = IPv4Interface(loop1_remote_addr)
    gre_dst_addr = loop1_remote_ip.ip
   
#------------------------------------------------------------------------------------------------------
   
    greip = IPv4Interface(loop2_addr)
    gre_addr = str(greip.ip)+"/32"
    
   
    
    sa_in_list = [sa_in_pro]
    
    #creating loopback interface for gre
    loopback_instance +=1
    loopgre = vpp.api.create_loopback_instance( mac_address=loop2_mac, 
                                                is_specified=1, 
                                                user_instance=loopback_instance
                                               )
    gre_loopback_linux = "vpp"+str(loopback_instance)
    gre_loopback_vpp = "loop"+str(loopback_instance)
    os.system(f"sudo vppctl set int mtu packet 1360 {gre_loopback_vpp}") 
    os.system(f"sudo vppctl set int l2 learn {gre_loopback_vpp} disable")
    vpp.api.sw_interface_set_flags( sw_if_index=loopgre.sw_if_index, 
                                    flags=3
                                  )
    
    loopname = "loop"+str(loopback_instance)
        
    
    

#bridge domain creation
    bridge_instance +=1
    vpp.api.bridge_domain_add_del_v2(   bd_id=bridge_instance,
                                        flood=1,
                                        learn=1, 
                                        uu_flood=1,
                                        forward=1,
                                        arp_term=0
                                    )

#create gre tunnel
    gre_instance +=1
    gretunnel = vpp.api.gre_tunnel_add_del( tunnel = {  "src":gre_src_addr,     
                                                        "dst":gre_dst_addr, 
                                                        "type":1, "mode":0, 
                                                        "instance":gre_instance
                                                     }, 
                                            is_add=1
                                          )
    vpp.api.sw_interface_set_flags( sw_if_index=gretunnel.sw_if_index, 
                                    flags=3
                                  )
    grename = "gre"+str(gre_instance)
    os.system(f"sudo vppctl set int mtu packet 1500 {grename}") 
  

#protect gre tunnel by ipsec
   
    vpp.api.ipsec_tunnel_protect_update(tunnel = {  "sw_if_index":gretunnel.sw_if_index,
                                                    "sa_in":sa_in_list,
                                                    "sa_out":sa_out_pro,
                                                    "n_sa_in":1
                                                 }
                                        )

#set gre1 to bridge 2 as shg 1
    vpp.api.sw_interface_set_l2_bridge(     rx_sw_if_index=gretunnel.sw_if_index,    
                                            bd_id=bridge_instance,
                                            shg=1,
                                            enable=1
                                       )
    vpp.api.sw_interface_set_l2_bridge( rx_sw_if_index=loopgre.sw_if_index, 
                                        bd_id=bridge_instance,
                                        shg=0,
                                        enable=1, 
                                        port_type=1
                                      ) 
   
    print(vpp.api.lcp_itf_pair_add_del_v2(is_add=1, sw_if_index=loopgre.sw_if_index, host_if_name=gre_loopback_linux, host_if_type=1))
    os.system(f"sudo vppctl lcp lcp-sync on")
    os.system(f"sudo ifconfig {gre_loopback_linux} {gre_loopback_addr} netmask 255.255.255.254")
      
#creating loopback interface for vxlan
    loopback_instance +=1
    loopvxlan = vpp.api.create_loopback_instance(   mac_address=loop1_mac,
                                                    is_specified=1,
                                                    user_instance=loopback_instance
                                                )
    vpp.api.sw_interface_set_flags(sw_if_index=loopvxlan.sw_if_index, flags=3)
    vxlan_loopback_vpp = "loop"+str(loopback_instance)
    vxlan_loopback_linux = "vpp"+str(loopback_instance)
    vpp.api.sw_interface_add_del_address(   sw_if_index=loopvxlan.sw_if_index,
                                            is_add=1,
                                            prefix=loop1_addr
                                        )
    
    
    
   
    os.system(f"sudo vppctl set int mtu packet 1500 {vxlan_loopback_vpp}") 
    
#vxlan tunnel creation
    vxlan_instance +=1
   
    vxtunnel = vpp.api.vxlan_add_del_tunnel_v2( src_address=vxlan_src_ip,
                                                dst_address=vxlan_dst_ip,
                                                vni=13, 
                                                is_add=1,
                                                decap_next_index=1, 
                                                instance=vxlan_instance
                                              )
    
#bridge domain creation
    bridge_instance +=1
    vpp.api.bridge_domain_add_del_v2(   bd_id=bridge_instance,  
                                        flood=1,
                                        learn=1, 
                                        uu_flood=1, 
                                        forward=1, 
                                        arp_term=0
                                    )

#set loopback to bridge as bvi
    vpp.api.sw_interface_set_l2_bridge( rx_sw_if_index=loopvxlan.sw_if_index,
                                        bd_id=bridge_instance,
                                        shg=0, 
                                        enable=1, 
                                        port_type=1
                                      )

#set vxlan tunnel to bridge as 1
    vpp.api.sw_interface_set_l2_bridge( rx_sw_if_index=vxtunnel.sw_if_index, 
                                        bd_id=bridge_instance, 
                                        shg=1, 
                                        enable=1
                                      )
    tunnelname = "vxlan_tunnel"+str(vxlan_instance)
    os.system(f"sudo vppctl set int mtu packet 1500 {tunnelname}") 
    
    #print(vpp.api.lcp_itf_pair_add_del_v2(is_add=1, sw_if_index=loopvxlan.sw_if_index, host_if_name=vxlan_loopback_linux, host_if_type=0))
    #os.system(f"sudo vppctl lcp create {vxlan_loopback_vpp} host-if {vxlan_loopback_linux}")
    #os.system(f"sudo ifconfig {vxlan_loopback_linux} {vxlan_loopback_addr} netmask 255.255.255.254")
    os.system(f"sudo vppctl set int ip table {vxlan_loopback_vpp} 0")




#add the tunnel details in database 
    
    col_vxlan_details.delete_many( {"dst_address": vxlan_dst_ip})   
    col_vxlan_details.insert_one({"src_address":vxlan_src_ip,
                                   "dst_address":vxlan_dst_ip,
                                   "src_loopback_addr":loop2_addr, 
                                   "dst_loopback_addr":loop2_remote_addr,
                                   "gre_bridge_id":bridge_instance, 
                                   "status":"connected", 
                                   "encrypt":"PSK" 
                                   }
                                )
    
# delete the old database and add new one
    col.delete_many({})
    col.insert_one({ "loopback_instance":loopback_instance, 
                     "bridge_instance":bridge_instance,
                     "vxlan_instance":vxlan_instance, 
                     "gre_instance":gre_instance 
                    }
                  )


# frr configuration
    
    with open("/etc/frr/frr.conf", "a") as f:
      f.write(f"\n!\nrouter bgp\n neighbor {gre_remote_looopback_addr} remote-as {data['remote_as_no']}\n neighbor {gre_remote_looopback_addr} peer-group upstream\n !\n address-family ipv4 unicast\n  network {loop2_addr}\n  neighbor {gre_remote_looopback_addr} next-hop-self\n  neighbor {gre_remote_looopback_addr} prefix-list list1 in\n  neighbor {gre_remote_looopback_addr} prefix-list list1 out\n exit-address-family\nexit\n!\n ")
    os.system(f"sudo service frr restart")
    return jsonify(response), 200

#------------------------------------------------------------------------------------------------------------------
#static route

@app.route('/static_route',  methods = ['POST'])
def static_route():
   data = request.json
   response = {"message":"successfull"}
   os.system(f"sudo ip route add {data['destination_network']} via {data['gateway']}")
   return jsonify(response), 200

#------------------------------------------------------------------------------------------------------------------
#Machine-ID - INFO

@app.route('/machine_id')
def get_machine_id():
    with open('/etc/machine-id', 'r') as f:
        return {'machine_id': f.read().strip()}

#------------------------------------------------------------------------------------------------------------------
#VPP Interface - INFO
@app.route('/vpp_interface_details')  
def get_vpp_interface_details():
    iface_list = vpp.api.sw_interface_dump()
    data = []
    int_ip = []
    for iface in iface_list:
        iface_ip = vpp.api.ip_address_dump(sw_if_index=iface.sw_if_index, is_ipv6=0)
        if len(iface_ip) !=0:
          for intip in iface_ip:
            int_ip = intip.prefix
        else:
          int_ip = "none"        
        
        colect = { "int_index":iface.sw_if_index, "int_mac_address":str(iface.l2_address), "int_speed":iface.link_speed, "int_link_mtu":iface.link_mtu, "int_ipv4_address":str(int_ip), "int_name":iface.interface_name, "int_mtu":iface.mtu[0], "int_status":iface.flags }
        data.append(colect)
    
    return data
#--------------------------------------------------------------------------------------------------------------------
@app.route('/asn')
def asn_number():
  data = {"as_no":65004}
  return data
#--------------------------------------------------------------------------------------------------------------------
#GRE Tunnel - INFO

@app.route('/gre_details')   
def get_gre_details():
	iface_list = vpp.api.gre_tunnel_dump()
	data = []
	for li in iface_list:
		for det in li:
			if(isinstance(det, tuple)):
				colect = {"src_address":str(det[7]), "dst_address":str(det[8]), "instance":det[4], "type":det[0]}
				data.append(colect)
	return data
#-----------------------------------------------------------------------------------------------------------------
#Vxlan Tunnel - INFO

@app.route('/vxlan_details')   
def get_vxlan_details():
    iface_list = vpp.api.vxlan_tunnel_v2_dump()
    data = []
    for iface in iface_list:
        colect = {"src_address":str(iface.src_address), "dst_address":str(iface.dst_address), "mcast_index":iface.mcast_sw_if_index, "encap_vrf_id":iface.encap_vrf_id, "vni":iface.vni, "decap_index":iface.decap_next_index}
        data.append(colect)
        
    return data
#------------------------------------------------------------------------------------------------------------------
@app.route('/vxlan_tunnel_details')   
def vxlan_details():
    data= []
    tunnel_details = col_vxlan_details.find({},{'_id':0})
    iface_list = vpp.api.vxlan_tunnel_v2_dump()
    for intfc in tunnel_details:
     for iface in iface_list:
        if str(iface.dst_address) == intfc["dst_address"]:
          if str(iface.src_address) == intfc["src_address"]:
           try:
            dst = intfc["dst_loopback_addr"].split("/")[0]
            command = (f"ping -c 5  {dst}")
            output = subprocess.check_output(command.split()).decode()
            lines = output.strip().split("\n")

        # Extract the round-trip time from the last line of output
            last_line = lines[-1].strip()
            rtt = last_line.split()[3]
            rtt_avg = rtt.split("/")[1]
              
            
           
           except subprocess.CalledProcessError:
              rtt_avg = -1           
           if rtt_avg != -1:
              colect ={"src_address":intfc["src_address"],
                "dst_address":intfc["dst_address"],
                "src_loopback_addr":intfc["src_loopback_addr"], 
                "dst_loopback_addr": intfc["dst_loopback_addr"],
                "rtt": rtt_avg,                   
                "status":"connected", 
                "encrypt":"PSK" 
                                  
                }
              
              data.append(colect)
           if rtt_avg == -1:
              colect ={"src_address":intfc["src_address"],
                "dst_address":intfc["dst_address"],
                "src_loopback_addr":intfc["src_loopback_addr"], 
                "dst_loopback_addr": intfc["dst_loopback_addr"],
                "rtt": rtt_avg,                   
                "status":"Not connected", 
                "encrypt":"PSK" 
                                  
                }
              
              data.append(colect)
          
    
    return (data)

#------------------------------------------------------------------------------
#Ipsec Tunnel - INFO
@app.route('/ipsec_details')   
def get_ipsec_details():
    tun_protect = vpp.api.ipsec_tunnel_protect_dump()
    data = []
    for iface in tun_protect:
        
        for ip in iface:
            if(isinstance(ip, tuple)):
                li = ip[4]
                colect = {"tunnel-id":ip[0], "sa-in":li[0], "sa-out":ip[2]}
                data.append(colect)
                
    return data   
#------------------------------------------------------------------------------------------------------------------------------------------


#--------------------------------------------------------------------------------------------------------------------------------------------
#Delete vxlan tunnel
@app.route('/vxlan_delete', methods = ['DELETE'])  
def vxlan_delete():
    vxlan_src_ip = request.args.get('vxlan_src_ip')
    vxlan_dst_ip = request.args.get('vxlan_dst_ip')
    response = {"message":"successfull"}
    vpp.api.vxlan_add_del_tunnel_v2(src_address=vxlan_src_ip, dst_address=vxlan_dst_ip, vni=24, is_add=0)
    return jsonify(response), 200
    
#----------------------------------------------------------------------------------------------------------------------------------
# function to insert outbound rule in ACL
proto_map = {   "HOPOPT": "0", 
                'ICMP': '1', 
                'IGMP': '2', 
                'TCP': '6',
                'UDP': '17', 
                'GRE': '47',
                'ESP': '50',
                'AH': '51', 
                'ICMP6': '58', 
                "EIGRP": '88',
                "OSPF": '89', 
                "SCTP": '132', 
                "Reserved": '255'
                }
                
@app.route('/outbound_aclrule', methods = ['POST'])  
def outbound_rule():
        data = request.json
        response = {"message":"successfull"}
        if data["protocol"] == "none":
          proto = "6"
        else:   
          proto = proto_map[data["protocol"]] 
        if data["src_port"] == "none":
          src_port = "0-65535"
        else:
          src_port = data["src_port"]
        if data["dst_port"] == "none":
          dst_port = "0-65535"
        else:
          dst_port = data["dst_port"] 
        
        acl_add = subprocess.check_output(["sudo", "vppctl", "set", "acl-plugin", "acl", data["action"], "src", data["source"], "dst", data["destination"], "sport", src_port, "dport", dst_port, "proto", proto, ",", "permit", "src", "any", "dst", "any"]).decode("utf-8")
        acl_ind = acl_add.split(":")[1]
        #os.system(f"sudo vppctl set acl-plugin acl {data['action']} src {data['source']} dst {data['destination']}, proto {data['protocol']} sport {data['sport_range']}, dport {data['dport_range']}, permit src any dst any")
        acl_int = vpp.api.acl_interface_add_del(is_add=1, is_input=0, sw_if_index=int(data["int_index"]), acl_index=int(acl_ind))
        return jsonify(response), 200
        
# function to insert outbound rule in ACL
@app.route('/inbound_aclrule', methods = ['POST'])  
def inbound_rule():
        data = request.json
        response = {"message":"successfull"}
        if data["protocol"] == "none":
          proto = "6"
        else:   
          proto = proto_map[data["protocol"]] 
        if data["src_port"] == "none":
          src_port = "0-65535"
        else:
          src_port = data["src_port"]
        if data["dst_port"] == "none":
          dst_port = "0-65535"
        else:
          dst_port = data["dst_port"] 
        
        acl_add = subprocess.check_output(["sudo", "vppctl", "set", "acl-plugin", "acl", data["action"], "src", data["source"], "dst", data["destination"], "sport", src_port, "dport", dst_port, "proto", proto, ",", "permit", "src", "any", "dst", "any"]).decode("utf-8")
        acl_ind = acl_add.split(":")[1]
        #os.system(f"sudo vppctl set acl-plugin acl {data['action']} src {data['source']} dst {data['destination']}, proto {data['protocol']} sport {data['sport_range']}, dport {data['dport_range']}, permit src any dst any")
        acl_int = vpp.api.acl_interface_add_del(is_add=1, is_input=1, sw_if_index=int(data["int_index"]), acl_index=int(acl_ind))
        return jsonify(response), 200


#----------------------------------------------------------------------------------------------------------------------------------
@app.route('/acl_status')  
def acl_status():
  i = 0
  data = []
  for i in range(100):
    stat = vpp.api.acl_dump(acl_index=i)
    if stat != []:
     rule = stat[0].r
     protocol = (rule[0].proto).value
     if protocol == 0:
       proto = "HOPOPT"
     elif protocol == 1:
       proto = "ICMP"
     elif protocol == 2:
       proto = "IGMP"
     elif protocol == 6:
      proto = "TCP"
     elif protocol == 17:
      proto = "UDP"
     elif protocol == 47:
      proto = "GRE"
     elif protocol == 50:
      proto = "ESP"
     elif protocol == 51:
      proto = "AH"
     elif protocol == 58:
      proto = "ICMP6"
     elif protocol == 88:
      proto = "EIGRP"
     elif protocol == 89:
       proto = "OSPF"
     elif protocol == 132:
       proto = "SCTP"
     elif protocol == 255:
       proto = "Reserved"

     act = (rule[0].is_permit).value
     if act == 0:
       action = "deny"
     elif act == 1:
       action = "permit"
     elif act ==2:
       action = "permit+reflect"
     if rule[0].srcport_or_icmptype_first == rule[0].srcport_or_icmptype_last:
       src_port = rule[0].srcport_or_icmptype_first
     else:
       src_port = str(rule[0].srcport_or_icmptype_first)+"-"+ str(rule[0].srcport_or_icmptype_last)
     if rule[0].dstport_or_icmpcode_first == rule[0].dstport_or_icmpcode_last:
       dst_port = rule[0].dstport_or_icmpcode_first
     else:
        dst_port = str(rule[0].dstport_or_icmpcode_first) + "-" + str(rule[0].dstport_or_icmpcode_last)
     colect = {"acl_index":i, "action":action, "src_port":src_port, "dst_port":dst_port, "source":str(rule[0].src_prefix), "destination":str(rule[0].dst_prefix), "protocol": proto}
  
    
     data.append(colect)
     i += 1 
    else:
      return data
#----------------------------------------------------------------------------------------------------------------------------------



#----------------------------------------------------------------------------------------------------------------------------------
# function to implement qos via policy based classification
@app.route('/qos_policy_add', methods = ['POST'])  
def qos_policy_add():
  data = request.json
  response = {'message':'successfull'}
  vpp.api.policer_add_del(is_add=1, name=data["policy_name"], conform_action={"type":2, "dscp":int(data["dscp"])})
  vpp.api.policer_input(name=data["policy_name"], sw_if_index=1, apply=1)
  vpp.api.policer_output(name=data["policy_name"], sw_if_index=1, apply=1)
  vpp.api.sw_interface_set_tx_placement(sw_if_index=int(data["int_index"]), queue_id=int(data["queue_id"]))
  vpp.api.sw_interface_set_rx_placement(sw_if_index=int(data["int_index"]), queue_id=int(data["queue_id"]))
  vpp.api.classify_add_del_session(is_add=1, table_index=0, hit_next_index=1, match_len=len(data["match"]), match = str.encode(data["match"]), opaque_index=1)
  vpp.api.qos_record_enable_disable(enable=1, record={"sw_if_index":int(data["int_index"]), "input_source":3})
  vpp.api.qos_mark_enable_disable(enable=1, mark={"sw_if_index":int(data["int_index"]), "output_source":3})
  return jsonify(response), 200

def get_openvpn_tunnel_ip():
  interface_details = get_netns_interface_details()
  for intfc in interface_details:
    if "IPv4address" in intfc:
      if ipaddress.ip_address(intfc["IPv4address_noprefix"]) in ipaddress.ip_network('10.8.0.0/24'):
        return intfc["IPv4address_noprefix"]
  
tunnel_ip = str(get_openvpn_tunnel_ip())
if __name__ == '__main__':
    app.run(host=tunnel_ip, port=5000)


