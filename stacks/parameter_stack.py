from aws_cdk import (
    core as cdk,
    aws_ssm as ssm,
)


class ParameterStack(cdk.Stack):
    def __init__(
        self,
        scope: cdk.Construct,
        id: str,
        parameter_list: str,
        repo_name: str,
        repo_branch: str,
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        params_to_create = parameter_list.split(",")

        if not params_to_create:
            raise ValueError(
                "A parameter list needs to be provided as `-c parameter_list=<param1,param2>`"
            )

        if repo_name == None:
            raise ValueError(
                "The repo name needs to be provided as `-c repo=<repo-name>`"
            )

        if repo_branch == None:
            raise ValueError(
                "The branch this pipeline will deploy must be provided as `-c branch=<branch-name>`"
            )

        for param in params_to_create:
            split_params = param.split(":")
            name = split_params[0]
            try:
                value = split_params[1]
            except IndexError:
                value = "placeholder"
            pipeline_name = "pipeline-" + "-".join((repo_name, repo_branch))
            param_name = "/" + "/".join((pipeline_name, name))

            ssm.StringParameter(
                self,
                "ParameterFor" + name.capitalize(),
                description="Param for " + name,
                parameter_name=param_name,
                string_value=value,
            )

            cdk.CfnOutput(
                self,
                "ParameterFor" + name.capitalize() + "Output",
                value=param_name,
                export_name=self.stack_name + ":" + pipeline_name + "-" + name,
            )


# cdk deploy  parameter-stack-reponame-branch -c repo=reponame -c branch=branch -c parameter_list=foo:value,bar:othervalue --profile contactmap
