# iOS App Naming — OSINT Legal Due Diligence

**Subject:** Name clearance research for a self-hosted iOS companion app to the open-source `printix-mcp` Docker MCP server.
**Developer:** Marcus Nimtz (Germany).
**Primary markets:** DE / EU. **Secondary:** US / global.
**Note on "Printix":** Printix is a registered trademark of Tungsten Automation Corp. It is **not** used in any candidate app name; it would appear only as a compatibility reference (e.g. "works with Printix Cloud Print") in the App Store subtitle/keywords, which raises separate App Store Review considerations (see end of report).
**Date of research:** 2026-06-27.
**Method:** Public OSINT only — web search, public App Store pages, WHOIS, vendor websites. Paid trademark databases were not used. WIPO Global Brand Database, USPTO TESS, EUIPO eSearch+, and DPMA Register all gate their search UIs behind JavaScript / CAPTCHA and could not be queried headlessly in this pass; findings below are therefore based on indirect signals (vendor marketing pages, App Store listings, secondary trademark aggregators referenced in search results). **A direct database check at USPTO / EUIPO / DPMA by a human or attorney remains required before commercial publication.**

---

## MySecurePrint

### Verdict: 🟡 Yellow — descriptive composite with a crowded adjacent field

The name combines a possessive prefix ("My") with two industry-generic feature terms ("Secure Print"). No direct collision with an existing app of that exact name was found on the iOS App Store, Google Play, or in web search. However, "Secure Print" is a long-standing **descriptive feature term** used by virtually every printer OEM (HP, Konica Minolta, Brother, Lexmark, Toshiba, Xerox, MyQ, PaperCut, Printix itself) and appears in several existing app names ("Secure Print" by Shanghai NextCont; "PaperCut Hive – Secure Print"; "Consult: Secure Print" by Konica Minolta; "HP JetAdvantage Secure Print"; "SafePrint" by Selbetti). The descriptiveness of "Secure Print" cuts both ways: it is hard for any third party to monopolise the phrase as a wordmark, but it also weakens the distinctiveness — and therefore the trademark protectability — of any composite built on it. The "My" prefix is a common but weak distinguishing element.

### Trademark Findings
| Jurisdiction | Database | Hit on "MySecurePrint" | Owner | Status | Risk |
|---|---|---|---|---|---|
| US | USPTO TESS | Not directly verified (CAPTCHA-gated); no public secondary-source hit found | — | — | Low–Med (unverified) |
| EU | EUIPO eSearch+ | Not directly verified (CAPTCHA-gated); no public secondary-source hit found | — | — | Low–Med (unverified) |
| DE | DPMA Register | Not directly verified; no public secondary-source hit found | — | — | Low–Med (unverified) |
| WO | WIPO Global Brand DB | Not directly verified (CAPTCHA-gated) | — | — | Low–Med (unverified) |

Adjacent registered marks that the developer should be aware of (these are NOT collisions with "MySecurePrint" but are part of the crowded field): **HP JetAdvantage Secure Print** (HP Inc.), **Consult: Secure Print** (Konica Minolta), **PaperCut Hive Secure Print** (PaperCut Software), **SafePrint** (Selbetti Gestão de Documentos).

### App Store Findings
| Store | Country | App name | Developer | Risk |
|---|---|---|---|---|
| Apple App Store | US/DE | No exact "MySecurePrint" hit | — | — |
| Apple App Store | US | Secure Print | Shanghai NextCont Information Technology Co., Ltd. | Low (different name, same field) |
| Apple App Store | US | HP JetAdvantage Secure Print | HP Inc. | Low (different name) |
| Apple App Store | US | PaperCut Hive – Secure Print | PaperCut Software | Low (different name) |
| Apple App Store | US | Consult: Secure Print | Konica Minolta Business Solutions U.S.A., Inc. | Low (different name) |
| Apple App Store | US | SafePrint | Selbetti Gestão de Documentos S.A. | Low (different name, similar concept) |
| Google Play | — | No exact "MySecurePrint" hit | — | — |

