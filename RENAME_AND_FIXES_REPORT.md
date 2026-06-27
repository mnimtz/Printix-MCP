# Rename + Critical Fixes — Execution Report

**Date:** 2026-06-27
**Branch (iOS / addon repo):** `claude/admiring-bhaskara`
**Server (printix-mcp-linux):** `main` (status as found)

iOS app rebranded from **Printix MobilePrint** → **MySecurePrint** with
fresh version 1.0.0 (build 1). Critical fixes C-1..C-5 plus important
fixes I-1, I-3, I-4 applied. Server-side comment updates published as
`printix-mcp-linux` v7.7.7 (transitional dual-accept; no behavioural
change). The `printix-mcp/` addon-subdir variant called for in the
brief does not exist in this checkout (was deleted prior to this
session) — see "Skipped" section.

Commits are staged but **not pushed**.

---

## 1. Files changed per category

### Naming (Part 1) — 10 files modified, 0 renamed

| File | Change |
|---|---|
| `MobileApp/ios-client/Printix MobilePrint.xcodeproj/project.pbxproj` | 4× `IPHONEOS_DEPLOYMENT_TARGET 26.2 → 17.0`; 4× `MARKETING_VERSION 1.8.0 → 1.0.0`; 4× `CURRENT_PROJECT_VERSION 6 → 1`; main bundle id `TungstenAutomation.Printix-MobilePrint → de.nimtz.mysecureprint`; share-ext bundle id `…PrintixShareExtension → de.nimtz.mysecureprint.share`; display-name keys `Printix MobilePrint → MySecurePrint` (4 configs). |
| `MobileApp/ios-client/Printix-MobilePrint-Info.plist` | `CFBundleDisplayName`, `CFBundleName` → `MySecurePrint`; URL scheme `printixmobileprint → mysecureprint`; `CFBundleURLName → de.nimtz.mysecureprint.oauth`; ATS narrowed (C-3, see below). |
| `MobileApp/ios-client/PrintixShareExtension/Info.plist` | unchanged structurally (no display-name override there; pbxproj sets it). |
| `MobileApp/ios-client/Printix MobilePrint/Printix MobilePrint.entitlements` | App-group `group.com.mnimtz.printixmobileprint → group.de.nimtz.mysecureprint`; **added** `keychain-access-groups` with `$(AppIdentifierPrefix)group.de.nimtz.mysecureprint`. |
| `MobileApp/ios-client/PrintixShareExtension/PrintixShareExtension.entitlements` | App-group renamed; **added** matching `keychain-access-groups` (C-4 prerequisite). |
| `MobileApp/ios-client/ExportOptions.plist` | Added `provisioningProfiles` dict with placeholder values for both bundle IDs. |
| `MobileApp/ios-client/Printix MobilePrint/SettingsStore.swift` | `appGroupID` renamed; bearer-token now read/written via Keychain (C-4) with one-time migration flag `migrated_to_keychain_v1`. |
| `MobileApp/ios-client/Printix MobilePrint/LoginView.swift` | `oauthRedirectURI`, `oauthCallbackScheme` rebranded to `mysecureprint://`. |
| `MobileApp/ios-client/PrintixShareExtension/ShareViewController.swift` | App-group renamed, token read from shared Keychain access-group, upload moved to `URLSession.uploadTask(with:fromFile:)` over a `background:`-config session writing multipart body to the App-Group container (I-4). |
| `MobileApp/ios-client/Printix MobilePrint/L10n.swift`, `DocumentPicker.swift` | Comment-string updates from "Printix MobilePrint" → "MySecurePrint". |
| `MobileApp/ios-client/README.md` | Rewritten with new name, disclaimer per `NAMING_LEGAL_REVIEW.md`, identities table, historic-URI note. |

### New files (Part 2 & 5) — 5 created

| File | Purpose |
|---|---|
| `MobileApp/ios-client/Printix MobilePrint/KeychainTokenStore.swift` | C-4: keychain wrapper, kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly. |
| `MobileApp/ios-client/Printix MobilePrint/PrivacyInfo.xcprivacy` | C-2 (main app). |
| `MobileApp/ios-client/PrintixShareExtension/PrivacyInfo.xcprivacy` | C-2 (share extension). |
| `MobileApp/ios-client/APP_STORE_LISTING.md` | App-Store metadata, DE+EN descriptions, review notes. |
| `MobileApp/ios-client/APP_PRIVACY_POLICY.md` | Privacy-policy template. |

### Server-side (Part 4) — `printix-mcp-linux` 4 files

