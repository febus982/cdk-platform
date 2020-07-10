from typing import Union

from aws_cdk.aws_ec2 import Vpc
from aws_cdk.aws_route53 import PublicHostedZone, PrivateHostedZone

from apps.abstract.base_app import BaseApp
from cdk_stacks.abstract.base_stack import BaseStack


class Route53Stack(BaseStack):
    def __init__(self, scope: BaseApp, id: str, vpc: Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        for zone in scope.environment_config.get('dns', []):
            domain_name = self._calculate_zone_domain(
                scope,
                zone.get('domainName'),
                zone.get('domainNameWithPrefix'),
            )
            zone_id = self._calculate_zone_identifier(
                domain_name,
                zone.get('privateZone'),
            )
            created_zone = self._create_zone(
                zone_id,
                domain_name,
                zone.get('privateZone'),
                vpc
            )

            if zone.get('eksExternalDnsSyncEnabled') and scope.environment_config.get('eks', {}).get('enabled'):
                print("Hey! I have enabled external-dns here. (Well, it will be after implementation :D )")

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
            return f"{scope.environment_config.get('projectName')}.{scope.environment_name}.{domain}"
        else:
            return domain

    def _calculate_zone_identifier(self, fqdn: str, private_zone: bool):
        return f"{fqdn.replace('.', '-')}-{'private' if private_zone else 'public'}"
