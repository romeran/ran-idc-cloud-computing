import json

import requests


class DataNodeSpecification:

    def __init__(self, instance_id, private_dns):
        self.instance_id = instance_id
        self.private_dns = private_dns


class DataNodeClient:

    @staticmethod
    def set_replica(private_dns, key, value):
        payload = {
            'key': key,
            'value': value
        }

        requests.post(f'http://{private_dns}/set-replica', data=json.dumps(payload))

    @staticmethod
    def get(private_dns, key):
        res = requests.get(f'http://{private_dns}/get/{key}')
        return res.json()
