import os
import typing

import yaml
from aws_cdk.core import App, Environment
from deepmerge import Merger


class BaseApp(App):
    ENV_BRANCH_PREFIX = 'env-'
    environment_name: str = None

    _config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config')
    _default_config_path = os.path.join(os.path.dirname(__file__), '..', 'default_config')

    def __init__(self, *, platform_account_env: Environment, users_account_env: Environment,
                 auto_synth: typing.Optional[bool] = None,
                 context: typing.Optional[typing.Mapping[str, str]] = None, outdir: typing.Optional[str] = None,
                 runtime_info: typing.Optional[bool] = None, stack_traces: typing.Optional[bool] = None,
                 tree_metadata: typing.Optional[bool] = None) -> None:
        super().__init__(auto_synth=auto_synth, context=context, outdir=outdir, runtime_info=runtime_info,
                         stack_traces=stack_traces, tree_metadata=tree_metadata)
        self.environment_config = {}

        self.stacks = {}
        self.platform_account_env = platform_account_env
        self.users_account_env = users_account_env
        self._set_environment(os.getenv("CIRCLE_BRANCH", "env-test"))
        self._parse_default_config()
        self._parse_custom_config_files()

    def _set_environment(self, branch: str) -> None:
        """
        Calculates environment name from branch name
        :return:
        """
        if branch[0:len(self.ENV_BRANCH_PREFIX)] == self.ENV_BRANCH_PREFIX:
            self.environment_name = branch

    def _parse_default_config(self) -> None:
        self._merge_file_in_config(self.environment_config, os.path.join(self._default_config_path, 'env.yaml'))

    def _parse_custom_config_files(self) -> None:
        self._merge_file_in_config(self.environment_config, os.path.join(self._config_path, 'env.yaml'), True)

        self._merge_file_in_config(self.environment_config, os.path.join(self._config_path, f'{self.environment_name}.yaml'),
                                   True)

    def _merge_file_in_config(self, config: dict, file_path: str, ignore_missing: bool = False) -> None:
        """
        Parses a yaml file and merges its content in a configuration dictionary

        :param config: Configuration dictionary
        :param file_path: Yaml file to be parsed
        :param ignore_missing: if True missing file error will be suppressed
        :return:
        """
        try:
            with open(file_path) as f:
                self._config_merger().merge(config, yaml.load(f, Loader=yaml.FullLoader))
        except FileNotFoundError:
            if not ignore_missing:
                raise

    def _config_merger(self) -> Merger:
        """
        Defines configuration files merger rules

        :return:
        """
        return Merger(
            [
                (list, ["override"]),
                (dict, ["merge"])
            ],
            ["override"],
            ["override"]
        )

    def prefixed_str(self, value: str) -> str:
        return f"{self.environment_name}-{self.environment_config.get('projectName')}-{value}"
