
import boto3
import botocore
import click
import datetime
import dateutil



session = boto3.Session(profile_name='snapshot')
ec2 = session.resource('ec2')
def filter_instances(project,server_id):
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

def has_current_snapshot(current_volume,project,server_id):
    instances = filter_instances(project,server_id)
    global snap_current
    snap_current = []
    for i in instances:
            for v in i.volumes.all():
                if v.id != current_volume:
                    continue
            else:
                print(v.id)
                delta = datetime.datetime.now() - datetime.timedelta(days=30)
                for s in v.snapshots.all():
                    snap_start = s.start_time
                    snap_start2 = snap_start.strftime ("%Y-%m-%d %H:%M:%S")
                    delta2 = delta.strftime ("%Y-%m-%d %H:%M:%S")
                    if snap_start2 > delta2:
                        snap_current = True
                        print(delta2,snap_start2)
                    else:
                        snap_current = False
                        print(snap_current)
    return snap_current == True


@click.group()
def cli():
    """snapshot.py manages snapshots"""

@cli.group('snapshots')
def snapshots():
    """Commands for snapshots"""
@snapshots.command('list')
@click.option('--project', default=None,
    help="Only return snapshots attached to specified project")
@click.option('--all', 'list_all', default=False, is_flag=True,
    help="List all snapshots for each volume, not just the most recent")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def list_snapshots(project, list_all, server_id):
    "List EC2 snapshots by (optional) project"

    instances = filter_instances(project,server_id)

    for i in instances:
        for v in i.volumes.all():
            for s in v.snapshots.all():
                print(", ".join((
                    s.id,
                    v.id,
                    i.id,
                    s.state,
                    s.progress,
                    s.start_time.strftime("%c")
                    )))

                if s.state == 'completed' and not list_all: break
    return

@cli.group('volumes')
def volumes():
    """Commands for volumes"""

@volumes.command('list')
@click.option('--project', default=None,
    help="Only return volumes attached to specified project")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def list_volumes(project,server_id):
    "List EC2 volumes by (optional) project"
    instances = filter_instances(project, server_id)
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

@cli.group('instances')
def instances():
    """Commands for instances"""
@instances.command('snapshot',
    help="Create snapshots of all instances")
@click.option('--project', default=None,
    help="Only return instances attached to specified project")
@click.option('--force',  default=False,
   help="Only return instances where no project specified if force option is applied")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def create_snapshots(project,force,server_id):
    "Create snapshots for EC2 instances"
    instances = filter_instances(project,server_id)


    if project == None and force == False and server_id == None:
        print("Requires either project name, server_id or force option!")
    else:
        for i in instances:
            i_state = i.state['Name']
            snap_current=False
            for v in i.volumes.all():
                delta = datetime.datetime.now() - datetime.timedelta(days=7)
                for s in v.snapshots.all():
                    snap_start = s.start_time
                    snap_start2 = snap_start.strftime ("%Y-%m-%d %H:%M:%S")
                    delta2 = delta.strftime ("%Y-%m-%d %H:%M:%S")
                    if snap_start2 > delta2:
                        snap_current=True
                        print(" Skipping {0}, current snapshot already present".format(v.id))

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
                    print("Creating snapshot of {0}".format(v.id))
                    v.create_snapshot(Description="Created by chip snapshot routine - get rid when session done!")
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
@click.option('--profile', default='snapshot',
    help="Specify profile other than default to be used in request")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def list_instances(project,profile, server_id):
    "List EC2 instances by (optional) project"
    session = boto3.Session(profile_name=profile)
    instances = filter_instances(project,server_id)

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

@instances.command('stop')
@click.option('--project', default=None,
    help="Only stop instances attached to specified project")
@click.option('--force',  default=False,
   help="Only return instances where no project specified if force option is applied")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def stop_instances(project,force,server_id):
    "Stop EC2 instances by (optional) project"
    instances = filter_instances(project,server_id)
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
    help="Only start instances attached to specified project")
@click.option('--force',  default=False,
   help="Only return instances where no project specified if force option is applied")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def start_instances(project,force,server_id):
    "Start EC2 instances by (optional) project"
    instances = filter_instances(project,server_id)
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
    help="Only terminate instances attached to specified project")
@click.option('--force',  default=False,
       help="Only return instances where no project specified if force option is applied")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def terminate_instances(project,force,server_id):
    "Terminate EC2 instances by (optional) project"
    instances = filter_instances(project,server_id)
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
    help="Only reboot instances attached to specified project")
@click.option('--force',  default=False,
       help="Only return instances where no project specified if force option is applied")
@click.option('--id', 'server_id', default=None,
			  help="The instance ID")
def reboot_instances(project,force,server_id):
    "Reboot EC2 instances by (optional) project"
    instances = filter_instances(project,server_id)
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