### Domain Availability
| Domain | Status | Owner/Use | Risk |
|---|---|---|---|
| mysecureprint.com | Registered 2025-11-29 via Namecheap, behind Cloudflare nameservers | Unknown (recent registration, no public site observed) | Med — recent third-party registration suggests someone else is sitting on it; could complicate domain acquisition and may indicate parallel branding intent |
| mysecureprint.de | Free (per DENIC whois "Status: free") | Unregistered | Low |

### Web Confusion Risk
"Secure Print" is the de-facto generic name for the print-release feature on every major MFP brand. End-users searching "secure print" + iOS find a dozen vendor-branded apps. A new "MySecurePrint" would compete for that search term against established corporate brands. There is meaningful **consumer-confusion risk** (users may assume affiliation with an OEM offering) and **descriptiveness risk** (the mark is weak and harder to defend / register as a wordmark on its own).

### Mitigation Recommendations
- Run a direct human search of DPMA, EUIPO, and USPTO databases before launch — the CAPTCHA-gated checks in this review were not completed.
- If pursued, consider DPMA wordmark registration in Nice classes 9 (downloadable software) and 42 (SaaS). DPMA basic fee: 290 EUR for up to 3 classes via DPMAdirektWeb; +100 EUR per additional class.
- The .com domain being freshly registered to an unknown party is a real friction point — try to acquire it or accept .de-only branding.
- Strongly disclaim affiliation with HP, Konica Minolta, Brother, Lexmark, PaperCut and Printix in App Store description and on any landing page.
- Consider a more distinctive coined element (the current name is essentially three generic words concatenated).

---

## PrintBridge

### Verdict: 🔴 Red — multiple active commercial users of the exact name in the same product field

This name has the **highest collision risk of the four**. "PrintBridge" is already in active commercial use by at least two independent vendors operating in the iOS / printing space, plus a long-standing domain registration:

1. **PrintBridge** at `printbridgeair.com` — a Windows-side service that turns any printer into an AirPrint printer for iOS / iPad / Mac. Direct functional overlap with the proposed app's domain (iOS + non-AirPrint printers + Windows host). Footer explicitly disclaims Apple affiliation, suggesting some IP awareness on their side.
2. **PrintBridge** at `printbridge.app` — a localhost REST API for silent printing from web apps, developed by **Virtex Solutions** ("Making printers behave since 2024"). Different technical niche (web-to-printer) but identical wordmark.
3. **printbridge.com** — registered since 1998-09-17 (GoDaddy, SiteGround DNS), 26+ years of prior use signal.
4. **PrintBridge Technology** — referenced as an InstaLabel web-to-printer connectivity offering.
5. Adjacent and easily-confused names: **Printer Bridge** (printerbridge.com print management software), **Printer Bridge** Android app (ar.com.thinkmobile.printerbridge), **e-BRIDGE Print & Capture** and **e-BRIDGE Global Print** (Toshiba TEC, established trademark family), **ZebraNet Bridge Enterprise** (Zebra).

### Trademark Findings
| Jurisdiction | Database | Hit on "PrintBridge" | Owner | Status | Risk |
|---|---|---|---|---|---|
| US | USPTO TESS | Not directly verified (CAPTCHA-gated); multiple active commercial users found, raising likelihood of registration or common-law rights | Possibly Virtex Solutions or printbridgeair operator (unverified) | Unknown | High |
| EU | EUIPO eSearch+ | Not directly verified | — | — | Med (unverified) |
| DE | DPMA Register | Not directly verified | — | — | Med (unverified) |
| WO | WIPO Global Brand DB | Not directly verified (CAPTCHA-gated) | — | — | Med (unverified) |
| US | Toshiba "e-BRIDGE" family (adjacent, NOT a direct collision but relevant trade dress) | Yes (publicly known Toshiba mark family) | Toshiba TEC | Active | Low (different mark, related field) |

**Common-law trademark risk:** Even absent formal registration, multiple years of active commercial use of "PrintBridge" by independent vendors creates likely common-law trademark rights in their respective jurisdictions, which are sufficient to ground an opposition or infringement claim, especially in the US.

