
import boto3
import botocore
import click
import datetime
import dateutil
import configparser
import csv

#import properties from local properties filter

config = configparser.RawConfigParser()
config.read('/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/site-packages/user_snapshot/config.properties')
#config.read('config.properties')
config_dict = dict(config.items('TEST_PROPERTIES'))
#region_dict = dict(config.items('ACTIVE_REGIONS'))

def get_config_dict():
    if not hasattr(get_config_dict, 'config_dict'):
        get_config_dict.config_dict = dict(config.items('TEST_PROPERTIES'))
    return get_config_dict.config_dict

config_properties = get_config_dict()
#print(config_properties)



#def get_active_regions():
#    if not hasattr(get_config_dict2, 'config_dict2'):
#       get_config_dict2.config_dict2 = dict(config.items('ACTIVE_REGIONS'))
#       return get_config_dict2.config_dict2

#active_regions = get_active_regions()

#print(active_regions)

user_name = config_properties['name']
user_email = config_properties['email']
default_region = config_properties['default_region']
default_profile = config_properties['default_profile']
default_create_days = int(config_properties['default_create_days'])
default_delete_days = int(config_properties['default_delete_days'])

#start program


def filter_instances(project,server_id,profile_name,region_name):
        session = boto3.Session(profile_name=profile_name,region_name=region_name)
        ec2 = session.resource('ec2')
        instances = []

        if project:
            filters = [{'Name':'tag:Project', 'Values':[project]}]
            instances = ec2.instances.filter(Filters=filters)
        elif server_id:
            instances = ec2.instances.filter(InstanceIds=[server_id])
        else:
            instances = ec2.instances.all()

        return instances


def has_pending_snapshot(volume):
    snapshots = list(volume.snapshots.all())
    return snapshots and snapshots[0].state == 'pending'

@click.group()
def cli():
    """snapshot.py manages snapshots"""
@cli.group('config')
def config():
    """Commands for confi"""
@config.command('list')
def list_config():
    print ("The following are the default options for certain parameters, all can be overridden")
    print("User profile is ",default_profile,".")
    print("Region is ",default_region,".")
    print("Creation days (age of an existing snapshot which will be considerdd not current and therefore new snapshot required) is ",default_create_days,".")
    print("Creation days (age of an existing snapshot which will be considerdd not current and therefore snapshot can be deleted) is ",default_delete_days,".")

@cli.group('snap')
def snapshots():
    """Commands for snapshots"""
@snapshots.command('list')
@click.option('--project', default=None,
    help="Only return snapshots attached to specified project")
@click.option('--all', 'list_all', default=False, is_flag=True,
    help="List all snapshots for each volume, not just the most recent")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def list_snapshots(project, list_all, server_id,profile_name,region_name):
    "List EC2 snapshots by (optional) project"
    session = boto3.Session(profile_name=profile_name,region_name=region_name)
    ec2 = session.resource('ec2')
    instances = filter_instances(project,server_id,profile_name,region_name)

    for i in instances:
        for v in i.volumes.all():
            for s in v.snapshots.all():
                print(", ".join((
                    s.id,
                    v.id,
                    i.id,
                    s.state,
                    s.progress,
                    s.start_time.strftime("%c"),
                    )))


                if s.state == 'completed' and not list_all: break
    return

@snapshots.command('expanded_list')
@click.option('--project', default=None,
    help="Only return snapshots attached to specified project")
@click.option('--all', 'list_all', default=False, is_flag=True,
    help="List all snapshots for each volume, not just the most recent")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def list_snapshots(project, list_all, server_id,profile_name,region_name):
    "List EC2 snapshots by (optional) project"
    session = boto3.Session(profile_name=profile_name,region_name=region_name)
    ec2 = session.resource('ec2')

    instances = filter_instances(project,server_id,profile_name,region_name)

    for i in instances:
        tags = { t['Key']: t['Value'] for t in i.tags or [] }
        for v in i.volumes.all():
            for s in v.snapshots.all():
                #if expand_description is True:
                print(", ".join((
                    s.id,
                    v.id,
                    i.id,
                    s.state,
                    s.progress,
                    s.start_time.strftime("%c"),
                    tags.get('Project', '<No Project>'),
                    s.description
                    )))


                if s.state == 'completed' and not list_all: break
    return

@snapshots.command('delete')
@click.option('--project', default=None,
    help="Only return instances attached to specified project")
@click.option('--force',  default=False,
   help="Only return instances where no project or server_id specified if --force True option is applied")
@click.option('--days',   default=default_delete_days,
    help="Define number of days required for snapshot to not be considered current, if all required, enter -1, default is 7")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID - to be applied as server_id")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")
