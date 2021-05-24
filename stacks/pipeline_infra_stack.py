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
)


class PipelineInfraStack(cdk.Stack):
    def __init__(
        self,
        scope: cdk.Construct,
        id: str,
        target_account_id: str,
        repo_name: str,
        repo_branch: str,
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        pipeline_key = kms.Key(
            self,
            "PipelineKey",
            description="CICD CMK shared with " + target_account_id,
            alias="cicd-" + repo_name + "-" + repo_branch + "-" + target_account_id,
            enable_key_rotation=False,
            trust_account_identities=True,
        )

        # the target account needs to be able to use the key to decrypt the artifacts
        pipeline_key.grant_decrypt(iam.AccountPrincipal(account_id=target_account_id))

        cdk.CfnOutput(
            self,
            "PipelineKeyArnOutput",
            value=pipeline_key.key_arn,
            export_name=self.stack_name + ":PipelineKeyArn",
        )
