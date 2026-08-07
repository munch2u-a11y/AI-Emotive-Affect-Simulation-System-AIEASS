# Security policy

## Supported version

The latest release on the default branch receives security fixes.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature for this
repository when available. Do not open a public issue containing an exploit,
sensitive path, token, or private agent state.

Useful reports include a minimal reproduction, affected version, impact,
platform, and suggested mitigation.

## Deployment guidance

- Prefer local stdio MCP for single-user installations.
- Store only opaque memory IDs, not conversation content or secrets.
- Restrict state-directory permissions to the agent process owner.
- Treat `affect_reset` and all step tools as state-changing operations.
- Do not expose Streamable HTTP publicly without authentication, TLS, request
  limits, and a deliberate source-offer mechanism for AGPL compliance.