### App Store Findings
| Store | Country | App name | Developer | Risk |
|---|---|---|---|---|
| Apple App Store | US/DE | No app *named exactly* "PrintBridge" found | — | Low for collision; but printbridgeair.com is functionally targeting the same iOS-AirPrint use case |
| Apple App Store | US | e-BRIDGE Print & Capture | Toshiba TEC | Med — similar wordstem in same field |
| Apple App Store | US | e-BRIDGE Global Print | Toshiba TEC | Med — same |
| Google Play | — | Printer Bridge | thinkmobile (Argentina) | Med — near-identical name, same field |

### Domain Availability
| Domain | Status | Owner/Use | Risk |
|---|---|---|---|
| printbridge.com | Registered 1998-09-17 (active, GoDaddy/SiteGround) | Third-party holder, 26+ years | High — primary .com is unavailable for the long term |
| printbridge.de | DENIC status "connect" (registered, in use or held) | Third-party | High — primary .de also unavailable |
| printbridge.app | Active product site (Virtex Solutions) | Active competing vendor | High |
| printbridgeair.com | Active product site (Windows→AirPrint bridge) | Active competing vendor in same iOS niche | High |

### Web Confusion Risk
Very high. A user searching "PrintBridge" + iOS today finds at least two existing products in the same problem space. SEO, branding, and App Store search relevance would all start at a disadvantage. The risk of a cease-and-desist from either the printbridge.app (Virtex) or printbridgeair.com operator is non-trivial.

### Mitigation Recommendations
- **Recommend against use** unless a direct DPMA / EUIPO / USPTO check by an attorney returns clean *and* one of the active vendors confirms in writing no objection — both unlikely.
- No reasonable domain strategy is available (the .com, .de, .app, and the AirPrint-specific .com are all taken).
- If pursued anyway, the only defensible path is heavy modification (e.g. a coined suffix), which essentially means picking a different name.

---

## SecurePrintCompanion

### Verdict: 🟡 Yellow — likely free of direct collision, but descriptiveness is severe

No App Store, Play Store, or web result for an existing app or product named "SecurePrintCompanion" or "Secure Print Companion" was found. The phrase is, however, **maximally descriptive** — it literally describes "a companion app for secure print." Under DPMA, EUIPO, and USPTO doctrine, such a mark is at very high risk of being refused as descriptive / non-distinctive for Nice class 9 software whose purpose is exactly that. It also reads as a feature description more than a brand, which weakens consumer-brand recall. "Companion" is a common pattern across the App Store (e.g. countless "X Companion" apps), reducing collision risk but also reducing distinctiveness.

### Trademark Findings
| Jurisdiction | Database | Hit on "SecurePrintCompanion" | Owner | Status | Risk |
|---|---|---|---|---|---|
| US | USPTO TESS | Not directly verified; no public secondary-source hit found | — | — | Low (collision); High (descriptiveness refusal) |
| EU | EUIPO eSearch+ | Not directly verified; no public secondary-source hit found | — | — | Low (collision); High (descriptiveness refusal) |
| DE | DPMA Register | Not directly verified; no public secondary-source hit found | — | — | Low (collision); High (descriptiveness refusal) |
| WO | WIPO Global Brand DB | Not directly verified | — | — | Low (collision) |

### App Store Findings
| Store | Country | App name | Developer | Risk |
|---|---|---|---|---|
| Apple App Store | US/DE | No exact hit | — | — |
| Google Play | — | No exact hit | — | — |
| Adjacent | — | HP JetAdvantage Secure Print is *explicitly* described as a "companion mobile application" in HP's own marketing language | HP Inc. | Med — HP uses "Secure Print" + "companion" in proximity to describe their product, increasing user-confusion likelihood |

