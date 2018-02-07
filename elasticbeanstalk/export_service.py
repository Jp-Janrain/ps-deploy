"""Deploy ElasticBeanstalk environments for Professional Services."""

import argparse
import copy
import json
import logging
import re
import sys
from time import sleep

import boto3

from devops import region_data
from devops.aws import arn
from devops.utils import prompt_yn, aws2dict, dict2aws

logger = logging.getLogger()

SOLUTION_STACK_NAME = "64bit Amazon Linux 2017.03 v2.5.2 running Python 3.4"


class deploy_export_service(object):
    """
    Deploy ElasticBeanstalk environments for Professional Services.

    This function-like class creates an "export-service" environment with a
    standard naming convention and adds the needed permissions to the IAM role
    to allow Delivery to change configuration and test exports by adding an
    event to the worker SQS queue.
    """

    def __init__(self, args):
        """Deploy the export-service environment."""
        self.session = boto3.Session(profile_name=args.profile,
                                     region_name=args.region)
        self.arn = arn.boto_arn(sess=self.session)
        self.ec2_client = self.session.client('ec2')
        self.eb_client = self.session.client('elasticbeanstalk')
        self.dynamodb_client = self.session.client('dynamodb')
        self.iam_client = self.session.client('iam')
        self.environment = args.environment
        self.subenv = args.customer_name
        env_name = "-".join([args.customer_name, args.environment])
        self.environment_name = env_name
        self.stackdriver_key_bucket = args.keybucket

        if args.vpc_id:
            vpc = args.vpc_id
        # default to deploying to the services account
        elif region_data.by_aws_name[args.region].services_vpc:
            vpc = region_data.by_aws_name[args.region].services_vpc
        else:
            vpc = region_data.by_aws_name[args.region].dip_vpc

        self.vpc = self._get_vpc_details(vpc)
        self.setup_application()
        self.setup_environment()
        self.setup_dynamodb()
        self.setup_beanstalk_config()
        self.update_iam_polices()
        logger.info("Done")

    def _wait_on_env_status(self):
        status = "Checking"
        while status != 'Ready':
            response = self.eb_client.describe_environments(
                ApplicationName='export-service',
                EnvironmentNames=[self.environment_name])
            status = response['Environments'][0]['Status']
            logger.info("Environment status: {}".format(status))
            sleep(3)

    def _get_vpc_details(self, vpc_id):
        def get_layer(subnet):
            tags = subnet["Tags"]
            name = aws2dict(tags)['Name']
            return name.split("-")[0]

        response = self.ec2_client.describe_vpcs(VpcIds=[vpc_id])
        vpc = {"vpc_id": vpc_id,
               "ec2subnets": [],
               "elbsubnets": [],
               "dbsubnets": []}
        response = self.ec2_client.describe_subnets(
            Filters=[{'Name': 'vpc-id',
                      'Values': [vpc_id]}]
        )
        logger.debug("describe subnets: {}".format(response))
        subnets = response['Subnets']
        for subnet in subnets:
            layer = get_layer(subnet)
            if layer == 'app':
                vpc["ec2subnets"].append(subnet["SubnetId"])
            elif layer == 'border':
                vpc["elbsubnets"].append(subnet["SubnetId"])
            elif layer == 'storage':
                vpc["dbsubnets"].append(subnet["SubnetId"])
            else:
                logger.debug("skipping subnet in layer {}: {}".format(
                             layer, subnet))
        return vpc

    def check_for_application(self):
        """Check if the "export-service" application exists."""
        logger.info("Checking for Application")
        response = self.eb_client.describe_applications()
        logger.debug("describe applications: {}".format(response))
        for app in response['Applications']:
            if app['ApplicationName'] == 'export-service':
                return True
        return False

    def check_for_environment(self):
        """Check if the given environment exists in the region."""
        logger.info("Checking if Environment exists within Application")
        response = self.eb_client.describe_environments(
            ApplicationName='export-service')
        logger.debug("describe environments: {}".format(response))
        env_names = [e['EnvironmentName'] for e in response['Environments']]
        logger.info("Found export-service environments: {}".format(env_names))
        for name in env_names:
            if name == self.environment_name:
                return True
        return False

    def create_application(self):
        """Create the "export-service" application."""
        role_name = "aws-elasticbeanstalk-service-role"
        service_role = "arn:{}:iam::{}:role/{}".format(
            self.arn.partition, self.arn.account, role_name)
        response = self.eb_client.create_application(
            ApplicationName='export-service',
            Description='Customer specific export service apps',
            ResourceLifecycleConfig={'ServiceRole': service_role}
        )
        logger.debug("create application: {}".format(response))

    def create_environment(self):
        """Create the environment for the customer."""
        security_group = self.create_sg()
        tags = {'region': self.session.region_name,
                'group': 'export-service',
                'env': "prod",
                'subenv': self.subenv,
                'name': "{}-export-service".format(self.subenv)}
        response = self.eb_client.create_environment(
            ApplicationName='export-service',
            EnvironmentName=self.environment_name,
            Tier={'Name': 'Worker', 'Type': 'SQS/HTTP'},
            Tags=dict2aws(tags),
            SolutionStackName=(SOLUTION_STACK_NAME),
            OptionSettings=[
                {'Namespace': 'aws:ec2:vpc',
                 'OptionName': 'VPCId',
                 'Value': self.vpc['vpc_id']},
                {'Namespace': 'aws:ec2:vpc',
                 'OptionName': 'Subnets',
                 'Value': ", ".join(self.vpc["ec2subnets"])},
                {'Namespace': 'aws:ec2:vpc',
                 'OptionName': 'ELBSubnets',
                 'Value': ", ".join(self.vpc["elbsubnets"])},
                {'Namespace': 'aws:ec2:vpc',
                 'OptionName': 'DBSubnets',
                 'Value': ", ".join(self.vpc["dbsubnets"])},
                {'Namespace': 'aws:ec2:vpc',
                 'OptionName': 'AssociatePublicIpAddress',
                 'Value': 'true'},
                {'Namespace': 'aws:autoscaling:launchconfiguration',
                 'OptionName': 'SecurityGroups',
                 'Value': security_group},
                {'Namespace': 'aws:autoscaling:launchconfiguration',
                 'OptionName': 'InstanceType',
                 'Value': 't2.micro'},
                {'Namespace': 'aws:autoscaling:launchconfiguration',
                 'OptionName': 'IamInstanceProfile',
                 'Value': 'export-service-elasticbeanstalk-ec2-worker-role'},
                {'Namespace': 'aws:elasticbeanstalk:environment',
                 'OptionName': 'EnvironmentType',
                 'Value': 'SingleInstance'},
                {'Namespace': 'aws:elasticbeanstalk:environment',
                 'OptionName': 'ServiceRole',
                 'Value': 'aws-elasticbeanstalk-service-role'},
            ]
        )
        logger.debug("create environment: {}".format(response))

    def create_sg(self):
        """Create the security group for instances of the environment."""
        sg_name = "{}-export-service".format(self.subenv)
        response = self.ec2_client.describe_security_groups(Filters=[
                        {'Name': 'vpc-id',
                         'Values': [self.vpc["vpc_id"]]},
                        {'Name': 'group-name',
                         'Values': [sg_name]}
                    ])
        logger.debug("describe sgs: {}".format(response))
        try:
            sg_id = response['SecurityGroups'][0]['GroupId']
            logger.info("found sg {}: {}".format(sg_name, sg_id))
        except:
            response = self.ec2_client.create_security_group(
                GroupName=sg_name,
                Description="{}-export-service".format(self.subenv),
                VpcId=self.vpc['vpc_id']
            )
            logger.debug("create sg: {}".format(response))
            sg_id = response['GroupId']
            logger.info("created sg")

        return sg_id

    def get_current_policy(self, policy_name):
        """Get the latest version of an IAM policy."""
        response = self.iam_client.list_policies(Scope='Local')
        polices = [(p['PolicyName'], p['Arn']) for p in response['Policies']]
        for policy in polices:
            if policy_name == policy[0]:
                arn = policy[1]
                response = self.iam_client.list_policy_versions(
                    PolicyArn=arn
                )
                versions = response['Versions']
                # this could be better...
                latest_date = max([v['CreateDate'] for v in versions])
                latest_version = [v['VersionId'] for v in versions
                                  if v['CreateDate'] == latest_date][0]

                sorted_versions = sorted(
                    versions, key=lambda version: version['CreateDate'])
                latest_version = sorted_versions[-1]

                if len(versions) == 5:
                    logger.info("Five policy versions found for {}. "
                                "Deleting the oldest".format(arn))
                    oldest_version = sorted_versions[0]
                    response = self.iam_client.delete_policy_version(
                        PolicyArn=arn,
                        VersionId=oldest_version['VersionId']
                    )

                response = self.iam_client.get_policy_version(
                    PolicyArn=arn,
                    VersionId=latest_version['VersionId']
                )
                policy_doc = response['PolicyVersion']['Document']
                return arn, policy_doc
        return

    def get_resources(self):
        """Get the worker queue and CloudFormation stack for the environment."""
        response = self.eb_client.describe_environment_resources(
            EnvironmentName=self.environment_name)
        logger.debug("describe environment resources: {}".format(response))
        queues = response['EnvironmentResources']['Queues']
        worker_queue_url = [q['URL'] for q in queues
                            if q['Name'] == "WorkerQueue"]
        worker_queue = re.search('/(awseb-e-.*)', worker_queue_url[0]).group(1)
        env_resources = response['EnvironmentResources']
        launch_config = env_resources['LaunchConfigurations'][0]['Name']
        cf_stack = re.search('(awseb-e-.*-stack)', launch_config).group(1)
        return worker_queue, cf_stack

    def get_stackdriver_key(self):
        """Retrieve the Stackdriver key from s3 for instance monitoring."""
        s3_client = self.session.client('s3')
        response = s3_client.get_object(
            Bucket=self.stackdriver_key_bucket,
            Key='multi/stackdriver/stackdriver.key'
        )
        return response['Body'].read().rstrip()

    def setup_application(self):
        """Create the "export-service" environment if it does not exist."""
        if self.check_for_application():
            logger.info("Application 'export-service' found")
        else:
            logger.info("export-service application not found")
            prompt = ("Did not find application \"export-service\" in {} for "
                      "account profile \"{}\".\nDo you want to create it?"
                      ).format(self.session.region_name,
                               self.session.profile_name)
            if prompt_yn(prompt):
                logger.info("Creating app 'export-service'")
                self.create_application()
            else:
                raise SystemExit("Exiting")

    def setup_beanstalk_config(self):
        """
        Configure the environment.

        Adds HttpPath, HttpConnections, and the Stackdriver key to the
        environment.
        """
        self._wait_on_env_status()
        option_settings = [
            {'Namespace': 'aws:elasticbeanstalk:sqsd',
             'OptionName': 'HttpPath',
             'Value': '/export'},
            {'Namespace': 'aws:elasticbeanstalk:sqsd',
             'OptionName': 'HttpConnections',
             'Value': '10'}
        ]
        if self.session.region_name == "cn-north-1":
            logger.info("skipping stackdriver key since there is none in cn")
        else:
            sd_key = self.get_stackdriver_key()
            option_settings.append({
                'Namespace': 'aws:elasticbeanstalk:application:environment',
                'OptionName': 'STACKDRIVER_API_KEY',
                'Value': sd_key
            })
        response = self.eb_client.update_environment(
            ApplicationName='export-service',
            EnvironmentName=self.environment_name,
            OptionSettings=option_settings
        )
        logger.debug("update_environment: {}".format(response))

    def setup_dynamodb(self):
        """Create the "export-service" dynamodb table if it does not exist."""
        response = self.dynamodb_client.list_tables()
        if 'export-service' in response['TableNames']:
            logger.info("Found table export-service")
        else:
            response = self.dynamodb_client.create_table(
                AttributeDefinitions=[
                    {'AttributeName': 'job_id',
                     'AttributeType': 'S'},
                ],
                TableName='export-service',
                KeySchema=[
                    {'AttributeName': 'job_id',
                     'KeyType': 'HASH'},
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 1,
                    'WriteCapacityUnits': 1
                }
            )
            logger.debug("create table: {}".format(response))
            logger.info("export-service table created")
        return True

    def setup_environment(self):
        """Create the customer's environment if it does not exist."""
        if self.check_for_environment():
            logger.info("Environment {} found".format(self.environment_name))
        else:
            prompt = ("Did not find environment {} for application "
                      "'export-service' in {} for account profile \"{}\""
                      ".\nDo you want to create it?").format(
                      self.environment_name, self.session.region_name,
                      self.session.profile_name)
            if prompt_yn(prompt):
                logger.info("Creating environment: {}".format(
                    self.environment_name))
                response = self.create_environment()
                logger.debug("create environment: {}".format(response))
            else:
                raise SystemExit("Exiting")

    def update_iam_polices(self):
        """
        Update IAM policies to allow Delivery to configure the "export-service"
        environment.
        """
        worker_queue, cf_stack = self.get_resources()
        worker_queue_arn = "arn:{}:sqs:{}:{}:{}".format(
            self.arn.partition, self.session.region_name, self.arn.account, worker_queue)
        cf_stack_arn = "arn:{}:cloudformation:{}:{}:stack/{}/*".format(
            self.arn.partition, self.session.region_name, self.arn.account, cf_stack)

        policy_name = "allow-export-service-configuration"
        policy_arn, policy = self.get_current_policy(policy_name)
        if not policy:
            msg = "No policy {} found.  Create policy then rerun".format(
                      policy_name)
            logger.exception(msg)
            raise EnvironmentError(msg)

        new_policy = copy.deepcopy(policy)
        for statement in new_policy['Statement']:
            cf_actions = ['cloudformation:UpdateStack',
                          'cloudformation:CancelUpdateStack']
            if (statement['Action'] == cf_actions and cf_stack_arn not in
                    statement['Resource']):
                statement['Resource'].append(cf_stack_arn)

            sqs_actions = ['sqs:SendMessage']
            if (statement['Action'] == sqs_actions and worker_queue_arn not in
                    statement['Resource']):
                statement['Resource'].append(worker_queue_arn)

        if new_policy != policy:
            self.update_policy(policy_arn, new_policy)
        else:
            logger.info("No change needed for IAM policy")

    def update_policy(self, policy_arn, policy):
        """Create/update a policy and set the new version as the default."""
        logger.info("updating iam policy {}".format(policy_arn))
        response = self.iam_client.create_policy_version(
                PolicyArn=policy_arn,
                PolicyDocument=json.dumps(policy),
                SetAsDefault=True
        )
        logger.info("update iam policy: {}".format(response))


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="set up export service "
        "environment: https://janrain.atlassian.net/wiki/display/ENG/Create+Export+Service+Environment+for+PS")
    parser.add_argument('-p', '--profile',
        help="Specify which boto profile in ~/.boto or ~/.aws to use")
    parser.add_argument('-r', '--region',
        help="Capture app region")
    parser.add_argument('-l', '--level', default="WARNING",
        help="Log level (default: WARNING)")
    parser.add_argument('customer_name', metavar='CUSTOMER_NAME',
        help=("name of customer, used for subenv and environment name. Use "
              "no special characters and use - instead of space.  E.g. "
              "mcdonalds-consumer"))
    parser.add_argument('environment', metavar='ENVIRONMENT',
        help="E.g.: dev, staging, test, prod")
    parser.add_argument('-k', '--keybucket', default="janrain-services-keys",
        help="s3 bucket for stackdriver keys. (default: janrain-services-keys)")
    parser.add_argument('-i', '--vpc-id',
        help="vpc where export service will be deployed. (default: region's dip vpc)")
    return parser.parse_args(argv)


def main(argv=None):
    """Run the deploy script."""
    args = _parse_args(argv)
    logging.basicConfig(stream=sys.stdout,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logger.setLevel(args.level)

    deploy_export_service(args)

if __name__ == "__main__":
    main()
