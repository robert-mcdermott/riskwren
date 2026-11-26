# RiskWren

**Risk and compliance people actually keep current.**

RiskWren is an open system of record for governance, risk, and compliance: one connected register of what an organization has, what could go wrong, what it must comply with, what it does about both, and the proof.

It is built first for research and health organizations that are not large corporations: research institutes, academic medical centers, universities, and the nonprofits around them. Nothing in it is specific to them, and any organization that wants a lightweight, self-hosted risk and compliance system can adopt it.

- **One connected register, not a suite of modules.** A control is described once, reduces the risks it is linked to, satisfies every requirement it is mapped to, and is tested once.
- **Working on the first day.** A risk taxonomy, a scoring method with defined scales, a library of common controls, and public frameworks arrive loaded.
- **Built for the people who own the risks.** One page of what each person owes, each item a short task.
- **Rating and standing are different things.** How much is at stake, and whether it is in order, are always two signals.
- **Show the reasoning; people decide.** Every rating and every readiness figure opens to what produced it. Named people assess and accept.
- **A history that cannot be quietly changed.** Every change is in an append-only, hash-chained log.
- **Passive by design.** No scanners, collectors, or agents, and no access to anything else on the network.
- **Open and yours.** Apache 2.0, no paid edition, SQLite on a laptop or PostgreSQL on a server, and your own name and colors.

## Status

RiskWren is at the start of its build. The plan is public:

- [What it is and who it is for](spec/vision.md)
- [How it works](spec/engine.md)
- [The roadmap](spec/roadmap.md), in waves that each end in a release
- [Everything else in the specification](spec/README.md)

Installation instructions arrive with the first release.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
