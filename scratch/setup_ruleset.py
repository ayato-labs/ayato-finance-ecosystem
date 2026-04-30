import os
import subprocess
import json

def update_ruleset():
    ruleset_id = 15711614
    ruleset = {
        "name": "Protect Core Branches",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["refs/heads/main", "refs/heads/develop"],
                "exclude": []
            }
        },
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 1,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": True
                }
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": [
                        {"context": "CI / Build"}
                    ]
                }
            }
        ]
    }
    
    # Use gh api to PATCH the ruleset
    cmd = [
        "gh", "api",
        "--method", "PATCH",
        f"/repos/ayato-labs/ayato-finance-ecosystem/rulesets/{ruleset_id}",
        "--input", "-"
    ]
    
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate(input=json.dumps(ruleset))
    
    if process.returncode == 0:
        print("Successfully created ruleset.")
        print(stdout)
    else:
        print(f"Failed to create ruleset. Error: {stderr}")

if __name__ == "__main__":
    update_ruleset()
