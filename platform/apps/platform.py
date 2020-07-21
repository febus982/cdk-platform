import typing

from aws_cdk.core import Environment

from apps.abstract.base_app import BaseApp
from cdk_stacks.environment.vpc import VPCStack


class Platform(BaseApp):
    def __init__(self, *, platform_account_env: Environment, users_account_env: Environment,
                 auto_synth: typing.Optional[bool] = None,
                 context: typing.Optional[typing.Mapping[str, str]] = None, outdir: typing.Optional[str] = None,
                 runtime_info: typing.Optional[bool] = None, stack_traces: typing.Optional[bool] = None,
                 tree_metadata: typing.Optional[bool] = None) -> None:
        super().__init__(platform_account_env=platform_account_env, users_account_env=users_account_env,
                         auto_synth=auto_synth, context=context, outdir=outdir, runtime_info=runtime_info,
                         stack_traces=stack_traces, tree_metadata=tree_metadata)

        self.generate_platform_stacks()

    def generate_platform_stacks(self):
        VPCStack(
            self,
            'VPC',
        )
