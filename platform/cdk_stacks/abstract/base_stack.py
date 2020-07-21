from aws_cdk import core

from apps.abstract.base_app import BaseApp


class BaseStack(core.Stack):
    def __init__(self, scope: BaseApp, id: str, **kwargs) -> None:
        super().__init__(scope, scope.prefixed_str(id), env=scope.platform_account_env, **kwargs)
        self._apply_tags(scope)

    def _apply_tags(self, scope) -> None:
        stack_tags = {
            'org-unit': 'engineering',
            'squad': f'{scope.environment_config.get("squadName")}-squad',
            'app-name': f'{scope.environment_config.get("projectName")}-project',
            'app-component': 'platform',
            'app-environment': scope.environment_name
        }

        for key, value in stack_tags.items():
            core.Tag.add(self, key, value)
