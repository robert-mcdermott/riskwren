# Third parties

This guide is for whoever looks after the organization's suppliers, service providers, and partners: most often the security office, which asks how each handles the organization's information, and the units that rely on each.

A third party has been a record of the inventory from the start: a name, a unit, owners, and links to the processes it performs and the systems it supplies. This guide is about what RiskWren adds to that: what each third party provides, how much is at stake with it, and what it says about itself when asked.

## Third parties and their services

**Third parties → Third parties** lists every supplier, service provider, contractor, collaborator, sponsor, and subrecipient, with its tier. **Third parties → Services** lists what they provide.

A **service** (`SVC-0001`) is what the organization gets from a third party: the hosted clinical record system, the maintenance contract for the freezer farm, the tests the clinical laboratory sends out. It is a record of the inventory beside its third party, with its own unit, criticality, data class, and owners. A third party with three services may hold restricted information through one and nothing through the others, so it is the services that say what a third party touches:

| From | Link | To |
|---|---|---|
| Service | reaches | System |
| Service | handles | Information asset |
| Process | relies on | Service |
| System | is supplied by | Service |

**Add a service** on a third party's page (those who keep the third party, or a unit's steward) names what it is and its kind. Link it from its own page, as any record is linked. A third party's page lists its services, and each service's page names its third party. Both are in the **Connections** picture.

![A third party's page: its tier and the reasons for it, and the services it provides](img/third-party-tiered-light.webp)

## Tiering

A third party's **tier** says how much is at stake with it, and so how closely it is reviewed. The program has four, as shipped:

| Tier | What puts a third party in it | Reviewed |
|---|---|---|
| **Tier 1** | It holds or can see restricted or regulated information, has privileged access to systems, or is relied on for critical work and reaches information or systems | Every 12 months |
| **Tier 2** | It holds confidential information, reaches the network, accounts, or systems, holds records about 500 or more people, or critical work stops without it | Every 24 months |
| **Tier 3** | It holds internal information, works on the premises, passes work on to others, holds information outside the United States, or would be missed | Every 36 months |
| **Tier 4** | None of the above | When something calls for it |

**Tier it** on the third party's page (those who keep it, and assessors) asks a few questions: the most sensitive information it will hold or see, whether any of it is regulated (health information, research participants' information, controlled-access data, payment cards, government identifiers, student records, export-controlled information), about how many people, how it reaches the organization, and what would happen if it stopped. Where the inventory already knows, the answer is filled in, and the form shows which records it comes from:

- the most sensitive **information** is the highest data class among the third party, its services, the information its services handle, and the information shared with it;
- the most critical **work that relies on it** is the highest criticality among the processes it performs or that rely on its services, and the systems it or its services supply;
- the **systems it reaches** are those its services reach and those it supplies.

As the answers change, the form shows the tier the program's rules give and every rule of that tier that holds, in words. The tiers are read in order, and the first with a rule that holds is the one given.

![Tiering a survey host: what the inventory says, with the records it comes from, and the questions, partly answered from it](img/third-party-tier-light.webp)

The tier recorded is a judgment by a named person, like every rating in RiskWren. Recording a different tier from the rules' needs a reason, and both are kept: the page shows the tier recorded, the one the rules give, and why they differ. Tiering again keeps the earlier tierings under the **Tiering** tab, each with its answers as they were asked, and the history tells each one.

The list of third parties sorts by tier, and can be cut to one tier or to those **not tiered**. A third party with no tier is listed in **Tidy** as missing one.

The tiers, their review cadences, and their rules are part of the program. Their rules are written in the same condition language as a questionnaire's, over the answers and what the inventory says, and travel with the program when it is exported and imported. The questions are the built-in questionnaire **Third-party tiering**, which can be edited like any other under **Admin → Questionnaires**.

## Due diligence

A **review** (`DDR-0001`) asks a third party about itself: a questionnaire, sent to one of its contacts through a link, answered without an account, and read by someone here who records what they concluded. **Third parties → Due diligence** lists them all, and each third party's **Due diligence** tab lists its own, with its contacts.

### Contacts

A **contact** is a person at the third party who can be asked: a name, an email address, and their role there. Contacts are not accounts and never sign in. Those who keep the third party, and assessors, add them on its **Due diligence** tab, and say when one has left; the tab, and their addresses, are shown to those people and to those who read everything.

### Start a review

**Start a review** on the third party's **Due diligence** tab. The questionnaire is the one its tier names, as shipped:

| Tier | Questionnaire |
|---|---|
| Tier 1 | **Due diligence: full**, about forty-five questions: governance, access, the organization's information, health information, building and changing the service, operations, incidents, continuity, and the others it uses |
| Tier 2 | **Due diligence: standard**, about twenty-five questions on the same ground |
| Tier 3 | **Due diligence: short**, eight questions |
| Tier 4 | None: choose one if a review is wanted at all |

The questionnaires are written for organizations in the United States: they ask about a business associate agreement where health information is involved, about notice of an incident within 72 hours, and where the information is held. They can be edited, or others added, under **Admin → Questionnaires**. A review records the tier when it was started, and asks the version of the questionnaire in use when it was first sent.

### Send it

**Send it** chooses the contact, the date the answers are wanted by (three weeks on, unless another is given), and how long the link lasts (30 days unless said, at most 90). The link is shown once, to copy, and is sent to the contact by email where [email](configuration.md#email) is set up.

The link is the contact's way in, and nothing else is:

- It is a long random token. Only a digest of it is kept, so nobody can read it back from the database, and a message that carried it is cleared once it has been sent.
- The token follows a `#` in the address. Browsers never send that part to a server, so it is not in any server's or proxy's logs.
- It opens one thing: the questionnaire of that review, as that contact. It reaches no other page, record, or route, and the contact has no account.
- It stops working when it expires, when it is withdrawn (**Withdraw the link**), when the review is sent again with a new one, when the review is cancelled, and once the answers have been sent with it.
- Guessing at links is slowed the way guessing at passwords is.

![What a contact sees through the link: who is asking, by when, and the questions, with nothing else of the app](img/respond-light.webp)

The contact sees who is asking, by when, and the questions, which show and hide as they answer like any questionnaire's. They can **save to finish later**, with the same link, and **send the answers**, which cannot be changed after. The history names them as acting by link.

### Review the answers

When the answers come in, the review's owners are told, and it waits on their Home. The review shows the answers as they were asked. Some answers are marked by the questionnaire as **concerns**: no second factor, critical updates applied only after a month or more, an incident reported in the last three years, information held outside the United States, no independent report. They are listed first, with how many of the answers the questionnaire marks are concerns. They are what to look at, and decide nothing.

![A survey host's answers, with the five concerns among them listed first](img/review-answered-light.webp)

**Conclude** records what was concluded: **approved**, **approved with conditions**, or **not approved**. Conditions, and a refusal, say what must change, or why.

A review whose answers are late, or whose link expired or was withdrawn before anyone answered, waits on its owners' Home until it is sent again or cancelled.
