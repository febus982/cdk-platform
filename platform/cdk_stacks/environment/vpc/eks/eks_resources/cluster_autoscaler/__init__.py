from typing import Dict

from aws_cdk.aws_eks import Cluster
from aws_cdk.aws_iam import Role, PolicyStatement, Effect

from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class ClusterAutoscaler:
    HELM_REPOSITORY = 'https://kubernetes-charts.storage.googleapis.com/'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster, kubernetes_version: str) -> None:
        """
        Deploys into the EKS cluster the kubernetes cluster autoscaler

        :param cluster:
        :param kubernetes_version:
        :return:
        """
        resource = ManifestGenerator.namespace_resource('cluster-autoscaler')
        namespace = cluster.add_resource(
            f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
            resource
        )

        sa = cluster.add_service_account(
            'ClusterAutoscalerServiceAccount',
            name='cluster-autoscaler',
            namespace=resource.get('metadata', {}).get('name'),
        )
        sa.node.add_dependency(namespace)
        cls.attach_iam_policies_to_role(sa.role)

        chart = cluster.add_chart(
            "helm-chart-cluster-autoscaler",
            release="cluster-autoscaler",
            chart="cluster-autoscaler",
            namespace=sa.service_account_namespace,
            repository=cls.HELM_REPOSITORY,
            version="7.3.3",
            values={
                "autoDiscovery": {
                    "clusterName": cluster.cluster_name,
                },
                "cloudProvider": "aws",
                "awsRegion": cluster.vpc.stack.region,
                "image": {
                    "repository": "eu.gcr.io/k8s-artifacts-prod/autoscaling/cluster-autoscaler",
                    "tag": cls._get_cluster_autoscaler_version(kubernetes_version),
                    "pullPolicy": "Always",
                },
                "extraArgs": {
                    "balance-similar-node-groups": "true"
                },
                "rbac": {
                    "create": True,
                    "serviceAccount": {
                        "name": sa.service_account_name,
                        "create": False,
                    },
                    "pspEnabled": True,
                },
            },
        )
        chart.node.add_dependency(sa)

    @classmethod
    def _get_cluster_autoscaler_version(cls, kubernetes_version: str) -> str:
        """
        Maps kubernetes version to cluster-autoscaler image tag. https://github.com/kubernetes/autoscaler/releases

        :param kubernetes_version:
        :return:
        """
        autoscaler_version_registry = {
            '1.18': 'v1.18.1',
            '1.17': 'v1.17.2',
            '1.16': 'v1.16.5',
            '1.15': 'v1.15.6',
            '1.14': 'v1.14.8',
        }
        return autoscaler_version_registry[kubernetes_version]

    @classmethod
    def attach_iam_policies_to_role(cls, role: Role):
        """
        Attach the inline policies necessary to manage autoscaling using the kubernetes cluster autoscaler

        :param role:
        :return:
        """
        # TODO: Extract this in a managed policy
        policies: Dict[str, PolicyStatement] = {
            'cluster_autoscaler': PolicyStatement(
                resources=["*"],
                effect=Effect.ALLOW,
                actions=[
                    "autoscaling:DescribeAutoScalingGroups",
                    "autoscaling:DescribeAutoScalingInstances",
                    "autoscaling:DescribeLaunchConfigurations",
                    "autoscaling:DescribeTags",
                    "autoscaling:SetDesiredCapacity",
                    "autoscaling:TerminateInstanceInAutoScalingGroup",
                    "ec2:DescribeLaunchTemplateVersions",
                ]
            ),
        }

        for policy in policies.values():
            role.add_to_policy(policy)
