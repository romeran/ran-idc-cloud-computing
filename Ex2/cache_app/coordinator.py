from .hash_ring import HashRing
from .datanode import DataNodeClient

REPLICATION_FACTOR = 2


class CacheCoordinator:

    def __init__(self, hash_ring: HashRing, instance_id: str):
        self.hash_ring = hash_ring
        self.instance_id = instance_id

        self.storage = {}

    def set(self, key, value):
        for node in self.hash_ring.range(key=key, size=REPLICATION_FACTOR):
            datanode = node['instance']
            if datanode.instance_id == self.instance_id:
                # store in local node
                datanode.set_data(key, value)
            else:
                key_datanode = self.hash_ring.get_node_instance(key)
                DataNodeClient.set_replica(key_datanode.private_dns, key, value)

    def get_value_from_datanode(self, key):
        key_datanode = self.hash_ring.get_node_instance(key)
        if key_datanode.instance_id == self.instance_id:
            return self.storage.get(key)

        else:
            return DataNodeClient.get(key_datanode.private_dns, key)

    def set_replica(self, key, value):
        self.storage[key] = value

    def get_dn_content(self):
        return self.storage
