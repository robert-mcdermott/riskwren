"""The one table that says what each API route requires (PLT-04).

Every route under ``/api`` must appear here. A route that does not is refused, and a test
fails the build if one is added without an entry. This is the coarse check; services check
again against the record itself (its unit, its owners, its visibility).
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import HTTPException, Request

from riskwren.access import roles
from riskwren.access.principal import Principal


class Needs(StrEnum):
    PUBLIC = "public"  # no sign-in: health, product name, signing in
    MEMBER = "member"  # anyone signed in
    ASSESS = "assess"  # assessors and managers, each within their scope
    STEWARD = "steward"  # stewards and managers, each within their scope
    LEAD = "lead"  # leaders, within their scope
    MANAGE = "manage"  # managers for the whole organization: running the program
    CONFIGURE = "configure"  # those managers, and administrators: shaping the program
    READ_ALL = "read_all"  # those managers, auditors, and administrators
    AUDIT = "audit"  # auditors: internal audit's own records
    ADMIN = "admin"  # administrators


POLICIES: dict[tuple[str, str], Needs] = {
    ("GET", "/api/v1/health/live"): Needs.PUBLIC,
    ("GET", "/api/v1/health/ready"): Needs.PUBLIC,
    ("GET", "/api/v1/meta"): Needs.PUBLIC,
    # Signing in and out
    ("GET", "/api/v1/session"): Needs.PUBLIC,  # answers 401 itself, so the app can show sign-in
    ("POST", "/api/v1/session"): Needs.PUBLIC,
    ("DELETE", "/api/v1/session"): Needs.PUBLIC,
    ("POST", "/api/v1/session/demo"): Needs.PUBLIC,  # answers 404 unless this is a demo
    ("POST", "/api/v1/session/password"): Needs.MEMBER,
    # Single sign-on. The round trip answers 404 itself unless it is set up.
    ("GET", "/api/v1/sso/start"): Needs.PUBLIC,
    ("GET", "/api/v1/sso/callback"): Needs.PUBLIC,
    ("GET", "/api/v1/sso"): Needs.ADMIN,
    ("POST", "/api/v1/sso/check"): Needs.ADMIN,
    ("PUT", "/api/v1/sso/mappings"): Needs.ADMIN,
    # Scheduled work and email, for whoever keeps the installation.
    ("GET", "/api/v1/jobs"): Needs.ADMIN,
    ("GET", "/api/v1/admin/operations"): Needs.ADMIN,
    # Other systems: tokens and webhooks
    ("GET", "/api/v1/admin/tokens"): Needs.ADMIN,
    ("POST", "/api/v1/admin/tokens"): Needs.ADMIN,
    ("POST", "/api/v1/admin/tokens/{token_id}/revoke"): Needs.ADMIN,
    ("GET", "/api/v1/admin/webhooks"): Needs.ADMIN,
    ("POST", "/api/v1/admin/webhooks"): Needs.ADMIN,
    ("PATCH", "/api/v1/admin/webhooks/{hook_id}"): Needs.ADMIN,
    ("DELETE", "/api/v1/admin/webhooks/{hook_id}"): Needs.ADMIN,
    ("POST", "/api/v1/admin/webhooks/{hook_id}/test"): Needs.ADMIN,
    # Results pushed in: reported by a token, confirmed by a person
    ("POST", "/api/v1/controls/{ref}/reported"): Needs.MEMBER,  # the service wants a token
    ("GET", "/api/v1/controls/{ref}/reported"): Needs.MEMBER,
    ("GET", "/api/v1/reported"): Needs.ASSESS,
    ("POST", "/api/v1/reported/{report_id}/confirm"): Needs.ASSESS,
    ("POST", "/api/v1/reported/{report_id}/set-aside"): Needs.ASSESS,
    ("GET", "/api/v1/standing/{kind}/{ref}"): Needs.MEMBER,
    # The assistant, when it is turned on: asked by a person or a token, set up by the file
    ("POST", "/api/v1/assistant/summary"): Needs.MEMBER,
    ("POST", "/api/v1/assistant/draft-risk"): Needs.MEMBER,
    ("GET", "/api/v1/admin/assistant"): Needs.ADMIN,
    ("POST", "/api/v1/admin/assistant/check"): Needs.ADMIN,
    # Drafts: proposed by an assistant or a token, made by a person in the ordinary form
    ("POST", "/api/v1/drafts"): Needs.MEMBER,
    ("GET", "/api/v1/drafts"): Needs.MEMBER,
    ("GET", "/api/v1/drafts/{draft_id}"): Needs.MEMBER,
    ("POST", "/api/v1/drafts/{draft_id}/use"): Needs.MEMBER,
    ("POST", "/api/v1/drafts/{draft_id}/set-aside"): Needs.MEMBER,
    ("POST", "/api/v1/jobs/{key}/run"): Needs.ADMIN,
    ("PUT", "/api/v1/jobs/{key}"): Needs.ADMIN,
    ("GET", "/api/v1/mail"): Needs.ADMIN,
    ("POST", "/api/v1/mail/test"): Needs.ADMIN,
    ("GET", "/api/v1/session/preferences"): Needs.MEMBER,
    ("PUT", "/api/v1/session/preferences"): Needs.MEMBER,
    # Questionnaires: anyone reads and answers; those who run the program change them.
    ("GET", "/api/v1/questionnaires"): Needs.MEMBER,
    ("POST", "/api/v1/questionnaires"): Needs.CONFIGURE,
    ("POST", "/api/v1/questionnaires/check"): Needs.CONFIGURE,
    ("GET", "/api/v1/questionnaires/{key}"): Needs.MEMBER,
    ("PATCH", "/api/v1/questionnaires/{key}"): Needs.CONFIGURE,
    ("POST", "/api/v1/questionnaires/{key}/responses"): Needs.MEMBER,
    ("GET", "/api/v1/responses/{response_id}"): Needs.MEMBER,
    # Finding and tidying: everything here is cut to what the person may see or change
    # where it is read or written.
    ("GET", "/api/v1/search"): Needs.MEMBER,
    ("GET", "/api/v1/views"): Needs.MEMBER,
    ("POST", "/api/v1/views"): Needs.MEMBER,
    ("PATCH", "/api/v1/views/{view_id}"): Needs.MEMBER,
    ("DELETE", "/api/v1/views/{view_id}"): Needs.MEMBER,
    ("GET", "/api/v1/tidy"): Needs.MEMBER,
    ("GET", "/api/v1/similar"): Needs.MEMBER,
    ("POST", "/api/v1/tidy/not-duplicates"): Needs.MEMBER,
    ("GET", "/api/v1/accounts/{account_id}/holdings"): Needs.MEMBER,
    ("POST", "/api/v1/accounts/{account_id}/handover"): Needs.MEMBER,
    # Documents are records like any other: who may add, change, approve, or read one is
    # decided where it is read or written.
    ("GET", "/api/v1/documents"): Needs.MEMBER,
    ("POST", "/api/v1/documents"): Needs.MEMBER,
    ("GET", "/api/v1/documents/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/documents/{ref}"): Needs.MEMBER,
    ("PUT", "/api/v1/documents/{ref}/owners"): Needs.MEMBER,
    ("GET", "/api/v1/documents/{ref}/history"): Needs.MEMBER,
    ("POST", "/api/v1/documents/{ref}/draft"): Needs.MEMBER,
    ("PATCH", "/api/v1/documents/{ref}/draft"): Needs.MEMBER,
    ("DELETE", "/api/v1/documents/{ref}/draft"): Needs.MEMBER,
    ("POST", "/api/v1/documents/{ref}/draft/file"): Needs.MEMBER,
    ("POST", "/api/v1/documents/{ref}/draft/submit"): Needs.MEMBER,
    ("POST", "/api/v1/documents/{ref}/draft/decision"): Needs.MEMBER,
    ("POST", "/api/v1/documents/{ref}/draft/withdraw"): Needs.MEMBER,
    ("POST", "/api/v1/documents/{ref}/draft/publish"): Needs.MEMBER,
    ("POST", "/api/v1/documents/{ref}/review"): Needs.MEMBER,
    ("POST", "/api/v1/documents/{ref}/retire"): Needs.MEMBER,
    ("POST", "/api/v1/documents/{ref}/reinstate"): Needs.MEMBER,
    ("GET", "/api/v1/documents/{ref}/versions/{version_id}"): Needs.MEMBER,
    ("GET", "/api/v1/documents/{ref}/compare"): Needs.MEMBER,
    ("GET", "/api/v1/documents/{ref}/versions/{version_id}/file"): Needs.MEMBER,
    ("PUT", "/api/v1/documents/{ref}/audience"): Needs.MEMBER,
    ("GET", "/api/v1/documents/{ref}/acknowledgments"): Needs.MEMBER,
    ("GET", "/api/v1/documents/{ref}/governs"): Needs.MEMBER,
    ("GET", "/api/v1/objectives"): Needs.MEMBER,
    ("POST", "/api/v1/objectives"): Needs.MEMBER,
    ("GET", "/api/v1/objectives/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/objectives/{ref}"): Needs.MEMBER,
    ("PUT", "/api/v1/objectives/{ref}/owners"): Needs.MEMBER,
    ("GET", "/api/v1/objectives/{ref}/history"): Needs.MEMBER,
    ("PUT", "/api/v1/risks/{ref}/objectives"): Needs.MEMBER,
    ("GET", "/api/v1/sessions"): Needs.MEMBER,
    ("POST", "/api/v1/sessions"): Needs.MEMBER,
    ("GET", "/api/v1/sessions/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/sessions/{ref}"): Needs.MEMBER,
    ("PUT", "/api/v1/sessions/{ref}/owners"): Needs.MEMBER,
    ("GET", "/api/v1/sessions/{ref}/history"): Needs.MEMBER,
    ("POST", "/api/v1/sessions/{ref}/items"): Needs.MEMBER,
    ("PATCH", "/api/v1/sessions/{ref}/items/{item_id}"): Needs.MEMBER,
    ("DELETE", "/api/v1/sessions/{ref}/items/{item_id}"): Needs.MEMBER,
    ("POST", "/api/v1/sessions/{ref}/items/{item_id}/move"): Needs.MEMBER,
    ("POST", "/api/v1/sessions/{ref}/items/{item_id}/decision"): Needs.MEMBER,
    ("POST", "/api/v1/sessions/{ref}/held"): Needs.MEMBER,
    ("POST", "/api/v1/sessions/{ref}/cancel"): Needs.MEMBER,
    ("GET", "/api/v1/framework-packs"): Needs.MEMBER,
    ("POST", "/api/v1/framework-packs"): Needs.CONFIGURE,
    ("GET", "/api/v1/frameworks/{key}/changes"): Needs.MEMBER,
    ("GET", "/api/v1/frameworks/{key}/change"): Needs.MEMBER,
    ("POST", "/api/v1/frameworks/{key}/versions"): Needs.MEMBER,
    ("GET", "/api/v1/frameworks/{key}/suggestions"): Needs.MEMBER,
    ("POST", "/api/v1/frameworks/{key}/suggestions/confirm"): Needs.MEMBER,
    ("POST", "/api/v1/frameworks/{key}/suggestions/set-aside"): Needs.MEMBER,
    ("POST", "/api/v1/scopes/{ref}/frameworks/{key}/move"): Needs.MEMBER,
    ("GET", "/api/v1/agreements"): Needs.MEMBER,
    ("POST", "/api/v1/agreements"): Needs.MEMBER,
    ("GET", "/api/v1/agreements/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/agreements/{ref}"): Needs.MEMBER,
    ("PUT", "/api/v1/agreements/{ref}/owners"): Needs.MEMBER,
    ("GET", "/api/v1/agreements/{ref}/history"): Needs.MEMBER,
    ("PUT", "/api/v1/agreements/{ref}/covers"): Needs.MEMBER,
    ("POST", "/api/v1/agreements/{ref}/close"): Needs.MEMBER,
    ("POST", "/api/v1/agreements/{ref}/reopen"): Needs.MEMBER,
    ("PUT", "/api/v1/documents/{ref}/controls"): Needs.MEMBER,
    ("DELETE", "/api/v1/documents/{ref}/controls/{link_id}"): Needs.MEMBER,
    ("PUT", "/api/v1/documents/{ref}/requirements"): Needs.MEMBER,
    ("DELETE", "/api/v1/documents/{ref}/requirements/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/library"): Needs.MEMBER,
    ("GET", "/api/v1/library/{ref}"): Needs.MEMBER,
    ("POST", "/api/v1/library/{ref}/acknowledge"): Needs.MEMBER,
    # Risk analyses are records like any other: who may start, work through, or read one
    # is decided where it is read or written.
    ("GET", "/api/v1/risk-analyses"): Needs.MEMBER,
    ("POST", "/api/v1/risk-analyses"): Needs.MEMBER,
    ("POST", "/api/v1/risk-analyses/preview"): Needs.MEMBER,
    ("GET", "/api/v1/risk-analyses/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/risk-analyses/{ref}"): Needs.MEMBER,
    ("PUT", "/api/v1/risk-analyses/{ref}/owners"): Needs.MEMBER,
    ("GET", "/api/v1/risk-analyses/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/risk-analyses/{ref}/assets/{subject}"): Needs.MEMBER,
    ("POST", "/api/v1/risk-analyses/{ref}/items/{item_id}"): Needs.MEMBER,
    ("POST", "/api/v1/risk-analyses/{ref}/assets/{subject}/rest"): Needs.MEMBER,
    ("POST", "/api/v1/risk-analyses/{ref}/close"): Needs.MEMBER,
    ("POST", "/api/v1/risk-analyses/{ref}/reopen"): Needs.MEMBER,
    # Indicators are records like any other: what a person may see or change is decided
    # where it is read or written.
    ("GET", "/api/v1/indicators"): Needs.MEMBER,
    ("POST", "/api/v1/indicators"): Needs.MEMBER,
    ("GET", "/api/v1/indicators/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/indicators/{ref}"): Needs.MEMBER,
    ("PUT", "/api/v1/indicators/{ref}/owners"): Needs.MEMBER,
    ("GET", "/api/v1/indicators/{ref}/history"): Needs.MEMBER,
    ("POST", "/api/v1/indicators/{ref}/readings"): Needs.MEMBER,
    ("PUT", "/api/v1/indicators/{ref}/risks"): Needs.MEMBER,
    ("GET", "/api/v1/risks/{ref}/indicators"): Needs.MEMBER,
    # Campaigns: assessors and managers run them; whoever is asked answers. What a person
    # may see of a campaign is decided where it is read.
    ("GET", "/api/v1/campaigns"): Needs.MEMBER,
    ("POST", "/api/v1/campaigns"): Needs.ASSESS,
    ("POST", "/api/v1/campaigns/preview"): Needs.ASSESS,
    ("GET", "/api/v1/campaigns/{ref}"): Needs.MEMBER,
    ("POST", "/api/v1/campaigns/{ref}/remind"): Needs.ASSESS,
    ("POST", "/api/v1/campaigns/{ref}/close"): Needs.ASSESS,
    ("POST", "/api/v1/campaigns/{ref}/cancel"): Needs.ASSESS,
    ("GET", "/api/v1/campaign-items/{item_id}"): Needs.MEMBER,
    ("POST", "/api/v1/campaign-items/{item_id}/answer"): Needs.MEMBER,
    ("POST", "/api/v1/campaign-items/{item_id}/excuse"): Needs.ASSESS,
    # People
    ("GET", "/api/v1/accounts"): Needs.MEMBER,  # the people picker; members see names only
    ("POST", "/api/v1/accounts"): Needs.ADMIN,
    ("GET", "/api/v1/accounts/{account_id}"): Needs.MEMBER,
    ("PATCH", "/api/v1/accounts/{account_id}"): Needs.MEMBER,  # one's own details, or admin
    ("PUT", "/api/v1/accounts/{account_id}/roles"): Needs.ADMIN,
    ("PUT", "/api/v1/accounts/{account_id}/units"): Needs.ADMIN,
    ("POST", "/api/v1/accounts/{account_id}/password"): Needs.ADMIN,
    ("GET", "/api/v1/roles"): Needs.MEMBER,
    # Units
    ("GET", "/api/v1/units"): Needs.MEMBER,
    ("POST", "/api/v1/units"): Needs.ADMIN,
    ("GET", "/api/v1/units/{unit_id}"): Needs.MEMBER,
    ("PATCH", "/api/v1/units/{unit_id}"): Needs.ADMIN,
    # Branding
    ("GET", "/api/v1/admin/branding"): Needs.ADMIN,
    ("PUT", "/api/v1/admin/branding"): Needs.ADMIN,
    ("POST", "/api/v1/admin/branding/check"): Needs.ADMIN,
    ("POST", "/api/v1/admin/branding/images/{kind}"): Needs.ADMIN,
    ("DELETE", "/api/v1/admin/branding/images/{kind}"): Needs.ADMIN,
    # Imports
    ("POST", "/api/v1/imports/units"): Needs.ADMIN,
    ("POST", "/api/v1/imports/people"): Needs.ADMIN,
    # The program
    ("GET", "/api/v1/vocabularies"): Needs.MEMBER,
    ("GET", "/api/v1/admin/visibility"): Needs.CONFIGURE,
    ("PUT", "/api/v1/admin/visibility"): Needs.CONFIGURE,
    ("GET", "/api/v1/admin/leadership-readers"): Needs.CONFIGURE,
    ("PUT", "/api/v1/admin/leadership-readers"): Needs.CONFIGURE,
    ("GET", "/api/v1/admin/vocabularies"): Needs.CONFIGURE,
    ("PUT", "/api/v1/vocabularies/{name}"): Needs.CONFIGURE,
    ("POST", "/api/v1/risk-categories"): Needs.CONFIGURE,
    ("POST", "/api/v1/program/preview"): Needs.CONFIGURE,
    ("POST", "/api/v1/program/publish"): Needs.CONFIGURE,
}


def record_policies(path: str, *, links: bool = True) -> dict[tuple[str, str], Needs]:
    """What every record type's routes need. Any member may ask; the services decide what
    each may see and change, by the record's unit, its owners, and its visibility."""
    base = f"/api/v1/{path}"
    found = {
        ("GET", base): Needs.MEMBER,
        ("POST", base): Needs.STEWARD,
        ("GET", base + "/{ref}"): Needs.MEMBER,
        ("PATCH", base + "/{ref}"): Needs.MEMBER,
        ("PUT", base + "/{ref}/owners"): Needs.MEMBER,
        ("GET", base + "/{ref}/history"): Needs.MEMBER,
    }
    if links:
        found[("POST", base + "/{ref}/links")] = Needs.MEMBER
        found[("DELETE", base + "/{ref}/links/{link_id}")] = Needs.MEMBER
    return found


