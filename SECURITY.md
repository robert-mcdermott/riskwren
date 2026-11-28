# Security

## Reporting a vulnerability

Please report security problems privately. On the repository's **Security** tab, choose
**Report a vulnerability**. If that is not available to you, open an issue that asks for a
private channel and gives no details.

You will get a reply within a week. Reporters are credited in the release notes unless they
ask not to be.

## Supported versions

Before version 1.0, only the latest release receives fixes.

## How RiskWren is kept secure

RiskWren 0.9.0 was reviewed against the OWASP Application Security Verification Standard 4.0.3 at level 2. The review, each finding, and what was done about it are in [`spec/security-review.md`](spec/security-review.md).

The threat model, the controls for each threat, and the table of who may see and do what are
in [`spec/security.md`](spec/security.md). `riskwren doctor` checks an installation, and
`riskwren verify` confirms that the history has not been altered.