| File | Change |
|---|---|
| `src/entra.py` | Comment block updated to mention both URI schemes (transitional). |
| `src/web/desktop_routes.py` | Same. |
| `VERSION` | `7.7.6 → 7.7.7`. |
| `CHANGELOG.md` | New 7.7.7 entry explaining dual-accept rationale. |

### iOS-app `Localizable.xcstrings` (Part 1.5)

No occurrence of "Printix MobilePrint" found in xcstrings (the catalog
uses no app-name strings at all — display name is read from
`Info.plist`). `grep -c "Printix MobilePrint" Localizable.xcstrings → 0`.
Skipped, nothing to replace. Confirmed deliberately, not by oversight.

---

## 2. Critical / important fixes

| Fix | Status | Notes |
|---|---|---|
| C-1 Deployment target → iOS 17.0 | **Done** | All 4 build configurations in pbxproj. |
| C-2 PrivacyInfo.xcprivacy | **Done (file content)** + **manual step required** | Both files written to the correct folder paths. The pbxproj uses `PBXFileSystemSynchronizedRootGroup` (Xcode 16 synchronized folders) so a `.xcprivacy` dropped into the target folder will be auto-included in the next Xcode open. **No pbxproj surgery attempted** to add explicit file references. User should open the project in Xcode once to verify both files appear under their respective targets and are bundled. |
| C-3 Narrow ATS | **Done** | `NSAllowsArbitraryLoads` removed; `NSAllowsLocalNetworking=true` + `NSAllowsArbitraryLoadsInWebContent=false` set. Pre-prepared App-Review justification text in `APP_STORE_LISTING.md`. |
| C-4 Keychain-token migration | **Done** | New `KeychainTokenStore.swift` using `kSecAttrService=de.nimtz.mysecureprint`, `kSecAttrAccessGroup=group.de.nimtz.mysecureprint` (iOS prepends `$(AppIdentifierPrefix)` automatically), `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`. `SettingsStore.init` migrates the legacy `bearerToken` from UserDefaults exactly once (guarded by `migrated_to_keychain_v1`). Share-extension reads the same item directly via `SecItemCopyMatching` (no separate Swift dependency added to keep extension build simple). Both targets carry matching `keychain-access-groups` entitlement. |
| C-5 NFC UID log gated | **Done** | UID-hex line wrapped in `#if DEBUG`; release builds log only tag type + length. The "Tags erkannt" line at L144 also gated behind `#if DEBUG`. |
| I-1 NFC handler retain cycle | **Done** | `self.session = nil` + `self.continuation = nil` both in `didInvalidateWithError` and in the success branch of `didDetect` before resuming. |
| I-3 Timer publisher re-init | **Done** | New `ResetClock` `ObservableObject` holds the autoconnected timer behind a single sink; UploadView uses it as `@StateObject` so SwiftUI instantiates it once for the lifetime of the view. |
| I-4 Background URLSession for share-ext | **Done with caveat** | Share extension now writes a streamed multipart body to the App-Group container and submits it via `URLSession.uploadTask(with:fromFile:)` over a `URLSessionConfiguration.background(...)` session (sharedContainerIdentifier set). The multipart layout mirrors `PrintixSendCore.ApiClient.sendData` (target_id, copies, color, duplex, file). **Important:** I did not write a delegate to surface terminal completion of the background task (extension may already be dead at completion). The last-upload-status keys (`share_lastUploadStatus`, `…At`, `…Error`, `…File`) are written to the App-Group `UserDefaults` at the moment the task is queued (`"queued"`). The main app can later poll these keys; surfacing a UI banner is out of scope here. Recommend a follow-up task to add a `URLSessionDelegate` (background events delivered via `application(_:handleEventsForBackgroundURLSession:completionHandler:)`) for true success/failure surfacing. |

---

## 3. Validation results

1. **plistlib parse** — all 7 plists (2× xcprivacy, 2× Info.plist, 2× entitlements, ExportOptions.plist) parse cleanly. **PASS**
2. **grep iOS for old identifiers** (`printixmobileprint`, `com.mnimtz.printixmobileprint`, `TungstenAutomation.Printix-MobilePrint`, excluding `build/` archive) — only hit is the deliberate historical reference in `README.md`. **PASS**
3. **grep server `src/` for `printixmobileprint`** — only deliberate dual-accept comments in `entra.py` and `desktop_routes.py`. **PASS**
4. **`python3 -c "import ast; ast.parse(...)" `** on `desktop_routes.py` and `entra.py` — both **PASS**.
5. **No `*.orig`, `*.swift~`, `*.pyc`** in either repo. **PASS**

