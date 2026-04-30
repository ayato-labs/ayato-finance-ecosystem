#!/usr/bin/env bash
set -euo pipefail

OWNER="Ayato-AI-for-Auto"
REPO="financial-figures"

apply_ruleset() {
  local file="$1"
  local name
  name=$(basename "$file" .json)

  echo "Applying ruleset: $name"
  gh api \
    --method POST \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/repos/${OWNER}/${REPO}/rulesets" \
    --input "$file"
  echo "Done: $name"
}

# Apply
apply_ruleset ".github/rulesets/protect-main.json"
apply_ruleset ".github/rulesets/protect-develop.json"

echo "All rulesets applied."
