from typing import List

from aws_cdk.aws_ec2 import SubnetConfiguration, SubnetType, BastionHostLinux, InstanceType, Vpc
from aws_cdk.core import Tag

from apps.abstract.base_app import BaseApp
from cdk_stacks.abstract.base_stack import BaseStack
from cdk_stacks.environment.vpc.eks import EKSStack
from cdk_stacks.environment.vpc.route53 import Route53Stack


class VPCStack(BaseStack):
    def __init__(self, scope: BaseApp, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc_creation_enabled = bool(scope.environment_config.get('vpc', {}).get('enabled'))
        vpc_selection_enabled = bool(scope.environment_config.get('vpcSelectionFilter', {}).get('enabled'))

        if not vpc_creation_enabled ^ vpc_selection_enabled:
            raise ValueError("One option between `vpc` and `vpcSelectionFilter` must be enabled (not both)")

        vpc = self.create_vpc(scope) if vpc_creation_enabled else self.select_vpc(scope)

        eks_stack = None
        if scope.environment_config.get('eks', {}).get('enabled'):
            eks_stack = EKSStack(scope, 'EKS', vpc)

        for zone in scope.environment_config.get('dnsZones', []):
            Route53Stack(scope, 'zone', zone, vpc, eks_stack.cluster if eks_stack else None)

    def select_vpc(self, scope: BaseApp) -> Vpc:
        vpc_filters = scope.environment_config.get("vpcSelectionFilter", {})

        return Vpc.from_lookup(
            self,
            scope.prefixed_str("vpc"),
            vpc_id=vpc_filters.get("vpcId"),
            vpc_name=vpc_filters.get("vpcName"),
            is_default=vpc_filters.get("isDefault"),
            tags=vpc_filters.get("tags"),
        )

    def create_vpc(self, scope: BaseApp, eks_enabled: bool = True) -> Vpc:
        vpc = Vpc(
            self,
            scope.prefixed_str(scope.environment_config.get('vpc', {}).get('name')),
            cidr=scope.environment_config.get('vpc', {}).get('cidr'),
            max_azs=scope.environment_config.get('vpc', {}).get('maxAZs'),
            enable_dns_hostnames=True,
            enable_dns_support=True,
            subnet_configuration=self._get_subnet_configuration(scope),
        )

        if eks_enabled:
            for subnet in vpc.public_subnets:
                Tag.add(subnet, "kubernetes.io/role/elb", "1")
                Tag.add(subnet,
                        f"kubernetes.io/cluster/{scope.prefixed_str(scope.environment_config.get('eks', {}).get('clusterName'))}",
                        "shared")
            for subnet in vpc.private_subnets:
                Tag.add(subnet, "kubernetes.io/role/internal-elb", "1")
                Tag.add(subnet,
                        f"kubernetes.io/cluster/{scope.prefixed_str(scope.environment_config.get('eks', {}).get('clusterName'))}",
                        "shared")

        if scope.environment_config.get('vpc', {}).get('bastionHost', {}).get('enabled'):
            BastionHostLinux(
                self,
                scope.prefixed_str('BastionHost'),
                vpc=vpc,
                instance_type=InstanceType(
                    scope.environment_config.get('vpc', {}).get('bastionHost', {}).get('instanceType')
                ),
                instance_name=scope.prefixed_str('BastionHost')
            )
        return vpc

    def _get_subnet_configuration(self, scope) -> List[SubnetConfiguration]:
        """
        Get VPC subnets based on desired configuration.
        :param scope:
        :return:
        """
        subnet_configuration = []

        """
        To generate a Private-only configuration we need one of [
          NatGatewayId,
          NetworkInterfaceId,
          GatewayId,
          EgressOnlyInternetGatewayId,
          VpcPeeringConnectionId,
          TransitGatewayId,
          InstanceId
        ] to specify the default route.
        For now we stick to use the default (NatGateway in the public subnets)
        """
        if True:
            subnet_configuration.append(
                SubnetConfiguration(
                    subnet_type=SubnetType.PUBLIC,
                    cidr_mask=scope.environment_config.get('vpc', {}).get('subnetsCIDRSuffixes', {}).get('public'),
                    name='Public'
                )
            )
        if True:
            subnet_configuration.append(
                SubnetConfiguration(
                    subnet_type=SubnetType.PRIVATE,
                    cidr_mask=scope.environment_config.get('vpc', {}).get('subnetsCIDRSuffixes', {}).get('private'),
                    name='Private',
                )
            )
        if True:
            subnet_configuration.append(
                SubnetConfiguration(
                    subnet_type=SubnetType.ISOLATED,
                    cidr_mask=scope.environment_config.get('vpc', {}).get('subnetsCIDRSuffixes', {}).get('isolated'),
                    name='Isolated'
                )
            )
        return subnet_configuration
