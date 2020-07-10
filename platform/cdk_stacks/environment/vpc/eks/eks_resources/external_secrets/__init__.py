from aws_cdk.aws_eks import Cluster
from aws_cdk.aws_iam import Role, PolicyStatement, Effect, ManagedPolicy

from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class ExternalSecrets:
    HELM_REPOSITORY = 'https://godaddy.github.io/kubernetes-external-secrets/'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster) -> None:
        """
        Deploys into the EKS cluster the external secrets manager

        :param cluster:
        :return:
        """
        resource = ManifestGenerator.namespace_resource('external-secrets')
        namespace = cluster.add_resource(
            f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
            resource
        )

        sa = cluster.add_service_account(
            'ExternalSecretsServiceAccount',
            name='external-secrets',
            namespace=resource.get('metadata', {}).get('name'),
        )
        sa.node.add_dependency(namespace)
        cls.attach_iam_policies_to_role(sa.role)

        chart = cluster.add_chart(
            "helm-chart-external-secrets",
            release="kubernetes-external-secrets",
            chart="kubernetes-external-secrets",
            namespace=sa.service_account_namespace,
            repository=cls.HELM_REPOSITORY,
            version="4.0.0",
            values={
                "customResourceManagerDisabled": True,
                "env": {
                    "AWS_REGION": cluster.vpc.stack.region,
                },
                "rbac": {
                    "create": True,
                    "serviceAccount": {
                        "name": sa.service_account_name,
                        "create": False,
                    },
                },
            },
        )
        chart.node.add_dependency(sa)

    @classmethod
    def attach_iam_policies_to_role(cls, role: Role):
        """
        Attach the necessary policies to read secrets from SSM and SecretsManager

        :param role:
        :return:
        """
        # TODO: Extract this in a managed policy
        secretsmanager_readonly_policy = PolicyStatement(
            resources=["*"],
            effect=Effect.ALLOW,
            actions=[
                "secretsmanager:GetResourcePolicy",
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret",
                "secretsmanager:ListSecretVersionIds",
            ]
        )
        role.add_to_policy(secretsmanager_readonly_policy)
        role.add_managed_policy(ManagedPolicy.from_aws_managed_policy_name('AmazonSSMReadOnlyAccess'))
