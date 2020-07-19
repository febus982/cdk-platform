from aws_cdk.aws_eks import Cluster, ServiceAccount

from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class Grafana:
    """
    https://github.com/bitnami/charts/tree/master/bitnami/grafana
    """
    HELM_REPOSITORY = 'https://charts.bitnami.com/bitnami'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster, env_domain: str = 'example.com') -> None:
        """
        Deploys into the EKS cluster the external secrets manager

        :param env_domain:
        :param cluster:
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
        cls._create_chart_release(cluster, sa, env_domain)

    @classmethod
    def _create_chart_release(
            cls,
            cluster: Cluster,
            service_account: ServiceAccount,
            env_domain: str,
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
                "ingress": {
                    "enabled": True,
                    "hosts": [
                        {
                            "paths": ["/*"],
                            "name": f"grafana.{env_domain}",
                            "backend": {
                                "servicePort": 3000,
                            }
                        },
                    ],
                },
            },
        )
        chart.node.add_dependency(service_account)
