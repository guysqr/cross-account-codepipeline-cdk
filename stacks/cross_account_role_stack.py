import constructs
import aws_cdk as cdk
from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
)

####################################################################################################
# This stack needs to be created in the target account the pipeline will deploy to
####################################################################################################


class CrossAccountRoleStack(cdk.Stack):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        devops_account_id: str,
        pipeline_key_arn: str,
        target_bucket: str = None,
        artifact_bucket: str = None,
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        if devops_account_id == None:
            raise ValueError(
                "The AWS account ID to be trusted needs to be provided as `-c devops_account_id=<account-id>`"
            )

        if pipeline_key_arn == None:
            raise ValueError(
                "The KMS key from the devops account needs to be provided as `-c pipeline_key_arn=<key-arn>`"
            )

        # if no artifact bucket is provided, allow access to all buckets
        # otherwise specify only the artifact bucket
        pipeline_s3_resources = "arn:aws:s3:::*"
        if artifact_bucket:
            art_bucket = s3.Bucket.from_bucket_name(
                self, "ArtBucketByAtt", bucket_name=artifact_bucket
            )
            pipeline_s3_resources = art_bucket.arn_for_objects("*")

        # Start with an empty policy statements list
        policy_statements = []
        deploy_policy_statements = []

        ####################################################################################################
        # These policies are required in both deployment types, to read artifacts and use the key
        # see https://aws.amazon.com/premiumsupport/knowledge-center/codepipeline-deploy-cloudformation/
        ####################################################################################################

        policy_statements.append(
            iam.PolicyStatement(
                actions=["cloudformation:*", "iam:PassRole"],
                effect=iam.Effect.ALLOW,
                resources=["*"],
            )
        )

        policy_statements.append(
            iam.PolicyStatement(
                actions=["s3:Get*", "s3:Put*", "s3:ListBucket"],
                effect=iam.Effect.ALLOW,
                resources=[pipeline_s3_resources],
            )
        )

        policy_statements.append(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                ],
                effect=iam.Effect.ALLOW,
                resources=[pipeline_key_arn],
            )
        )
        # allow this role to get items from the parameter store
        policy_statements.append(
            iam.PolicyStatement(
                actions=["ssm:GetParameters"],
                effect=iam.Effect.ALLOW,
                resources=["*"],
            )
        )

        ####################################################################################################
        # If you pass a target_bucket value, then we build a cross account role for S3Deploy
        ####################################################################################################
        if target_bucket:
            dep_bucket = s3.Bucket.from_bucket_name(
                self,
                "BucketByAtt",
                bucket_name=target_bucket,
            )
            # Add the S3 deploy action to put objects in the deployment bucket
            policy_statements.append(
                iam.PolicyStatement(
                    actions=["s3:DeleteObject*", "s3:PutObject*", "s3:Abort*"],
                    effect=iam.Effect.ALLOW,
                    resources=[dep_bucket.bucket_arn, dep_bucket.arn_for_objects("*")],
                )
            )

        ####################################################################################################
        # Otherwise, we build a cross account role for Cloudformation Deploy
        #
        # Note you may need to change permissions granted in this role if you are deploying more than
        # Lambda & API Gateway
        ####################################################################################################
        else:
            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=[
                        "cloudformation:CreateChangeSet",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=[
                        "arn:aws:cloudformation:*:aws:transform/Serverless-2016-10-31"
                    ],
                )
            )

            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=[
                        "cloudformation:CreateChangeSet",
                        "cloudformation:DeleteStack",
                        "cloudformation:DescribeChangeSet",
                        "cloudformation:DescribeStackEvents",
                        "cloudformation:DescribeStacks",
                        "cloudformation:ExecuteChangeSet",
                        "cloudformation:GetTemplateSummary",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=["arn:aws:cloudformation:*:" + self.account + ":stack/*"],
                )
            )
            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=["wafv2:*"],
                    effect=iam.Effect.ALLOW,
                    resources=[
                        "arn:aws:wafv2:" + self.region + ":" + self.account + ":*"
                    ],
                )
            )
            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=["apigateway:*"],
                    effect=iam.Effect.ALLOW,
                    resources=["arn:aws:apigateway:" + self.region + "::*"],
                )
            )
            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=["route53:*"],
                    effect=iam.Effect.ALLOW,
                    resources=["arn:aws:route53:::*"],
                )
            )
            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=["events:*"],
                    effect=iam.Effect.ALLOW,
                    resources=[
                        "arn:aws:events:" + self.region + ":" + self.account + ":rule/*"
                    ],
                )
            )

            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=[
                        "iam:AttachRolePolicy",
                        "iam:DeleteRole",
                        "iam:DetachRolePolicy",
                        "iam:GetRole",
                        "iam:PassRole",
                        "iam:TagRole",
                        "iam:CreateRole",
                        "iam:DeleteRolePolicy",
                        "iam:PutRolePolicy",
                        "iam:GetRolePolicy",
                        "iam:CreateServiceLinkedRole",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=["arn:aws:iam::" + self.account + ":role/*"],
                )
            )
            lambda_resource_prefix = "arn:aws:lambda:"
            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=[
                        "lambda:AddPermission",
                        "lambda:CreateFunction",
                        "lambda:DeleteFunction",
                        "lambda:GetFunction",
                        "lambda:GetFunctionConfiguration",
                        "lambda:ListTags",
                        "lambda:RemovePermission",
                        "lambda:TagResource",
                        "lambda:UntagResource",
                        "lambda:UpdateFunctionCode",
                        "lambda:UpdateFunctionConfiguration",
                        "lambda:PublishLayerVersion",
                        "lambda:GetLayerVersion",
                        "lambda:EnableReplication*",
                        "lambda:ListVersionsByFunction",
                        "lambda:PublishVersion",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=[
                        lambda_resource_prefix
                        + self.region
                        + ":"
                        + self.account
                        + ":*:*",
                        lambda_resource_prefix
                        + self.region
                        + ":"
                        + self.account
                        + ":layer:*:*",
                        lambda_resource_prefix
                        + self.region
                        + ":"
                        + self.account
                        + ":layer:*",
                        lambda_resource_prefix
                        + "ap-southeast-2:580247275435:layer:LambdaInsightsExtension:14",
                    ],
                )
            )

            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=[
                        "secretsmanager:*",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=["*"],
                )
            )

            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=["cloudfront:*", "acm:*"],
                    effect=iam.Effect.ALLOW,
                    resources=["*"],
                )
            )
            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:PutRetentionPolicy",
                        "logs:DeleteLogGroup",
                        "logs:DescribeLogGroups",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=["*"],
                )
            )

            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=[
                        "ec2:DescribeSecurityGroups",
                        "ec2:CreateSecurityGroup",
                        "ec2:DeleteSecurityGroup",
                        "ec2:AuthorizeSecurityGroupIngress",
                        "ec2:CreateVpcEndpoint",
                        "ec2:ModifyVpcEndpoint",
                        "ec2:DescribeVpcEndpoints",
                        "ec2:DeleteVpcEndpoints",
                        "ec2:DescribeSubnets",
                        "ec2:DescribeVpcs",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:CreateTags",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=["*"],
                )
            )

            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=["dynamodb:*"],
                    effect=iam.Effect.ALLOW,
                    resources=[
                        "arn:aws:dynamodb:"
                        + self.region
                        + ":"
                        + self.account
                        + ":table/*"
                    ],
                )
            )

            deploy_policy_statements.append(
                iam.PolicyStatement(
                    actions=["states:*"],
                    effect=iam.Effect.ALLOW,
                    resources=[
                        "arn:aws:states:" + self.region + ":" + self.account + ":*"
                    ],
                )
            )

        # allow the cross account role to be assumed by the devops account
        cross_account_role = iam.Role(
            self,
            "CrossAccountRole",
            assumed_by=iam.AccountPrincipal(devops_account_id),
            inline_policies=[
                iam.PolicyDocument(statements=policy_statements),
            ],
        )

        if target_bucket == None:
            # merge the basic permissions with the extra cloudformation permissions
            policy_statements.extend(deploy_policy_statements)
            # create the deployment role, and allow it to be assumed by the Cloudformation service principal
            deployment_role = iam.Role(
                self,
                "DeploymentRole",
                assumed_by=iam.ServicePrincipal(service="cloudformation.amazonaws.com"),
                inline_policies=[
                    iam.PolicyDocument(statements=policy_statements),
                ],
            )
            cdk.CfnOutput(
                self,
                "DeploymentRoleArnOutput",
                description="This role is for CloudFormation deployments and is configured in the deployment_role property of the CloudFormationCreateReplaceChangeSetAction action",
                value=deployment_role.role_arn,
            )

        cdk.CfnOutput(
            self,
            "CrossAccountRoleArnOutput",
            description="This role is assumed by the pipeline to operate on the target account.",
            value=cross_account_role.role_arn,
        )
