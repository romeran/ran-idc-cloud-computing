import base64

import boto3
from botocore import exceptions

PREFIX = "cache-elb"
PROFILE_NAME = 'default-ran'

session = boto3.Session(profile_name=PROFILE_NAME)
# session = boto3.Session(region_name='us-east-1')

elb = session.client('elbv2')
iam = session.client('iam')
ec2 = session.client('ec2')
s3 = session.client('s3')

CACHE_INSTANCE_INIT_SCRIPT = """
#!/bin/bash -x

sudo apt-get update --yes
sudo apt-get install --yes --allow-unauthenticated \
              aws virtualenv python3-pip python3-venv unzip
              
aws s3api get-object --bucket idc-ex2-cache-app-bucket --key cache_app.zip cache_app.zip
export INSTANCE_ID=$(curl http://169.254.169.254/latest/meta-data/instance-id)
unzip cache_app.zip

python3 -m venv cache-app-env
source tutorial-env/bin/activate

cd cache_app
pip install -r requirements.txt

flask run --port=8080 --host=0.0.0.0 
echo "Cache node up" > /home/ubuntu/cache_node  
"""


def init_security_groups(vpc_id):
    try:
        response = ec2.describe_security_groups(GroupNames=[PREFIX + "elb-access"])
        elb_access = response["SecurityGroups"][0]
        response = ec2.describe_security_groups(GroupNames=[PREFIX + "instance-access"])
        instance_access = response["SecurityGroups"][0]
        return {
            "elb-access": elb_access["GroupId"],
            "instance-access": instance_access["GroupId"],
        }
    except exceptions.ClientError as e:
        if e.response['Error']['Code'] != 'InvalidGroup.NotFound':
            raise e

    vpc = ec2.describe_vpcs(VpcIds=[vpc_id])
    cidr_block = vpc["Vpcs"][0]["CidrBlock"]

    elb = ec2.create_security_group(
        Description="ELB External Access",
        GroupName=PREFIX + "elb-access",
        VpcId=vpc_id)

    elb_sg = session.resource('ec2').SecurityGroup(elb["GroupId"])
    elb_sg.authorize_ingress(
        CidrIp="0.0.0.0/0",
        FromPort=80,
        ToPort=80,
        IpProtocol="TCP")

    instances = ec2.create_security_group(
        Description="ELB Access to instances",
        GroupName=PREFIX + "instance-access",
        VpcId=vpc_id)

    instance_sg = session.resource('ec2').SecurityGroup(instances["GroupId"])
    instance_sg.authorize_ingress(
        CidrIp=cidr_block,
        FromPort=8080,
        ToPort=8080,
        IpProtocol="TCP",
    )
    return {
        "elb-access": elb["GroupId"],
        "instance-access": instances["GroupId"]
    }


def get_default_subnets():
    response = ec2.describe_subnets(
        Filters=[{"Name": "default-for-az", "Values": ["true"]}]
    )
    subnetIds = [s["SubnetId"] for s in response["Subnets"]]
    return subnetIds


# creates the ELB as well as the target group
# that it will distribute the requests to
def ensure_elb_setup_created():
    response = None
    try:
        response = elb.describe_load_balancers(Names=[PREFIX])
    except exceptions.ClientError as e:
        if e.response['Error']['Code'] != 'LoadBalancerNotFound':
            raise e
        subnets = get_default_subnets()
        response = elb.create_load_balancer(
            Name=PREFIX,
            Scheme='internet-facing',
            IpAddressType='ipv4',
            Subnets=subnets)

    elb_arn = response["LoadBalancers"][0]["LoadBalancerArn"]
    vpc_id = response["LoadBalancers"][0]["VpcId"]
    results = init_security_groups(vpc_id)
    elb.set_security_groups(
        LoadBalancerArn=elb_arn,
        SecurityGroups=[results["elb-access"]])

    target_group = None
    try:
        target_group = elb.describe_target_groups(Names=[PREFIX + "-tg"])

    except exceptions.ClientError as e:
        if e.response['Error']['Code'] != 'TargetGroupNotFound':
            raise e

        target_group = elb.create_target_group(
            Name=PREFIX + "-tg",
            Protocol="HTTP",
            Port=80,
            VpcId=vpc_id,
            HealthCheckProtocol="HTTP",
            HealthCheckPort="8080",
            HealthCheckPath="/health",
            TargetType="instance")

    target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
    listeners = elb.describe_listeners(LoadBalancerArn=elb_arn)
    if len(listeners["Listeners"]) == 0:
        elb.create_listener(
            LoadBalancerArn=elb_arn,
            Protocol="HTTP",
            Port=80,
            DefaultActions=[
                {
                    "Type": "forward",
                    "TargetGroupArn": target_group_arn,
                    "Order": 100
                }
            ])

    return results


def register_instance_in_elb(instance_id):
    results = ensure_elb_setup_created()
    target_group = elb.describe_target_groups(
        Names=[PREFIX + "-tg"],
    )
    instance = session.resource('ec2').Instance(instance_id)
    sgs = [sg["GroupId"] for sg in instance.security_groups]
    sgs.append(results["instance-access"])
    instance.modify_attribute(
        Groups=sgs
    )
    target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
    elb.register_targets(
        TargetGroupArn=target_group_arn,
        Targets=[{
            "Id": instance_id,
            "Port": 8080
        }]
    )


def create_instance():
    response = ec2.run_instances(
        ImageId="ami-09e67e426f25ce0d7",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        SecurityGroupIds=[
            "sg-01f62ba7ff6ff3d2c"
        ],
        IamInstanceProfile={
            'Name': 'CacheNodeInstance',
        },
        KeyName='cache-keypair',
        UserData=base64.b64encode(CACHE_INSTANCE_INIT_SCRIPT.encode('ascii')))

    return response['Instances'][0]['InstanceId']


def upload_cache_app():
    import os
    import zipfile

    cache_app_zip = "cache_app.zip"
    zf = zipfile.ZipFile("cache_app.zip", "w")
    for dirname, subdirs, files in os.walk("cache_app"):
        zf.write(dirname)
        for filename in files:
            zf.write(os.path.join(dirname, filename))
    zf.close()

    bucket_name = "idc-ex2-cache-app-bucket"
    # s3.create_bucket(Bucket=bucket_name)

    s3.upload_file(cache_app_zip, bucket_name, cache_app_zip)


def deploy_app():
    ensure_elb_setup_created()
    upload_cache_app()

    # create and register two instances
    first_instance_id = create_instance()
    second_instance_id = create_instance()

    register_instance_in_elb(first_instance_id)
    register_instance_in_elb(second_instance_id)


def provision_cache_node():
    pass


def kill_cache_node():
    pass


def list_cache_node_ids():
    pass


if __name__ == "__main__":
    print(create_instance())
    # register_instance_in_elb("i-05b62076406e69011")
    # upload_cache_app()
