# iOS App Review — Printix MobilePrint v1.8.0 (Build 6)

Scope: full read of all 15 Swift sources in `MobileApp/ios-client/Printix MobilePrint/` and `MobileApp/ios-client/PrintixShareExtension/` plus Info.plists, entitlements, ExportOptions and the pbxproj. Read-only — nothing modified.

Verdict at a glance: the app is well-structured for a single-developer SwiftUI app, async/await is used consistently and main-thread handling is largely correct. There are no force-unwraps and no obvious crashers. **However it cannot ship to TestFlight or the App Store in its current form** — three blockers (deployment target, missing privacy manifest, ATS arbitrary-loads with no exception list) and a security regression vs. the user's own design notes (bearer token in App-Group UserDefaults, not Keychain).

---

## 1. 🔴 Critical — must fix before any submission

### C-1 Deployment target is iOS 26.2
File: `MobileApp/ios-client/Printix MobilePrint.xcodeproj/project.pbxproj` (`IPHONEOS_DEPLOYMENT_TARGET = 26.2;` — 4 build configurations).
Problem: ships only to iOS 26.2 devices — that excludes essentially the entire installed base and will be a TestFlight onboarding showstopper for any tester not on the very latest beta.
Fix: lower to iOS 16.0 (the SwiftUI features actually used — `NavigationStack`, `PhotosPicker`, `topBarTrailing`, `.refreshable`, `.onChange(of:_:_:)` two-param form — all work from iOS 16 onward; `.onChange(of:_:_:)` was added in iOS 17, so iOS 17.0 is the safer floor).

