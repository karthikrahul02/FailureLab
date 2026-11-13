#!/usr/bin/env bash
set -euo pipefail
: "${USER_POOL_ID:?Set USER_POOL_ID from terraform output cognito_user_pool_id}"
: "${USER_EMAIL:?Set USER_EMAIL to the user email address}"
if [[ -z "${USER_PASSWORD:-}" ]]; then
  [[ -t 0 ]] || { echo "Set USER_PASSWORD in the environment for non-interactive use." >&2; exit 1; }
  read -r -s -p "Choose a strong permanent Cognito password: " USER_PASSWORD
  echo
  export USER_PASSWORD
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "$SCRIPT_DIR/create_cognito_user.py"
unset USER_PASSWORD
