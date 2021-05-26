from aws_cdk import (
    core as cdk,
    aws_codebuild as codebuild,
    aws_codecommit as codecommit,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_s3 as s3,
    aws_iam as iam,
    aws_kms as kms,
)


class S3PipelineStack(cdk.Stack):
    def __init__(
        self,
        scope: cdk.Construct,
        id: str,
        repo_name: str,
        repo_branch: str,
        build_env: str,
        target_bucket: str,
        approvers: str,
        cross_account_role_arn: str,
        github_oauth_token: str,
        repo_owner: str,
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        if target_bucket == None:
            raise ValueError(
                "The target bucket name needs to be provided as `-c target_bucket=<bucket-name>`"
            )

        if repo_name == None:
            raise ValueError(
                "The repo name needs to be provided as `-c repo=<repo-name>`"
            )

        if repo_branch == None:
            raise ValueError(
                "The branch this pipeline will deploy must be provided as `-c branch=<branch-name>`"
            )

        if cross_account_role_arn == None:
            raise ValueError(
                "The cross account role this pipeline will assume must be provided as `-c cross_account_role_arn=<cross_account_role_arn>`"
            )

        deploy_bucket = s3.Bucket.from_bucket_name(
            self, "BucketByAtt", bucket_name=target_bucket
        )

        # get the key ARN from the create-pipeline-infra stack
        pipeline_key = kms.Key.from_key_arn(
            self,
            "DeployKey",
            key_arn=cdk.Fn.import_value(
                self.stack_name.replace("s3-create-pipeline", "create-pipeline-infra")
                + ":PipelineKeyArn"
            ),
        )
        # Create the artifacts bucket we'll use
        artifacts_bucket = s3.Bucket(
            self,
            "PipelineArtifactsBucket",
            bucket_key_enabled=True,
            encryption_key=pipeline_key,
            encryption=s3.BucketEncryption.KMS,
        )

        # create the pipeline and tell it to use the artifacts bucket
        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline-" + repo_name + "-" + repo_branch,
            artifact_bucket=artifacts_bucket,
            pipeline_name="pipeline-" + repo_name + "-" + repo_branch,
            cross_account_keys=True,
        )

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
        build_output = codepipeline.Artifact()
        build_project = codebuild.PipelineProject(
            self,
            "Build",
            build_spec=codebuild.BuildSpec.from_source_filename("buildspec.yml"),
            environment={"build_image": codebuild.LinuxBuildImage.AMAZON_LINUX_2_3},
            environment_variables={
                "PACKAGE_BUCKET": codebuild.BuildEnvironmentVariable(
                    value=artifacts_bucket.bucket_name
                ),
                "ENVIRONMENT": codebuild.BuildEnvironmentVariable(value=build_env),
            },
        )
        # add permission to get parameter store values
        ssm_access = iam.PolicyStatement(
            actions=["ssm:GetParameters"], effect=iam.Effect.ALLOW, resources=["*"]
        )
        build_project.add_to_role_policy(ssm_access)

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
        if approvers:
            pipeline.add_stage(
                stage_name="ManualApproval",
                actions=[
                    codepipeline_actions.ManualApprovalAction(
                        notify_emails=approvers.split(","),
                        action_name="AwaitApproval",
                    )
                ],
            )

        ##########################################################
        # S3 DEPLOYMENT
        ##########################################################

        cross_account_role = iam.Role.from_role_arn(
            self,
            "CrossAccountRole",
            role_arn=cross_account_role_arn,
        )

        pipeline.add_stage(
            stage_name="Deploy",
            actions=[
                codepipeline_actions.S3DeployAction(
                    bucket=deploy_bucket,
                    input=build_output,
                    action_name="S3Deploy",
                    role=cross_account_role,
                ),
            ],
        )

        cdk.CfnOutput(self, "ArtifactBucketArn", value=artifacts_bucket.bucket_arn)
