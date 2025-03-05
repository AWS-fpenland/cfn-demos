#!/usr/bin/env python3

import boto3
import json
import sys
import time
import os
import yaml
import uuid
from botocore.exceptions import ClientError

# Define a mapping of CloudFormation resource types to IAM permissions
# This is a starting point and should be expanded for production use
CFN_RESOURCE_TO_IAM_MAPPING = {
    'AWS::S3::Bucket': [
        's3:CreateBucket',
        's3:DeleteBucket',
        's3:PutBucketPolicy',
        's3:DeleteBucketPolicy',
        's3:PutEncryptionConfiguration',
        's3:GetEncryptionConfiguration',
        's3:ListBucket',
        's3:GetObject',
        's3:PutObject',
        's3:DeleteObject'
    ],
    'AWS::Lambda::Function': [
        'lambda:CreateFunction',
        'lambda:DeleteFunction',
        'lambda:GetFunction',
        'lambda:GetFunctionConfiguration',
        'lambda:UpdateFunctionCode',
        'lambda:UpdateFunctionConfiguration',
        'lambda:AddPermission',
        'lambda:RemovePermission'
    ],
    'AWS::IAM::Role': [
        'iam:CreateRole',
        'iam:DeleteRole',
        'iam:GetRole',
        'iam:PassRole',
        'iam:PutRolePolicy',
        'iam:DeleteRolePolicy',
        'iam:AttachRolePolicy',
        'iam:DetachRolePolicy',
        'iam:UpdateRole',
        'iam:UpdateAssumeRolePolicy'
    ],
    'AWS::IAM::ManagedPolicy': [
        'iam:CreatePolicy',
        'iam:DeletePolicy',
        'iam:GetPolicy',
        'iam:GetPolicyVersion',
        'iam:CreatePolicyVersion',
        'iam:DeletePolicyVersion',
        'iam:SetDefaultPolicyVersion'
    ],
    'AWS::DynamoDB::Table': [
        'dynamodb:CreateTable',
        'dynamodb:DeleteTable',
        'dynamodb:DescribeTable',
        'dynamodb:UpdateTable'
    ],
    'AWS::EC2::Instance': [
        'ec2:RunInstances',
        'ec2:TerminateInstances',
        'ec2:DescribeInstances',
        'ec2:CreateTags'
    ],
    'AWS::SNS::Topic': [
        'sns:CreateTopic',
        'sns:DeleteTopic',
        'sns:GetTopicAttributes',
        'sns:SetTopicAttributes'
    ],
    'AWS::SQS::Queue': [
        'sqs:CreateQueue',
        'sqs:DeleteQueue',
        'sqs:GetQueueAttributes',
        'sqs:SetQueueAttributes'
    ],
    'AWS::ACMPCA::CertificateAuthority': [
        'acm-pca:CreateCertificateAuthority',
        'acm-pca:DeleteCertificateAuthority',
        'acm-pca:DescribeCertificateAuthority',
        'acm-pca:UpdateCertificateAuthority',
        'acm-pca:GetCertificateAuthorityCertificate',
        'acm-pca:GetCertificateAuthorityCsr',
        'acm-pca:TagResource'
    ],
    'AWS::ACMPCA::Certificate': [
        'acm-pca:IssueCertificate',
        'acm-pca:GetCertificate',
        'acm-pca:RevokeCertificate'
    ],
    'AWS::ACMPCA::CertificateAuthorityActivation': [
        'acm-pca:ImportCertificateAuthorityCertificate',
        'acm-pca:UpdateCertificateAuthority'
    ],
    'AWS::RolesAnywhere::TrustAnchor': [
        'rolesanywhere:CreateTrustAnchor',
        'rolesanywhere:DeleteTrustAnchor',
        'rolesanywhere:GetTrustAnchor',
        'rolesanywhere:UpdateTrustAnchor',
        'rolesanywhere:TagResource'
    ],
    'AWS::RolesAnywhere::Profile': [
        'rolesanywhere:CreateProfile',
        'rolesanywhere:DeleteProfile',
        'rolesanywhere:GetProfile',
        'rolesanywhere:UpdateProfile',
        'rolesanywhere:TagResource'
    ],
    # Add more mappings as needed
}

