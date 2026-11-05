# Verification record

Historical record of the original two prototypes. The current selected Bulgarian production site is documented in [production-refinement.md](production-refinement.md) and [production-verification.md](production-verification.md).

5 November 2026. Scope: comparison page, Sea Glass, Atelier and both standalone exports.

## Executed checks

| Check | Result |
| --- | --- |
| `python3 scripts/build.py` | Generated 32 static HTML pages: two designs × four languages × homepage/treatments/gallery/privacy. |
| `python3 scripts/check.py` | PASS: 33 pages, 5,400 local links/assets, unique IDs, one H1 per page, document languages, alternate-language links, local font/CSS assets and anchors. |
| Original-text preservation | PASS: all 15 complete Bulgarian treatment texts and all 10 supplementary source sections occur in each design's treatment library. |
| Image/certificate preservation | PASS: all 38 gallery originals and 10 certificates are linked in both designs; all 253 source images are present. |
| EN/RU article coverage | PASS: all 15 treatment IDs have translated content. Four homepage languages each have 15 names/summaries and all seven practice principles. |
| `node --check assets/site.js` | PASS. |
| Python compilation of build/check/package/http_smoke scripts | PASS. |
| Image decoding with Pillow | PASS: 253 original images verified; 253 WebP display derivatives generated. Largest original image is 4.95 MB. |
| Local font glyph checks | PASS: all seven font files contain the tested Cyrillic characters БЖЩюя; SIL OFL license texts included. |
| `python3 scripts/http_smoke.py` | PASS: 33 pages and 419 unique page/asset paths served HTTP 200 beneath `/pancheva/`, with correct HTML MIME types. Temporary server stopped. |
| Standalone Sea Glass static check | PASS: 16 pages and 2,683 local references. |
| Standalone Atelier static check | PASS: 16 pages and 2,699 local references. |
| Standalone Sea Glass HTTP check | PASS: 16 pages and 400 unique paths beneath `/pancheva/`. |
| Standalone Atelier HTTP check | PASS: 16 pages and 399 unique paths beneath `/pancheva/`. |
| Summary language regression check | PASS: all 170 original-text/supplementary toggle labels use their page language while the original content remains marked Bulgarian. |
| ZIP integrity | PASS: both archives contain 538 files, including 16 HTML pages; no CRC errors. Each archive is approximately 65.6 MB because full-resolution original imagery is retained. |

Standalone artifacts:

- `/tmp/pancheva-delivery/sea-glass/` and `/tmp/pancheva-delivery/sea-glass.zip`
- `/tmp/pancheva-delivery/atelier/` and `/tmp/pancheva-delivery/atelier.zip`

All source edits are in the shared workspace. No repository IDs are configured in the project kit's multi-git configuration, so no Git status/diff, commit, push or publication was performed. The final review uses the complete new application file set and the changed project-kit documents in place of a Git diff.

## Verification limits

The Browser skill was read, the browser runtime was connected, and browser discovery returned no available browsers. Its prescribed troubleshooting confirmed an empty browser list. No alternative browser automation was installed or used.

Consequently, desktop/mobile screenshots, actual layout rendering, keyboard navigation, menu clicks, treatment filtering/search in a real DOM, dialog focus/keyboard behavior and interaction with a configured email application have **not** been exercised in a browser. Static checks and HTTP checks do not establish those behaviors. Those are the remaining manual checks before a public replacement.

Source medical descriptions and dated practice claims were preserved, not independently clinically assessed. The content inventory records the 13-year experience claim, historical dates, guarantee, opening hours and template-language discrepancies for owner review.

## Final read-only review

The initial read-only review found one P3 accessibility defect in `scripts/build.py`: the translated original-text and supplementary-page summaries inherited Bulgarian language metadata. This could cause incorrect screen-reader pronunciation. The finding was reported before edits; the user explicitly approved “fix and refresh both versions.”

The narrow fix adds the page language to the summary labels while retaining Bulgarian metadata on the original body content. A focused checker now covers these labels. Regeneration, static/content checks, Python compilation and both standalone checks passed. Both refreshed ZIPs pass CRC checks and match their exported files byte for byte.

The second read-only review examined the generator/checker changes and all 538 files in each export. Only four treatment HTML files per export differ from the previously checked exports, and those differences consist solely of the corrected summary language attributes. All asset bytes and paths are unchanged. The prior HTTP repository-prefix results therefore remain applicable; HTTP tests were not needlessly repeated after this metadata-only correction.

No further findings were identified in the resulting change. Browser rendering and interaction checks remain unverified, as described above.
