# Production refinement — selected Sea Glass design

Status: complete. Scope is explicitly requested by the user on 2026-11-05; routine changes to the approved static site, with no new backend, deployment or Git operation.

- Promote option 1 with a white background as the production homepage, entirely in Bulgarian. Preserve the existing practice information except the explicitly requested removals.
- Add four image-led services and full Bulgarian articles: iTero Element Plus, Invisalign, Zimmer implants and Spark aligners. Download the supplied imagery locally and ground clinical descriptions in manufacturer information. Record product/image sources; do not infer provider credentials or unsupported global rankings.
- Change the monogram to capital N, update the patient-feedback label, remove Facebook, appointment CTAs, payment information, the comparison link and the non-submitting enquiry form.
- Use the supplied Google Maps place URL and postal code 9009. Retain existing floor/room information for the same street address.
- Keep the earlier prototypes as unlinked development references; the production export contains only the four Bulgarian pages and their assets. Refresh the Bulgarian option-1 paths for existing preview links.
- Verify source coverage, all 19 services, local assets and links, requested removals, address/schema consistency, JavaScript syntax, HTTP paths and the standalone archive. Attempt browser QA if a browser is available. Perform the required separate read-only final review after implementation and checks.

Related: [original approved plan](../plans/site-revamp.md). The user's current detailed change request supersedes the earlier multilingual/comparison frontend and email-preparation form.


Completion: root Bulgarian site and selected preview URLs updated; final package is `/tmp/pancheva-dentist-production.zip`. Static/content/image/syntax/HTTP/export integrity checks pass. Separate read-only review found no new reportable defects. Browser discovery returned no available browser, so visual and interaction QA remains explicitly unverified. Evidence: [production verification](../../docs/production-verification.md).
