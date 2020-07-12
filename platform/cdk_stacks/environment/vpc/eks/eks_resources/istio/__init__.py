import os
import subprocess
from typing import Iterable

import yaml
from aws_cdk.aws_eks import Cluster
from aws_cdk.core import IConstruct

from cdk_stacks.environment.vpc.eks.eks_resources.manifest_generator import ManifestGenerator


class Istio:
    """
    CDK does not support yet the deploy of custom helm charts, so we need to generate and apply the manifests manually.

    Reference: https://istio.io/latest/docs/setup/install/standalone-operator/

    We expect the Docker image to download Istio sources and Helm cli at build time.
    """
    @classmethod
    def add_to_cluster(cls, cluster: Cluster) -> None:
        """
        Deploys Istio into the EKS cluster

        :param cluster:
        :return:
        """
        resource = ManifestGenerator.namespace_resource('istio-system')
        ns = cluster.add_resource(
            f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
            resource
        )

        operator_manifest_path = f'/tmp/istio_manifest.yml'
        cls._generate_istio_operator_manifest(operator_manifest_path)

        operator_resources_list = cls._apply_manifest(cluster, operator_manifest_path, [ns])
        cls._apply_manifest(cluster, os.path.join(os.path.dirname(__file__), 'istio_operator_settings.yaml'), operator_resources_list)


    @classmethod
    def _generate_istio_operator_manifest(
            cls,
            destination_path: str,
            operator_namespace: str = 'istio-operator',
            istio_namespace: str = 'istio-system',
    ):
        result = subprocess.run([
            'helm', 'template', f'/cdk_app/istio-{os.environ.get("ISTIO_VERSION")}/manifests/charts/istio-operator/',
            '--set', 'hub=docker.io/istio',
            '--set', f'tag={os.environ.get("ISTIO_VERSION")}-distroless',
            '--set', f'operatorNamespace={operator_namespace}',
            '--set', f'istioNamespace={istio_namespace}',
        ], capture_output=True)
        manifest_file = open(destination_path, "w")
        manifest_file.write(result.stdout.decode())
        manifest_file.close()

    @classmethod
    def _apply_manifest(cls, cluster, manifest_path, dependencies: Iterable[IConstruct] = []):
        """
        Applies a list of kubernetes resources giving priority to resources of type `Namespace`.

        :param cluster:
        :param manifest_path:
        :param dependencies:
        :return:
        """
        resource_list = []
        namespace = None
        with open(manifest_path) as f:
            for resource in yaml.safe_load_all(f):
                if resource.get('kind') == 'Namespace':
                    namespace = cluster.add_resource(
                        f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
                        resource,
                    )
                    for dependency in dependencies:
                        namespace.node.add_dependency(dependency)
                resource_list.append(namespace)

        with open(manifest_path) as f:
            for resource in yaml.safe_load_all(f):
                if resource.get('kind') != 'Namespace':
                    res = cluster.add_resource(
                        f"{resource.get('kind')}-{resource.get('metadata', {}).get('name')}",
                        resource
                    )
                    if namespace:
                        res.node.add_dependency(namespace)
                    for dependency in dependencies:
                        res.node.add_dependency(dependency)
                    resource_list.append(res)
        return resource_list
