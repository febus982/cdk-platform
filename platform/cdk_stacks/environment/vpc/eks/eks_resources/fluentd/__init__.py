from aws_cdk.aws_eks import Cluster


# https://github.com/bitnami/charts/tree/master/bitnami/fluentd


class Fluentd:
    HELM_REPOSITORY = 'https://charts.bitnami.com/bitnami'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster) -> None:
        """
        Deploys into the EKS cluster the external secrets manager

        :param cluster:
        :return:
        """
        # namespace = "fluentd"
        # resource = ManifestGenerator.namespace_resource(namespace)
        # ns = cluster.add_resource(
        #     f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
        #     resource
        # )
        #
        # sa = cluster.add_service_account(
        #     'fluentd',
        #     name=f'fluentd',
        #     namespace=resource.get('metadata', {}).get('name'),
        # )
        # sa.node.add_dependency(ns)
        cls._create_chart_release(cluster)

    @classmethod
    def _create_chart_release(
            cls,
            cluster: Cluster,
    ) -> None:
        cluster.add_chart(
            "helm-chart-fluentd",
            release="fluentd",
            chart="fluentd",
            namespace="fluentd",
            repository=cls.HELM_REPOSITORY,
            version="1.2.7",
            values={
                "aggregator": {
                    "replicaCount": 1,
                },
                "serviceAccount": {
                    "create": True,
                },
                "metrics": {
                    "enabled": True,
                },
            },
        )
