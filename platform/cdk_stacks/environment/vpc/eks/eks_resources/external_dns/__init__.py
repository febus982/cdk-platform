from aws_cdk.aws_eks import Cluster, ServiceAccount
from aws_cdk.aws_iam import Role, PolicyStatement, Effect

# https://github.com/bitnami/charts/tree/master/bitnami/external-dns
# https://github.com/kubernetes-sigs/external-dns/blob/master/docs/tutorials/istio.md
from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class ExternalDns:
    HELM_REPOSITORY = 'https://charts.bitnami.com/bitnami'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster, zone_id: str) -> None:
        """
        Deploys into the EKS cluster the external secrets manager

        :param cluster:
        :param zone_id:
        :return:
        """
        namespace = f"external-dns-{zone_id}"
        resource = ManifestGenerator.namespace_resource(namespace)
        ns = cluster.add_resource(
            f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
            resource
        )

        sa = cluster.add_service_account(
            f'externalDnsServiceAccount-{zone_id}',
            name=f'external-dns-{zone_id}',
            namespace=resource.get('metadata', {}).get('name'),
        )
        sa.node.add_dependency(ns)
        cls.attach_iam_policies_to_role(sa.role, zone_id)

        cls._create_chart_release(cluster, sa, zone_id)

    @classmethod
    def _create_chart_release(cls, cluster: Cluster, service_account: ServiceAccount, zone_id: str) -> None:
        chart = cluster.add_chart(
            f"helm-chart-external-dns-{zone_id}",
            release=f"ext-dns-{zone_id}",
            chart="external-dns",
            namespace=service_account.service_account_namespace,
            repository=cls.HELM_REPOSITORY,
            version="3.2.3",
            values={
                "aws": {
                    "region": cluster.vpc.stack.region,
                },
                "serviceAccount": {
                    "name": service_account.service_account_name,
                    "create": False,
                },
                "sources": [
                    'service',
                    'ingress',
                    'istio-gateway',
                    # 'istio-virtualservice',  # Soon to be released, keep an eye on releases
                ],
                "txtOwnerId": cluster.cluster_name,
                "rbac": {
                    "create": True,
                    "pspEnabled": True,
                },
                "replicas": 1,
                "metrics": {
                    "enabled": True,
                },
                "annotationFilter": f"external-dns-route53-zone={zone_id}",
                "zoneIdFilters": [
                    zone_id,
                ],
            },
        )
        chart.node.add_dependency(service_account)

    @classmethod
    def attach_iam_policies_to_role(cls, role: Role, zone_id: str):
        """
        Attach the necessary policies to read secrets from SSM and SecretsManager

        :param role:
        :param zone_id:
        :return:
        """
        # TODO: Extract this in a managed policy
        route53_policy = PolicyStatement(
            resources=["*"],
            effect=Effect.ALLOW,
            actions=[
                "route53:ListHostedZones",
                "route53:ListResourceRecordSets",
            ],
        )
        route53_recordset_policy = PolicyStatement(
            resources=["arn:aws:route53:::hostedzone/*"],  # To be restricted to interested zone
            effect=Effect.ALLOW,
            actions=[
                "route53:ChangeResourceRecordSets",
            ],
        )
        role.add_to_policy(route53_policy)
        role.add_to_policy(route53_recordset_policy)