### C-2 No PrivacyInfo.xcprivacy
File: missing — searched the whole `ios-client` tree.
Problem: since May 1, 2024 the App Store rejects uploads whose binary uses any "required reason API" without an accompanying privacy manifest. This app uses at least: `UserDefaults` (everywhere in `SettingsStore.swift`), `FileManager.default.temporaryDirectory` / file timestamps (UploadView's `importPhoto`, ShareViewController PDF write), and `Bundle.main.infoDictionary` reads. Submission will be auto-rejected with the "ITMS-91053 Missing API declaration" warning that becomes a hard reject.
Fix: add `PrivacyInfo.xcprivacy` to both the app target and the Share Extension target, declaring `NSPrivacyAccessedAPICategoryUserDefaults` (reason `CA92.1`), `NSPrivacyAccessedAPICategoryFileTimestamp` (reason `C617.1`), and `NSPrivacyCollectedDataTypes` for the email / name / device-name that get sent to the user's own server (collection purpose: AppFunctionality, linked to user, not for tracking).

### C-3 `NSAllowsArbitraryLoads = true` (Info.plist line 21)
File: `Printix-MobilePrint-Info.plist`.
Problem: blanket ATS bypass. App Review's standard response is a rejection asking for a justification or a narrower `NSExceptionDomains` list. The Info.plist comment ("self-configurable server") is the right argument but Apple still typically requires the dictionary form `NSAllowsLocalNetworking = true` or `NSExceptionAllowsInsecureHTTPLoads` per domain rather than the global flag.
Fix: replace with `NSAllowsLocalNetworking = true` (covers `.local`, link-local, and unqualified hostnames — the LAN case) and require HTTPS for everything else. If users genuinely need HTTP on routable IPs, leave `NSAllowsArbitraryLoads = true` but add the `NSAllowsArbitraryLoadsInWebContent = false` companion and prepare a one-paragraph review-note justification in App Store Connect ("on-prem MCP server URL is user-supplied").

### C-4 Bearer token + email + name stored in App-Group UserDefaults, not Keychain
File: `Printix MobilePrint/SettingsStore.swift` lines 52–53, 139–146, 213.
Problem: a code comment (lines 11–14) explicitly says "later it can move to Keychain". `UserDefaults` for the App Group is a plist on disk — included in unencrypted iTunes/Finder backups, readable on jailbroken devices, and survives app deletion under some restore conditions. Tokens that authenticate against the user's full Printix tenant deserve `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` with a Keychain Access Group shared with the extension.
Fix: introduce a small `KeychainTokenStore` that wraps `SecItemAdd/Copy/Delete` with `kSecAttrService = "printix-mcp"`, `kSecAttrAccessGroup = "$(AppIdentifierPrefix)group.com.mnimtz.printixmobileprint"` (note: keychain groups need the team prefix), and `kSecAttrAccessible = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` (extensions run before first unlock isn't an issue here, but `WhenUnlocked…` would break first-unlock auto-print scenarios). Migrate the existing UserDefaults token on first launch.

### C-5 NFC UID logged via NSLog
File: `Printix MobilePrint/NFCCardScanner.swift` lines 144 and 166.
Problem: `NSLog("[NFCScanner] UID: \(hex) ...")` writes the literal card UID to the unified system log. That log is visible to anyone with Console.app while the device is connected to a Mac, and is collected in `sysdiagnose` bundles. Card UIDs are not high-secret but they are exactly the identifier used for door access in many companies — leaking them via diagnostic logs is something an App Store privacy reviewer will flag and a CISO will be furious about.
Fix: gate behind `#if DEBUG`, or drop the UID from the log line entirely (keep tag-type and length, drop the hex).

---

## 2. 🟠 Important — should fix before App Store (TestFlight tolerable)

### I-1 NFCSessionHandler is leaked per scan
File: `NFCCardScanner.swift` lines 55–60.
Problem: `let handler = NFCSessionHandler(...)` is held only by the local variable. The handler stores `self.session` and the session retains the delegate (`self`) — that's a normal retain chain — but the *outer* caller releases the handler immediately upon `return try await handler.run()` returning. Inside `run()` the `withCheckedThrowingContinuation` keeps the closure alive but does not keep `handler` alive; the only thing keeping the handler alive is `self.session = session` plus the session retaining the handler as its delegate (closing the cycle). Result: on every scan you allocate one `NFCSessionHandler` + one `NFCTagReaderSession` that are kept alive forever by their mutual retain. Leak grows with each scan.
Fix: nil out `self.session` and `self.continuation` in `didInvalidateWithError` AND at the end of `didDetect` before resuming the continuation, breaking the cycle.

### I-2 `WebAuthAnchor` instance lives forever
File: `LoginView.swift` line 28 (`@State private var webAuthAnchor: WebAuthAnchor = WebAuthAnchor()`).
Problem: minor — a single instance per LoginView, no functional issue. But it's recreated on every LoginView push (NavigationStack push from SetupView). Not a leak per se, just sloppy.
Fix: make it `static let` shared instance, or accept the small overhead.

### I-3 Timer publisher recreated every view-rebuild
File: `UploadView.swift` line 216 (`private let resetTick = Timer.publish(...).autoconnect()`).
Problem: on a `struct View`, `let` properties are re-initialised every time SwiftUI rebuilds the view body's outer struct (i.e. potentially many times per second when other state changes). Each re-init triggers a fresh `Timer.publish(...).autoconnect()` and the previous timers are not cancelled. Over time you get many fired timers per second all calling `resetToDefaultIfExpired()`. Not a crash, but real CPU/battery drain.
Fix: move to a `StateObject`-backed wrapper, or use `TimelineView(.periodic…)` (which is already used a few lines above for the banner) for the reset check, or hold the publisher as `@State`.

### I-4 Share-Extension uses `Task.detached` with `[weak self]`
File: `PrintixShareExtension/ShareViewController.swift` line 120.
Problem: `Task.detached { [weak self] in defer { self?.close() } ... }` — if iOS tears the extension down before the upload finishes (extensions get killed aggressively after dismissal), the URL request is silently cancelled and the user has no idea whether the print job made it. Also `close()` runs inside `defer` so it fires even if the user's network is down.
Fix: use `Task { ... }` (inherits actor + lives with the host), keep `self` strong, and only call `close()` after the request returns (success or failure). For "background completion" reliability switch the upload to `URLSession.shared.uploadTask(with: …, fromFile: …, completionHandler: nil)` with a configured background `URLSessionConfiguration(background:)` so iOS finishes the upload after the extension dies — that's the proper Apple pattern for share extensions.

### I-5 Share extension is single-target, ignores `selectedTargetIds`
File: `ShareViewController.swift` reads only `lastTargetId` (line 19). The user's design (SettingsStore line 88-99) mirrors the first selected ID into `lastTargetId` — so it works, but the share-extension cannot send to multiple targets the way UploadView does. Likely acceptable; just document or remove the multi-target promise from the UI for share-flow.

### I-6 Share extension does not use the same App-Group key normalisation as the main app
Same file lines 17–20 redefines key strings (`serverURL`, `bearerToken`, `lastTargetId`) instead of importing `SettingsStore.Keys`. Risk: drift — if `SettingsStore.Keys.bearerToken` is ever renamed, the extension silently breaks ("not logged in" sheets) but the main app keeps working.
Fix: extract a tiny `SharedSettingsKeys` enum into a file that both targets compile.

### I-7 Custom URL scheme `printixmobileprint://` is generic — no callback handling
File: `Printix-MobilePrint-Info.plist` declares the scheme but no `.onOpenURL` handler exists anywhere in the SwiftUI tree.
Problem: it works for `ASWebAuthenticationSession` because that uses the scheme purely to intercept the redirect. But any *other* app on the device can also register the same scheme (no uniqueness enforcement on schemes), enabling an OAuth-code interception attack. `ASWebAuthenticationSession` does mitigate this somewhat by binding the callback to the session.
Fix: switch to Universal Links (`applinks:` entitlement + `/.well-known/apple-app-site-association` on the MCP server) for the OAuth callback. Higher engineering effort; not a TestFlight blocker.

### I-8 `URL(string: draftURL) != nil` validates almost anything
File: `SetupView.swift` line 52.
Problem: `URL(string:)` happily accepts `"x"`, `"foo bar"` (after trim no), `"file:///etc/passwd"`. The "Weiter zum Login" button enables for inputs that won't work.
Fix: also require `url.scheme == "https" || url.scheme == "http"` and a non-empty host.

### I-9 `defaults.set(date, forKey:)` writes Date directly; read with `defaults.object(... ) as? Date` — fine in UserDefaults but the App-Group plist round-trips via `__NSCFCalendarDate` weirdness on cross-locale devices.
Minor; flagging because it's the only Date stored that way. Consider `timeIntervalSince1970` as Double for safety.

### I-10 `Data(contentsOf: fileURL)` loads the entire file into memory
Files: `UploadView.swift` line 272, `ShareViewController.swift` lines 57, 78.
Problem: a 50-MB PDF from the Files-app crashes a Share Extension (it gets ~120 MB of RAM). Even in the main app, large scanned PDFs are common in the print scenario.
Fix: stream uploads using `URLSession.upload(fromFile:)` rather than reading into Data; PrintixSendCore would need an alternate entry point.

### I-11 Open-redirect-style trust of `result.user.email/fullName/roleType`
File: `LoginView.swift` lines 209–214, `ContentView.swift` lines 60–62.
Problem: minor — the server is trusted to send a valid role. If the server is ever compromised, an attacker can return `roleType:"admin"` and unlock the Management/Cards tabs on the client. The actual API calls inside those tabs still server-side-authorise, so the worst case is leaking *which* admin endpoints exist. Acceptable for v1, document.

### I-12 Empty-state "no targets" gives no actionable guidance
File: `TargetsView.swift` line 36.
Problem: "Keine Ziele gefunden." — the user has no idea whether the server is broken, the user has no print queues, or the API call silently failed. The `error` variable is also rendered, so this should generally only show after a successful `targets()` returning `[]`, but the message should mention that this means the server returned no print queues.

### I-13 ManagementView prefix-truncates errors at 280 chars *after* stringifying the entire error including raw decoded JSON
File: `ManagementView.swift` line 300. Decode errors will dump model internals to the user — fine for TestFlight diagnostics, *not* OK for App Store where it can leak server response shape.
Fix: in release builds, replace decode-error rendering with a generic "Konnte 'users' nicht laden." and surface details only in `#if DEBUG`.

---

## 3. 🟡 Nice-to-have — UX polish

- **N-1** `ContentView.swift` lines 89–139: account section uses German hard-coded labels (`"Angemeldet als"`, `"Server"`, `"Gerät"`, `"Sprache"`, `"Konto"`) even though the rest of the app uses xcstrings. Run through `String(localized:)` for consistency.
- **N-2** `CardsView.swift` line 281: `.navigationTitle("Karten-Details")` — same; missing localisation key.
- **N-3** No VoiceOver labels anywhere. The icon-only delete button in CardDetailView is just `Image(systemName: "trash")` with `Label`, which is fine, but the green/grey online dots in ManagementView have no `accessibilityLabel("online")` / `("offline")`.
- **N-4** Offline behaviour: every screen surfaces a generic "Kein Server konfiguriert" or `localizedDescription` from URLSession. Consider a single `NetworkError`-to-UI translator that distinguishes 401 (relogin), 5xx (retry), no-network (retry) and shows a Retry button.
- **N-5** `UploadView.swift` line 234: temp PDF/photo files are never cleaned up. They accumulate in `temporaryDirectory` until iOS reaps it (which can be never).
- **N-6** `UploadView.swift` line 314 (`successDetail`): `(r.status ?? "gesendet").capitalized` capitalises German "queued" → "Queued" but localised "gesendet" → "Gesendet"; fine, but the mix of localised + raw English status from the server is jarring.
- **N-7** Dark-mode: all colours are semantic (`Color.secondary`, `.tint`, `Color.green/.orange/.red`) — should look correct in dark mode but no review was done with screenshots.
- **N-8** iPad layout: `TARGETED_DEVICE_FAMILY = "1,2"` means iPad is enabled but every view uses `NavigationStack` (single-column). On iPad Pro this looks barren — consider `NavigationSplitView`. Not a blocker.
- **N-9** `QRScannerView`: no on-screen scan reticle, no torch toggle, no permission-denied message ("Camera access needed in Settings").
- **N-10** LoginView shows `error.localizedDescription` from the API client raw — for users that's e.g. "The data couldn't be read because it isn't in the correct format." Translate to UX-friendly strings.
- **N-11** No haptic feedback on send-success / NFC-card-read (`UINotificationFeedbackGenerator().notificationOccurred(.success)`).

---

## 4. 🟢 Looks good — keep

- **G-1** Pervasive `async/await` with `@MainActor` annotations on UI mutators. No `DispatchQueue.main.async` antipatterns, no closure-callback soup.
- **G-2** Zero force-unwraps (`!`), zero `try!`, zero `as!` across the entire 2 830-line codebase. Excellent baseline crash-safety.
- **G-3** PKCE flow correctly delegates verifier generation + token exchange to the server (LoginView lines 122–182). The client never sees the verifier, which avoids the most common PKCE mistake.
- **G-4** `ASWebAuthenticationSession` used correctly with a held presentation provider; `.canceledLogin` is silently swallowed instead of shown as an error.
- **G-5** App-Group sharing between main + extension is wired correctly via matching entitlements and shared suite name.
- **G-6** NFC implementation is careful: no `session.connect()` (avoids the ISO7816 entitlement trap), `.iso14443 + .iso15693` polling only (skips FeliCa to avoid the system-code entitlement), and the explanatory comment block is the kind of thing the next maintainer will thank past-you for.
- **G-7** Auto-reset timer for non-default print targets is a thoughtful UX safeguard against "I forgot I was printing to Marc's queue".
- **G-8** Decoupled per-endpoint error handling in `ManagementView.reload()` (one failed endpoint doesn't blank the whole tab).
- **G-9** Two-language picker shows each language in its native script (`Deutsch`, `Norsk`, `English`) — discoverability win over translating language names.
- **G-10** `ExportOptions.plist` is set up for `app-store-connect`, not ad-hoc.
- **G-11** `ITSAppUsesNonExemptEncryption = false` declared in both Info.plists — avoids the per-upload encryption prompt.
- **G-12** xcstrings catalog used throughout; no legacy `.strings` files to maintain.

---

## Summary

| Severity | Count |
|---|---|
| 🔴 Critical | 5 |
| 🟠 Important | 13 |
| 🟡 Nice-to-have | 11 |
| 🟢 Looks good | 12 |

**App Store readiness: NO-GO** in current state.

Blocking reasons:
1. Deployment target iOS 26.2 will accept essentially zero TestFlight installs and is almost certainly a typo for 16.0 or 17.0.
2. Missing `PrivacyInfo.xcprivacy` triggers automatic App Store ingestion rejection.
3. `NSAllowsArbitraryLoads` without an exception list will trigger an App Review reply asking for justification — fixable in review but slows the first submission.
4. Bearer token in `UserDefaults` is a contract-with-yourself violation (your own comment says "should be Keychain") and is the kind of thing a security-conscious enterprise customer (and the user's MEMORY.md "durable round-trip" mindset) will rightly object to before broader rollout.
5. NFC UID via `NSLog` leaks the exact data the app exists to manage.

**Estimated effort to reach GO state**: ~1–1.5 dev days.
- 30 min: lower deployment target + verify build (C-1).
- 1 h: write & wire `PrivacyInfo.xcprivacy` for app + extension (C-2).
- 30 min: narrow ATS to `NSAllowsLocalNetworking` + write App-Review note (C-3).
- 3 h: implement `KeychainTokenStore`, migrate existing UserDefaults token at launch, route both targets through it (C-4).
- 15 min: gate NFC logs behind `#if DEBUG` and drop the UID (C-5).
- 2 h: fix the two real leaks (I-1 NFC handler, I-3 timer publisher) and move Share-Extension upload to a background URLSession (I-4).
- 1 h: minor I-* polish (URL validation, Decode-error gating in release).

After those, the app is in GO-with-fixes state and the remaining 🟠 items can land in 1.8.1 / 1.9.0.
