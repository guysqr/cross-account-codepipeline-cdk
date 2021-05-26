from aws_cdk import (
    core,
    aws_codebuild as codebuild,
    aws_codecommit as codecommit,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_iam as iam,
)


class RepoStack(core.Stack):
    def __init__(
        self, scope: core.Construct, id: str, repo_name: str, **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        if repo_name == None:
            raise ValueError("Need repo name to be provided as `-c repo=<repo name>`")

        repo_desc = "Repo created by " + self.stack_name + "."
        if repo_name.endswith("-mirror"):
            repo_desc = (
                repo_desc
                + " NOTE: THIS IS A MIRROR REPO AND SHOULD NOT BE CHECKED OUT OR COMMITTED TO BY DEVELOPERS. It is here to acts as a source stage for CodePipeline only."
            )

        # create the code repo we'll be mirroring to for the source stage
        code_repo = codecommit.Repository(
            self,
            "Repository",
            repository_name=repo_name,
            description=repo_desc,
        )

        # create the Gitlab user and attach least privileges inline policy
        gitlab_user = iam.User(
            self, "GitlabIamUser", user_name=repo_name + "-gitlab-user"
        )
        mirror_policy_statement = iam.PolicyStatement(
            actions=["codecommit:GitPull", "codecommit:GitPush"],
            effect=iam.Effect.ALLOW,
            resources=[code_repo.repository_arn],
        )

        custom_policy_document = iam.PolicyDocument(
            statements=[mirror_policy_statement]
        )

        gitlab_policy = iam.Policy(
            self, "GitlabMirrorPolicy", document=custom_policy_document
        )
        gitlab_user.attach_inline_policy(gitlab_policy)

        core.CfnOutput(
            self,
            "CodeCommitRepoCloneUrlHttp",
            value=code_repo.repository_clone_url_http,
        )
        core.CfnOutput(self, "IamUserForGitlab", value=gitlab_user.user_name)
