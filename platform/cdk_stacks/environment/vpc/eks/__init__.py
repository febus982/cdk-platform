from typing import List, Dict

from aws_cdk.aws_autoscaling import CfnAutoScalingGroup, AutoScalingGroup
from aws_cdk.aws_ec2 import Vpc, SubnetSelection, SubnetType, InstanceType
from aws_cdk.aws_eks import Cluster, BootstrapOptions
from aws_cdk.aws_iam import Role, AccountRootPrincipal, ManagedPolicy
from aws_cdk.core import Tag

from apps.abstract.base_app import BaseApp
from cdk_stacks.abstract.base_stack import BaseStack
from cdk_stacks.environment.vpc.eks.eks_resources.amazon_node_drainer.function.lambda_singleton_resource import \
    AmazonNodeDrainerLambda
from cdk_stacks.environment.vpc.eks.eks_resources.metrics_server import MetricsServer


class EKSStack(BaseStack):
    HELM_STABLE_REPOSITORY = 'https://kubernetes-charts.storage.googleapis.com/'
    HELM_EKS_REPOSITORY = 'https://aws.github.io/eks-charts/'

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
            if fleet.get('type') == 'managed':
                self.add_managed_fleet(eks_cluster, fleet)
            if fleet.get('type') == 'ASG':
                raise NotImplementedError("ASG Nodes are not yet implemented")
                # self.add_asg_fleet(scope, eks_cluster, cluster_name, fleet, {})

        MetricsServer.add_to_cluster(eks_cluster)

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
        cluster.add_nodegroup(
            fleet.get('name'),
            instance_type=InstanceType(fleet.get('instanceType')),
            min_size=fleet.get('autoscaling', {}).get('minInstances'),
            max_size=fleet.get('autoscaling', {}).get('maxInstances'),
            labels=fleet.get('nodeLabels')
        )

    def add_asg_fleet(self, scope: BaseApp, cluster: Cluster, cluster_name: str,
                       fleet, fleet_policies: Dict[str, ManagedPolicy]):
        node_labels = fleet.get('nodeLabels', {})
        node_labels["fleetName"] = fleet.get('name')
        node_labels["cluster-autoscaler-enabled"] = "true"
        node_labels["cluster-autoscaler-{}".format(cluster_name)] = "owned"
        node_labels_as_str = ','.join(map('='.join, node_labels.items()))

        # Source of tweaks: https://kubedex.com/90-days-of-aws-eks-in-production/
        kubelet_extra_args = ' '.join([
            # Add node labels
            f'--node-labels {node_labels_as_str}' if len(node_labels_as_str) else '',

            # Capture resource reservation for kubernetes system daemons like the kubelet, container runtime,
            # node problem detector, etc.
            '--kube-reserved cpu=250m,memory=1Gi,ephemeral-storage=1Gi',

            # Capture resources for vital system functions, such as sshd, udev.
            '--system-reserved cpu=250m,memory=0.2Gi,ephemeral-storage=1Gi',

            # Start evicting pods from this node once these thresholds are crossed.
            '--eviction-hard memory.available<0.2Gi,nodefs.available<10%',
        ])

        # For correctly autoscaling the cluster we need our autoscaling groups to not span across AZs
        # to avoid the AZ Rebalance, hence we create an ASG per subnet
        for subnet in cluster.vpc.private_subnets:
            fleet_id = f'{fleet.get("name")}-{subnet.availability_zone}'
            self.eks_fleets[fleet_id]: AutoScalingGroup = cluster.add_capacity(
                id=scope.prefixed_str(fleet_id),
                instance_type=InstanceType(fleet.get('instanceType')),
                min_capacity=fleet.get('autoscaling', {}).get('minInstances'),
                max_capacity=fleet.get('autoscaling', {}).get('maxInstances'),
                bootstrap_options=BootstrapOptions(
                    kubelet_extra_args=kubelet_extra_args,
                ),
            )

            self._add_userdata_production_tweaks(self.eks_fleets[fleet_id])

            for key, value in node_labels.items():
                Tag.add(self.eks_fleets[fleet_id], key, value, apply_to_launched_instances=True)

            asg_cfn_construct: CfnAutoScalingGroup = self.eks_fleets[fleet_id].node.find_child("ASG")
            asg_cfn_construct.vpc_zone_identifier = [subnet.subnet_id]

            # self.attach_iam_policies_to_fleet_role(self.eks_fleets[fleet_id], fleet_policies)
            # self.attach_cluster_autoscaler_policies_to_fleet_role(self.eks_fleets[fleet_id])
            # if scope.environment_config.get('eks', {}).get('externalDnsPolicy'):
            #     self.attach_external_dns_policies(self.eks_fleets[fleet_id])

        # self._enable_cross_fleet_communication(self.eks_fleets)
