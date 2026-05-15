import boto3
import base64

region = 'ap-south-1'

ec2 = boto3.client('ec2', region_name=region)
elbv2 = boto3.client('elbv2', region_name=region)
autoscaling = boto3.client('autoscaling', region_name=region)

# -------------------------------
# 1. Create Security Group
# -------------------------------
# sg = ec2.create_security_group(
#     GroupName='web-sg',
#     Description='Allow HTTP'
# )

# sg_id = sg['GroupId']

# ec2.authorize_security_group_ingress(
#     GroupId=sg_id,
#     IpPermissions=[
#         {
#             'IpProtocol': 'tcp',
#             'FromPort': 80,
#             'ToPort': 80,
#             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
#         }
#     ]
# )

# print("Security Group:", sg_id)


# Check if SG already exists
response = ec2.describe_security_groups(
    Filters=[{'Name': 'group-name', 'Values': ['web-sg']}]
)

if response['SecurityGroups']:
    sg_id = response['SecurityGroups'][0]['GroupId']
    print("Using existing Security Group:", sg_id)
else:
    sg = ec2.create_security_group(
        GroupName='web-sg',
        Description='Allow HTTP'
    )
    sg_id = sg['GroupId']

    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {
                'IpProtocol': 'tcp',
                'FromPort': 80,
                'ToPort': 80,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            }
        ]
    )

    print("Created Security Group:", sg_id)

# -------------------------------
# 2. Get Default VPC + Subnets
# -------------------------------
vpcs = ec2.describe_vpcs()
vpc_id = vpcs['Vpcs'][0]['VpcId']

subnets = ec2.describe_subnets()
subnet_ids = [s['SubnetId'] for s in subnets['Subnets'][:2]]

# -------------------------------
# 3. Create Target Group
# -------------------------------
# tg = elbv2.create_target_group(
#     Name='web-tg',
#     Protocol='HTTP',
#     Port=80,
#     VpcId=vpc_id,
#     TargetType='instance'
# )

# tg_arn = tg['TargetGroups'][0]['TargetGroupArn']



try:
    tg = elbv2.describe_target_groups(Names=['web-tg'])
    tg_arn = tg['TargetGroups'][0]['TargetGroupArn']
    print("Using existing Target Group")

except:
    tg = elbv2.create_target_group(
        Name='web-tg',
        Protocol='HTTP',
        Port=80,
        VpcId=vpc_id,
        TargetType='instance'
    )
    tg_arn = tg['TargetGroups'][0]['TargetGroupArn']
    print("Created Target Group")

# -------------------------------
# 4. Create Load Balancer
# -------------------------------
# lb = elbv2.create_load_balancer(
#     Name='web-alb',
#     Subnets=subnet_ids,
#     SecurityGroups=[sg_id],
#     Scheme='internet-facing',
#     Type='application'
# )

# lb_arn = lb['LoadBalancers'][0]['LoadBalancerArn']
# dns = lb['LoadBalancers'][0]['DNSName']

# print("ALB DNS:", dns)

# -------------------------------
# 4. Create or Get Load Balancer
# -------------------------------
try:
    lb = elbv2.describe_load_balancers(Names=['web-alb'])
    lb_arn = lb['LoadBalancers'][0]['LoadBalancerArn']
    dns = lb['LoadBalancers'][0]['DNSName']
    print("Using existing ALB:", dns)

except elbv2.exceptions.LoadBalancerNotFoundException:
    lb = elbv2.create_load_balancer(
        Name='web-alb',
        Subnets=subnet_ids,
        SecurityGroups=[sg_id],
        Scheme='internet-facing',
        Type='application'
    )

    lb_arn = lb['LoadBalancers'][0]['LoadBalancerArn']
    dns = lb['LoadBalancers'][0]['DNSName']

    print("Created ALB:", dns)

# -------------------------------
# 5. Create Listener
# -------------------------------
elbv2.create_listener(
    LoadBalancerArn=lb_arn,
    Protocol='HTTP',
    Port=80,
    DefaultActions=[
        {
            'Type': 'forward',
            'TargetGroupArn': tg_arn
        }
    ]
)

# -------------------------------
# 6. Read User Data
# -------------------------------
with open('user_data.sh', 'r') as f:
    user_data = f.read()

# -------------------------------
# 7. Create Launch Template
# -------------------------------
# lt = ec2.create_launch_template(
#     LaunchTemplateName='web-template',
#     LaunchTemplateData={
#         'ImageId': 'ami-0f5ee92e2d63afc18',
#         'InstanceType': 't2.micro',
#         'SecurityGroupIds': [sg_id],
#         'UserData': base64.b64encode(user_data.encode()).decode()
#     }
# )

# lt_id = lt['LaunchTemplate']['LaunchTemplateId']



try:
    lt = ec2.describe_launch_templates(
        LaunchTemplateNames=['web-template']
    )
    lt_id = lt['LaunchTemplates'][0]['LaunchTemplateId']
    print("Using existing Launch Template")

except:
    lt = ec2.create_launch_template(
        LaunchTemplateName='web-template',
        LaunchTemplateData={
            'ImageId': 'ami-0f5ee92e2d63afc18',
            'InstanceType': 't2.micro',
            'SecurityGroupIds': [sg_id],
            'UserData': base64.b64encode(user_data.encode()).decode()
        }
    )
    lt_id = lt['LaunchTemplate']['LaunchTemplateId']
    print("Created Launch Template")

# -------------------------------
# 8. Create Auto Scaling Group
# -------------------------------
# autoscaling.create_auto_scaling_group(
#     AutoScalingGroupName='web-asg',
#     LaunchTemplate={
#         'LaunchTemplateId': lt_id,
#         'Version': '$Latest'
#     },
#     MinSize=2,
#     MaxSize=4,
#     DesiredCapacity=2,
#     VPCZoneIdentifier=",".join(subnet_ids),
#     TargetGroupARNs=[tg_arn]
# )

# print("Auto Scaling Group created")



# -------------------------------
# 8. Create or Update Auto Scaling Group
# -------------------------------
asg_name = 'web-asg'

response = autoscaling.describe_auto_scaling_groups(
    AutoScalingGroupNames=[asg_name]
)

if response['AutoScalingGroups']:
    print("Updating existing Auto Scaling Group")

    autoscaling.update_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        LaunchTemplate={
            'LaunchTemplateId': lt_id,
            'Version': '$Latest'
        },
        MinSize=2,
        MaxSize=4,
        DesiredCapacity=2,
        VPCZoneIdentifier=",".join(subnet_ids)
    )

else:
    print("Creating Auto Scaling Group")

    autoscaling.create_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        LaunchTemplate={
            'LaunchTemplateId': lt_id,
            'Version': '$Latest'
        },
        MinSize=2,
        MaxSize=4,
        DesiredCapacity=2,
        VPCZoneIdentifier=",".join(subnet_ids),
        TargetGroupARNs=[tg_arn]
    )
    
autoscaling.attach_load_balancer_target_groups(
    AutoScalingGroupName=asg_name,
    TargetGroupARNs=[tg_arn]
)