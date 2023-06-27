import pymongo
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["iteration_variable"]
col = db["instance_list"]
col.delete_many({})
col.insert_one({ "loopback_instance":3, "bridge_instance":3, "vxlan_instance":3, "gre_instance":3 })