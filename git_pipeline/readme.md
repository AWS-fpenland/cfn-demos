# CloudFormation Git Pipeline Deployment

A Python script for deploying AWS CloudFormation templates from Git repositories using AWS CodePipeline. This tool automates the creation of CI/CD pipelines that automatically deploy your infrastructure as code whenever changes are pushed to your repository.

## Features

- **Git Integration**: Deploy CloudFormation templates directly from GitHub, Bitbucket, or other Git providers via AWS CodeStar Connections
- **Deployment Configuration Files**: Support for deployment configuration files that specify template path, parameters, and tags
- **Least Privilege IAM Roles**: Analyzes CloudFormation templates to create roles with only the required permissions
- **Region Selection**: Deploy to any AWS region regardless of your AWS profile's default region
- **Parameter Support**: Use parameter files stored in your Git repository
- **CloudFormation Capabilities**: Support for IAM resources and other CloudFormation capabilities
- **Pipeline Automation**: Automatically creates the necessary IAM roles, S3 buckets, and pipeline structure

## Prerequisites

- Python 3.6+
- AWS CLI configured with appropriate credentials
- Boto3 (AWS SDK for Python)
- AWS account with permissions to create:
  - IAM roles and policies
  - S3 buckets
  - CodePipeline pipelines
  - CloudFormation stacks
- An AWS CodeStar Connection to your Git provider (GitHub, Bitbucket, etc.)

## Installation

1. Clone or download this script to your local machine.

2. Install required Python packages:

```bash
pip install boto3 pyyaml
```

3. Ensure your AWS CLI is configured with a profile that has appropriate permissions:

```bash
aws configure --profile your-profile-name
```

## Usage

Run the script with your AWS profile name:

```bash
python pipeline-deploy.py your-profile-name
```

Follow the interactive prompts to:

1. Select the AWS region for deployment
2. Choose an existing CodeStar connection to your Git provider
3. Enter repository details (repository name, branch)
4. Specify the CloudFormation template path in your repository
5. Optionally select a deployment configuration file
6. Create or select IAM roles for pipeline execution and CloudFormation deployment
7. Specify CloudFormation capabilities if required

## Deployment Configuration Files

You can use a deployment configuration file in your repository to specify how your CloudFormation template should be deployed. Example format:

```yaml
template-file-path: path/to/your/template.yaml
Parameters:
  ParameterName1: Value1
  ParameterName2: Value2
tags:
  environment: dev
  project: example
```

## IAM Role Options

The script offers two approaches for creating CloudFormation execution roles:

1. **Admin Permissions**: Creates a role with full administrator access (simpler but less secure)
2. **Least Privilege**: Analyzes your template to determine the minimum required permissions

For the least privilege option, you can either:
- Provide a local copy of your template for analysis
- Paste the template content directly

## Example Workflow

1. Set up an AWS CodeStar connection to your Git provider
2. Run the script: `python pipeline-deploy.py my-aws-profile`
3. Select your region and CodeStar connection
4. Enter repository details: `username/my-infra-repo` and branch `main`
5. Specify template path: `templates/network.yaml`
6. Optionally provide a deployment file: `config/dev-deployment.yaml`
7. Create a least-privilege IAM role by analyzing your template
8. Review the deployment details and confirm

The script will create:
- An S3 bucket for pipeline artifacts
- Required IAM roles with appropriate permissions
- A CodePipeline pipeline that deploys your template whenever changes are pushed

## Troubleshooting

- **Role Permission Issues**: If deployment fails due to insufficient permissions, check the CloudFormation service role permissions
- **S3 Bucket Naming**: If bucket creation fails, the script will show the error and exit
- **Template Validation**: Pre-validate your CloudFormation templates with `aws cloudformation validate-template`
- **Pipeline Failures**: Check the pipeline execution details in the AWS Console for specific error messages

## Security Considerations

- The default IAM role analysis creates roles with broad permissions for each service
- For production use, consider further restricting IAM permissions by resource ARNs
- Review the generated IAM policies before deployment to production environments

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
