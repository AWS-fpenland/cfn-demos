terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  # Configuration options
}

variable "org_name" {
  type        = string
  description = "Organization name to be used in resource naming"
}

variable "signing_algorithm" {
  type        = string
  description = "Signing algorithm for the certificate"
}

# Private Certificate Authority
resource "aws_acmpca_certificate_authority" "private_ca" {
  certificate_authority_configuration {
    key_algorithm     = "RSA_2048"
    signing_algorithm = var.signing_algorithm

    subject {
      common_name = "root.${var.org_name}.com"
    }
  }

  type = "ROOT"

  tags = {
    Name = "IAMRolesAnywhere-Demo-${var.org_name}"
  }
}

# Certificate
resource "aws_acmpca_certificate" "cert" {
  certificate_authority_arn   = aws_acmpca_certificate_authority.private_ca.arn
  certificate_signing_request = aws_acmpca_certificate_authority.private_ca.certificate_signing_request
  signing_algorithm          = var.signing_algorithm

  template_arn = "arn:aws:acm-pca:::template/RootCACertificate/V1"

  validity {
    type  = "YEARS"
    value = 10
  }
}

# S3 Bucket
resource "aws_s3_bucket" "demo_bucket" {
  bucket = "iam-roles-anywhere-demo-${var.org_name}"
}

# IAM Managed Policy
resource "aws_iam_policy" "s3_access" {
  name        = "IAMRolesAnywhere-S3Access-${var.org_name}"
  description = "Policy to allow S3 access for IAM Roles Anywhere demo"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.demo_bucket.arn,
          "${aws_s3_bucket.demo_bucket.arn}/*"
        ]
      }
    ]
  })
}

# IAM Role
resource "aws_iam_role" "demo_role" {
  name = "IAMRolesAnywhereDemoRole-${var.org_name}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "rolesanywhere.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:PrincipalTag/x-amz-machineid" = "true"
          }
        }
      }
    ]
  })

  managed_policy_arns = [aws_iam_policy.s3_access.arn]
}

# Roles Anywhere Trust Anchor
resource "aws_rolesanywhere_trust_anchor" "demo" {
  name    = "IAMRolesAnywhereDemoTrustAnchor-${var.org_name}"
  enabled = true
  source {
    source_data {
      acm_pca_arn = aws_acmpca_certificate_authority.private_ca.arn
    }
    source_type = "AWS_ACM_PCA"
  }
}

# Outputs
output "s3_bucket_name" {
  value = aws_s3_bucket.demo_bucket.id
}

output "certificate_authority_arn" {
  value = aws_acmpca_certificate_authority.private_ca.arn
}

output "role_arn" {
  value = aws_iam_role.demo_role.arn
}

output "trust_anchor_arn" {
  value = aws_rolesanywhere_trust_anchor.demo.arn
}

output "instructions" {
  description = "Instructions to issue a client certificate"
  value = <<EOF
To issue a client certificate:
1. Download the CA certificate:
   aws acm-pca get-certificate-authority-certificate --certificate-authority-arn ${aws_acmpca_certificate_authority.private_ca.arn} --output text --region <your-region>

2. Issue a certificate using the CA:
   aws acm-pca issue-certificate --certificate-authority-arn ${aws_acmpca_certificate_authority.private_ca.arn} --csr file://certificate-signing-request.pem --signing-algorithm ${var.signing_algorithm} --template-arn arn:aws:acm-pca:::template/EndEntityCertificate/V1 --validity Value=365,Type=DAYS --region <your-region>

3. Get the certificate:
   aws acm-pca get-certificate --certificate-authority-arn ${aws_acmpca_certificate_authority.private_ca.arn} --certificate-arn <certificate-arn> --output text --region <your-region>
EOF
}