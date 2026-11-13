#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform"
TF_VARS_FILE="${TF_VARS_FILE:-$TF_DIR/terraform.tfvars}"
BACKEND_TAG="${BACKEND_TAG:-v1}"

command -v aws >/dev/null || { echo "AWS CLI is required." >&2; exit 1; }
command -v terraform >/dev/null || { echo "Terraform >= 1.6 is required." >&2; exit 1; }
command -v docker >/dev/null || { echo "Docker is required." >&2; exit 1; }
command -v npm >/dev/null || { echo "Node.js/npm is required." >&2; exit 1; }

if [[ ! -f "$TF_VARS_FILE" ]]; then
  echo "Missing $TF_VARS_FILE. Copy terraform.tfvars.example to terraform.tfvars and review every value." >&2
  exit 1
fi

cd "$TF_DIR"
terraform init

apply_reviewed_plan() {
  local stage="$1"
  shift
  local plan_file="$TF_DIR/.${stage}.tfplan"
  echo "==> Planning ${stage}"
  terraform plan -var-file="$TF_VARS_FILE" -out="$plan_file" "$@"
  echo
  echo "Review the Terraform plan above. It may create billable AWS resources."
  if [[ "${CONFIRM_AWS_DEPLOY:-}" == "YES" ]]; then
    echo "CONFIRM_AWS_DEPLOY=YES supplied; applying reviewed plan."
  else
    [[ -t 0 ]] || { echo "Non-interactive deployment requires CONFIRM_AWS_DEPLOY=YES after you have reviewed the plan." >&2; exit 1; }
    read -r -p "Apply this ${stage} plan? Type 'yes' to continue: " answer
    [[ "$answer" == "yes" ]] || { echo "Deployment stopped before applying ${stage}."; exit 1; }
  fi
  terraform apply "$plan_file"
  rm -f "$plan_file"
}

echo "==> Stage 1: provision AWS foundation and ECR (backend service remains disabled)"
apply_reviewed_plan "foundation" -var='deploy_backend=false'

REGION="$(terraform output -raw aws_region 2>/dev/null || true)"
if [[ -z "$REGION" ]]; then REGION="$(awk -F'"' '/^aws_region[[:space:]]*=/{print $2}' "$TF_VARS_FILE" | tail -1)"; fi
if [[ -z "$REGION" ]]; then REGION="ap-south-1"; fi
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REPO="$(terraform output -raw backend_ecr_repository_url)"

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
docker build -t "$ECR_REPO:$BACKEND_TAG" "$ROOT_DIR/backend"
docker push "$ECR_REPO:$BACKEND_TAG"

echo "==> Stage 2: enable the ECS service with the pushed container image"
apply_reviewed_plan "application" -var='deploy_backend=true' -var="backend_image_tag=$BACKEND_TAG"

API_URL="$(terraform output -raw api_url)"
FRONTEND_BUCKET="$(terraform output -raw frontend_bucket)"
FRONTEND_URL="$(terraform output -raw frontend_url)"
POOL_ID="$(terraform output -raw cognito_user_pool_id)"
CLIENT_ID="$(terraform output -raw cognito_app_client_id)"
CF_ID="$(terraform output -raw cloudfront_distribution_id)"

cat > "$ROOT_DIR/frontend/.env.production" <<EOF
VITE_API_BASE_URL=$API_URL/api/v1
VITE_AUTH_MODE=cognito
VITE_COGNITO_USER_POOL_ID=$POOL_ID
VITE_COGNITO_CLIENT_ID=$CLIENT_ID
VITE_AWS_REGION=$REGION
VITE_ENABLE_REAL_FIS=$(terraform output -raw real_fis_enabled)
EOF

cd "$ROOT_DIR/frontend"
npm ci || npm install
npm run build
aws s3 sync dist/ "s3://$FRONTEND_BUCKET/" --delete --cache-control 'public,max-age=300'
aws cloudfront create-invalidation --distribution-id "$CF_ID" --paths '/*' >/dev/null

cat <<EOF

FailureLab deployment complete.
Frontend: $FRONTEND_URL
API:      $API_URL
Region:   $REGION
Cognito pool: $POOL_ID
Cognito app client: $CLIENT_ID

Create a Cognito user with a permanent password using scripts/create_cognito_user.sh.
Set USER_POOL_ID, USER_EMAIL and AWS_REGION in your local shell first; the helper securely prompts for the password.
Do not enable AWS FIS until you have reviewed docs/SAFETY.md and the Terraform plan.
EOF
