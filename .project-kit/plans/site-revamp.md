# Plan: Pancheva dental practice website redesign

Status: complete

## Outcome and scope

Recreate https://panchevadentist-varna.com as two distinct responsive designs in HTML, CSS, and vanilla JavaScript. Preserve the source site's information, treatment details, clinical examples, practice/gallery images, qualifications, contacts, external links, and existing language coverage. Deliver locally in this workspace with a comparison entry page and instructions for GitHub Pages. Do not commit, push, replace the live website, or publish a hosted Site.

## Approach and decisions

- Version 1, **Sea Glass**: bright coastal palette, teal accents, contemporary sans-serif typography, airy composition, and image-led introduction.
- Version 2, **Atelier**: warm ivory, deep green, editorial serif headings, stronger typographic hierarchy, and a different page composition/navigation.
- Use relative asset paths and no framework, build step, backend, or runtime dependencies. Share preserved content/assets where useful while keeping each version selectable and independently deployable with documented files.
- Audit the Bulgarian source and its English, Russian, and German links, including linked biographies/qualifications, galleries, footer information, forms, and available policy pages before implementation. Track source-to-destination coverage.
- Preserve facts and substantive information. Do not invent reviews, statistics, prices, opening hours, credentials, or medical claims. Clearly record unavailable source content/assets and any dated or inconsistent source facts.
- Contact actions use the practice's existing telephone, email, and map destination. A static contact flow must make its actual behavior clear; it must not claim to submit or confirm an appointment without a backend.
- Follow applicable project rules. No nested AGENTS or Cursor rules were found. The multi-git configuration currently defines no repository IDs; no Git mutation is planned.

## Steps and progress

- [x] Audit source pages and assets; record a content inventory and coverage checklist.
- [x] Obtain explicit agreement on this plan before dependent implementation.
- [x] Build two complete designs and a comparison page; preserve full content and language access.
- [x] Verify static links/assets/content coverage/syntax and standalone HTTP paths. Browser discovery found no available browsers, so rendered layout and interactions remain an explicitly recorded verification limit.
- [x] Document local preview and GitHub Pages deployment; update project state/usage instructions.
- [x] Conduct a separate read-only final file review. Reported one P3 language-metadata issue, obtained explicit approval, applied the narrow fix, rechecked/refreshed exports and completed a read-only re-review with no further findings.

## Validation

Use automated static checks for local links/assets and source coverage, plus browser QA at desktop/mobile sizes if the available browser can connect. Check treatment detail access, gallery/lightbox operation, menus, language navigation, and telephone/email/map actions. Record executed checks and any verification limits honestly.

## Deployment / rollback

Prepare repository files and GitHub Pages instructions only. Hosting will be performed after the user chooses a version and explicitly requests publication. Files are additive to an initially empty application workspace; preserve all existing project-kit files. No database work is needed.

## Agreement and changes

- Agreement: user replied “Agree—build both versions” on 2026-11-05.
- Content decision: user replied “Use translations of the Bulgarian practice content; keep a record of the discrepancies.” English/Russian demo service claims and placeholder blog/sample content will be recorded in the audit rather than republished as practice facts.
- Review-fix agreement: on 2026-11-05 the user approved “fix and refresh both versions” for the reported screen-reader language metadata issue. Completed and re-reviewed.
- Material revisions: none.


## Subsequent selected-design refinement

The user's 2026-11-05 follow-up selected option 1 and requested a Bulgarian-only production frontend, four new services and specific removals. This completed follow-up supersedes the comparison/multilingual frontend and enquiry form in the original delivery. See [production-refinement task](../tasks/production-refinement.md).
