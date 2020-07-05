import hashlib
import os
from pathlib import Path

from aws_cdk.aws_iam import PolicyStatement, Effect, ServicePrincipal
from aws_cdk.aws_lambda import Function, Runtime, AssetCode
from aws_cdk.aws_logs import RetentionDays
from aws_cdk.core import Construct, Duration


class AmazonNodeDrainerLambda:
    _lambda_resource: Function = None

    @classmethod
    def get_function(cls, scope: Construct, cluster_name: str) -> Function:
        if not cls._lambda_resource:
            cls._lambda_resource = Function(
                scope,
                'AmazonEKSNodeDrainer',
                function_name='AmazonEKSNodeDrainer',
                code=AssetCode(
                    path=str(Path(__file__).parent.joinpath('assets', 'amazon-k8s-node-drainer.zip')),
                    source_hash=hash_directory(str(Path(__file__).parent.joinpath('assets')))
                ),
                handler='handler.lambda_handler',
                timeout=Duration.seconds(300),
                memory_size=128,
                runtime=Runtime.PYTHON_3_7,
                log_retention=RetentionDays.ONE_MONTH,
                environment={
                    'CLUSTER_NAME': cluster_name
                },
            )

            cls._lambda_resource.add_to_role_policy(
                PolicyStatement(
                    actions=[
                        'autoscaling:CompleteLifecycleAction',
                        'ec2:DescribeInstances',
                        'eks:DescribeCluster',
                        'sts:GetCallerIdentity'
                    ],
                    effect=Effect.ALLOW,
                    resources=["*"]
                )
            )

            cls._lambda_resource.add_permission(
                'AmazonEKSNodeDrainerEventInvokePermission',
                action='lambda:InvokeFunction',
                principal=ServicePrincipal('events.amazonaws.com'),
            )

        return cls._lambda_resource


def hash_directory(path):
    digest = hashlib.sha1()

    for root, dirs, files in os.walk(path):
        for names in files:
            file_path = os.path.join(root, names)

            # Hash the path and add to the digest to account for empty files/directories
            digest.update(hashlib.sha1(file_path[len(path):].encode()).digest())

            if os.path.isfile(file_path):
                with open(file_path, 'rb') as f_obj:
                    while True:
                        buf = f_obj.read(1024 * 1024)
                        if not buf:
                            break
                        digest.update(buf)

    return digest.hexdigest()