# Always needed CloudFormation permissions
CLOUDFORMATION_PERMISSIONS = [
    'cloudformation:CreateStack',
    'cloudformation:DeleteStack',
    'cloudformation:DescribeStacks',
    'cloudformation:UpdateStack',
    'cloudformation:ValidateTemplate',
    'cloudformation:GetTemplate',
    'cloudformation:GetTemplateSummary'
]

# Pipeline specific permissions
PIPELINE_PERMISSIONS = [
    # CodePipeline permissions
    'codepipeline:CreatePipeline',
    'codepipeline:DeletePipeline',
    'codepipeline:GetPipeline',
    'codepipeline:GetPipelineState',
    'codepipeline:StartPipelineExecution',
    'codepipeline:TagResource',
    # CodeStar Connections permissions
    'codestar-connections:UseConnection',
    # S3 permissions for artifact store
    's3:CreateBucket',
    's3:DeleteBucket',
    's3:GetObject',
    's3:PutObject',
    's3:DeleteObject'
]


def analyze_template_content_and_create_role(template_content, role_name, iam_client, account_id):
    """
    Analyzes CloudFormation template content and creates a role with necessary permissions.
    
    Args:
        template_content (str): The CloudFormation template content (JSON or YAML)
        role_name (str): Name for the new IAM role
        iam_client: Boto3 IAM client
        account_id (str): AWS account ID
        
    Returns:
        str: The ARN of the created role, or None if creation failed
    """
    print(f"Analyzing CloudFormation template content")
    
    try:
        # Parse the template (could be either JSON or YAML)
        try:
            template = json.loads(template_content)
        except json.JSONDecodeError:
            try:
                template = yaml.safe_load(template_content)
            except yaml.YAMLError as e:
                print(f"Error parsing template content: {e}")
                return None
        
        # Extract resource types
        resources = template.get('Resources', {})
        resource_types = set()
        
        for resource_name, resource_def in resources.items():
            resource_type = resource_def.get('Type')
            if resource_type:
                resource_types.add(resource_type)
        
        if resource_types:
            print(f"Found resource types: {', '.join(resource_types)}")
        else:
            print("No resources found in template.")
            return None
        
        # Map resource types to permissions
        needed_permissions = set(CLOUDFORMATION_PERMISSIONS)  # Start with CF permissions
        needed_permissions.update(PIPELINE_PERMISSIONS)  # Add pipeline permissions
        
        for resource_type in resource_types:
            if resource_type in CFN_RESOURCE_TO_IAM_MAPPING:
                needed_permissions.update(CFN_RESOURCE_TO_IAM_MAPPING[resource_type])
            else:
                print(f"Warning: No permission mapping for resource type: {resource_type}")
        
        print(f"Required permissions: {', '.join(sorted(needed_permissions))}")
        
        # Create the role
        # Trust policy for stack role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": [
                            "cloudformation.amazonaws.com",
                            "codepipeline.amazonaws.com"
                        ]
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        try:
            response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"CloudFormation and CodePipeline execution role with scoped permissions"
            )
            
            # Create policy document with needed permissions
            permission_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": list(needed_permissions),
                        "Resource": "*"  # Note: In production, you'd want to scope this down
                    }
                ]
            }
            
            # Attach the policy
            policy_name = f"{role_name}Policy"
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(permission_policy)
            )
            
            print(f"Created execution role with scoped permissions: {role_name}")
            print(f"Attached policy '{policy_name}' with {len(needed_permissions)} needed permissions")
            
            return response['Role']['Arn']
            
        except ClientError as e:
            print(f"Error creating execution role: {e}")
            return None
            
    except Exception as e:
        print(f"Error analyzing template: {e}")
        return None