### Domain Availability
| Domain | Status | Owner/Use | Risk |
|---|---|---|---|
| secureprintcompanion.com | WHOIS reports an ACTIVE status line, but no creation/registrar details were returned (response was sparse — likely registered but with thin/private WHOIS, or a transient WHOIS server response) | Unknown | Med — needs human re-check |
| secureprintcompanion.de | Free (DENIC) | Unregistered | Low |

### Web Confusion Risk
Low–medium. No direct competitor uses the exact phrase. The risk is not collision but **brand weakness**: the name will be hard to register as a wordmark and hard to defend if registered, because it describes the product instead of identifying its source.

### Mitigation Recommendations
- If used, do not bet on getting a wordmark registration — pursue a figurative/combined mark (logo + word) instead, which is much more likely to clear DPMA's distinctiveness bar.
- Confirm secureprintcompanion.com WHOIS status with a fresh, manual check (the response in this pass was incomplete).
- Consider shortening or coining a distinct element (e.g. a portmanteau) to gain trademark distinctiveness.

---

## InkRelay

### Verdict: 🟡 Yellow — no app collision, but the wordmark is in commercial use (Alibaba) and metaphor is weak for the actual product

No iOS or Android app named "InkRelay" or "Ink Relay" was found. However, "Ink Relay" is in active commercial use on Alibaba as a supplier / brand name for **wholesale printer machine parts** (ink relays, ink pumps, ink tubes, etc.). That is a different Nice class (typically class 7 / class 9 hardware) from the proposed app (class 9 software / class 42 SaaS), so direct trademark collision risk is moderate-to-low — but not zero, because trademark protection can extend across related classes where consumer confusion is plausible, and "printer parts" plus "printer software" are arguably related.

Separately, the metaphor "Ink" + "Relay" is **a poor semantic fit** for the actual product — Printix Cloud Print typically targets enterprise MFPs and laser printers, not inkjet workflows; "ink" connotes consumables / inkjet. This is a marketing concern, not a legal one, but it weakens SEO and App Store keyword strategy.

### Trademark Findings
| Jurisdiction | Database | Hit on "InkRelay" / "Ink Relay" | Owner | Status | Risk |
|---|---|---|---|---|---|
| US | USPTO TESS | Not directly verified; no public secondary-source hit found | — | — | Low–Med (unverified) |
| EU | EUIPO eSearch+ | Not directly verified; no public secondary-source hit found | — | — | Low–Med (unverified) |
| DE | DPMA Register | Not directly verified | — | — | Low–Med (unverified) |
| WO | WIPO Global Brand DB | Not directly verified | — | — | Low–Med (unverified) |
| CN (Alibaba) | Commercial use, not necessarily registered | "Ink Relay" used as a printer-parts brand/supplier | Unknown Chinese supplier(s) | Active commercial use | Low (different class), Med (related class / cross-class confusion theory) |

### App Store Findings
| Store | Country | App name | Developer | Risk |
|---|---|---|---|---|
| Apple App Store | US/DE | No exact hit | — | — |
| Google Play | — | No exact hit | — | — |

### Domain Availability
| Domain | Status | Owner/Use | Risk |
|---|---|---|---|
| inkrelay.com | Registered 2025-08-20 via Namecheap | Unknown (recent registration, no public site observed) | Med — same pattern as mysecureprint.com: a third party recently picked it up |
| inkrelay.de | Free (DENIC) | Unregistered | Low |

### Web Confusion Risk
Low for app discovery. Medium for brand association: a "printer-adjacent" mark that already exists in Chinese B2B parts wholesale could surface confusing results when users research the brand.

### Mitigation Recommendations
- Confirm via direct USPTO / EUIPO / DPMA search that no registered wordmark exists for "Ink Relay" / "InkRelay" in class 9 or 42.
- The Alibaba use is unlikely to be a registered mark in the EU/US, but a direct search is required.
- Consider whether "Ink" is the right metaphor for a Printix-compatible app (Printix targets office MFPs, generally toner-based). Marketing/positioning concern, not legal.
- Acquire .de; .com is freshly taken and may need to be approached or skipped.

---

## App Store Review Guideline Notes (apply to all candidates)

