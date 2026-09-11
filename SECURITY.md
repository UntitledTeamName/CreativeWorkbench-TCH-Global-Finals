# Security Policy

## Localhost-First Security Model

Story Universe Architect is strictly a local desktop authoring tool designed to protect creative intellectual property:
1. **Loopback Binding**: The runtime binds exclusively to `127.0.0.1`. It never listens on external network interfaces (`0.0.0.0`).
2. **Origin Verification**: Requests are checked against `127.0.0.1:<port>` and `localhost:<port>`. Cross-origin browser requests are rejected with HTTP 403.
3. **Path Traversal Protection**: Workspace IDs are strictly sanitized to alphanumeric characters, dashes, and underscores. Path traversal attacks are rejected.
4. **No Cloud Leakage**: Story text, premise details, and character profiles are stored only on the local machine in the user's data directory. No telemetry or analytics exist.
5. **Verified Release Material**: The Skill verifies runtime wheels against cryptographic SHA-256 digests before execution.

## Reporting Vulnerabilities
To report a security vulnerability, please open a confidential advisory in the project repository.
