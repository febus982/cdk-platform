import yaml


class ManifestGenerator:
    @classmethod
    def namespace_resource(cls, name: str):
        return yaml.safe_load(f"""
---
apiVersion: v1
kind: Namespace
metadata:
  name: {name}
...
""")
