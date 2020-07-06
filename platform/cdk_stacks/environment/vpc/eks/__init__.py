from typing import List

from aws_cdk.aws_ec2 import Vpc, SubnetSelection, SubnetType, InstanceType
from aws_cdk.aws_eks import Cluster
from aws_cdk.aws_iam import Role, AccountRootPrincipal

from apps.abstract.base_app import BaseApp
from cdk_stacks.abstract.base_stack import BaseStack
from cdk_stacks.environment.vpc.eks.eks_resources.cluster_autoscaler import ClusterAutoscaler
from cdk_stacks.environment.vpc.eks.eks_resources.external_secrets import ExternalSecrets
from cdk_stacks.environment.vpc.eks.eks_resources.istio import Istio
from cdk_stacks.environment.vpc.eks.eks_resources.metrics_server import MetricsServer


class EKSStack(BaseStack):
    def __init__(self, scope: BaseApp, id: str, vpc: Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        kubernetes_version = scope.environment_config.get('eks', {}).get('kubernetesVersion')
        cluster_name = scope.prefixed_str(scope.environment_config.get('eks', {}).get('clusterName'))

        cluster_admin_role = Role(
            self,
            scope.prefixed_str('EKS-AdminRole'),
            role_name=scope.prefixed_str('EKS-AdminRole'),
            assumed_by=AccountRootPrincipal(),
        )

        eks_cluster = Cluster(
            self,
            cluster_name,
            cluster_name=cluster_name,
            vpc=vpc,
            version=kubernetes_version,
            default_capacity=0,  # We define later the capacity
            masters_role=cluster_admin_role,
            vpc_subnets=self._get_control_plane_subnets(scope),  # Control plane subnets
        )

        # for profile in scope.environment_config.get('eks', {}).get('fargateProfiles', []):
        #     eks_cluster.add_fargate_profile(
        #         profile.get('name'),
        #         selectors=[
        #             Selector(
        #                 namespace=profile.get('namespace'),
        #                 labels=profile.get('labels')
        #             )
        #         ]
        #     )

        for fleet in scope.environment_config.get('eks', {}).get('workerNodesFleets'):
            self.add_managed_fleet(eks_cluster, fleet)

        MetricsServer.add_to_cluster(eks_cluster)
        ClusterAutoscaler.add_to_cluster(eks_cluster, kubernetes_version)
        ExternalSecrets.add_to_cluster(eks_cluster)
        Istio.add_to_cluster(eks_cluster)

    def _get_control_plane_subnets(self, scope: BaseApp) -> List[SubnetSelection]:
        """
        This method selects the allowed Subnets only for the control plane, on which will load balancers be allowed.
        The kubectl nodes will be in the private Subnets. ALWAYS.

        :param scope:
        :return:
        """
        eks_subnets = [SubnetSelection(subnet_type=SubnetType.PRIVATE)]
        if scope.environment_config.get('eks', {}).get('usePublicSubnets'):
            eks_subnets += [SubnetSelection(subnet_type=SubnetType.PUBLIC)]
        return eks_subnets

    def add_managed_fleet(self, cluster: Cluster, fleet: dict):
        # To correctly sclae the cluster we need our node groups to not span across AZs
        # to avoid the automatic AZ re-balance, hence we create a node group per subnet

        for counter, subnet in enumerate(cluster.vpc.private_subnets):
            fleet_id = f'{fleet.get("name")}-{counter}'
            cluster.add_nodegroup(
                id=fleet_id,
                instance_type=InstanceType(fleet.get('instanceType')),
                min_size=fleet.get('autoscaling', {}).get('minInstances'),
                max_size=fleet.get('autoscaling', {}).get('maxInstances'),
                labels=fleet.get('nodeLabels'),
                nodegroup_name=f'{fleet.get("name")}-{subnet.availability_zone}',
                subnets=SubnetSelection(subnets=[subnet]),
            )

#
#     def attach_iam_policies_to_fleet_role(self, fleet: AutoScalingGroup, fleet_policies: Dict[str, ManagedPolicy]):
#         """
#         Attach the custom policies to the worker ec2 instances
#
#         :param fleet:
#         :param fleet_policies:
#         :return:
#         """
#         for policy in fleet_policies.values():
#             fleet.role.add_managed_policy(policy)
#

#
#     def attach_external_dns_policies(self, fleet: AutoScalingGroup) -> None:
#         """
#         Attach the inline policies necessary to manage route53 zone entries using kubernetes external dns
#
#         :param fleet:
#         :return:
#         """
#         policies: Dict[str, PolicyStatement] = {
#             'route_53': PolicyStatement(
#                 resources=["*"],
#                 effect=Effect.ALLOW,
#                 actions=[
#                     "route53:ListHostedZones",
#                     "route53:ListResourceRecordSets",
#                 ]
#             ),
#             'route_53_recordset_change': PolicyStatement(
#                 resources=["arn:aws:route53:::hostedzone/*"],
#                 effect=Effect.ALLOW,
#                 actions=[
#                     "route53:ChangeResourceRecordSets",
#                 ]
#             )
#         }
#
#         for policy in policies.values():
#             fleet.add_to_role_policy(policy)
