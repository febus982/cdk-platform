from typing import Union

from aws_cdk.aws_ec2 import Vpc
from aws_cdk.aws_eks import Cluster
from aws_cdk.aws_route53 import PublicHostedZone, PrivateHostedZone

from apps.abstract.base_app import BaseApp
from cdk_stacks.abstract.base_stack import BaseStack
from cdk_stacks.environment.vpc.eks.eks_resources.external_dns import ExternalDns


class Route53Stack(BaseStack):
    def __init__(self, scope: BaseApp, id: str, dns_config: dict, vpc: Vpc, eks_cluster: Cluster = None,
                 **kwargs) -> None:

        super().__init__(scope, id, **kwargs)

        self._create_environment_main_zones(scope, dns_config, eks_cluster, vpc)

        for zone in dns_config.get("additionalZones", []):
            zone_domain_name = self._calculate_zone_domain(
                scope,
                zone.get('domainName'),
            )
            zone_id = self._calculate_zone_identifier(
                zone_domain_name,
                private_zone=zone.get("privateZone"),
            )
            self._create_zone(
                zone_id,
                fqdn=zone_domain_name,
                private_zone=True,
                vpc=vpc
            )
            if zone.get('eksExternalDnsSyncEnabled') and isinstance(eks_cluster, Cluster):
                ExternalDns.add_to_cluster(eks_cluster, zone_id)

    def _create_environment_main_zones(self, scope, dns_config, eks_cluster, vpc):
        main_zone_domain_name = self._calculate_zone_domain(
            scope,
            dns_config.get('domainName'),
        )
        if dns_config.get("privateZone", {}).get("enabled"):
            zone_id = self._calculate_zone_identifier(
                main_zone_domain_name,
                private_zone=True,
            )
            self._create_zone(
                zone_id,
                fqdn=main_zone_domain_name,
                private_zone=True,
                vpc=vpc
            )
            if dns_config.get("privateZone", {}).get('eksExternalDnsSyncEnabled') and isinstance(eks_cluster, Cluster):
                ExternalDns.add_to_cluster(eks_cluster, zone_id)
        if dns_config.get("publicZone", {}).get("enabled"):
            zone_id = self._calculate_zone_identifier(
                main_zone_domain_name,
                private_zone=False,
            )
            self._create_zone(
                zone_id,
                fqdn=main_zone_domain_name,
                private_zone=False,
                vpc=vpc
            )
            if dns_config.get("privateZone", {}).get('eksExternalDnsSyncEnabled') and isinstance(eks_cluster, Cluster):
                ExternalDns.add_to_cluster(eks_cluster, zone_id)

    def _create_zone(self, zone_id: str, fqdn: str, private_zone: bool, vpc: Vpc) -> Union[
        PublicHostedZone, PrivateHostedZone]:
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

    def _calculate_zone_domain(self, scope: BaseApp, domain: str) -> str:
        return f"{scope.environment_name}.{scope.environment_config.get('projectName')}.{domain}"

    def _calculate_zone_identifier(self, fqdn: str, private_zone: bool):
        return f"{fqdn.replace('.', '-')}-{'private' if private_zone else 'public'}"