---

## 4. Skipped / deferred

- **Folder rename** of `Printix MobilePrint/` → `MySecurePrint/`: SKIPPED per brief (high pbxproj-corruption risk). Folder names remain as-is; only display names + bundle IDs changed. Visible in Finder but not to App Store / users.
- **Pbxproj surgery to add explicit `xcprivacy` file refs**: SKIPPED. The two targets use `PBXFileSystemSynchronizedRootGroup` (Xcode 16+ auto-sync of folder contents), so the new `PrivacyInfo.xcprivacy` files will be picked up automatically on next Xcode open. User: please open Xcode once and verify both targets show the privacy manifest under their resources before archiving.
- **`printix-mcp/` addon-subdir bump to 6.9.4**: SKIPPED — the `printix-mcp/` directory inside `printix-mcp-addon/` no longer exists in this checkout (git shows it as deleted prior to this session). No version file or `config.yaml` available to bump. If the addon repo lives elsewhere (separate checkout), apply the same comment change in `src/entra.py` + `src/web/desktop_routes.py` + bump VERSION 6.9.3 → 6.9.4 + add an analogous CHANGELOG entry there.
- **I-1 second-pass review**: the new continuation-resume path in `didDetect` clears `self.session` + `self.continuation` before resuming. The session-retain cycle is broken at the same point — verified by code reading; not exercised by a leak-instrumented test build.
- **I-4 delegate-based completion handler**: deferred (see C/I status table).

---

## 5. Commits prepared (not pushed)

- `printix-mcp-addon` (this worktree): one commit covering iOS rebrand + C-1..C-5 + I-1 + I-3 + I-4 + listings/policy/report files.
- `printix-mcp-linux`: one commit `v7.7.7: iOS OAuth redirect URI rebranded to mysecureprint:// (transitional dual-accept)`.

---

## 6. Next steps for the user

1. **Apple Developer Portal**
   - Create new App ID `de.nimtz.mysecureprint` (+ Share-Extension `de.nimtz.mysecureprint.share`), enable App Groups, Keychain Sharing, NFC Tag Reading capabilities.
   - Register App Group `group.de.nimtz.mysecureprint`.
   - Generate fresh provisioning profiles, re-sign or let Xcode automatic-sign do it.
2. **Entra App-Registration (Azure portal)**
   - Add Redirect URI `mysecureprint://oauth/callback` under *Authentication → Mobile and desktop applications*. Keep the old `printixmobileprint://oauth/callback` for now (transitional).
3. **Xcode bookkeeping**
   - Open the project once and verify both `PrivacyInfo.xcprivacy` files appear under their target's "Build Phases → Copy Bundle Resources" (auto-included via folder sync). If not, drag them into Xcode against the matching target.
   - Verify entitlements show `keychain-access-groups` in both targets.
   - Verify Signing & Capabilities now lists the new bundle IDs and the new app group.
4. **Device test**
   - First launch after upgrade: confirm UserDefaults-token migration happens (`migrated_to_keychain_v1` true; legacy `bearerToken` key removed). Subsequent login writes only to keychain.
   - Confirm Entra Microsoft-Sign-In completes via `mysecureprint://oauth/callback`.
   - Share PDF from Safari → confirm the upload-status keys (`share_lastUploadStatus`) flip to `"queued"` and the main app sees the new key on next launch.
   - NFC scan: read a tag, verify Release-build console no longer prints the UID hex.
5. **TestFlight**
   - Archive with the new bundle IDs, upload, ensure no `ITMS-91053` warning (privacy manifest acceptance) and no ATS rejection.
   - Submit App-Review notes per `APP_STORE_LISTING.md`.
6. **Server-side**
   - Deploy `printix-mcp-linux` 7.7.7 (commentary-only release; safe).
   - When confident, drop the old `printixmobileprint://` URI from Entra and remove the dual-accept note from the changelog in a follow-up minor.

---

## 7. Estimated remaining manual hours

- Apple Developer Portal new IDs + profiles: **~45 min**
- Entra App-Registration update: **~10 min**
- Xcode verification (privacy manifests, signing): **~30 min**
- Manual device smoke-test (migration, OAuth, NFC, share-ext background upload): **~1.5 h**
- TestFlight build + submit + listing copy: **~2 h**
- Follow-up: I-4 background URLSession delegate + UI banner, I-2/I-5..I-13 polish: **~1 day**

Total to TestFlight-go: **~5 h manual**, plus the ~1-day follow-up before App-Store-go.