def delete_snapshots(project,force,server_id,days,profile_name,region_name):
    "Delete snapshots for EC2 instances"
    instances = filter_instances(project,server_id,profile_name,region_name)
    snap_current=False

    if project == None and force == False and server_id == None:
        print("Requires either project name, server_id or force option!")
    else:
        for i in instances:
            #print("Snapshot is not current if it is older than",days,"days")
            i_state = i.state['Name']
            snap_current=False
            for v in i.volumes.all():
                delta = datetime.datetime.now() - datetime.timedelta(days=days)
                for s in v.snapshots.all():
                    snap_start = s.start_time
                    snap_start2 = snap_start.strftime ("%Y-%m-%d %H:%M:%S")
                    delta2 = delta.strftime ("%Y-%m-%d %H:%M:%S")
                    if snap_start2 < delta2 :
                        s.delete()
                        print(" Deleting snapshot",s.id," for volume",v.id," it is not current (older than ",days,"days)")
                        continue
                    else:
                        print(" Not deleting snapshot",s.id," for volume",v.id," it is current (younger than ",days,"days)")

@cli.group('vol')
def volumes():
    """Commands for volumes"""

@volumes.command('list')
@click.option('--project', default=None,
    help="Only return volumes attached to specified project")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")
def list_volumes(project,server_id,profile_name,region_name):
    "List EC2 volumes by (optional) project"
    instances = filter_instances(project, server_id,profile_name,region_name)
    for i in instances:
        for v in i.volumes.all():
            print(", ".join((
                v.id,
                i.id,
                v.state,
                str(v.size) + "GiB",
                v.encrypted and "Encrypted" or "Not Encrypted"
            )))
    return

@cli.group('ins')
def instances():
    """Commands for instances"""
@instances.command('snapshot',
    help="Create snapshots of all instances")
@click.option('--project', default=None,
    help="Only return instances attached to specified project")
@click.option('--force',  default=False,
   help="Only return instances where no project or server_id specified if --force True option is applied")
@click.option('--days',   default=default_create_days,
    help="Define number of days required for snapshot to not be considered current, if all required, enter -1, default is 7")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID - to be applied as server_id")
@click.option('--description', 'snap_description', default="Created by chip snapshot routine - get rid when session done!",
			  help="The instance ID - to be applied as server_id")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")
def create_snapshots(project,force,server_id,days,snap_description,profile_name,region_name):
    "Create snapshots for EC2 instances"
    instances = filter_instances(project,server_id,profile_name,region_name)
    snap_current=False


    if project == None and force == False and server_id == None:
        print("Requires either project name, server_id or force option!")
    else:
        for i in instances:
            i_state = i.state['Name']
            snap_current=False
            for v in i.volumes.all():
                if has_pending_snapshot(v):
                    print(" Skipping {0}, snapshot already in progress".format(v.id))
                    snap_current=True
                if snap_current is False:
                    delta = datetime.datetime.now() - datetime.timedelta(days=days)
                    for s in v.snapshots.all():
                        snap_start = s.start_time
                        snap_start2 = snap_start.strftime ("%Y-%m-%d %H:%M:%S")
                        delta2 = delta.strftime ("%Y-%m-%d %H:%M:%S")
                        if snap_start2 > delta2 :
                            snap_current=True
                            print(" Skipping snapshot for ",v.id,", current (less than",days,"days old) snapshot already present".format(v.id))
                            break


            if snap_current is False:
                try:
                    i.stop()
                except botocore.exceptions.ClientError as e:
                    print("Could not create snapshot for {0}. ".format(i.id) + str(e))
                    continue
                print("Stopping {0}...".format(i.id))
                i.wait_until_stopped()
                if has_pending_snapshot(v):
                    print(" Skipping {0}, snapshot already in progress".format(v.id))
                    continue
                print("As there is no snapshot younger than",days,"days, creating snapshot of {0}".format(v.id))
                v.create_snapshot(Description=snap_description)
                #v.create_snapshot(Description="Created by chip snapshot routine - get rid when session done!")
                if i_state == 'running':
                    print("Starting {0}...".format(i.id))
                    try:
                        i.start()
                    except botocore.exceptions.ClientError as e:
                        print("Could not create snapshot for {0}. ".format(i.id) + str(e))
                        continue
                    i.wait_until_running()
                else:
                    print("Instance not running before snapshot taken, will not restart now")

        print("All done!")

    return

@instances.command('list')
@click.option('--project', default=None,
    help="Only return instances attached to specified project")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")

def list_instances(project, server_id,profile_name,region_name):
    "List EC2 instances by (optional) project"
    session = boto3.Session(profile_name=profile_name,region_name=region_name)
    ec2 = session.resource('ec2')
    instances = filter_instances(project,server_id,profile_name,region_name)

    for i in instances:
        tags = { t['Key']: t['Value'] for t in i.tags or [] }
        print(','.join((
        i.id,
        i.instance_type,
        i.placement['AvailabilityZone'],
        i.state['Name'],
        i.public_dns_name,
        tags.get('Project', '<No Project>'))))
    return

