from aws_cdk.aws_eks import Cluster, ServiceAccount

from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class PrometheusOperator:
    """
    https://github.com/bitnami/charts/tree/master/bitnami/prometheus-operator
    """
    HELM_REPOSITORY = 'https://charts.bitnami.com/bitnami'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster) -> None:
        """
        Deploys into the EKS cluster the external secrets manager

        :param cluster:
        :return:
        """
        namespace = "prometheus"
        resource = ManifestGenerator.namespace_resource(namespace)
        ns = cluster.add_resource(
            f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
            resource
        )

        operator_sa = cluster.add_service_account(
            'prometheus-operator',
            name=f'prometheus-operator',
            namespace=resource.get('metadata', {}).get('name'),
        )
        operator_sa.node.add_dependency(ns)
        prometheus_sa = cluster.add_service_account(
            'prometheus',
            name=f'prometheus',
            namespace=resource.get('metadata', {}).get('name'),
        )
        prometheus_sa.node.add_dependency(ns)
        alertmanager_sa = cluster.add_service_account(
            'alertmanager',
            name=f'alertmanager',
            namespace=resource.get('metadata', {}).get('name'),
        )
        alertmanager_sa.node.add_dependency(ns)

        cls._create_chart_release(cluster, operator_sa, prometheus_sa, alertmanager_sa)

    @classmethod
    def _create_chart_release(
            cls,
            cluster: Cluster,
            operator_service_account: ServiceAccount,
            prometheus_service_account: ServiceAccount,
            alertmanager_service_account: ServiceAccount,
    ) -> None:
        chart = cluster.add_chart(
            "helm-chart-prometheus",
            release="prometheus",
            chart="prometheus-operator",
            namespace=operator_service_account.service_account_namespace,
            repository=cls.HELM_REPOSITORY,
            version="0.22.3",
            values={
                "operator": {
                    "serviceAccount": {
                        "create": False,
                        "name": operator_service_account.service_account_name,
                    },
                },
                "prometheus": {
                    "serviceAccount": {
                        "create": False,
                        "name": prometheus_service_account.service_account_name,
                    },
                },
                "alertmanager": {
                    "serviceAccount": {
                        "create": False,
                        "name": alertmanager_service_account.service_account_name,
                    },
                },

            },
        )
        chart.node.add_dependency(operator_service_account)
        chart.node.add_dependency(prometheus_service_account)
        chart.node.add_dependency(alertmanager_service_account)
