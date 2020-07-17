from aws_cdk.aws_eks import Cluster


class Loki:
    """
    https://github.com/grafana/loki/tree/master/production/helm/loki-stack
    """
    HELM_REPOSITORY = 'https://grafana.github.io/loki/charts'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster) -> None:
        """
        Deploys into the EKS cluster Loki stack

        :param cluster:
        :return:
        """
        # namespace = "loki"
        # resource = ManifestGenerator.namespace_resource(namespace)
        # ns = cluster.add_resource(
        #     f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
        #     resource
        # )
        #
        # sa = cluster.add_service_account(
        #     'loki',
        #     name=f'loki',
        #     namespace=resource.get('metadata', {}).get('name'),
        # )
        # sa.node.add_dependency(ns)
        cls._create_chart_release(cluster)

    @classmethod
    def _create_chart_release(
            cls,
            cluster: Cluster,
    ) -> None:
        chart = cluster.add_chart(
            "helm-chart-loki",
            release="loki",
            chart="loki-stack",
            namespace="loki",
            repository=cls.HELM_REPOSITORY,
            version="0.38.2",
            values=None,
        )
