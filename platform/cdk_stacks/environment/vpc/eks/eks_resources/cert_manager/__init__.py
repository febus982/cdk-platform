from aws_cdk.aws_eks import Cluster

from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class CertManager:
    """
    https://github.com/jetstack/cert-manager/blob/master/deploy/charts/cert-manager/values.yaml
    https://hub.helm.sh/charts/jetstack/cert-manager
    """
    HELM_REPOSITORY = 'https://charts.jetstack.io'

    @classmethod
    def add_to_cluster(cls, cluster: Cluster) -> None:
        """
        Deploys cert-manager into the EKS cluster

        :param cluster:
        :return:
        """
        resource = ManifestGenerator.namespace_resource('cert-manager')
        namespace = cluster.add_resource(
            f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
            resource
        )

        sa = cluster.add_service_account(
            'CertManagerServiceAccount',
            name='cert-manager',
            namespace=resource.get('metadata', {}).get('name'),
        )
        sa.node.add_dependency(namespace)
        injector_sa = cluster.add_service_account(
            'CertManagerCAInjectorServiceAccount',
            name='cert-manager-ca-injector',
            namespace=resource.get('metadata', {}).get('name'),
        )
        injector_sa.node.add_dependency(namespace)
        webhook_sa = cluster.add_service_account(
            'CertManagerWebhookServiceAccount',
            name='cert-manager-webhook',
            namespace=resource.get('metadata', {}).get('name'),
        )
        webhook_sa.node.add_dependency(namespace)

        chart = cluster.add_chart(
            "helm-chart-cert-manager",
            release="cert-manager",
            chart="cert-manager",
            namespace="cert-manager",
            repository=cls.HELM_REPOSITORY,
            version="v0.15.2",
            values={
                "global": {
                    "podSecurityPolicy": {
                        "enabled": True,
                    },
                },
                "installCRDs": True,
                "serviceAccount": {
                    "create": False,
                    "name": sa.service_account_name,
                },
                "cainjector": {
                    "serviceAccount": {
                        "create": False,
                        "name": injector_sa.service_account_name
                    },
                },
                "webhook": {
                    "serviceAccount": {
                        "create": False,
                        "name": injector_sa.service_account_name
                    },
                },
            },
        )
        chart.node.add_dependency(sa)
        chart.node.add_dependency(injector_sa)
        chart.node.add_dependency(webhook_sa)
