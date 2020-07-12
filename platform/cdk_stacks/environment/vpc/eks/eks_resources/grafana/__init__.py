from aws_cdk.aws_eks import Cluster, ServiceAccount

# https://github.com/bitnami/charts/tree/master/bitnami/grafana
from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class Grafana:
    HELM_REPOSITORY = 'https://charts.bitnami.com/bitnami'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster) -> None:
        """
        Deploys into the EKS cluster the external secrets manager

        :param cluster:
        :param zone_id:
        :return:
        """
        namespace = "grafana"
        resource = ManifestGenerator.namespace_resource(namespace)
        ns = cluster.add_resource(
            f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
            resource
        )

        sa = cluster.add_service_account(
            'grafana',
            name=f'grafana',
            namespace=resource.get('metadata', {}).get('name'),
        )
        sa.node.add_dependency(ns)
        cls._create_chart_release(cluster, sa)

    @classmethod
    def _create_chart_release(
            cls,
            cluster: Cluster,
            service_account: ServiceAccount,
    ) -> None:
        chart = cluster.add_chart(
            "helm-chart-grafana",
            release="grafana",
            chart="grafana",
            namespace=service_account.service_account_namespace,
            repository=cls.HELM_REPOSITORY,
            version="3.1.1",
            values={
                "serviceAccount": {
                    "create": False,
                    "name": service_account.service_account_name,
                },
            },
        )
        chart.node.add_dependency(service_account)
