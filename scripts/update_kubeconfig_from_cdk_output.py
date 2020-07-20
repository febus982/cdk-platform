import json
import os


def _find_kubeconfig_command(obj):
    found = None
    for k, v in obj.items():
        if "EKSClusterConfigCommand" in k:
            found = v
        if isinstance(v, dict):
            res = _find_kubeconfig_command(v)
            if res is not None:
                found = res

    return found


with open(os.path.join(os.path.dirname(__file__), '..', 'outputs.json')) as f:
    print(_find_kubeconfig_command(json.load(f)))
