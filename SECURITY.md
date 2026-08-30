# Security Policy

## Supported Versions

OpenAgentNet is currently under active development. Security fixes are applied to the current development line represented by the default branch.

| Version | Supported |
|---|---|
| Current default branch | Yes |
| Older releases | Best effort; upgrade to the current line where possible |

## Reporting a Vulnerability

We take the security of OpenAgentNet seriously. If you believe you have found a vulnerability, please report it privately rather than opening a public issue.

Send a description of the vulnerability, reproduction steps, affected components, and potential impact to **itsmebk2007@gmail.com**. Please avoid including live credentials, private keys, or other sensitive production data in the initial report.

Reports will be reviewed by the maintainer, and follow-up communication will be provided as the investigation progresses.

## Security Model

OpenAgentNet relies on the following mechanisms:

- Ed25519 for agent identity and message signing.
- RS256-compatible JWT signing for API token issuance.
- Namespace isolation for shared memory.
- ACL-based permissions for memory objects.
- Payload validation, rate limiting, and audit-oriented administrative controls.

For the broader design, see [docs/DESIGN.md](docs/DESIGN.md) and [docs/SECURITY.md](docs/SECURITY.md).
