# ADR-0008: Local accounts, and single sign-on with OpenID Connect

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

A risk and compliance record depends on knowing who did what, so RiskWren always requires sign-in. A small organization, or anyone trying RiskWren, wants accounts that work with nothing else installed. A larger one wants people to sign in with the identity they already have, under its own multi-factor authentication and offboarding, and to manage who holds which role from its identity provider. Microsoft Entra ID is the most common provider among the organizations RiskWren is built for, and others use different ones.

## Decision

**Local accounts, always available.**

- Passwords are hashed with scrypt from the standard library, with parameters stored beside each hash.
- Sessions are server-side: an opaque token in an `HttpOnly`, `SameSite=Strict`, `Secure` cookie, stored only as a hash, with idle and absolute expiry.
- Every state-changing request carries a per-session CSRF token, and cross-origin requests are refused.
- Sign-in is throttled per account and per address, with counters in the database.
- `riskwren init` creates the first administrator. The last active administrator can never be removed.

**Single sign-on with OpenID Connect, optional, beside local accounts.**

- Any standards-based provider: setting an issuer turns it on, and everything else comes from the provider's discovery document.
- The authorization-code flow with PKCE, `state`, and `nonce`. Sign-in state is stored server-side, used once, expires in minutes, and is tied to the browser that started it.
- The ID token's signature, issuer, audience, expiry, and nonce are verified before a session starts. Verification is written against the standard library and the HTTP client RiskWren already has.
- Accounts are linked by the provider's subject identifier and created at first sign-in unless that is turned off.
- **Roles from the provider.** A table in the configuration maps values of a claim (group identifiers or application roles) to a role, optionally with a unit scope and, for a leader, an acceptance limit. Mapped grants are marked as coming from the provider and are replaced at every sign-in; grants made in RiskWren are left alone.
- For Microsoft Entra ID the guide recommends application roles over groups, because group claims are omitted from tokens for people in many groups.
- The password form remains for accounts that have one, so a local administrator can always get in.

## Consequences

- No new dependency for either mechanism.
- Removing someone from a group takes effect at their next sign-in; a short maximum session age bounds the gap.
- Signing out of RiskWren does not sign anyone out of the provider.
- Providers that sign tokens with algorithms other than RSA need a setting changed at the provider; the error message names the algorithm.
- Unit scopes mapped from the provider refer to units by their code, so codes must be stable.

## Alternatives

- **Single sign-on only:** no way in when the provider is misconfigured, and nothing for a small organization or a first look.
- **SAML 2.0:** still common, but XML signatures are hard to verify safely without a library, and the providers in view all support OpenID Connect. It can be added if an adopter needs it.
- **An authentication library or an external identity proxy:** convenient, at the cost of a dependency or a second service to run.
- **Directory provisioning of accounts and groups:** useful at scale, and deferred; first sign-in creation and mapped roles cover most needs.
