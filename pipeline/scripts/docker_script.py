"""
A script for creating a docker image and uploading it to an AWS ECS repository.
This should be run on a machine running Amazon Linux.
"""

import os.path
import subprocess

import boto3
from botocore.exceptions import ClientError

from boto_helpers import get_aws_object_names, get_pipeline_folder


def run():
    """
    Run the code
    :return: The repository's URI, to be used in creating AWS Batch jobs elsewhere
    """
    
    # Install docker, git and AWS command line interface
    # -y means "don't ask for confirmation"
    # check_call will raise an error if the command fails (i.e. returns nonzero)
    subprocess.check_call(['sudo', 'yum', 'update', '-y'])
    subprocess.check_call(['sudo', 'yum', 'install', '-y', 'docker'])
    subprocess.check_call(['sudo', 'yum', 'install', '-y', 'git'])
    subprocess.check_call(['pip', 'install', 'awscli', '--upgrade', '--user'])
    print('Installations complete')
    
    # Get git repo to put in the docker
    # TODO: when the pipeline branch has been merged with master on Beiwe-Analysis, get rid of the --branch pipeline argument
    pipeline_folder = get_pipeline_folder()
    git_destination = os.path.join(pipeline_folder, 'Beiwe-Analysis')
    try:
        subprocess.check_call(['git', 'clone', 'https://github.com/onnela-lab/Beiwe-Analysis.git',
                               git_destination, '--branch', 'pipeline'])
        print('Git repository cloned')
    except subprocess.CalledProcessError:
        # TODO: when the pipeline branch has been merged with master on Beiwe-Analysis, change 'pipeline' to 'master'
        subprocess.check_call(['git', '-C', git_destination, 'checkout', 'pipeline'])
        subprocess.check_call(['git', '-C', git_destination, 'pull'])
        print('Git repository updated')
    
    # Create the docker image
    subprocess.check_call(['sudo', 'service', 'docker', 'start'])
    subprocess.check_call(['sudo', 'docker', 'build', '-t', 'beiwe-analysis', pipeline_folder])
    print('Docker image created')
    
    # Configure AWS ECR
    aws_object_names = get_aws_object_names()
    region_name = aws_object_names['region_name']
    subprocess.check_call(['aws', 'configure', 'set', 'default.region', region_name])
    
    # Create an AWS ECR repository to put the docker image into, and get the repository's URI
    # If such a repository already exists, get the repository's URI
    ecr_repo_name = aws_object_names['ecr_repo_name']
    client = boto3.client('ecr')
    try:
        resp = client.create_repository(
            repositoryName=ecr_repo_name,
        )
        repo_uri = resp['repository']['repositoryUri']
        print('ECR repository created')
    except ClientError:
        resp = client.describe_repositories(
            repositoryNames=(ecr_repo_name,),
        )
        repo_uri = resp['repositories'][0]['repositoryUri']
        print('Existing ECR repository found')
    
    # Tag the local docker image with the remote repository's URI. This is similar to
    # having a local git branch track a remote one.
    subprocess.check_call(['sudo', 'docker', 'tag', 'beiwe-analysis', repo_uri])
    
    # Push the docker file to our new repository
    ecr_login = subprocess.check_output(['aws', 'ecr', 'get-login', '--no-include-email'])
    ecr_login_as_list = ['sudo'] + ecr_login.strip('\n').split(' ')
    subprocess.check_call(ecr_login_as_list)
    subprocess.check_call(['sudo', 'docker', 'push', repo_uri])
    print('Docker pushed')
    
    return repo_uri
