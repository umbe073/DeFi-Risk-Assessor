#!/usr/bin/env bash
set -euo pipefail

# Apply branch protection for main.
# Requires: gh auth login

REPO="${1:-ddos-revenge/DeFi-Risk-Assessor}"

gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/${REPO}/branches/main/protection" \
  -f required_status_checks[strict]=true \
  -F required_status_checks[contexts][]="v2.8 lint, smoke, and secret guard" \
  -f enforce_admins=true \
  -f required_pull_request_reviews[dismiss_stale_reviews]=true \
  -f required_pull_request_reviews[require_code_owner_reviews]=false \
  -f required_pull_request_reviews[required_approving_review_count]=1 \
  -f restrictions= \
  -f required_linear_history=false \
  -f allow_force_pushes=false \
  -f allow_deletions=false \
  -f block_creations=false \
  -f required_conversation_resolution=true

echo "Branch protection applied for ${REPO} main."
