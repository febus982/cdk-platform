from typing import List

from aws_cdk.aws_autoscaling import AutoScalingGroup
from aws_cdk.aws_ec2 import Vpc, SubnetSelection, SubnetType, InstanceType, SecurityGroup, Port
from aws_cdk.aws_eks import Cluster, Selector, KubernetesVersion, BootstrapOptions
from aws_cdk.aws_iam import Role, AccountRootPrincipal
from aws_cdk.core import Tag

from apps.abstract.base_app import BaseApp
from cdk_stacks.abstract.base_stack import BaseStack
from cdk_stacks.environment.vpc.eks.eks_resources.cert_manager import CertManager
from cdk_stacks.environment.vpc.eks.eks_resources.cluster_autoscaler import ClusterAutoscaler
from cdk_stacks.environment.vpc.eks.eks_resources.external_dns import ExternalDns
from cdk_stacks.environment.vpc.eks.eks_resources.external_secrets import ExternalSecrets
from cdk_stacks.environment.vpc.eks.eks_resources.fluentd import Fluentd
from cdk_stacks.environment.vpc.eks.eks_resources.grafana import Grafana
from cdk_stacks.environment.vpc.eks.eks_resources.metrics_server import MetricsServer
from cdk_stacks.environment.vpc.eks.eks_resources.prometheus_operator import PrometheusOperator


class EKSStack(BaseStack):
    __cluster: Cluster

    @property
    def cluster(self):
        return self.__cluster

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

        self.__cluster = eks_cluster = Cluster(
            self,
            cluster_name,
            cluster_name=cluster_name,
            vpc=vpc,
            version=KubernetesVersion.of(kubernetes_version),
            default_capacity=0,  # We define later the capacity
            masters_role=cluster_admin_role,
            vpc_subnets=self._get_control_plane_subnets(scope),  # Control plane subnets
        )

        for profile in scope.environment_config.get('eks', {}).get('fargateProfiles', []):
            eks_cluster.add_fargate_profile(
                profile.get('name'),
                selectors=[
                    Selector(
                        namespace=profile.get('namespace'),
                        labels=profile.get('labels')
                    )
                ]
            )

        asg_fleets = []
        for fleet in scope.environment_config.get('eks', {}).get('workerNodesFleets'):
            if fleet.get('type') == 'managed':
                self.add_managed_fleet(eks_cluster, fleet)
            if fleet.get('type') == 'ASG':
                asg_fleets += self.add_asg_fleet(scope, eks_cluster, fleet)

        self._enable_cross_fleet_communication(asg_fleets)

        # Base cluster applications
        MetricsServer.add_to_cluster(eks_cluster)
        ClusterAutoscaler.add_to_cluster(eks_cluster, kubernetes_version)
        ExternalSecrets.add_to_cluster(eks_cluster)
        CertManager.add_to_cluster(eks_cluster)

        # Monitoring applications
        PrometheusOperator.add_to_cluster(eks_cluster)
        Grafana.add_to_cluster(eks_cluster)

        # Logging & tracing applications
        Fluentd.add_to_cluster(eks_cluster)
        # Loki ?
        # Elasticsearch + Kibana ?
        # Jaeger

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
        # To correctly scale the cluster we need our node groups to not span across AZs
        # to avoid the automatic AZ re-balance, hence we create a node group per subnet

        for counter, subnet in enumerate(cluster.vpc.private_subnets):
            fleet_id = f'{fleet.get("name")}-{counter}'
            cluster.add_nodegroup(
                id=fleet_id,
                instance_type=InstanceType(fleet.get('instanceType')),
                min_size=fleet.get('autoscaling', {}).get('minInstances'),
                max_size=fleet.get('autoscaling', {}).get('maxInstances'),
                labels=dict(**fleet.get('nodeLabels', {}), fleetName=fleet.get('name')),
                nodegroup_name=f'{fleet.get("name")}-{subnet.availability_zone}',
                subnets=SubnetSelection(subnets=[subnet]),
            )

    def add_asg_fleet(self, scope: BaseApp, cluster: Cluster, fleet) -> List[AutoScalingGroup]:
        created_fleets: List[AutoScalingGroup] = []

        node_labels = fleet.get('nodeLabels', {})
        node_labels["fleetName"] = fleet.get('name')
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

        cluster_sg = SecurityGroup.from_security_group_id(
            self,
            'eks-cluster-sg',
            security_group_id=cluster.cluster_security_group_id
        )

        asg_tags = {
            "k8s.io/cluster-autoscaler/enabled": "true",
            f"k8s.io/cluster-autoscaler/{cluster.cluster_name}": "owned",
        }

        # For correctly autoscaling the cluster we need our autoscaling groups to not span across AZs
        # to avoid the AZ Rebalance, hence we create an ASG per subnet
        for counter, subnet in enumerate(cluster.vpc.private_subnets):
            asg: AutoScalingGroup = cluster.add_capacity(
                id=scope.prefixed_str(f'{fleet.get("name")}-{counter}'),
                instance_type=InstanceType(fleet.get('instanceType')),
                min_capacity=fleet.get('autoscaling', {}).get('minInstances'),
                max_capacity=fleet.get('autoscaling', {}).get('maxInstances'),
                bootstrap_options=BootstrapOptions(
                    kubelet_extra_args=kubelet_extra_args,
                ),
                spot_price=str(fleet.get('spotPrice')) if fleet.get('spotPrice') else None,
                vpc_subnets=SubnetSelection(subnets=[subnet]),
            )
            created_fleets.append(asg)
            self._add_userdata_production_tweaks(asg)

            for key, value in asg_tags.items():
                Tag.add(asg, key, value)

        return created_fleets

    def _enable_cross_fleet_communication(self, fleets: List[AutoScalingGroup]):
        security_groups: List[SecurityGroup] = [fleet.node.find_child("InstanceSecurityGroup") for fleet in fleets]
        security_groups = list(set(security_groups))  # deduplication

        """
        This is horrible but we can't actually specify a common security group for all the ASGs, like managed nodes.
        We could add an additional common security group but this would breaks services of type `LoadBalancer`
        """
        for sg_target in security_groups:
            for sg_source in security_groups:
                rule_found = False
                for rule, value in sg_target.to_ingress_rule_config().items():
                    if rule == "sourceSecurityGroupId" and value == sg_source.security_group_id:
                        rule_found = True

                if not rule_found:
                    sg_target.connections.allow_from(sg_source, Port.all_traffic())

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