Because the app is positioned as a Printix companion, the following App Store Review Guidelines warrant attention regardless of which name is chosen:

- **Guideline 4.1 (Copycats)** — All four candidates are sufficiently far from existing Printix-branded products (Printix App, Printix Go, Printix Client) to avoid copycat concerns, provided the icon, color scheme, and visual identity are distinct. PrintBridge is the only name where competing-vendor branding could be argued to confuse users in the same submission category.
- **Guideline 4.2.7 (Remote Desktop Clients / generic functionality)** — Not directly applicable to a print companion, but the proposed app should not be a thin client mirror of the MCP server's web UI; it must provide a native iOS experience.
- **Guideline 5.2.5 (Apps and metadata that mention other apps or platforms)** — Mentioning **Printix** in subtitle, keywords, or screenshots requires that the developer either be authorised by Tungsten Automation Corp or use the mark only in a **descriptive, nominative fair-use** manner ("compatible with Printix Cloud Print Management"). Use of the Printix logo, icon, or trade dress is **not** permitted without licence. Apple reviewers can and do reject apps that use third-party product names prominently in titles. Safer pattern: keep "Printix" out of the app name and subtitle, mention it only in the long description with a clear "not affiliated with" disclaimer.
- **Apple's general trademark policy** also restricts use of "Apple," "iOS," "AirPrint," etc. in app names — none of the four candidates trigger this, but the description copy should be checked.

---

## Overall Recommendation

**Ranking by clearance risk (lowest risk first):**

1. **SecurePrintCompanion** — 🟡 No collisions found on the open web or App Stores; primary risk is **descriptiveness** (likely refusal as a pure wordmark) and brand weakness. Acceptable as a working product name; weak as a defendable brand.
2. **InkRelay** — 🟡 No app collisions; existing Chinese printer-parts commercial use is in a different Nice class. Primary risk is metaphor mismatch (ink vs. office-MFP product) and a recently-taken .com.
3. **MySecurePrint** — 🟡 No exact collisions, but lives in the most crowded field of all candidates ("Secure Print" is a feature term used by every major OEM with multiple existing competing apps). Mark is weak; .com was registered by an unknown third party in late 2025.
4. **PrintBridge** — 🔴 **Recommend against.** Multiple active commercial users of the exact wordmark in the same product space (Virtex Solutions' printbridge.app, printbridgeair.com, instalabel's PrintBridge Technology, plus a 1998-registered printbridge.com and adjacent Toshiba "e-BRIDGE" family). Realistic risk of common-law trademark conflict and cease-and-desist.

**Safest single candidate from a *collision-avoidance* perspective: `SecurePrintCompanion`** — but with the caveat that it is highly descriptive and unlikely to be registrable as a strong wordmark. If trademark strength matters more than zero-collision-risk, **`InkRelay`** is a better balance (more distinctive, no app collisions found, only adjacent-class commercial use).

**`MySecurePrint`** can be used if marketed clearly as a third-party tool with strong "not affiliated with HP/Konica/Brother/Lexmark/PaperCut/Printix" disclaimers, but the developer should accept a weak trademark position.

**`PrintBridge` should be dropped** from the candidate list.

**Before commercial publication, the developer should:**
- Have a German `Patentanwalt` (patent/trademark attorney) run direct DPMA, EUIPO, and (if US launch is planned) USPTO TESS searches on the chosen mark in Nice classes 9 and 42. The CAPTCHA-gated databases were not directly queried in this OSINT pass.
- Budget ca. 290 EUR (DPMA wordmark, up to 3 Nice classes, via DPMAdirektWeb) or ca. 1,050 EUR (EUTM via EUIPO, 1 class + 50 EUR per additional class) for a registration filing if defensive registration is desired.
- Decide the Printix-compatibility wording for the App Store listing in consultation with counsel given Tungsten Automation Corp's trademark rights.

---

## DISCLAIMER

This is OSINT research, not legal advice. Final clearance for commercial publication should be obtained from a qualified intellectual property attorney, especially for use in jurisdictions outside the ones surveyed.
