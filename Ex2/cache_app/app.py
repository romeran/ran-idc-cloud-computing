import os
import boto3
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request
from .coordinator import CacheCoordinator
from .datanode import DataNodeSpecification
from .hash_ring import HashRing

session = boto3.Session(region_name='us-east-1')
elb = session.client('elbv2')
ec2 = session.client('ec2')

app = Flask(__name__)

instance_id = os.environ.get("INSTANCE_ID")

# Initialize empty hash ring
hash_ring = HashRing()
coordinator = CacheCoordinator(hash_ring, instance_id)


def populate_datanode_state():
    def get_targets_status():
        target_group = elb.describe_target_groups(Names=["cache-elb-tg"])
        target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
        health = elb.describe_target_health(TargetGroupArn=target_group_arn)
        healthy = []
        sick = {}
        for target in health["TargetHealthDescriptions"]:
            if target["TargetHealth"]["State"] == "unhealthy":
                sick[target["Target"]["Id"]] = target["TargetHealth"]["Description"]
            else:
                healthy.append(target["Target"]["Id"])
        return healthy, sick

    target_groups = get_targets_status()

    healthy = target_groups[0]
    for healthy_instance in healthy:
        private_dns = ec2.describe_instances(
            InstanceIds=[healthy_instance]).get("Reservations")[0]['Instances'][0]['PrivateDnsName']

        dn_config = {
            'hostname': healthy_instance,
            'instance': DataNodeSpecification(instance_id=healthy_instance, private_dns=private_dns)
        }

        hash_ring.add_node(healthy_instance, dn_config)

    sick = list(target_groups[1].keys())
    for sick_instance in sick:
        # might be that the instance has registered but not yet initialized
        if hash_ring.get_node(sick_instance):
            hash_ring.remove_node(sick_instance)


scheduler = BackgroundScheduler()
scheduler.add_job(func=populate_datanode_state, trigger="interval", seconds=5)
scheduler.start()


@app.route('/')
def index():
    return "Hello cache!"


@app.route('/set', methods=['POST'])
def set_data():
    data = request.json
    key = data['key']
    value = data['value']
    coordinator.set(key, value)
    return ""


@app.route('/set-replica', methods=['POST'])
def set_replica():
    data = request.json
    key = data['key']
    value = data['value']
    coordinator.set_replica(key, value)
    return ""


@app.route('/get/<key>', methods=['GET'])
def get_data(key):
    return coordinator.get_value_from_datanode(key)


@app.route('/get-content', methods=['GET'])
def get_content():
    return coordinator.get_dn_content()


@app.route('/health', methods=['GET'])
def health():
    return "Healthy"