def create_pipeline_role(role_name, iam_client, account_id):
    """Creates a role for CodePipeline to deploy CloudFormation stacks"""
    print(f"Creating pipeline service role: {role_name}")
    
    # Trust policy for pipeline role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "codepipeline.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for CodePipeline to deploy CloudFormation stacks"
        )
        
        # Create policy document for pipeline role
        pipeline_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "cloudformation:CreateStack",
                        "cloudformation:DeleteStack",
                        "cloudformation:DescribeStacks",
                        "cloudformation:UpdateStack",
                        "cloudformation:CreateChangeSet",
                        "cloudformation:DeleteChangeSet",
                        "cloudformation:DescribeChangeSet",
                        "cloudformation:ExecuteChangeSet",
                        "cloudformation:SetStackPolicy",
                        "cloudformation:ValidateTemplate"
                    ],
                    "Resource": f"arn:aws:cloudformation:*:{account_id}:stack/*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "iam:PassRole"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringEqualsIfExists": {
                            "iam:PassedToService": [
                                "cloudformation.amazonaws.com",
                                "elasticbeanstalk.amazonaws.com"
                            ]
                        }
                    }
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "codestar-connections:UseConnection"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow", 
                    "Action": [
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:GetBucketVersioning",
                        "s3:PutObject"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        # Create and attach the policy
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}Policy",
            PolicyDocument=json.dumps(pipeline_policy)
        )
        
        # Return the role ARN
        return response['Role']['Arn']
        
    except ClientError as e:
        print(f"Error creating pipeline role: {e}")
        sys.exit(1)


def create_cloudformation_role(role_name, iam_client):
    """Creates the CloudFormation execution role with admin permissions"""
    print(f"Creating CloudFormation execution role with admin permissions: {role_name}")
    
    # Trust policy for CloudFormation role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "cloudformation.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="CloudFormation execution role with administrator access"
        )
        
        # Attach the AdministratorAccess policy
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess"
        )
        
        # Return the role ARN
        return response['Role']['Arn']
        
    except ClientError as e:
        print(f"Error creating CloudFormation role: {e}")
        sys.exit(1)


def create_artifact_bucket(session, region):
    """
    Creates an S3 bucket for CodePipeline artifacts with valid naming conventions
    """
    s3_client = session.client('s3')
    account_id = session.client('sts').get_caller_identity()['Account']
    
    # Generate a bucket name that follows S3 naming conventions:
    # - 3-63 characters
    # - Only lowercase letters, numbers, dots (.), and hyphens (-)
    # - Begin and end with a letter or number
    # - Not formatted as an IP address
    
    # Use lowercase for all elements
    region_lower = region.lower()
    
    # Create a unique suffix limited to ensure we don't exceed 63 characters
    unique_suffix = str(uuid.uuid4())[:8].lower()
    
    # Build a bucket name with prefix + region + account id + unique suffix
    # with account ID shortened if necessary to stay under the 63 char limit
    account_id_short = account_id[-8:] if len(account_id) > 8 else account_id
    
    bucket_name = f"pipeline-{region_lower}-{account_id_short}-{unique_suffix}"
    
    # Ensure the bucket name is not too long (max 63 chars)
    if len(bucket_name) > 63:
        bucket_name = bucket_name[:63]
    
    # Ensure the bucket name doesn't end with a dash or dot
    if bucket_name[-1] in ['-', '.']:
        bucket_name = bucket_name[:-1] + 'a'
    
    try:
        if region == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        print(f"Created artifact bucket: {bucket_name}")
        return bucket_name
    except ClientError as e:
        print(f"Error creating artifact bucket: {e}")
        sys.exit(1)


def select_option(options):
    """Displays a selection menu and returns the selected option"""
    print("Available options:")
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")
    
    while True:
        try:
            choice = int(input("Please select an option (number): "))
            if 1 <= choice <= len(options):
                return options[choice - 1]
            else:
                print("Invalid option. Please try again.")
        except ValueError:
            print("Please enter a number.")


