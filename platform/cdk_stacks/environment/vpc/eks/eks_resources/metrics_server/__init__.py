import os

import yaml
from aws_cdk.aws_eks import Cluster


class MetricsServer:
    HELM_STABLE_REPOSITORY = 'https://kubernetes-charts.storage.googleapis.com/'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster) -> None:
        """
        Deploys into the EKS cluster the kubernetes metrics server

        :param cluster:
        :return:
        """
        with open(
                os.path.join(os.path.dirname(__file__), 'namespace.yaml')) as f:
            resource = yaml.safe_load(f)
        namespace = cluster.add_resource(
            f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
            resource
        )

        chart = cluster.add_chart(
            'helm-chart-metrics-server',
            release="metrics-server",
            chart="metrics-server",
            namespace="metrics-server",
            repository=cls.HELM_STABLE_REPOSITORY,
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