#
#     def _enable_cross_fleet_communication(self, fleets: Dict[str, AutoScalingGroup]):
#         security_groups: List[SecurityGroup] = []
#
#         # list all SGs
#         for fleet in fleets.values():
#             sg: SecurityGroup = fleet.node.find_child("InstanceSecurityGroup")
#             security_groups.append(sg)
#
#         # cross-sg rule creation
#         for sg_target in security_groups:
#             for sg_source in security_groups:
#                 rule_found = False
#                 for rule, value in sg_target.to_ingress_rule_config().items():
#                     if rule == "sourceSecurityGroupId" and value == sg_source.security_group_id:
#                         rule_found = True
#
#                 if not rule_found:
#                     sg_target.connections.allow_from(sg_source, Port.all_traffic())
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
#     def attach_cluster_autoscaler_policies_to_fleet_role(self, fleet: AutoScalingGroup):
#         """
#         Attach the inline policies necessary to manage autoscaling using the kubernetes cluster autoscaler
#
#         :param fleet:
#         :return:
#         """
#         policies: Dict[str, PolicyStatement] = {
#             'cluster_autoscaler': PolicyStatement(
#                 resources=["*"],
#                 effect=Effect.ALLOW,
#                 actions=[
#                     "autoscaling:DescribeAutoScalingGroups",
#                     "autoscaling:DescribeAutoScalingInstances",
#                     "autoscaling:DescribeLaunchConfigurations",
#                     "autoscaling:DescribeTags",
#                     "autoscaling:SetDesiredCapacity",
#                     "autoscaling:TerminateInstanceInAutoScalingGroup",
#                     "ec2:DescribeLaunchTemplateVersions",
#                 ]
#             ),
#         }
#
#         for policy in policies.values():
#             fleet.add_to_role_policy(policy)
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
#
#     def deploy_autoscaler_resources(self, cluster: Cluster, cluster_name: str, kubernetes_version: str) -> None:
#         """
#         Deploys into the EKS cluster the kubernetes cluster autoscaler
#
#         :param cluster:
#         :param cluster_name:
#         :param kubernetes_version:
#         :return:
#         """
#         with open(
#                 os.path.join(os.path.dirname(__file__), 'eks_resources', 'cluster_autoscaler', 'namespace.yaml')) as f:
#             resource = yaml.safe_load(f)
#         namespace = cluster.add_resource(
#             '{}-{}'.format(resource.get('kind'), resource.get('metadata', {}).get('name')),
#             resource
#         )
#
#         cluster.add_chart(
#             "helm-chart-cluster-autoscaler",
#             release="cluster-autoscaler",
#             chart="cluster-autoscaler",
#             namespace="cluster-autoscaler",
#             repository=self.HELM_STABLE_REPOSITORY,
#             version="6.2.0",
#             values={
#                 "autoDiscovery": {
#                     "clusterName": cluster_name,
#                     "tags": [
#                         "cluster-autoscaler-enabled",
#                         f"cluster-autoscaler-{cluster_name}",
#                     ]
#                 },
#                 "cloudProvider": "aws",
#                 "awsRegion": self.region,
#                 "image": {
#                     "tag": self._get_cluster_autoscaler_version(kubernetes_version),
#                 },
#                 "rbac": {
#                     "create": "true",
#                 },
#             },
#         ).node.add_dependency(namespace)
#
#     def deploy_metrics_server_resources(self, cluster: Cluster) -> None:
#         """
#         Deploys into the EKS cluster the kubernetes metrics server
#
#         :param cluster:
#         :return:
#         """
#         with open(
#                 os.path.join(os.path.dirname(__file__), 'eks_resources', 'metrics_server', 'namespace.yaml')) as f:
#             resource = yaml.safe_load(f)
#         namespace = cluster.add_resource(
#             '{}-{}'.format(resource.get('kind'), resource.get('metadata', {}).get('name')),
#             resource
#         )
#
#         cluster.add_chart(
#             'helm-chart-metrics-server',
#             release="metrics-server",
#             chart="metrics-server",
#             namespace="metrics-server",
#             repository=self.HELM_STABLE_REPOSITORY,
#             version="2.9.0",
#             values={
#                 "image": {
#                     "tag": "v0.3.6",
#                 },
#                 "args": [
#                     "--kubelet-preferred-address-types=InternalIP"
#                 ]
#             },
#         ).node.add_dependency(namespace)
#
#     def deploy_amazon_node_drainer_resources(self, cluster_name: str, eks_cluster: Cluster,
#                                              fleets: Dict[str, AutoScalingGroup]) -> None:
#         """
#         Deploys the amazon node drainer resources in the stack and in the EKS cluster
#
#         :param eks_cluster:
#         :param fleets:
#         :return:
#         """
#         for filename in [
#             'cluster_role.yaml',
#             'cluster_rolebinding.yaml'
#         ]:
#             with open(
#                     os.path.join(os.path.dirname(__file__), 'eks_resources', 'amazon_node_drainer',
#                                  filename)) as f:
#                 resource = yaml.safe_load(f)
#             eks_cluster.add_resource(
#                 '{}-{}'.format(resource.get('kind'), resource.get('metadata', {}).get('name')),
#                 resource
#             )
#
#         Rule(
#             self,
#             'AmazonEKSNodeDrainerEventRule',
#             event_pattern=EventPattern(
#                 source=["aws.autoscaling"],
#                 detail_type=["EC2 Instance-terminate Lifecycle Action"],
#                 detail={
#                     "AutoScalingGroupName": [x.auto_scaling_group_name for x in self.eks_fleets.values()],
#                 }
#             ),
#             targets=[
#                 LambdaFunction(AmazonNodeDrainerLambda.get_function(self, cluster_name=cluster_name))
#             ]
#         )
#
#         eks_cluster.aws_auth.add_role_mapping(
#             AmazonNodeDrainerLambda.get_function(self, cluster_name=cluster_name).role,
#             groups=['system:authenticated'],
#             username='lambda',
#         )
#
#         for fleet_id, fleet in fleets.items():
#             CfnLifecycleHook(
#                 self,
#                 f'TerminationLifeCycle{fleet_id}',
#                 auto_scaling_group_name=fleet.auto_scaling_group_name,
#                 lifecycle_transition='autoscaling:EC2_INSTANCE_TERMINATING',
#                 heartbeat_timeout=450,
#             )
#


    def _add_userdata_production_tweaks(self, fleet: AutoScalingGroup):
        # Source of tweaks: https://kubedex.com/90-days-of-aws-eks-in-production
        fleet.user_data.add_commands(
            """
# Sysctl changes
## Disable IPv6
cat <<EOF > /etc/sysctl.d/10-disable-ipv6.conf
# disable ipv6 config
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1
EOF""",
            """
## Kube network optimisation.
## Stolen from this guy: https://blog.codeship.com/running-1000-containers-in-docker-swarm/
cat <<EOF > /etc/sysctl.d/99-kube-net.conf
# Have a larger connection range available
net.ipv4.ip_local_port_range=1024 65000

# Reuse closed sockets faster
net.ipv4.tcp_tw_reuse=1
net.ipv4.tcp_fin_timeout=15

# The maximum number of "backlogged sockets".  Default is 128.
net.core.somaxconn=4096
net.core.netdev_max_backlog=4096

# 16MB per socket - which sounds like a lot,
# but will virtually never consume that much.
net.core.rmem_max=16777216
net.core.wmem_max=16777216

# Various network tunables
net.ipv4.tcp_max_syn_backlog=20480
net.ipv4.tcp_max_tw_buckets=400000
net.ipv4.tcp_no_metrics_save=1
net.ipv4.tcp_rmem=4096 87380 16777216
net.ipv4.tcp_syn_retries=2
net.ipv4.tcp_synack_retries=2
net.ipv4.tcp_wmem=4096 65536 16777216
#vm.min_free_kbytes=65536

# Connection tracking to prevent dropped connections (usually issue on LBs)
net.netfilter.nf_conntrack_max=262144
net.ipv4.netfilter.ip_conntrack_generic_timeout=120
net.netfilter.nf_conntrack_tcp_timeout_established=86400

# ARP cache settings for a highly loaded docker swarm
net.ipv4.neigh.default.gc_thresh1=8096
net.ipv4.neigh.default.gc_thresh2=12288
net.ipv4.neigh.default.gc_thresh3=16384
EOF""",
            "systemctl restart systemd-sysctl.service"
        )
