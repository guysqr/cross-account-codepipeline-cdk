import constructs
import aws_cdk as cdk
from aws_cdk import (
    aws_route53 as route53,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as cloudfront_origins,
    aws_s3 as s3,
    aws_certificatemanager as acm,
    aws_wafv2 as wafv2,
    aws_secretsmanager as secretsmanager,
    aws_lambda,
)

# this is needed to fix a bug in CDK

import jsii


@jsii.implements(wafv2.CfnRuleGroup.IPSetReferenceStatementProperty)
class IPSetReferenceStatement:
    @property
    def arn(self):
        return self._arn

    @arn.setter
    def arn(self, value):
        self._arn = value


# stack begins


class DemoCloudfrontStack(cdk.Stack):
    def __init__(
        self, scope: constructs.Construct, construct_id: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ##############################################################################
        # Create the source bucket
        ##############################################################################

        s3_bucket_source = s3.Bucket(
            self,
            "AppDeploymentBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            server_access_logs_bucket=s3.Bucket(self, "AppLogsBucket"),
        )

        ##############################################################################
        # Create the OAI
        ##############################################################################

        oai = cloudfront.OriginAccessIdentity(
            self, "OAI", comment="Connects CF with S3"
        )
        s3_bucket_source.grant_read(oai)

        ##############################################################################
        # Create the Distribution
        ##############################################################################

        distribution = cloudfront.Distribution(
            self,
            "NewCloudFrontDistribution",
            geo_restriction=cloudfront.GeoRestriction.allowlist("AU", "NZ"),
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2019,
            enable_logging=True,
            default_behavior=cloudfront.BehaviorOptions(
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                origin=cloudfront_origins.S3Origin(
                    bucket=s3_bucket_source,
                    origin_access_identity=oai,
                    origin_path="/",
                ),
                compress=True,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(amount=0),
                    response_http_status=200,
                )
            ],
        )

        cdk.CfnOutput(
            self,
            "CloudFrontDistributionDomain",
            value=distribution.domain_name,
            description="The domain of the CloudFront distribution created, should be used for CNAME alias mapping",
            export_name=self.stack_name + "-CloudFrontDistributionDomain",
        )
        cdk.CfnOutput(
            self,
            "BucketName",
            value=s3_bucket_source.bucket_name,
            description="The bucket used for static content behind the CloudFront distribution",
            export_name=self.stack_name + "-Bucket",
        )
