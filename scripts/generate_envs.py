#!/usr/bin/env python

import json
import os
from abc import ABC
from typing import Dict, IO, Optional

import click


class VariablesDTO(ABC):
    """
    Abstract DTO class with helpers to convert public attributes <-> dict
    """

    @classmethod
    def from_dict(cls, values: Dict[str, str]):
        obj = cls()
        for attr in cls.__dict__.keys():
            if not attr.startswith("_"):
                obj.__setattr__(attr, values.get(attr))
        return obj

    def to_dict(self) -> Dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class EnvironmentVariables(VariablesDTO):
    """
    Data object for variables needed for an environment
    """
    AWS_ACCOUNT_ID: str = None
    AWS_PROFILE: str = None
    AWS_CF_ROLE: str = None
    CIRCLE_BRANCH: str = None


class SharedVariables(VariablesDTO):
    """
    Data object for variables common to all environments
    """
    AWS_DEFAULT_REGION: str = None
    AWS_BASTION_ACCOUNT_ID: str = None


def save_env_file(shared_vars: SharedVariables, environment_vars: EnvironmentVariables, file: IO) -> None:
    """
    Saves an environment file to be used by docker-compose using format ENV=value (uppercase keys, raw values)

    :param shared_vars:
    :param environment_vars:
    :param file:
    :return:
    """
    filtered_vars: Dict[str, str] = {
        k.upper(): v
        for k, v in {**shared_vars.to_dict(), **environment_vars.to_dict()}.items()
        if v is not None
    }

    formatted_env_file = "\n".join(
        map('='.join, filtered_vars.items())
    )
    click.echo(
        formatted_env_file,
        file=file,
    )


def save_variables(common_variables: SharedVariables, environment_variables: Dict[str, EnvironmentVariables],
                   file=None) -> None:
    """
    Saves the variables to a json file for future reuse

    :param file:
    :param common_variables:
    :param environment_variables:
    :return:
    """
    click.echo(
        json.dumps({
            'common': common_variables.to_dict(),
            'envs': {k: v.to_dict() for k, v in environment_variables.items()},
        }),
        file=file,
    )


def load_saved_variables(file_path: str) -> Dict:
    """
    Load saved variables into a dictionary

    :param file_path:
    :return:
    """
    saved_vars = {}
    try:
        with open(file_path) as f:
            saved_vars = json.load(f)
    except FileNotFoundError:
        pass

    return saved_vars


def _click_input_value_proc(value) -> Optional[str]:
    """
    Process value to be null if input is '-1' or empty string

    :param value:
    :return:
    """
    return str(value) if value not in ["-1", ""] else None


def _prompt_for_var(var_name, default_value) -> Optional[str]:
    """
    Create a formatted prompt to read a variable, with default value and instructions for null value

    :param var_name:
    :param default_value:
    :return:
    """
    value = click.prompt(
        f'{var_name}',
        value_proc=_click_input_value_proc,
        prompt_suffix=f'{" (-1 to delete)" if default_value else ""}: ',
        default=default_value or "",
    )

    return value if value != "" else None


def prompt_for_shared_vars(common_vars: SharedVariables) -> SharedVariables:
    """
    Iterate over shared vars and prompt for input

    :param common_vars:
    :return:
    """
    common_vars.AWS_DEFAULT_REGION = _prompt_for_var("AWS Region", common_vars.AWS_DEFAULT_REGION)
    click.echo()

    click.echo('/==== BASTION ACCOUNT (OPTIONAL) ========/')
    common_vars.AWS_BASTION_ACCOUNT_ID = _prompt_for_var("Bastion AWS account number",
                                                         common_vars.AWS_BASTION_ACCOUNT_ID)
    click.echo('/========================================/')
    click.echo()
    return common_vars


def prompt_for_environment_vars(environment_name: str, branch_name: str,
                                environment_vars: EnvironmentVariables) -> EnvironmentVariables:
    """
    Iterate over environment variables and prompt for input

    :param environment_name:
    :param branch_name:
    :param environment_vars:
    :return:
    """
    click.echo(f'/=========== {environment_name} =============/')
    environment_vars.CIRCLE_BRANCH = branch_name
    environment_vars.AWS_ACCOUNT_ID = _prompt_for_var(f"{environment_name} AWS account number",
                                                      environment_vars.AWS_ACCOUNT_ID)
    environment_vars.AWS_PROFILE = _prompt_for_var(f"{environment_name} AWS CLI profile name",
                                                   environment_vars.AWS_PROFILE)
    environment_vars.AWS_CF_ROLE = _prompt_for_var(f"{environment_name} AWS Cloudformation role to use with with Bastion account",
                                                   environment_vars.AWS_CF_ROLE)
    click.echo('/========================================/')
    click.echo()
    return environment_vars


@click.command()
def generate_envs():
    """
    Configure AWS credentials and generate env files

    :return:
    """

    env_directory = os.path.join(os.path.dirname(__file__), '..', '.aws_envs')
    environments_branches_registry = {
        'prod': 'env-prod',
        'staging': 'env-staging',
        'lower': 'env-lower'
    }

    environment_vars: Dict[str, EnvironmentVariables] = {}
    saved_vars = load_saved_variables(os.path.join(env_directory, ".vars.json"))

    click.echo('Configure AWS credentials:')
    shared_vars = prompt_for_shared_vars(SharedVariables.from_dict(saved_vars.get('common', {})))

    for env_name, branch in environments_branches_registry.items():
        environment_vars[env_name] = prompt_for_environment_vars(
            environment_name=env_name,
            branch_name=branch,
            environment_vars=EnvironmentVariables.from_dict(saved_vars.get('envs', {}).get(env_name, {})),
        )

    with open(os.path.join(env_directory, ".vars.json"), mode="w") as f:
        save_variables(shared_vars, environment_vars, f)

    for env_name, env_object in environment_vars.items():
        with open(os.path.join(env_directory, f"env-{env_name}"), mode="w") as f:
            save_env_file(shared_vars, env_object, f)


if __name__ == '__main__':
    generate_envs()
