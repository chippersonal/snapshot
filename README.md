## Readme for the snapshot repository and related code

## about

This is a demo project and uses boto3 to manage ec2 instance snapshots

## Configuration

snapshot uses config file created by aws cli e.g.

`aws configure --profile snapshot`

## Running

`pipenv run python user_snapshot/snapshot.py 'command' --project=projectname'

'command -  instances, volumes, snapshots'
'sub command depending on command - list,stop,start,terminate'
'project is optional omitting applies command to all instances'
