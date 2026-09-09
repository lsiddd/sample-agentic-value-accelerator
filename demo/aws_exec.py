"""Run a local command with AWS CLI login credentials kept only in memory.

Usage: python demo/aws_exec.py terraform -chdir=demo/pipeline plan
"""
import json
import os
import subprocess
import sys

identity = json.loads(subprocess.check_output([
    'aws', 'sts', 'get-caller-identity', '--profile', 'default', '--output', 'json'
]))
if identity['Account'] != '821672147714':
    raise SystemExit('Unexpected AWS account; stopped')
credentials = json.loads(subprocess.check_output([
    'aws', 'configure', 'export-credentials', '--profile', 'default', '--format', 'process'
]))
env = {**os.environ, 'AWS_REGION': 'us-east-1', 'TF_VAR_expected_account_id': identity['Account']}
for source, target in [('AccessKeyId', 'AWS_ACCESS_KEY_ID'), ('SecretAccessKey', 'AWS_SECRET_ACCESS_KEY'), ('SessionToken', 'AWS_SESSION_TOKEN')]:
    env[target] = credentials.get(source, '')
raise SystemExit(subprocess.call(sys.argv[1:], env=env))