for _path in ("processes", "systems", "third-parties", "information", "services", "sites"):
    POLICIES.update(record_policies(_path))

# Third parties as a program. Who may tier one is decided where it is written.
POLICIES.update(
    {
        ("GET", "/api/v1/tiers"): Needs.MEMBER,
        ("GET", "/api/v1/third-parties/{ref}/tiering"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/tiering"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/contacts"): Needs.MEMBER,
        ("PATCH", "/api/v1/contacts/{contact_id}"): Needs.MEMBER,
        ("GET", "/api/v1/reviews"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/reviews"): Needs.MEMBER,
        ("GET", "/api/v1/reviews/{ref}"): Needs.MEMBER,
        ("PATCH", "/api/v1/reviews/{ref}"): Needs.MEMBER,
        ("PUT", "/api/v1/reviews/{ref}/owners"): Needs.MEMBER,
        ("GET", "/api/v1/reviews/{ref}/history"): Needs.MEMBER,
        ("POST", "/api/v1/reviews/{ref}/send"): Needs.MEMBER,
        ("POST", "/api/v1/reviews/{ref}/withdraw"): Needs.MEMBER,
        ("POST", "/api/v1/reviews/{ref}/conclude"): Needs.MEMBER,
        ("POST", "/api/v1/reviews/{ref}/cancel"): Needs.MEMBER,
        # Someone without an account, holding a link: each route finds the link by the token
        # in its header and reaches that link's questionnaire and nothing else.
        ("GET", "/api/v1/respond"): Needs.PUBLIC,
        ("PUT", "/api/v1/respond"): Needs.PUBLIC,
        ("POST", "/api/v1/respond/submit"): Needs.PUBLIC,
        ("POST", "/api/v1/respond/files"): Needs.PUBLIC,
        ("GET", "/api/v1/coverage"): Needs.MEMBER,
        # Measures carry the organization's trend, so they are for those who read everything.
        ("GET", "/api/v1/measures"): Needs.READ_ALL,
        # Leadership reports: read by those who read everything and those who lead all of it,
        # which the service decides; prepared and issued by managers for the organization.
        ("GET", "/api/v1/leadership-reports"): Needs.MEMBER,
        ("GET", "/api/v1/leadership-reports/next"): Needs.MANAGE,
        ("POST", "/api/v1/leadership-reports"): Needs.MANAGE,
        ("GET", "/api/v1/leadership-reports/{ref}"): Needs.MEMBER,
        # As of a day: what each person may see, rebuilt from the history.
        ("GET", "/api/v1/as-of"): Needs.MEMBER,
        ("GET", "/api/v1/as-of/{ref}"): Needs.MEMBER,
        # Internal audit: read by those who read everything and those who lead the whole
        # organization, changed by auditors alone; the service decides both.
        ("GET", "/api/v1/audit/universe"): Needs.MEMBER,
        ("GET", "/api/v1/audit/universe/{kind}/{key}"): Needs.MEMBER,
        ("PUT", "/api/v1/audit/universe/{kind}/{key}"): Needs.AUDIT,
        ("GET", "/api/v1/audit/plans"): Needs.MEMBER,
        ("POST", "/api/v1/audit/plans"): Needs.AUDIT,
        ("GET", "/api/v1/audit/plans/{ref}"): Needs.MEMBER,
        ("POST", "/api/v1/audit/plans/{ref}/engagements"): Needs.AUDIT,
        ("POST", "/api/v1/audit/plans/{ref}/approve"): Needs.MEMBER,
        ("POST", "/api/v1/audit/plans/{ref}/close"): Needs.AUDIT,
        ("POST", "/api/v1/engagements/{ref}/drop"): Needs.AUDIT,
        ("POST", "/api/v1/engagements/{ref}/restore"): Needs.AUDIT,
        ("GET", "/api/v1/auditors"): Needs.MEMBER,
        ("GET", "/api/v1/engagements/{ref}"): Needs.MEMBER,
        ("POST", "/api/v1/engagements/{ref}/start"): Needs.AUDIT,
        ("POST", "/api/v1/engagements/{ref}/advance"): Needs.AUDIT,
        ("POST", "/api/v1/engagements/{ref}/workpapers"): Needs.AUDIT,
        ("PUT", "/api/v1/workpapers/{paper_id}"): Needs.AUDIT,
        ("POST", "/api/v1/workpapers/{paper_id}/sign-off"): Needs.AUDIT,
        ("POST", "/api/v1/workpapers/{paper_id}/notes"): Needs.AUDIT,
        ("POST", "/api/v1/review-notes/{note_id}/answer"): Needs.AUDIT,
        ("POST", "/api/v1/review-notes/{note_id}/clear"): Needs.AUDIT,
        ("POST", "/api/v1/engagements/{ref}/requests"): Needs.AUDIT,
        # A request is answered by whoever it was asked of, auditor or not.
        ("GET", "/api/v1/audit/requests/{request_id}"): Needs.MEMBER,
        ("POST", "/api/v1/audit/requests/{request_id}/answer"): Needs.MEMBER,
        ("POST", "/api/v1/audit/requests/{request_id}/accept"): Needs.AUDIT,
        ("POST", "/api/v1/audit/requests/{request_id}/return"): Needs.AUDIT,
        ("POST", "/api/v1/engagements/{ref}/findings"): Needs.AUDIT,
        ("GET", "/api/v1/audit/plans/{ref}/committee-report"): Needs.MEMBER,
        ("GET", "/api/v1/audit/outside"): Needs.MEMBER,
        ("POST", "/api/v1/audit/outside"): Needs.AUDIT,
        ("POST", "/api/v1/audit/outside/{access_id}/revoke"): Needs.AUDIT,
        # An outside auditor has no account: their link, in a header, opens one engagement or
        # scope, read-only, and each use is recorded.
        ("GET", "/api/v1/outside"): Needs.PUBLIC,
        # Incidents: anyone reports one; the service decides who sees, triages, and handles
        # each (its reporter, handlers, triagers, its unit's leaders and stewards).
        ("GET", "/api/v1/incidents"): Needs.MEMBER,
        ("POST", "/api/v1/incidents"): Needs.MEMBER,
        ("GET", "/api/v1/incidents/{ref}"): Needs.MEMBER,
        ("PATCH", "/api/v1/incidents/{ref}"): Needs.MEMBER,
        ("PUT", "/api/v1/incidents/{ref}/owners"): Needs.MEMBER,
        ("PUT", "/api/v1/incidents/{ref}/case"): Needs.MEMBER,
        ("POST", "/api/v1/incidents/{ref}/triage"): Needs.ASSESS,
        ("POST", "/api/v1/incidents/{ref}/close"): Needs.MEMBER,
        ("POST", "/api/v1/incidents/{ref}/reopen"): Needs.ASSESS,
        ("POST", "/api/v1/incidents/{ref}/messages"): Needs.MEMBER,
        ("GET", "/api/v1/incidents/{ref}/history"): Needs.MEMBER,
        ("GET", "/api/v1/incidents/summary"): Needs.MEMBER,
        ("PUT", "/api/v1/incidents/{ref}/learning"): Needs.MEMBER,
        ("POST", "/api/v1/incidents/{ref}/losses"): Needs.MEMBER,
        ("POST", "/api/v1/incidents/{ref}/issues"): Needs.MEMBER,
        ("GET", "/api/v1/incidents/{ref}/breach"): Needs.MEMBER,
        ("POST", "/api/v1/incidents/{ref}/breach"): Needs.MEMBER,
        ("POST", "/api/v1/incidents/{ref}/notifications"): Needs.MEMBER,
        # Privacy impact assessments: where each process and system stands, read by everyone
        # as the inventory is; reviewed by those who assess.
        ("GET", "/api/v1/privacy"): Needs.MEMBER,
        ("POST", "/api/v1/privacy/reviews/{item_id}"): Needs.ASSESS,
        ("GET", "/api/v1/admin/anonymous-reporting"): Needs.CONFIGURE,
        ("PUT", "/api/v1/admin/anonymous-reporting"): Needs.ADMIN,
        # Reporting without a name: no account, and nothing kept of who sent it. Closed
        # unless an administrator opens it.
        ("GET", "/api/v1/anonymous-reports"): Needs.PUBLIC,
        ("POST", "/api/v1/anonymous-reports"): Needs.PUBLIC,
        ("POST", "/api/v1/anonymous-reports/follow-up"): Needs.PUBLIC,
        ("POST", "/api/v1/anonymous-reports/messages"): Needs.PUBLIC,
        # Resilience: read with the record, changed by those who keep it.
        ("GET", "/api/v1/resilience"): Needs.MEMBER,
        ("GET", "/api/v1/processes/{ref}/impact"): Needs.MEMBER,
        ("POST", "/api/v1/processes/{ref}/impact"): Needs.MEMBER,
        ("GET", "/api/v1/systems/{ref}/recovery"): Needs.MEMBER,
        ("POST", "/api/v1/systems/{ref}/recovery"): Needs.MEMBER,
        ("GET", "/api/v1/services/{ref}/recovery"): Needs.MEMBER,
        ("POST", "/api/v1/services/{ref}/recovery"): Needs.MEMBER,
        ("GET", "/api/v1/sites/{ref}/recovery"): Needs.MEMBER,
        ("POST", "/api/v1/sites/{ref}/recovery"): Needs.MEMBER,
        ("GET", "/api/v1/third-parties/{ref}/recovery"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/recovery"): Needs.MEMBER,
        # Continuity plans: documents of their own kind; the service decides who may change
        # what a plan restores and who records its exercises.
        ("GET", "/api/v1/continuity"): Needs.MEMBER,
        ("GET", "/api/v1/continuity/{ref}"): Needs.MEMBER,
        ("PUT", "/api/v1/continuity/{ref}/covers"): Needs.MEMBER,
        ("POST", "/api/v1/continuity/{ref}/exercises"): Needs.MEMBER,
        ("POST", "/api/v1/continuity/{ref}/exercises/{exercise_id}/issues"): Needs.MEMBER,
        ("GET", "/api/v1/continuity/{ref}/offline"): Needs.MEMBER,
        # Dossiers and a scope's plans hold what the person may see, checked by the record.
        ("GET", "/api/v1/dossiers/{ref}"): Needs.MEMBER,
        ("POST", "/api/v1/dossiers/check"): Needs.MEMBER,
        ("GET", "/api/v1/scopes/{ref}/security-plan"): Needs.MEMBER,
        ("GET", "/api/v1/scopes/{ref}/oscal/{document}"): Needs.MEMBER,
        # Scenarios, estimates, and the bow-tie: decided by the record, as for risks.
        ("GET", "/api/v1/scenarios"): Needs.MEMBER,
        ("POST", "/api/v1/scenarios"): Needs.MEMBER,
        ("GET", "/api/v1/scenarios/{ref}"): Needs.MEMBER,
        ("PATCH", "/api/v1/scenarios/{ref}"): Needs.MEMBER,
        ("PUT", "/api/v1/scenarios/{ref}/owners"): Needs.MEMBER,
        ("PUT", "/api/v1/scenarios/{ref}/subjects"): Needs.MEMBER,
        ("GET", "/api/v1/scenarios/{ref}/history"): Needs.MEMBER,
        ("GET", "/api/v1/risks/{ref}/bow-tie"): Needs.MEMBER,
        ("GET", "/api/v1/risks/{ref}/estimate"): Needs.MEMBER,
        ("POST", "/api/v1/risks/{ref}/estimate"): Needs.MEMBER,
        # The portfolio counts only what each person may see, as the dashboards do.
        ("GET", "/api/v1/portfolio"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/call-review"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/offboarding"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/offboarding/steps/{step}"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/offboarding/cancel"): Needs.MEMBER,
        ("POST", "/api/v1/reviews/{ref}/findings"): Needs.MEMBER,
        ("PUT", "/api/v1/agreements/{ref}/parties"): Needs.MEMBER,
        ("GET", "/api/v1/assurance-kinds"): Needs.MEMBER,
        ("GET", "/api/v1/third-parties/{ref}/assurance"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/assurance"): Needs.MEMBER,
        ("POST", "/api/v1/third-parties/{ref}/assurance/{document}/reviews"): Needs.MEMBER,
    }
)

# The risk register
POLICIES.update(record_policies("risks", links=False))
POLICIES.update(
    {
        ("GET", "/api/v1/program"): Needs.MEMBER,
        ("PATCH", "/api/v1/risk-categories/{key}"): Needs.CONFIGURE,
        ("GET", "/api/v1/program/fields"): Needs.MEMBER,
        ("PUT", "/api/v1/program/fields/{type_key}"): Needs.CONFIGURE,
        ("GET", "/api/v1/risk-library"): Needs.MEMBER,
        ("GET", "/api/v1/risks/{ref}/assessments"): Needs.MEMBER,
        ("POST", "/api/v1/risks/{ref}/assessments"): Needs.MEMBER,
        ("PUT", "/api/v1/risks/{ref}/subjects"): Needs.MEMBER,
        ("PUT", "/api/v1/risks/{ref}/escalation"): Needs.MEMBER,
    }
)

# Controls and treatment. As with every record, any member may ask, and the services decide
# by the record: who owns it, whose unit it is in, and who has the authority.
POLICIES.update(record_policies("controls", links=False))
POLICIES.update(
    {
        ("GET", "/api/v1/control-library"): Needs.MEMBER,
        ("GET", "/api/v1/controls/{ref}/requirements"): Needs.MEMBER,
        ("PUT", "/api/v1/controls/{ref}/requirements"): Needs.MEMBER,
        ("POST", "/api/v1/controls/{ref}/requirements/suggested"): Needs.MEMBER,
        ("DELETE", "/api/v1/controls/{ref}/requirements/{mapping_id}"): Needs.MEMBER,
        ("GET", "/api/v1/controls/{ref}/ratings"): Needs.MEMBER,
        ("POST", "/api/v1/controls/{ref}/ratings"): Needs.MEMBER,
        ("GET", "/api/v1/risks/{ref}/controls"): Needs.MEMBER,
        ("PUT", "/api/v1/risks/{ref}/controls"): Needs.MEMBER,
        ("DELETE", "/api/v1/risks/{ref}/controls/{control_ref}"): Needs.MEMBER,
        ("GET", "/api/v1/risks/{ref}/treatment"): Needs.MEMBER,
        ("PUT", "/api/v1/risks/{ref}/response"): Needs.MEMBER,
        ("POST", "/api/v1/risks/{ref}/plans"): Needs.MEMBER,
        ("POST", "/api/v1/risks/{ref}/acceptances"): Needs.LEAD,
        ("POST", "/api/v1/acceptances/{acceptance_id}/withdrawal"): Needs.MEMBER,
        ("GET", "/api/v1/acceptances"): Needs.MEMBER,
        ("GET", "/api/v1/plans"): Needs.MEMBER,
        ("GET", "/api/v1/plans/{ref}"): Needs.MEMBER,
        ("POST", "/api/v1/plans/{ref}/cancellation"): Needs.MEMBER,
        ("POST", "/api/v1/plans/{ref}/actions"): Needs.MEMBER,
        ("GET", "/api/v1/actions"): Needs.MEMBER,
        ("PATCH", "/api/v1/actions/{ref}"): Needs.MEMBER,
    }
)

# Frameworks: anyone signed in may read what the organization is held to; those who run the
# program enter and keep its own.
POLICIES.update(
    {
        ("GET", "/api/v1/frameworks"): Needs.MEMBER,
        ("POST", "/api/v1/frameworks"): Needs.CONFIGURE,
        ("GET", "/api/v1/frameworks/{key}"): Needs.MEMBER,
        ("PATCH", "/api/v1/frameworks/{key}"): Needs.CONFIGURE,
        ("GET", "/api/v1/frameworks/{key}/requirements"): Needs.MEMBER,
        ("GET", "/api/v1/frameworks/{key}/coverage"): Needs.MEMBER,
        ("POST", "/api/v1/frameworks/{key}/requirements"): Needs.CONFIGURE,
        ("POST", "/api/v1/frameworks/{key}/requirements/paste"): Needs.CONFIGURE,
        ("GET", "/api/v1/frameworks/{key}/requirement"): Needs.MEMBER,
        ("PATCH", "/api/v1/frameworks/{key}/requirement"): Needs.CONFIGURE,
        ("DELETE", "/api/v1/frameworks/{key}/requirement"): Needs.CONFIGURE,
    }
)

# Scopes. As with every record, any member may ask, and the service decides by the scope:
# whose unit it is in, and who owns it.
POLICIES.update(record_policies("scopes", links=False))
POLICIES.update(
    {
        ("PUT", "/api/v1/scopes/{ref}/members"): Needs.MEMBER,
        ("PUT", "/api/v1/scopes/{ref}/frameworks"): Needs.MEMBER,
        ("DELETE", "/api/v1/scopes/{ref}/frameworks/{key}"): Needs.MEMBER,
        ("GET", "/api/v1/scopes/{ref}/requirements"): Needs.MEMBER,
        ("PUT", "/api/v1/scopes/{ref}/requirements"): Needs.MEMBER,
        ("GET", "/api/v1/scopes/{ref}/controls"): Needs.MEMBER,
        ("PUT", "/api/v1/scopes/{ref}/controls"): Needs.MEMBER,
        ("GET", "/api/v1/scopes/{ref}/controls/candidates"): Needs.MEMBER,
        ("GET", "/api/v1/scopes/{ref}/controls/offered"): Needs.MEMBER,
        ("POST", "/api/v1/scopes/{ref}/controls/inherited"): Needs.MEMBER,
        ("DELETE", "/api/v1/scopes/{ref}/controls/{implementation_id}"): Needs.MEMBER,
    }
)

# Evidence. Anyone may add it for a unit they work in; who sees an item, and its file, is
# decided by the item.
POLICIES.update(
    {
        ("GET", "/api/v1/evidence"): Needs.MEMBER,
        ("POST", "/api/v1/evidence"): Needs.MEMBER,
        ("GET", "/api/v1/evidence/{ref}"): Needs.MEMBER,
        ("PATCH", "/api/v1/evidence/{ref}"): Needs.MEMBER,
        ("PUT", "/api/v1/evidence/{ref}/owners"): Needs.MEMBER,
        ("GET", "/api/v1/evidence/{ref}/history"): Needs.MEMBER,
        ("PUT", "/api/v1/evidence/{ref}/subjects"): Needs.MEMBER,
        ("POST", "/api/v1/evidence/{ref}/file"): Needs.MEMBER,
        ("GET", "/api/v1/evidence/{ref}/file"): Needs.MEMBER,
        ("GET", "/api/v1/evidence-for/{ref}"): Needs.MEMBER,
    }
)

# Assessments and tests. Any member may ask; the services decide who may plan, record, and
# review, and nobody does so for a control they own.
POLICIES.update(
    {
        ("GET", "/api/v1/assessments"): Needs.MEMBER,
        ("POST", "/api/v1/assessments"): Needs.ASSESS,
        ("GET", "/api/v1/assessments/{ref}"): Needs.MEMBER,
        ("PATCH", "/api/v1/assessments/{ref}"): Needs.MEMBER,
        ("PUT", "/api/v1/assessments/{ref}/owners"): Needs.MEMBER,
        ("GET", "/api/v1/assessments/{ref}/history"): Needs.MEMBER,
        ("POST", "/api/v1/assessments/{ref}/tests"): Needs.MEMBER,
        ("POST", "/api/v1/assessments/{ref}/completion"): Needs.MEMBER,
        ("POST", "/api/v1/assessments/{ref}/cancellation"): Needs.MEMBER,
        ("PATCH", "/api/v1/tests/{test_id}"): Needs.MEMBER,
        ("DELETE", "/api/v1/tests/{test_id}"): Needs.MEMBER,
        ("POST", "/api/v1/tests/{test_id}/results"): Needs.ASSESS,
        ("POST", "/api/v1/results/{result_id}/review"): Needs.ASSESS,
    }
)

# Issues and exceptions. Any member may ask, and may say that something is wrong; the
# services decide the rest. Confirming a closure, withdrawing an issue, and reopening one are
# the second line's. Nobody confirms their own closure or decides their own request.
POLICIES.update(
    {
        ("GET", "/api/v1/issues"): Needs.MEMBER,
        ("POST", "/api/v1/issues"): Needs.MEMBER,
        ("GET", "/api/v1/issues/{ref}"): Needs.MEMBER,
        ("PATCH", "/api/v1/issues/{ref}"): Needs.MEMBER,
        ("PUT", "/api/v1/issues/{ref}/owners"): Needs.MEMBER,
        ("GET", "/api/v1/issues/{ref}/history"): Needs.MEMBER,
        ("PUT", "/api/v1/issues/{ref}/subjects"): Needs.MEMBER,
        ("POST", "/api/v1/issues/{ref}/actions"): Needs.MEMBER,
        ("POST", "/api/v1/issues/{ref}/due-date"): Needs.MEMBER,
        ("POST", "/api/v1/issues/{ref}/closure"): Needs.MEMBER,
        # Assessors and managers confirm closures; auditors confirm their own findings.
        ("POST", "/api/v1/issues/{ref}/validation"): Needs.MEMBER,
        ("POST", "/api/v1/issues/{ref}/cancellation"): Needs.ASSESS,
        ("POST", "/api/v1/issues/{ref}/reopening"): Needs.ASSESS,
        ("GET", "/api/v1/scopes/{ref}/plan-of-action"): Needs.MEMBER,
        ("GET", "/api/v1/exceptions"): Needs.MEMBER,
        ("POST", "/api/v1/exceptions"): Needs.MEMBER,
        ("GET", "/api/v1/exceptions/{ref}"): Needs.MEMBER,
        ("PATCH", "/api/v1/exceptions/{ref}"): Needs.MEMBER,
        ("GET", "/api/v1/exceptions/{ref}/history"): Needs.MEMBER,
        ("POST", "/api/v1/exceptions/{ref}/decision"): Needs.MEMBER,
        ("POST", "/api/v1/exceptions/{ref}/withdrawal"): Needs.MEMBER,
        ("GET", "/api/v1/notices"): Needs.MEMBER,
        ("GET", "/api/v1/notices/count"): Needs.MEMBER,
        ("POST", "/api/v1/notices/read"): Needs.MEMBER,
    }
)

# Import and export. An export is the list its asker could already see, and is recorded.
# Records are imported by those who could add them by hand, a row at a time by the same
# service; requirements by those who shape the program.
POLICIES.update(
    {
        ("GET", "/api/v1/exports/{kind}"): Needs.MEMBER,
        ("POST", "/api/v1/imports/records/{path}/columns"): Needs.STEWARD,
        ("POST", "/api/v1/imports/records/{path}"): Needs.STEWARD,
        ("POST", "/api/v1/imports/requirements/{key}/columns"): Needs.CONFIGURE,
        ("POST", "/api/v1/imports/requirements/{key}"): Needs.CONFIGURE,
    }
)

# Reporting: every figure counts only what the asker may see.
POLICIES.update(
    {
        ("GET", "/api/v1/home"): Needs.MEMBER,
        ("GET", "/api/v1/compliance"): Needs.MEMBER,
        ("GET", "/api/v1/graph/{ref}"): Needs.MEMBER,
        # Every change in one place is for those who may read everything.
        ("GET", "/api/v1/history"): Needs.READ_ALL,
        ("GET", "/api/v1/heat-map"): Needs.MEMBER,
        ("GET", "/api/v1/dashboard"): Needs.MEMBER,
    }
)


def allowed(principal: Principal | None, needs: Needs) -> bool:
    if needs is Needs.PUBLIC:
        return True
    if principal is None:
        return False
    return {
        Needs.MEMBER: True,
        Needs.ASSESS: principal.assesses,
        Needs.STEWARD: principal.stewards or principal.manages_somewhere,
        Needs.LEAD: principal.leads,
        Needs.MANAGE: principal.manages,
        Needs.CONFIGURE: principal.configures,
        Needs.READ_ALL: principal.reads_all,
        Needs.AUDIT: principal.has(roles.AUDITOR),
        Needs.ADMIN: principal.is_admin,
    }[needs]


# Judgments a named person makes, with their name on them: rating, accepting, deciding,
# confirming, approving, signing off, publishing. A token acts as a role, never as a person,
# so it may not make them; and a person's second pair of eyes cannot be a token.
PERSON_ONLY = frozenset({
    ("POST", "/api/v1/risks/{ref}/assessments"),
    ("POST", "/api/v1/risks/{ref}/acceptances"),
    ("POST", "/api/v1/acceptances/{acceptance_id}/withdrawal"),
    ("POST", "/api/v1/controls/{ref}/ratings"),
    ("POST", "/api/v1/tests/{test_id}/results"),
    ("POST", "/api/v1/results/{result_id}/review"),
    ("POST", "/api/v1/issues/{ref}/validation"),
    ("POST", "/api/v1/exceptions/{ref}/decision"),
    ("POST", "/api/v1/documents/{ref}/draft/decision"),
    ("POST", "/api/v1/documents/{ref}/draft/publish"),
    ("POST", "/api/v1/sessions/{ref}/items/{item_id}/decision"),
    ("POST", "/api/v1/program/publish"),
    ("POST", "/api/v1/audit/plans/{ref}/approve"),
    ("POST", "/api/v1/audit/requests/{request_id}/accept"),
    ("POST", "/api/v1/workpapers/{paper_id}/sign-off"),
    ("POST", "/api/v1/review-notes/{note_id}/clear"),
    ("POST", "/api/v1/reviews/{ref}/conclude"),
    ("POST", "/api/v1/incidents/{ref}/triage"),
    ("PUT", "/api/v1/incidents/{ref}/case"),
    ("POST", "/api/v1/reported/{report_id}/confirm"),
    ("POST", "/api/v1/reported/{report_id}/set-aside"),
    ("POST", "/api/v1/drafts/{draft_id}/use"),
    ("POST", "/api/v1/drafts/{draft_id}/set-aside"),
    ("POST", "/api/v1/privacy/reviews/{item_id}"),
})  # fmt: skip


def authorize(request: Request) -> None:
    """The app-wide dependency: look the matched route up in the table and check it."""
    route = request.scope.get("route")
    path = getattr(route, "path", "")
    if not path.startswith("/api/"):
        return  # the web app's own files
    needs = POLICIES.get((request.method, path))
    if needs is None:
        raise HTTPException(403, "This route has no access policy.")
    principal: Principal | None = getattr(request.state, "principal", None)
    if (
        principal is not None
        and principal.token_id is not None
        and ((request.method, path) in PERSON_ONLY)
    ):
        raise HTTPException(403, "This is a judgment a named person makes, not a token.")
    if allowed(principal, needs):
        return
    if principal is None:
        raise HTTPException(401, "Sign in to continue.")
    raise HTTPException(403, "Your role does not allow this.")


def current(request: Request) -> Principal:
    """The signed-in person, for routes that the table says need one."""
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(401, "Sign in to continue.")
    return principal
