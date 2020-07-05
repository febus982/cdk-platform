#!/usr/bin/env bash
set -ef

COMMAND="cdk"

if [[ ! -z "${AWS_CF_ROLE}" ]]; then
  COMMAND="${COMMAND} --role-arn ${AWS_CF_ROLE} "
fi
COMMAND="${COMMAND} ${@}"

eval "${COMMAND}"
