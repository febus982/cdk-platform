from aws_cdk.aws_eks import Cluster

from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class MetricsServer:
    """
    https://github.com/helm/charts/tree/master/stable/metrics-server
    """
    HELM_REPOSITORY = 'https://kubernetes-charts.storage.googleapis.com/'

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
            version="2.11.1",
            values={
                "image": {
                    "tag": "v0.3.6",
                },
                "args": [
                    "--kubelet-preferred-address-types=InternalIP"
                ],
                "rbac": {
                    "pspEnabled": True,
                },
            },
        )
        chart.node.add_dependency(namespace)
