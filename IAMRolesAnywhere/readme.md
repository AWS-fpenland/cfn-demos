# IAM Roles Anywhere Demo

## Overview

This CloudFormation template deploys a complete environment for demonstrating AWS IAM Roles Anywhere with an ACM Private Certificate Authority (PCA) infrastructure. IAM Roles Anywhere allows workloads running outside of AWS to authenticate using X.509 certificates and assume IAM roles to access AWS services.

## Architecture

The template creates the following resources:

1. **ACM Private Certificate Authority (PCA)** - A root CA for issuing client certificates
2. **PCA Certificate** - The self-signed certificate for the CA
3. **PCA Activation** - Activates the CA with the certificate
4. **S3 Bucket** - A demo bucket for testing access
5. **IAM Role** - Can be assumed through IAM Roles Anywhere
6. **IAM Policy** - Grants access to the S3 bucket
7. **IAM Roles Anywhere Trust Anchor** - Links to the private CA
8. **IAM Roles Anywhere Profile** - Associates with the IAM role

## Deployment Instructions

1. Navigate to the CloudFormation console in your AWS account
2. Choose "Create stack" and upload the template file
3. Enter a stack name (e.g., "IAM-Roles-Anywhere-Demo")
4. Configure the template parameters:
   - **SigningAlgorithm**: Algorithm used for signing certificates (default: SHA256WITHRSA)
   - **KeyAlgorithm**: Algorithm used for the CA key (default: RSA_2048)
   - **CACountry**: Country code for the CA subject (default: US)
   - **OrgName**: Organization name for the CA subject (default: Demo Organization)
   - **CACommonName**: Common name for the CA subject (default: demo.root.ca)
   - **CACertValidity**: Number of years the CA certificate is valid (default: 10)
5. Review the configuration and create the stack
6. Wait for the stack creation to complete (approximately 5-10 minutes)

## Post-Deployment Steps

After deployment, the CloudFormation outputs provide instructions for:

1. Creating a private key on your client machine
2. Generating a Certificate Signing Request (CSR)
3. Issuing a client certificate using the Private CA
4. Setting up the AWS Roles Anywhere credential helper
5. Configuring your AWS CLI to use certificate-based authentication
6. Testing access to the S3 bucket

## Client Certificate Process

```bash
# 1. Create a private key
openssl genrsa -out private-key.pem 2048

# 2. Create a Certificate Signing Request (CSR)
openssl req -new -key private-key.pem -out csr.pem

# 3. Issue a certificate using the CSR and Private CA
aws acm-pca issue-certificate \
  --certificate-authority-arn <PrivateCA-ARN> \
  --csr fileb://csr.pem \
  --signing-algorithm <SigningAlgorithm> \
  --validity Value=365,Type=DAYS

# 4. Retrieve the certificate
aws acm-pca get-certificate \
  --certificate-authority-arn <PrivateCA-ARN> \
  --certificate-arn <certificate-arn-from-previous-command> \
  --output text > certificate.pem
```

Note: The `<SigningAlgorithm>` should match the one used when creating the stack (e.g., SHA256WITHRSA).

## Setting Up the Credential Helper

1. Download the AWS Roles Anywhere credential helper from [GitHub](https://github.com/aws/rolesanywhere-credential-helper/releases)
2. Install the credential helper on your client machine
3. Configure your AWS CLI config file:

```
[profile iamra-demo]
credential_process = aws_signing_helper credential-process --certificate certificate.pem --private-key private-key.pem --trust-anchor-arn <TrustAnchor-ARN> --profile-arn <Profile-ARN> --role-arn <Role-ARN>
```

4. Test the setup:

```bash
aws s3 ls s3://<BucketName> --profile iamra-demo
```

## Resources Created

- **Private Certificate Authority**: A root CA for issuing client certificates
- **CA Certificate**: Self-signed certificate created for the CA
- **CA Activation**: Resource that activates the CA with the certificate
- **S3 Bucket**: Named `iamra-demo-bucket-<AccountID>-<Region>`
- **IAM Role**: Named `IAMRolesAnywhereDemoRole`
- **IAM Policy**: Grants access to the demo S3 bucket
- **IAM Roles Anywhere Trust Anchor**: Named `DemoTrustAnchor`
- **IAM Roles Anywhere Profile**: Named `DemoProfile`

## CA Activation Process

The template uses AWS native resources to handle the CA activation process:

1. The `AWS::ACMPCA::CertificateAuthority` resource creates the Private CA
2. The `AWS::ACMPCA::Certificate` resource creates a self-signed certificate using the CA's CSR
3. The `AWS::ACMPCA::CertificateAuthorityActivation` resource activates the CA with the certificate

This approach leverages CloudFormation's built-in resources without requiring custom Lambda functions.

## Security Considerations

- The Private CA is created as a ROOT CA for demonstration purposes
- In production environments, consider using a proper PKI hierarchy
- Review and adjust the IAM permissions based on your requirements
- Set appropriate certificate validity periods for your use case

## Clean Up

To avoid ongoing charges, delete the CloudFormation stack when you're done with the demo:

1. Navigate to the CloudFormation console
2. Select the stack
3. Choose "Delete" and confirm the deletion

## Troubleshooting

- Verify that the CA status is "ACTIVE" before attempting to issue client certificates
- You can check the CA status using AWS CLI: `aws acm-pca describe-certificate-authority --certificate-authority-arn <CA-ARN>`
- Ensure the private key permissions are restricted (chmod 400 private-key.pem)
- Check for AWS CLI configuration errors in the credential process setup
- If the stack creation fails, review the CloudFormation events for specific error messages

## Additional Resources

- [IAM Roles Anywhere Documentation](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/introduction.html)
- [AWS ACM Private CA Documentation](https://docs.aws.amazon.com/acm-pca/latest/userguide/PcaWelcome.html)
- [AWS Roles Anywhere Credential Helper Repository](https://github.com/aws/rolesanywhere-credential-helper)
