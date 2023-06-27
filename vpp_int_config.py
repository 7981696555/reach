import os
import pymongo
import subprocess

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["int_details"]
coll_interface_info = db["ubuntu_interface_info"]
coll_vpp_pci_info = db["vpp_pci_info"]
coll_vpp_pci_info.delete_many({})

interface_details = subprocess.check_output(["sudo", "vppctl", "show", "hardware-interfaces"]).decode()
with open("int_details.txt", "w") as f:
  f.write(interface_details)
pci_out1 = subprocess.check_output(["awk", "/Gigabit/ {print $1} /pci/ {print $7}", "int_details.txt"]).decode()
pci_out2 = pci_out1.split("\n")
j=0
list_len = int(len(pci_out2)/2)
for i in range(list_len):
  colect = {"interface_name":pci_out2[j], "pci_address":pci_out2[j+1]}
  j = j+2
  coll_vpp_pci_info.insert_one(colect)

for  i in coll_vpp_pci_info.find():
  for j in coll_interface_info.find():
    if "pci_address" in j:
      if i["pci_address"] == j["pci_address"]:
       
         query = {"pci_address":j["pci_address"]}
         update_data = {"$set": {"IPv4address": j["IPv4address"]}}
         coll_vpp_pci_info.update_many(query, update_data)
         query = {"pci_address":j["pci_address"]}
         update_data1 = {"$set": {"type": j["type"]}}
         coll_vpp_pci_info.update_many(query, update_data1)
         with open("/etc/vpp/bootstrap.vpp", "a") as f:
           f.write(f"\nset int state {i['interface_name']} up\nset int mtu packet 1500 {i['interface_name']}\nset int ip address {i['interface_name']} {j['IPv4address']}\nlcp create {i['interface_name']} host-if {j['interface_name']}\nlcp lcp-sync on\nlcp lcp-auto-subint on\n")
          
         if "gateway" in j:
           with open("/etc/vpp/bootstrap.vpp", "a") as f:
             f.write(f"\nip route add 0.0.0.0/0 via {j['gateway']}\n")
           with open ("/etc/frr/frr.conf", "a") as f:
             f.write(f"\n!\nip route 0.0.0.0/0 {j['gateway']}\n!\n")
           
           query = {"pci_address":j["pci_address"]}
           update_data = {"$set": {"gateway": j["gateway"]}}
           coll_vpp_pci_info.update_many(query, update_data)
#---------------------------
#nat configuration 
 
lan_count = 0
wan_count = 0
for  i in coll_vpp_pci_info.find():
  if wan_count == 0:
    if i["type"] == "wan":
      nat_intfc_out = i["interface_name"]
      wan_count =1
    if lan_count == 0:
      if i["type"] == "lan":
        nat_intfc_in = i["interface_name"]
        lan_count = 1
         
with open("/etc/vpp/bootstrap.vpp", "a") as f:
  f.write(f"\nnat44 plugin enable sessions 10000\nnat44 forwarding enable\nnat44 add interface address {nat_intfc_out}\nset int nat44 in {nat_intfc_in} out {nat_intfc_out}\n")

interface_vpp = []
for intfc in coll_vpp_pci_info.find({},{'_id':0}):
    interface_vpp.append(intfc)

print(interface_vpp)	
os.system("sudo service vpp restart")    
os.system(f"sudo service frr restart")
os.system("sudo mv /etc/netplan/00-installer-config.yaml .") 

	     

