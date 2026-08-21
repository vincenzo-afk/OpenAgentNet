# Security Policy

## Supported Versions

We currently provide security updates for the following versions:

| Version | Supported |
| ------- | --------- |
| v0.6.x  | ✅ Yes    |
| < v0.6  | ❌ No     |

## Reporting a Vulnerability

We take the security of OpenAgentNet seriously. If you believe you have found a security vulnerability, please report it to us privately.

**Do not open a public issue for security vulnerabilities.**

Instead, please send an email to itsmebk2007@gmail.com with a description of the vulnerability, steps to reproduce, and any potential impact.

We will acknowledge your report within 48 hours and provide a timeline for a fix if the vulnerability is confirmed.

## Security Model

OpenAgentNet relies on:
- Ed25519 for agent identity and message signing.
- RSA-256 for API token issuance (JWT).
- Namespace isolation for shared memory.
- ACL-based permissions for memory objects.

For more details, see `docs/DESIGN.md`.
