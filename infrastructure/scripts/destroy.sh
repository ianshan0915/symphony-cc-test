#!/usr/bin/env bash
#
# destroy.sh — Tear down the Terraform bootstrap resources
# (S3 state bucket, DynamoDB lock table, OIDC provider).
#
# Usage: ./destroy.sh [OPTIONS]
#   --region       AWS region (default: us-east-1)
#   --project      Project name prefix (default: symphony)
#   --account-id   AWS account ID (auto-detected if not provided)
#   --force        Skip confirmation prompt
#
set -euo pipefail

# ------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------
AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT="${PROJECT:-symphony}"
ACCOUNT_ID=""
FORCE=false

# ------------------------------------------------------------------
# Parse arguments
# ------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)      AWS_REGION="$2"; shift 2 ;;
    --project)     PROJECT="$2"; shift 2 ;;
    --account-id)  ACCOUNT_ID="$2"; shift 2 ;;
    --force)       FORCE=true; shift ;;
    *)             echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Auto-detect account ID if not provided
if [[ -z "$ACCOUNT_ID" ]]; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

BUCKET_NAME="${PROJECT}-terraform-state-${ACCOUNT_ID}"
DYNAMODB_TABLE="${PROJECT}-terraform-locks"

echo "============================================"
echo "  Terraform Bootstrap Destroy"
echo "============================================"
echo "  Region:         ${AWS_REGION}"
echo "  Project:        ${PROJECT}"
echo "  Account ID:     ${ACCOUNT_ID}"
echo "  State Bucket:   ${BUCKET_NAME}"
echo "  Lock Table:     ${DYNAMODB_TABLE}"
echo "============================================"
echo ""
echo "WARNING: This will permanently delete:"
echo "  - S3 bucket: ${BUCKET_NAME} (including all state files)"
echo "  - DynamoDB table: ${DYNAMODB_TABLE}"
echo "  - GitHub Actions OIDC provider"
echo ""

if [[ "$FORCE" != true ]]; then
  read -r -p "Are you sure? Type 'yes' to confirm: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# ------------------------------------------------------------------
# Delete S3 State Bucket
# ------------------------------------------------------------------
echo ""
echo ">>> Deleting S3 bucket: ${BUCKET_NAME}"

if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
  # Remove all object versions and delete markers
  echo "    Removing all object versions..."
  aws s3api list-object-versions \
    --bucket "${BUCKET_NAME}" \
    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
    --output json | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
objects = data.get('Objects') or []
if objects:
    print(json.dumps({'Objects': objects, 'Quiet': True}))
" | while read -r batch; do
    if [[ -n "$batch" ]]; then
      aws s3api delete-objects --bucket "${BUCKET_NAME}" --delete "$batch"
    fi
  done

  # Remove delete markers
  echo "    Removing delete markers..."
  aws s3api list-object-versions \
    --bucket "${BUCKET_NAME}" \
    --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
    --output json | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
objects = data.get('Objects') or []
if objects:
    print(json.dumps({'Objects': objects, 'Quiet': True}))
" | while read -r batch; do
    if [[ -n "$batch" ]]; then
      aws s3api delete-objects --bucket "${BUCKET_NAME}" --delete "$batch"
    fi
  done

  aws s3api delete-bucket --bucket "${BUCKET_NAME}" --region "${AWS_REGION}"
  echo "    Bucket deleted."
else
  echo "    Bucket does not exist. Skipping."
fi

# ------------------------------------------------------------------
# Delete DynamoDB Lock Table
# ------------------------------------------------------------------
echo ""
echo ">>> Deleting DynamoDB table: ${DYNAMODB_TABLE}"

if aws dynamodb describe-table --table-name "${DYNAMODB_TABLE}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  aws dynamodb delete-table \
    --table-name "${DYNAMODB_TABLE}" \
    --region "${AWS_REGION}"
  echo "    Table deleted."
else
  echo "    Table does not exist. Skipping."
fi

# ------------------------------------------------------------------
# Delete OIDC Provider
# ------------------------------------------------------------------
echo ""
echo ">>> Deleting GitHub Actions OIDC provider"

OIDC_ARN=$(aws iam list-open-id-connect-providers \
  --query "OpenIDConnectProviderList[?ends_with(Arn, 'token.actions.githubusercontent.com')].Arn" \
  --output text)

if [[ -n "${OIDC_ARN}" ]]; then
  aws iam delete-open-id-connect-provider --open-id-connect-provider-arn "${OIDC_ARN}"
  echo "    OIDC provider deleted."
else
  echo "    OIDC provider not found. Skipping."
fi

echo ""
echo "============================================"
echo "  Bootstrap resources destroyed."
echo "============================================"
