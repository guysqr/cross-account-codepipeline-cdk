#!/usr/bin/env python3

import aws_cdk as cdk
from aws_cdk import Aspects

from stacks.repo_stack import RepoStack
from stacks.cloudformation_pipeline_stack import CloudformationPipelineStack
from stacks.s3_pipeline_stack import S3PipelineStack
from stacks.cross_account_role_stack import CrossAccountRoleStack
from stacks.pipeline_infra_stack import PipelineInfraStack
from stacks.parameter_stack import ParameterStack

from stacks.demo_s3_cloudfront import DemoCloudfrontStack

import os

app = cdk.App()

if os.environ.get("CDK_DEFAULT_ACCOUNT") is None:
    raise ValueError(
        "You are not logged in to AWS, or you need to otherwise set CDK_DEFAULT_ACCOUNT in your environment"
    )

account_num = os.environ["CDK_DEFAULT_ACCOUNT"]
deploy_region = os.environ["CDK_DEFAULT_REGION"]

# repo config
repo = app.node.try_get_context("repo")
branch = app.node.try_get_context("branch")
github_secret_arn = app.node.try_get_context("github_secret_arn")
repo_owner = app.node.try_get_context("repo_owner")

# buckets
target_bucket = app.node.try_get_context("target_bucket")
artifact_bucket = app.node.try_get_context("artifact_bucket")

# build vars
build_env = app.node.try_get_context("build_env")
stack_name = app.node.try_get_context("stack_name")
approvers = app.node.try_get_context("approvers")
devops_account_id = app.node.try_get_context("devops_account_id")
target_account_id = app.node.try_get_context("target_account_id")
pipeline_key_arn = app.node.try_get_context("pipeline_key_arn")
cross_account_role = app.node.try_get_context("cross_account_role_arn")
deployment_role_arn = app.node.try_get_context("deployment_role_arn")
parameter_list = app.node.try_get_context("parameter_list")
region = app.node.try_get_context("region")

if region:
    deploy_region = region

deploy_environment = cdk.Environment(account=account_num, region=deploy_region)

if build_env == None:
    build_env = ""

DemoCloudfrontStack(
    app,
    "demo-app-bucket",
    env=cdk.Environment(account=target_account_id, region="us-east-1"),
)

if repo and branch:

    if target_account_id:
        # create in the devops account
        PipelineInfraStack(
            app,
            "pipeline-key-" + repo + "-" + branch,
            target_account_id=target_account_id,
            repo_name=repo,
            repo_branch=branch,
            env=deploy_environment,
        )

    if devops_account_id:
        CrossAccountRoleStack(
            app,
            "cross-account-role-" + repo + "-" + branch,
            devops_account_id=devops_account_id,
            pipeline_key_arn=pipeline_key_arn,
            artifact_bucket=artifact_bucket,
            target_bucket=target_bucket,
            env=deploy_environment,
        )

if repo:
    RepoStack(
        app,
        "repo-" + repo,
        repo_name=repo,
        env=deploy_environment,
    )
else:
    RepoStack(
        app,
        "repo-dummy",
        repo_name="dummy",
        env=deploy_environment,
    )

if all([target_bucket, repo, branch, cross_account_role]):
    S3PipelineStack(
        app,
        "s3-pipeline-" + repo + "-" + branch,
        repo_name=repo,
        repo_branch=branch,
        build_env=build_env,
        target_bucket=target_bucket,
        approvers=approvers,
        cross_account_role_arn=cross_account_role,
        env=deploy_environment,
        github_secret_arn=github_secret_arn,
        repo_owner=repo_owner,
    )

if all([repo, branch, cross_account_role, deployment_role_arn]):
    CloudformationPipelineStack(
        app,
        "cf-pipeline-" + repo + "-" + branch,
        repo_name=repo,
        repo_branch=branch,
        github_secret_arn=github_secret_arn,
        build_env=build_env,
        stack_name=stack_name,
        repo_owner=repo_owner,
        cross_account_role_arn=cross_account_role,
        deployment_role_arn=deployment_role_arn,
        approvers=approvers,
        env=deploy_environment,
    )

if all([parameter_list, repo, branch]):
    ParameterStack(
        app,
        "parameter-stack-" + repo + "-" + branch,
        repo_name=repo,
        repo_branch=branch,
        parameter_list=parameter_list,
        env=deploy_environment,
    )

if build_env:
    Aspects.of(app).add(cdk.Tag("environment-type", build_env))
if repo:
    Aspects.of(app).add(cdk.Tag("repository", repo))
if branch:
    Aspects.of(app).add(cdk.Tag("branch", branch))

# more tags here

app.synth()
