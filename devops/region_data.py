from collections import namedtuple

region_keys = ['name', 'aws_name', 'partition', 'puppet', 'ansible', 'logs',
               'jump', 'zookeeper', 'iso_name', 'dip_vpc', 'services_vpc']
Region = namedtuple('Region', region_keys)
regions = {}
def add_region(**kwargs):
    reg = Region(**kwargs)
    regions[reg.name] = reg

add_region(name="va",
           aws_name="us-east-1",
           partition="aws",
           puppet="puppet-us.janrain.com",
           ansible="ansible-ec2-orchestration.utility.prod.va.janrain.com",
           logs="logs-us.janrain.com",
           jump="jump-us.janrain.com",
           zookeeper="1.zoo.janraincapture.com",
           iso_name="us-va",
           dip_vpc="vpc-31040c55",
           services_vpc="vpc-2e252b57")
add_region(name="ie",
           aws_name="eu-west-1",
           partition="aws",
           puppet="puppet-eu.janrain.com",
           ansible="ansible-ec2-orchestration.utility.prod.ie.janrain.com",
           logs="logs-eu.janrain.com",
           jump="jump-eu.janrain.com",
           zookeeper="1.eu-zoo.janraincapture.com",
           iso_name="ie-be",
           dip_vpc="vpc-12065777",
           services_vpc=None)
add_region(name="sy",
           aws_name="ap-southeast-2",
           partition="aws",
           puppet="puppet-au.janrain.com",
           ansible="ansible-ec2-orchestration.utility.prod.sy.janrain.com",
           logs="logs-au.janrain.com",
           jump="jump-au.janrain.com",
           zookeeper="1.au-zoo.janraincapture.com",
           iso_name="au-nsw",
           dip_vpc="vpc-78bdb41d",
           services_vpc=None)
add_region(name="or",
           aws_name="us-west-2",
           partition="aws",
           puppet="puppet-us-west2.janrain.com",
           ansible="ansible-ec2-orchestration.utility.prod.or.janrain.com",
           logs="logs-us-west2.janrain.com",
           jump="jump-us-west2.janrain.com",
           zookeeper="zoo1-prod.or.janrain.com",
           iso_name="us-or",
           dip_vpc=None,
           services_vpc=None)
add_region(name="sp",
           aws_name="sa-east-1",
           partition="aws",
           puppet="puppet.unknown",
           ansible="ansible-ec2-admin.multi.prod.sp.janrain.com",
           logs="logs-ec2-storage.multi.prod.sp.janrain.com",
           jump="jump-sp.janrain.com",
           zookeeper="zookeeper-multi-prod-sp.janrain.com",
           iso_name="br-sp",
           dip_vpc=None,
           services_vpc=None)
add_region(name="cn",
           aws_name="cn-north-1",
           partition="aws-cn",
           jump="jump-cn.janrain.com",
           puppet="puppet-ec2-admin.multi.prod.cn.janrain.com",
           ansible="ansible-ec2-admin.multi.prod.cn.janrain.com",
           logs="logs-ec2-storage-0.multi.prod.cn.janrain.com",
           zookeeper="zookeeper-multi-prod-cn.janrain.com",
           iso_name="cn-11",
           dip_vpc="vpc-51994d35",
           services_vpc=None)

by_name = regions
by_aws_name = {reg.aws_name: reg for reg in regions.itervalues()}
by_iso_name = {reg.iso_name: reg for reg in regions.itervalues()}

Partition = namedtuple('Partition', ['name', 'default_region'])
partitions = {}
def add_partition(**kwargs):
    part = Partition(**kwargs)
    partitions[part.name] = part

add_partition(name="aws",
              default_region=by_aws_name['us-east-1'])
add_partition(name="aws-cn",
              default_region=by_aws_name['cn-north-1'])
