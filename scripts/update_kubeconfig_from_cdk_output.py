import json
import os


def _find_kubeconfig_command(obj):
    for k, v in obj.items():
        if "EKSClusterConfigCommand" in k:
            return v
        if isinstance(v, dict):
            return _find_kubeconfig_command(v)


with open(os.path.join(os.path.dirname(__file__), '..', 'outputs.json')) as f:
    print(_find_kubeconfig_command(json.load(f)))
