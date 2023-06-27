import pymongo
import os
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["int_details"]
coll_interface_info = db["ubuntu_interface_info"]

def dev_bind():
  for i in coll_interface_info.find():
    if "pci_address" in i:
      intfc_name = i["interface_name"]
      print(intfc_name)
      print(os.system(f"sudo python3 dpdk-devbind.py --bind=vfio-pci {intfc_name}"))
      os.system("sudo service vpp restart")
	  
dev_bind()