@instances.command('biglist',help="List Instances, Volumes and snapshots for every active region")
@click.option('--project', default=None,
    help="Only return instances attached to specified project")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")

def list_instances(project, server_id,profile_name,region_name):
    "List Instances, Volumes and snapshots for every active region"
    f = open('/Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/site-packages/user_snapshot/active_regions.csv')
    csv_f = csv.reader(f)

    for row in csv_f:
        region_name = row[0]
        print("Region:",region_name)
        session = boto3.Session(profile_name=profile_name,region_name=region_name)
        ec2 = session.resource('ec2')
        instances = filter_instances(project,server_id,profile_name,region_name)
        for i in instances:
            print("Instance")
            tags = { t['Key']: t['Value'] for t in i.tags or [] }
            print(','.join((
            i.id,
            i.instance_type,
            i.placement['AvailabilityZone'],
            i.state['Name'],
            i.public_dns_name,
            tags.get('Project', '<No Project>'))))            
            for v in i.volumes.all():
                print("Volumes")
                print(", ".join((
                    v.id,
                    #i.id,
                    v.state,
                    str(v.size) + "GiB",
                    v.encrypted and "Encrypted" or "Not Encrypted"
                )))
                for s in v.snapshots.all():
                    print("Snapshots")
                    print(", ".join((
                        s.id,
                        #v.id,
                        #i.id,
                        s.state,
                        s.progress,
                        s.start_time.strftime("%c"),
                        #tags.get('Project', '<No Project>'),
                        s.description
                        )))
        continue

@instances.command('stop')
@click.option('--project', default=None,
    help="Only return instances attached to specified project")
@click.option('--force',  default=False,
   help="Only return instances where no project specified if force option is applied")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def stop_instances(project,force,server_id,profile_name,region_name):
    "Stop EC2 instances by (optional) project or server_id"
    session = boto3.Session(profile_name=profile_name,region_name=region_name)
    ec2 = session.resource('ec2')
    instances = filter_instances(project,server_id,profile_name,region_name)
    if project == None and force == False and server_id == None:
        print("Requires either project name, server_id or force option!")
    else:
        for i in instances:
            print("Stopping {0}.......".format(i.id))
            try:
                i.stop()
            except botocore.exceptions.ClientError as e:
                print("Could not stop {0}. ".format(i.id) + str(e))
                continue
    return

@instances.command('start')
@click.option('--project', default=None,
    help="Only return instances attached to specified project")
@click.option('--force',  default=False,
   help="Only return instances where no project specified if force option is applied")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def start_instances(project,force,server_id,profile_name,region_name):
    "Start EC2 instances by (optional) project"
    instances = filter_instances(project,server_id,profile_name,region_name)
    if project == None and force == False and server_id == None:
        print("Requires either project name, server_id or force option!")
    else:
        for i in instances:
            print("Starting {0}.......".format(i.id))
            try:
                i.start()
            except botocore.exceptions.ClientError as e:
                print("Could not start {0}. ".format(i.id) + str(e))
                continue
    return

@instances.command('terminate')
@click.option('--project', default=None,
    help="Only return instances attached to specified project")
@click.option('--force',  default=False,
   help="Only return instances where no project specified if force option is applied")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def terminate_instances(project,force,server_id,profile_name,region_name):
    "Terminate EC2 instances by (optional) project"
    instances = filter_instances(project,server_id,profile_name,region_name)
    if project == None and force == False and server_id == None:
        print("Requires either project name, server_id or force option!")
    else:
        for i in instances:
            print("Terminating {0}.......".format(i.id))
            try:
                i.terminate()
            except botocore.exceptions.ClientError as e:
                print("Could not terminate {0}. ".format(i.id) + str(e))
                continue
    return
@instances.command('reboot')
@click.option('--project', default=None,
    help="Only return instances attached to specified project")
@click.option('--force',  default=False,
   help="Only return instances where no project specified if force option is applied")
@click.option('--profile', 'profile_name', default=default_profile,
    help="Specify profile other than default to be used in request")
@click.option('--region', 'region_name', default=default_region,
			  help="The AWS region")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def reboot_instances(project,force,server_id,profile_name,region_name):
    "Reboot EC2 instances by (optional) project"
    instances = filter_instances(project,server_id,profile_name,region_name)
    if project == None and force == False and server_id == None:
        print("Requires either project name, server_id or force option!")
    else:
        for i in instances:
            print("Rebooting {0}.......".format(i.id))
            try:
                i.reboot()
            except botocore.exceptions.ClientError as e:
                print("Could not reboot {0}. ".format(i.id) + str(e))
                continue
    return


if __name__ == '__main__':
    cli()
