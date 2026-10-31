# NSP Portal Validation Report

**Checkpoint:** 0 (portal reconnaissance)
**Date of reconnaissance:** 31 October 2026
**Target:** https://scholarships.gov.in/
**Status:** PARTIAL. Public homepage verified. Everything else is listed as UNVERIFIED and must be checked by a human on a normal network before browser automation is enabled.

## 1. How this was done, and its limits

| Method | Result |
|---|---|
| Fetched the NSP homepage | Succeeded. Findings in section 2. |
| Fetched `/All-Scholarships` and `/allschemesdomicile` | Blocked by the research tool (URLs not returned by search). Not inspected. |
| Searched for the scheme catalogue | Only third-party pages and college notices were returned. None are authoritative. |
| Fetched login, OTR, application form, Terms, robots.txt | Not attempted. Not inspected. |
| Sandbox network access to scholarships.gov.in | Not in the sandbox allow-list, so live discovery code could not be run here. |

Nothing below about the application form, authentication flow, DOM structure or terms of use has been observed.

## 2. Verified from the NSP homepage (retrieved 2026-10-31)

- **Portal is open for AY 2026-27 from 1 June 2026.**
- **Renewal window (announcement banner):** PM-USP CSSS (Merit Based) and PM-USP Special Scholarship Scheme for J&K and Ladakh renewals are open. Student application closes **31-10-2026** (today). Institute verification closes **15-11-2026**. L2 verification closes **30-11-2026**.
- **Application cap:** students may apply for one merit-based scheme and one or more welfare-based schemes from AY 2026-27, subject to scheme eligibility.
- **One Time Registration (OTR):** a 14-digit number, required to apply since AY 2024-25, generated using Aadhaar or Aadhaar Enrolment ID. The NSP OTR mobile app is used for it.
- **Face authentication** (UIDAI AadhaarFaceRD) is part of OTR. The homepage warns about error 904 and Aadhaar biometric lock.
- **CSC route exists** for OTR and application filing (stated fee Rs 30).
- **Accessibility controls and a virtual assistant (Vani)** are present on the page.

## 3. Implications for the spec

1. **Deadline pressure.** As of retrieval, the student deadline for the announced renewal schemes is the same day. Discovery must show deadlines with retrieval timestamps and must never present a past-deadline scheme as open.
2. **Identity gating.** OTR depends on Aadhaar and biometric/face authentication, which must be done by the student. This matches spec rules 8.5 and 9.2. SevaAgent must not collect Aadhaar numbers or automate any step of OTR.
3. **Renewal vs fresh.** The homepage announcement concerns renewals. Fresh-application availability per scheme has to be checked per scheme.
4. **Mobile app dependency.** OTR is done through the NSP OTR app, which cannot be automated by Playwright.

## 4. Unverified items (human checkpoint required)

Check each on a normal browser and record the answer here before building the authenticated agent.

| # | Item | Status |
|---|---|---|
| 1 | Scheme catalogue pages (`/All-Scholarships`, domicile-wise list) and whether they list AY, deadlines, guideline PDFs | UNVERIFIED |
| 2 | Per-scheme eligibility text and official guideline PDF links | UNVERIFIED |
| 3 | Login flow after OTR (credentials, CAPTCHA, OTP) | UNVERIFIED |
| 4 | Application form structure, field labels, upload requirements | UNVERIFIED |
| 5 | Terms of use and any clause restricting automated access or scraping | UNVERIFIED |
| 6 | robots.txt and rate limit expectations | UNVERIFIED |
| 7 | Whether acknowledgement/reference pages are shown after submission and what they look like | UNVERIFIED |
| 8 | Whether a public API or open data feed exists for scheme data | UNVERIFIED |

## 5. Decision

The spec (section 9.4) says: if automation is restricted or not safely testable, build discovery, eligibility, document preparation and a human-operated portal handoff instead.

Given what is and is not verified:

- **Authenticated browser automation: NOT ENABLED.** It stays behind a feature flag (`ENABLE_PORTAL_AUTOMATION=false`). It must not be switched on until items 3, 4, 5 and 7 above are resolved by a person.
- **Public-page discovery: allowed to build**, but it must be polite (identify itself, rate-limit, cache, honour robots.txt) and be confirmed against item 5 before production use.
- **Eligibility: built against an admin-approved rule store.** Rules are entered with a source URL and marked verified only by a human. The repo ships **no** invented scheme rules. The demo rule file is clearly marked as a test fixture.
- **Handoff mode** is the default for the portal step.

## 6. Third-party sources seen (not authoritative, not used as rule sources)

Buddy4Study, Careers360, college notices and similar pages repeat the 1 June 2026 opening and a 31 October 2026 deadline for most post-matric schemes. They disagree on details (for example some pre-matric deadlines) and are not an authority. Use them only as leads to find the official source.
