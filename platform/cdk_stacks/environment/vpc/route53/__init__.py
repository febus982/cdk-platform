from typing import Union

from aws_cdk.aws_ec2 import Vpc
from aws_cdk.aws_eks import Cluster
from aws_cdk.aws_route53 import PublicHostedZone, PrivateHostedZone

from apps.abstract.base_app import BaseApp
from cdk_stacks.abstract.base_stack import BaseStack
from cdk_stacks.environment.vpc.eks.eks_resources.external_dns import ExternalDns


class Route53Stack(BaseStack):
    def __init__(self, scope: BaseApp, id: str, zone: dict, vpc: Vpc, eks_cluster: Cluster = None, **kwargs) -> None:

        domain_name = self._calculate_zone_domain(
            scope,
            zone.get('domainName'),
            zone.get('domainNameWithPrefix'),
        )
        zone_id = self._calculate_zone_identifier(
            domain_name,
            zone.get('privateZone'),
        )
        super().__init__(scope, f"{id}-{zone_id}", **kwargs)
        created_zone = self._create_zone(
            zone_id,
            domain_name,
            zone.get('privateZone'),
            vpc
        )

        if zone.get('eksExternalDnsSyncEnabled') and isinstance(eks_cluster, Cluster):
            ExternalDns.add_to_cluster(eks_cluster, zone_id)

    def _create_zone(self, zone_id: str, fqdn: str, private_zone: bool, vpc: Vpc) -> Union[PublicHostedZone, PrivateHostedZone]:
        if private_zone:
            return PrivateHostedZone(
                self,
                zone_id,
                zone_name=fqdn,
                vpc=vpc,
            )
        else:
            return PublicHostedZone(
                self,
                zone_id,
                zone_name=fqdn,
            )

    def _calculate_zone_domain(self, scope: BaseApp, domain: str, with_prefix: bool) -> str:
        if with_prefix:
            return f"{scope.environment_name}.{scope.environment_config.get('projectName')}.{domain}"
        else:
            return domain

    def _calculate_zone_identifier(self, fqdn: str, private_zone: bool):
        return f"{fqdn.replace('.', '-')}-{'private' if private_zone else 'public'}"
