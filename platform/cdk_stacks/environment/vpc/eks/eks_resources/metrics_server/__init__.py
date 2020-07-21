from aws_cdk.aws_eks import Cluster

from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class MetricsServer:
    """
    https://github.com/bitnami/charts/tree/master/bitnami/metrics-server
    """
    HELM_REPOSITORY = 'https://charts.bitnami.com/bitnami'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster) -> None:
        """
        Deploys into the EKS cluster the kubernetes metrics server

        :param cluster:
        :return:
        """
        resource = ManifestGenerator.namespace_resource('metrics-server')
        namespace = cluster.add_resource(
            f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
            resource
        )

        chart = cluster.add_chart(
            'helm-chart-metrics-server',
            release="metrics-server",
            chart="metrics-server",
            namespace="metrics-server",
            repository=cls.HELM_REPOSITORY,
            version="4.2.1",
            values={
                "extraArgs": {
                    "kubelet-preferred-address-types": "InternalIP",
                },
                "apiService": {
                    "create": True,
                },
            },
        )
        chart.node.add_dependency(namespace)
