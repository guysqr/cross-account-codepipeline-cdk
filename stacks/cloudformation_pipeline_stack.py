from aws_cdk import (
    core as cdk,
    aws_codebuild as codebuild,
    aws_codecommit as codecommit,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_iam as iam,
    aws_kms as kms,
    aws_logs as logs,
)


class CloudformationPipelineStack(cdk.Stack):
    def __init__(
        self,
        scope: cdk.Construct,
        id: str,
        repo_name: str,
        repo_branch: str,
        build_env: str,
        cross_account_role_arn: str,
        deployment_role_arn: str,
        github_oauth_token: str,
        stack_name: str,
        repo_owner: str,
        approvers: str,
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        if repo_name == None:
            raise ValueError(
                "The repo name needs to be provided as `-c repo=<repo-name>`"
            )
            exit()

        if repo_branch == None:
            raise ValueError(
                "The branch this pipeline will deploy must be provided as `-c branch=<branch-name>`"
            )
            exit()

        if cross_account_role_arn == None:
            raise ValueError(
                "The cross account role this pipeline will assume must be provided as `-c cross_account_role_arn=<cross_account_role_arn>`"
            )
            exit()

        pipeline_key = kms.Key.from_key_arn(
            self,
            "DeployKey",
            key_arn=cdk.Fn.import_value(
                self.stack_name.replace("cf-create-pipeline", "create-pipeline-infra")
                + ":PipelineKeyArn"
            ),
        )

        # Create the artifacts bucket we'll use
        artifacts_bucket = s3.Bucket(
            self,
            "PipelineArtifactsBucket",
            encryption_key=pipeline_key,
            encryption=s3.BucketEncryption.KMS,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        cross_account_role = iam.Role.from_role_arn(
            self,
            "CrossAccountRole",
            role_arn=cross_account_role_arn,
        )

        # derive the target account id from the supplied role
        target_account_id = cross_account_role.principal_account

        deployment_role = iam.Role.from_role_arn(
            self,
            "DeploymentRole",
            role_arn=deployment_role_arn,
        )

        artifacts_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:Get*", "s3:Put*"],
                resources=[artifacts_bucket.arn_for_objects("*")],
                principals=[iam.AccountPrincipal(account_id=target_account_id)],
            )
        )

        artifacts_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:List*"],
                resources=[
                    artifacts_bucket.bucket_arn,
                    artifacts_bucket.arn_for_objects("*"),
                ],
                principals=[iam.AccountPrincipal(account_id=target_account_id)],
            )
        )

        # create the pipeline and tell it to use the artifacts bucket
        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline-" + repo_name + "-" + repo_branch,
            artifact_bucket=artifacts_bucket,
            pipeline_name="pipeline-" + repo_name + "-" + repo_branch,
            cross_account_keys=True,
            restart_execution_on_update=True,
        )

        # allow the pipeline to assume any role in the target account
        cross_account_access = iam.PolicyStatement(
            actions=["sts:AssumeRole"],
            effect=iam.Effect.ALLOW,
            resources=["arn:aws:iam::" + target_account_id + ":role/*"],
        )

        pipeline.add_to_role_policy(cross_account_access)

        # create the source stage, which grabs the code from the repo and outputs it as an artifact
        source_output = codepipeline.Artifact()

        if github_oauth_token and repo_owner:
            pipeline.add_stage(
                stage_name="Source",
                actions=[
                    codepipeline_actions.GitHubSourceAction(
                        oauth_token=github_oauth_token,
                        owner=repo_owner,
                        action_name="GetGitHubSource",
                        repo=repo_name,
                        branch=repo_branch,
                        trigger=codepipeline_actions.GitHubTrigger.WEBHOOK,
                        output=source_output,
                    )
                ],
            )
        else:
            pipeline.add_stage(
                stage_name="Source",
                actions=[
                    codepipeline_actions.CodeCommitSourceAction(
                        action_name="GetSource",
                        repository=codecommit.Repository.from_repository_name(
                            self, "Repo", repo_name
                        ),
                        output=source_output,
                        branch=repo_branch,
                    )
                ],
            )

        # create the build stage which takes the source artifact and outputs the built artifact
        # to allow use of docker, need privileged flag to be set to True
        build_output = codepipeline.Artifact()
        build_project = codebuild.PipelineProject(
            self,
            "Build",
            build_spec=codebuild.BuildSpec.from_source_filename("buildspec.yml"),
            logging=codebuild.LoggingOptions(
                cloud_watch=codebuild.CloudWatchLoggingOptions(
                    enabled=True,
                    log_group=logs.LogGroup(
                        self,
                        "PipelineLogs",
                    ),
                )
            ),
            environment={
                "build_image": codebuild.LinuxBuildImage.AMAZON_LINUX_2_3,
                "privileged": True,
            },
            environment_variables={
                "PACKAGE_BUCKET": codebuild.BuildEnvironmentVariable(
                    value=artifacts_bucket.bucket_name
                ),
                "ENVIRONMENT": codebuild.BuildEnvironmentVariable(value=build_env),
            },
        )
        pipeline.add_stage(
            stage_name="Build",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="Build",
                    project=build_project,
                    input=source_output,
                    outputs=[build_output],
                )
            ],
        )

        # create the deployment stages that take the built artifact and create a change set then deploy it

        ##########################################################
        # CLOUDFORMATION DEPLOYMENT
        ##########################################################

        # let's map some new ones to old ones so we don't get into trouble...
        stack_name = stack_name or repo_name + "-" + repo_branch + "-stack"

        # only set Environment is build_env is set
        if build_env:
            parameters = {"Environment": build_env}
        else:
            parameters = None

        pipeline.add_stage(
            stage_name="CreateChangeSet",
            actions=[
                codepipeline_actions.CloudFormationCreateReplaceChangeSetAction(
                    change_set_name=stack_name + "-changeset",
                    action_name="CreateChangeSet",
                    template_path=build_output.at_path("packaged.yaml"),
                    stack_name=stack_name,
                    cfn_capabilities=[
                        cdk.CfnCapabilities.NAMED_IAM,
                        cdk.CfnCapabilities.AUTO_EXPAND,
                    ],
                    admin_permissions=True,
                    parameter_overrides=parameters,
                    role=cross_account_role,
                    deployment_role=deployment_role,
                ),
            ],
        )

        if approvers:
            pipeline.add_stage(
                stage_name="ApproveChangeSet",
                actions=[
                    codepipeline_actions.ManualApprovalAction(
                        notify_emails=approvers.split(","),
                        action_name="AwaitApproval",
                    )
                ],
            )

        pipeline.add_stage(
            stage_name="DeployChangeSet",
            actions=[
                codepipeline_actions.CloudFormationExecuteChangeSetAction(
                    change_set_name=stack_name + "-changeset",
                    stack_name=stack_name,
                    action_name="Deploy",
                    role=cross_account_role,
                ),
            ],
        )

        cdk.CfnOutput(self, "ArtifactBucketArn", value=artifacts_bucket.bucket_arn)
        cdk.CfnOutput(self, "ArtifactBucketName", value=artifacts_bucket.bucket_name)
