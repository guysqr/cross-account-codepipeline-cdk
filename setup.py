import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="Pipeline-Creator",
    version="0.0.1",
    description="A CDK Python app to build AWS CodePipelines",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="guy.morton@versent.com.au",
    package_dir={"": "stacks"},
    packages=setuptools.find_packages(where="stacks"),
    install_requires=[
        "aws-cdk.core",
        "aws_cdk.aws_apigateway",
        "aws_cdk.aws_codedeploy",
        "aws_cdk.aws_lambda",
        "aws_cdk.aws_codebuild",
        "aws_cdk.aws_codepipeline",
        "aws_cdk.aws_codecommit",
        "aws_cdk.aws_codepipeline_actions",
        "aws_cdk.aws_s3",
        "aws_cdk.aws_iam",
        "aws_cdk.aws_logs",
        "aws_cdk.pipelines",
    ],
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
)
