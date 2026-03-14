#!/usr/bin/env bash
#
# bootstrap.sh — Create S3 state bucket, DynamoDB lock table, and OIDC provider
# for Terraform remote state management.
#
# Usage: ./bootstrap.sh [OPTIONS]
#   --region       AWS region (default: us-east-1)
#   --project      Project name prefix (default: symphony)
#   --account-id   AWS account ID (auto-detected if not provided)
#
set -euo pipefail

# ------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------
AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT="${PROJECT:-symphony}"
ACCOUNT_ID=""

# ------------------------------------------------------------------
# Parse arguments
# ------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)      AWS_REGION="$2"; shift 2 ;;
    --project)     PROJECT="$2"; shift 2 ;;
    --account-id)  ACCOUNT_ID="$2"; shift 2 ;;
    *)             echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Auto-detect account ID if not provided
if [[ -z "$ACCOUNT_ID" ]]; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

BUCKET_NAME="${PROJECT}-terraform-state-${ACCOUNT_ID}"
DYNAMODB_TABLE="${PROJECT}-terraform-locks"
OIDC_PROVIDER_URL="https://token.actions.githubusercontent.com"

echo "============================================"
echo "  Terraform Bootstrap"
echo "============================================"
echo "  Region:         ${AWS_REGION}"
echo "  Project:        ${PROJECT}"
echo "  Account ID:     ${ACCOUNT_ID}"
echo "  State Bucket:   ${BUCKET_NAME}"
echo "  Lock Table:     ${DYNAMODB_TABLE}"
echo "============================================"

# ------------------------------------------------------------------
# S3 State Bucket
# ------------------------------------------------------------------
echo ""
echo ">>> Creating S3 state bucket: ${BUCKET_NAME}"

if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
  echo "    Bucket already exists. Skipping creation."
else
  if [[ "${AWS_REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket \
      --bucket "${BUCKET_NAME}" \
      --region "${AWS_REGION}"
  else
    aws s3api create-bucket \
      --bucket "${BUCKET_NAME}" \
      --region "${AWS_REGION}" \
      --create-bucket-configuration LocationConstraint="${AWS_REGION}"
  fi
  echo "    Bucket created."
fi

# Enable versioning
echo ">>> Enabling versioning on ${BUCKET_NAME}"
aws s3api put-bucket-versioning \
  --bucket "${BUCKET_NAME}" \
  --versioning-configuration Status=Enabled

# Enable server-side encryption
echo ">>> Enabling SSE-S3 encryption on ${BUCKET_NAME}"
aws s3api put-bucket-encryption \
  --bucket "${BUCKET_NAME}" \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "aws:kms"
        },
        "BucketKeyEnabled": true
      }
    ]
  }'

# Block public access
echo ">>> Blocking public access on ${BUCKET_NAME}"
aws s3api put-public-access-block \
  --bucket "${BUCKET_NAME}" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# ------------------------------------------------------------------
# DynamoDB Lock Table
# ------------------------------------------------------------------
echo ""
echo ">>> Creating DynamoDB lock table: ${DYNAMODB_TABLE}"

if aws dynamodb describe-table --table-name "${DYNAMODB_TABLE}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "    Table already exists. Skipping creation."
else
  aws dynamodb create-table \
    --table-name "${DYNAMODB_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${AWS_REGION}" \
    --tags Key=Project,Value="${PROJECT}" Key=ManagedBy,Value=bootstrap

  echo "    Waiting for table to become active..."
  aws dynamodb wait table-exists \
    --table-name "${DYNAMODB_TABLE}" \
    --region "${AWS_REGION}"
  echo "    Table created."
fi

# ------------------------------------------------------------------
# OIDC Provider for GitHub Actions
# ------------------------------------------------------------------
echo ""
echo ">>> Creating OIDC provider for GitHub Actions"

EXISTING_OIDC=$(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[?ends_with(Arn, 'token.actions.githubusercontent.com')].Arn" --output text)

if [[ -n "${EXISTING_OIDC}" ]]; then
  echo "    OIDC provider already exists: ${EXISTING_OIDC}"
else
  THUMBPRINT="6938fd4d98bab03faadb97b34396831e3780aea1"

  aws iam create-open-id-connect-provider \
    --url "${OIDC_PROVIDER_URL}" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "${THUMBPRINT}" \
    --tags Key=Project,Value="${PROJECT}" Key=ManagedBy,Value=bootstrap

  echo "    OIDC provider created."
fi

echo ""
echo "============================================"
echo "  Bootstrap complete!"
echo "============================================"
echo ""
echo "Add the following to your Terraform backend configuration:"
echo ""
echo '  terraform {'
echo '    backend "s3" {'
echo "      bucket         = \"${BUCKET_NAME}\""
echo "      key            = \"<environment>/terraform.tfstate\""
echo "      region         = \"${AWS_REGION}\""
echo "      dynamodb_table = \"${DYNAMODB_TABLE}\""
echo '      encrypt        = true'
echo '    }'
echo '  }'
