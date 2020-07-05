import typing

from aws_cdk.core import Environment

from apps.abstract.base_app import BaseApp
# from cdk_stacks.bastion_stacks import IAMUsersStack
# from cdk_stacks.environment_stacks import EKSStack
# from cdk_stacks.environment_stacks.ecs_stack import ECSStack
# from cdk_stacks.platform_stacks import VPCStack, IAMRolesStack
from cdk_stacks.environment.vpc import VPCStack


class Platform(BaseApp):
    STACK_BASTION_IAM_USERS = 'bastion-IAM-users'

    STACK_PLATFORM_IAM_ROLES = 'platform-IAM-roles'

    STACK_ENV_VPC = 'VPC'
    STACK_ENV_EKS = 'EKS'
    STACK_ENV_ECS = 'ECS'

    def __init__(self, *, platform_account_env: Environment, users_account_env: Environment,
                 auto_synth: typing.Optional[bool] = None,
                 context: typing.Optional[typing.Mapping[str, str]] = None, outdir: typing.Optional[str] = None,
                 runtime_info: typing.Optional[bool] = None, stack_traces: typing.Optional[bool] = None,
                 tree_metadata: typing.Optional[bool] = None) -> None:
        super().__init__(auto_synth=auto_synth, context=context, outdir=outdir, runtime_info=runtime_info,
                         stack_traces=stack_traces, tree_metadata=tree_metadata)

        self.generate_platform_stacks(platform_account_env, users_account_env.account)

    def generate_platform_stacks(self, env: Environment, users_account_principal_id: str):
        self.stacks[self.STACK_ENV_VPC] = VPCStack(
            self,
            self.STACK_ENV_VPC,
        )
        # self.stacks[self.STACK_PLATFORM_VPC] = VPCStack(
        #     self,
        #     self.STACK_PLATFORM_VPC,
        #     env=env,
        # )
        # self.stacks[self.STACK_PLATFORM_IAM_ROLES] = IAMRolesStack(
        #     self,
        #     self.STACK_PLATFORM_IAM_ROLES,
        #     env=env,
        #     users_account_principal_id=users_account_principal_id,
        # )

    def generate_users_stacks(self, env: Environment):
        pass
        # self.stacks[self.STACK_BASTION_IAM_USERS] = IAMUsersStack(
        #     self,
        #     self.STACK_BASTION_IAM_USERS,
        #     env=env,
        # )

    def generate_environment_stacks(self, env):
        pass
        # if self.environment:
        #     if self.environment_config.get('eks', {}).get('enabled'):
        #         self.stacks[self.STACK_ENV_EKS] = EKSStack(
        #             self,
        #             'EKS',
        #             env=env,
        #             environment=self._set_environment(),
        #             vpc_stack=self.stacks[self.STACK_PLATFORM_VPC],
        #         )
        #     if self.environment_config.get('ecs', {}).get('enabled'):
        #         self.stacks[self.STACK_ENV_ECS] = ECSStack(
        #             self,
        #             'ECS',
        #             env=env,
        #             environment=self._set_environment(),
        #             vpc_stack=self.stacks[self.STACK_PLATFORM_VPC],
        #         )
