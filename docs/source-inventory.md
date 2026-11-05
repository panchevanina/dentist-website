# Source inventory and migration decisions

Historical record of the original two prototypes. The current selected Bulgarian production site is documented in [production-refinement.md](production-refinement.md) and [production-verification.md](production-verification.md).

Audited on 5 November 2026 from https://panchevadentist-varna.com/ and its directly linked practice/treatment pages. This document records the source as published; it does not independently verify clinical claims or current business policies.

## Coverage in both designs

| Original information | Destination |
| --- | --- |
| Welcome, comfort after anaesthesia, high-quality materials, experienced laboratory, continuing education | Homepage introduction and About section in BG/EN/RU/DE |
| Crowns and bridges; metal-ceramic, ceramic and zirconia; temporary bridges; endocrowns and three clinical cases | Treatment library → crowns |
| Aesthetic composite fillings and clinical stages | Treatment library → fillings |
| Ceramic inlays/onlays, models, placement sequences and case photographs | Treatment library → inlays |
| Periodontitis, all eight symptoms, intensive and supportive therapy, five comparisons | Treatment library → gums |
| Extraction, bone preservation and upper/lower wisdom teeth; maxillofacial specialist and local anaesthesia | Treatment library → extraction |
| Bonding indications and comparison with veneers | Treatment library → bonding |
| Whitening duration, Opalescence link, sensitivity, repeat interval, two-week aftercare and examples | Treatment library → whitening |
| Sealants, six-month checks, GC Fuji TRIAGE link and product statements | Treatment library → sealants |
| everStick/StickTech, adhesive bridges, splinting, posts, retainers and two cases | Treatment library → fibres |
| Veneer thickness, four groups of indications and material comparison | Treatment library → veneers |
| Tartar above/below gums, gingivitis and periodontitis, ultrasonic/Air Flow/polishing, hygiene demonstration and six-month prevention | Treatment library → cleaning |
| Primary/secondary caries, progression, prevention and restorations | Treatment library → caries |
| Pulpitis, periodontitis/granulomas, instruments, X-ray control, retreatment and healing | Treatment library → root-canals |
| Implants, osseointegration, abutments/bridges, quality, preparatory surgery and recovery description | Treatment library → implants |
| Sinus lift, bone dimensions, sinus anatomy, nerve repositioning, ridge split, chin graft and operative photos/notice | Treatment library → sinus-lift |
| Aesthetic dentistry, prosthetic dentistry and surgery category pages plus linked standalone articles | Library category index and expandable supplementary original pages |
| Nina Pancheva biography: 2008 graduation, practice since 2012, 2013–2014 assistantship for three semesters, four continuing-education areas | Homepage doctor section in all languages |
| All 10 certificate images | Gallery → certificates, full resolution available |
| Seven reasons: experience, materials, anaesthesia, NHIF, five-year guarantee and conditions, response to pain, payments | Homepage principles and contact sections |
| Five testimonials, original initials, ages and Varna attribution | All five shown in a horizontally browsable row; translated quotations preserve meaning |
| Two homepage before/after comparisons and the original clinical illustrations | Homepage before/after pairs and complete treatment library |
| All 38 images from the standalone gallery | Gallery in every language |
| Telephone, email, full address including floor/room/postcode, Monday–Friday 10:00–19:00 | Header, contact section and footer links |
| Facebook, product links and map destination | Explicit external links; no third-party content loaded automatically |
| Contact fields: name, telephone, email, callback date/time and message | Static email preparation form with clear confirmation explanation |
| BG/RU/EN/DE language access | Four complete static page sets per design |
| WordPress cookie descriptions | Historical notice archived in original-privacy-notice.txt; new privacy page describes actual static behavior |

The preservation check compares the entire original Bulgarian text of all 15 treatment topics and all 10 supplementary sections against each design's generated treatment library. It also verifies every gallery/certificate original is linked. All 253 unique source image URLs were downloaded; the URL-to-file map is in `asset-manifest.json`. Large original images are retained, with smaller display derivatives.

## Source pages audited

- `/` — Bulgarian homepage and embedded full service articles.
- `/en/home/`, `/ru/начало/`, `/de/startseite/` — existing language pages.
- `/estetichna-stomatologia/`, `/protetichna-stomatologia/`, `/hirurgia/` — category pages.
- `/cirkonievi-koronki/`, `/estetichni-plombi/`, `/faceti/`, `/izbelvane-na-zybi/` — aesthetic detail pages.
- `/keramichni-inlei/`, `/koronki-i-mostove/` — prosthetic detail pages.
- `/sinus-lift/`, `/vadene-na-zyb/` — surgical detail pages.
- `/kvalifikacii/`, `/de/qualifikationen/` — biography and certificates.
- `/snimki/` — full gallery.
- `/our-blog/`, `/sample-page/` — placeholder destinations linked from the English template; no substantive practice content found.

## Approved handling of discrepancies

The user approved both designs and instructed: “Use translations of the Bulgarian practice content; keep a record of the discrepancies.”

The English and Russian pages contain “Welcome to Dentist” template content, empty hero headings, an empty/unfinished service section and claims including **24 Hour Emergency Service**, **15 Years of Experience**, **Offering Sedation Services**, **Invisalign Premier Provider**, **Work with Most Insurance Plans**, and **Flexible Payment Options**. These do not match the Bulgarian practice text, which lists seven different reasons and specific payment methods. They were replaced with translations of Bulgarian information, rather than republished as confirmed services. The original language-page text is preserved in `original-language-content.txt` for reference.

The linked blog contains a lorem ipsum post dated June 2015 and the standard WordPress “Hello world!” post dated October 2014. The sample page has no substantive practice information. Their template/sample nature is recorded here; a blog was not invented for the redesign.

The German site has 13 translated treatment articles, omitting implants and the separately linked sinus-lift article. The original German treatment content was preserved; those two missing articles were translated from the Bulgarian information. English/Russian treatment text is translated and restructured for readability, with the full Bulgarian originals and clinical captions still available under each article. Supplementary category/detail-page copies remain explicitly labelled Bulgarian because they duplicate the complete library rather than representing separate new treatments.

The source advertises **13 years of experience** while also specifying graduation in **2008** and independent practice since **2012**. The redesign retains the published number, dates and five-year guarantee conditions; it does not invent a new experience total or assume the policy has changed. The source's Monday–Friday 10:00–19:00 opening hours, NHIF participation and payment methods are likewise retained as published. These dated practice statements should be confirmed by the owner before a future public replacement.

The original site has WordPress consent-plugin descriptions for six cookie categories and eleven-month consent cookies. The new static site does not use that plugin or its cookies. Its privacy page reflects the implemented behavior, and the historical notice is archived instead of presenting obsolete tracking descriptions as current facts. The original ©2021 credit is retained in this audit; the new design footer uses ©2026 PANCHEVA DENTIST.
