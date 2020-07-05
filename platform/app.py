#!/usr/bin/env python3
import os

from aws_cdk.core import Environment

from apps.platform import Platform

platform_account_env = Environment(
    account=os.getenv("AWS_ACCOUNT_ID", "360064003702"),
    region=os.getenv("AWS_DEFAULT_REGION", "eu-west-1"),
)

users_account_env = Environment(
    account=os.getenv("AWS_BASTION_ACCOUNT_ID", platform_account_env.account),
    region=os.getenv("AWS_DEFAULT_REGION", platform_account_env.region),
)

app = Platform(platform_account_env=platform_account_env, users_account_env=users_account_env)
app.synth()
