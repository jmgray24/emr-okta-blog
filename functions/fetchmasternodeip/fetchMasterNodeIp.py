import boto3
from crhelper import CfnResource

helper = CfnResource(
	json_logging=False,
	log_level='DEBUG', 
	boto_level='CRITICAL'
)

def handler(event, context):
    helper(event, context)

@helper.create
@helper.update
def fetch_ip(event, context):
    cluster_id = event['ResourceProperties']['ClusterId']
    emr = boto3.client('emr')
    instances = emr.list_instances(
        ClusterId=cluster_id,
        InstanceGroupTypes=[
            'MASTER',
        ],
        InstanceStates=[
            'RUNNING',
        ]
    )
    helper.Data['MasterNodeIp'] = instances['Instances'][0]['PrivateIpAddress']
    helper.Data['MasterNodeInstanceId'] = instances['Instances'][0]['Ec2InstanceId']
    print(instances['Instances'][0]['PrivateIpAddress'])
    print(instances['Instances'][0]['Ec2InstanceId'])

@helper.delete
def no_op(_, __):
    pass