def main():
    # Check if profile argument is provided
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <aws-profile>")
        print("Please provide an AWS CLI profile name")
        sys.exit(1)
    
    aws_profile = sys.argv[1]
    
    # Initialize session with profile
    session = boto3.Session(profile_name=aws_profile)
    default_region = session.region_name
    
    # Ask if user wants to use a custom region
    use_custom_region = input(f"Default region from profile is {default_region}. Do you want to use a different region? (y/n): ").lower()
    if use_custom_region == 'y':
        # List available regions for selection
        ec2_client = session.client('ec2')
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        print("Available regions:")
        selected_region = select_option(regions)
        region = selected_region
        print(f"Using region: {region}")
    else:
        region = default_region
        print(f"Using default region: {region}")
    
    # Re-initialize session with the selected region
    session = boto3.Session(profile_name=aws_profile, region_name=region)
    iam_client = session.client('iam')
    sts_client = session.client('sts')
    cf_client = session.client('cloudformation')
    pipeline_client = session.client('codepipeline')
    codestar_client = session.client('codestar-connections')
    
    # Get account ID
    account_id = sts_client.get_caller_identity()['Account']
    
    # Get connections and format them
    print(f"Fetching CodeStar connections using profile: {aws_profile}...")
    try:
        connections_response = codestar_client.list_connections()
        connections = connections_response.get('Connections', [])
        
        if not connections:
            print("No CodeStar connections found. Please create a connection first.")
            sys.exit(1)
        
        connection_names = [conn['ConnectionName'] for conn in connections]
        connection_arns = [conn['ConnectionArn'] for conn in connections]
        
        # Display connections for selection
        print("Available connections:")
        selected_connection = select_option(connection_names)
        
        # Get the corresponding ARN
        connection_arn = connection_arns[connection_names.index(selected_connection)]
        
        # Get repository details
        repository = input("Enter repository name (e.g., username/repository): ")
        branch = input("Enter branch name (e.g., main): ")
        stack_name = input("Enter stack name: ")
        template_path = input("Enter template path (relative to repository root, e.g., templates/my-template.yaml): ")
        
        # Ask for deployment file
        use_deployment_file = input("Do you want to use a deployment configuration file from the repository? (y/n): ").lower()
        deployment_file_path = None
        if use_deployment_file == 'y':
            deployment_file_path = input("Enter deployment file path (relative to repository root, e.g., deployment-file.yaml): ")
        
        # Ask for parameters file (traditional CloudFormation parameters format) 
        # Only if not using deployment file
        params_file_path = None
        if not deployment_file_path:
            use_params_file = input("Do you want to use a parameters file from the repository? (y/n): ").lower()
            if use_params_file == 'y':
                params_file_path = input("Enter parameters file path (relative to repository root, e.g., params/dev.json): ")
        
        # Create pipeline role
        pipeline_role_name = f"CodePipeline-{stack_name}-{str(uuid.uuid4())[:8]}"
        pipeline_role_arn = create_pipeline_role(pipeline_role_name, iam_client, account_id)
        print(f"Created pipeline role with ARN: {pipeline_role_arn}")
        
        # Handle CloudFormation execution role
        create_cf_role_input = input("Do you want to create a new CloudFormation execution role? (y/n): ").lower()
        cf_role_arn = None
        
        if create_cf_role_input == 'y':
            role_type = input("Create (1) A role with full admin permissions, or (2) A role with minimum required permissions? (1/2): ")
            cf_role_name = f"CloudFormation-{stack_name}-{str(uuid.uuid4())[:8]}"
            
            if role_type == '1':
                # Create role with admin permissions
                cf_role_arn = create_cloudformation_role(cf_role_name, iam_client)
            elif role_type == '2':
                template_source = input("Provide template from (1) Local file path or (2) Paste content? (1/2): ")
                template_content = None
                
                if template_source == '1':
                    local_template_path = input("Enter local path to CloudFormation template for analysis: ")
                    try:
                        with open(local_template_path, 'r') as f:
                            template_content = f.read()
                    except FileNotFoundError:
                        print(f"Template file not found: {local_template_path}")
                
                elif template_source == '2':
                    print("Paste your CloudFormation template content below and press Ctrl+D (Unix) or Ctrl+Z (Windows) when done:")
                    template_lines = []
                    try:
                        while True:
                            line = input()
                            template_lines.append(line)
                    except EOFError:
                        template_content = '\n'.join(template_lines)
                
                else:
                    print("Invalid option selected.")
                
                if template_content:
                    cf_role_arn = analyze_template_content_and_create_role(
                        template_content, cf_role_name, iam_client, account_id
                    )
                
                if not cf_role_arn:
                    create_admin_role = input("Failed to create scoped role. Create a role with admin permissions instead? (y/n): ").lower()
                    if create_admin_role == 'y':
                        cf_role_arn = create_cloudformation_role(cf_role_name, iam_client)
            else:
                print("Invalid option selected.")
                
            if cf_role_arn:
                print(f"Created CloudFormation execution role with ARN: {cf_role_arn}")
        else:
            cf_role_arn = input("Enter existing CloudFormation role ARN: ")
        
        # Ask about IAM capabilities
        iam_confirm = input("Does this template require IAM capabilities? (y/n): ").lower()
        capabilities = ['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'] if iam_confirm == 'y' else []
        
        # Create artifact bucket
        artifact_bucket = create_artifact_bucket(session, region)
        
        # Create pipeline name
        pipeline_name = f"{stack_name}-Pipeline-{str(uuid.uuid4())[:8]}"
        
        # Confirm details
        print("\nDeployment Details:")
        print(f"AWS Profile: {aws_profile}")
        print(f"AWS Region: {region}")
        print(f"Connection: {selected_connection}")
        print(f"Connection ARN: {connection_arn}")
        print(f"Repository: {repository}")
        print(f"Branch: {branch}")
        print(f"Stack Name: {stack_name}")
        if not deployment_file_path:
            print(f"Template Path: {template_path}")
            if params_file_path:
                print(f"Parameters File: {params_file_path}")
        else:
            print(f"Deployment File: {deployment_file_path}")
        print(f"Pipeline Role ARN: {pipeline_role_arn}")
        print(f"CloudFormation Role ARN: {cf_role_arn}")
        print(f"Artifact Bucket: {artifact_bucket}")
        print(f"Pipeline Name: {pipeline_name}")
        if capabilities:
            print("IAM Capabilities: Enabled")
        
        confirm = input("Do you want to proceed with the deployment? (y/n): ").lower()
        
        if confirm == 'y':
            print("Creating CodePipeline...")
            
            # Define pipeline structure
            pipeline_definition = {
                'name': pipeline_name,
                'roleArn': pipeline_role_arn,
                'artifactStore': {
                    'type': 'S3',
                    'location': artifact_bucket
                },
                'stages': [
                    {
                        'name': 'Source',
                        'actions': [
                            {
                                'name': 'Source',
                                'actionTypeId': {
                                    'category': 'Source',
                                    'owner': 'AWS',
                                    'provider': 'CodeStarSourceConnection',
                                    'version': '1'
                                },
                                'configuration': {
                                    'ConnectionArn': connection_arn,
                                    'FullRepositoryId': repository,
                                    'BranchName': branch,
                                    'OutputArtifactFormat': 'CODE_ZIP'
                                },
                                'outputArtifacts': [
                                    {
                                        'name': 'SourceCode'
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'name': 'Deploy',
                        'actions': [
                            {
                                'name': 'CreateOrUpdateStack',
                                'actionTypeId': {
                                    'category': 'Deploy',
                                    'owner': 'AWS',
                                    'provider': 'CloudFormation',
                                    'version': '1'
                                },
                                'configuration': {
                                    'ActionMode': 'CREATE_UPDATE',
                                    'StackName': stack_name,
                                    'TemplatePath': f'SourceCode::{template_path}',
                                    'RoleArn': cf_role_arn,
                                    'Capabilities': ','.join(capabilities) if capabilities else '',
                                    **({"ParametersFilePath": f'SourceCode::{params_file_path}'} if params_file_path else {})
                                },
                                'inputArtifacts': [
                                    {
                                        'name': 'SourceCode'
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
            
            try:
                # Create the pipeline
                response = pipeline_client.create_pipeline(
                    pipeline=pipeline_definition
                )
                
                print(f"Pipeline created successfully!")
                print(f"Pipeline ARN: {response['pipeline'].get('pipelineARN', 'N/A')}")
                print("Pipeline will start automatically and deploy your stack.")
                print("You can monitor the pipeline in the AWS CodePipeline console")
                print("and the resulting stack in the AWS CloudFormation console.")
                
                # Start the pipeline execution
                start_confirm = input("Do you want to manually start the pipeline now? (y/n): ").lower()
                if start_confirm == 'y':
                    pipeline_client.start_pipeline_execution(name=pipeline_name)
                    print(f"Pipeline execution started for {pipeline_name}")
                
            except ClientError as e:
                print(f"Error creating or starting pipeline: {e}")
                sys.exit(1)
        else:
            print("Deployment cancelled.")
    
    except ClientError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()