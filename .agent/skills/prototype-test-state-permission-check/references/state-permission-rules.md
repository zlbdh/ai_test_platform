# State And Permission Rules

## Minimum Verification

- Is the state set complete?
- Is the initial state explicit?
- Are state-changing actions explicit?
- Do buttons differ by state?
- Do buttons differ by role?
- Are read-only and disabled states represented?

## High-Risk False Passes

- A State column exists without any state-transition path.
- Both approval and rejection lack opinion or reason fields.
- Every user sees the same dangerous actions.
