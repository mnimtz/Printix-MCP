# Printix MCP — Handbuch für Anwender

> **Version:** 6.7.116
> **Zielgruppe:** Administratoren, Helpdesk und Power-User, die den Printix MCP Server über einen AI-Assistenten (claude.ai, ChatGPT, Claude Desktop) ansprechen.
> **Sprache:** Deutsch · Englische Version siehe `MCP_MANUAL_EN.pdf`

---

## Was ist Printix MCP?

Der Printix MCP Server ist eine Brücke zwischen modernen AI-Assistenten und der Printix Cloud Print API. Er stellt **über 100 Werkzeuge (Tools)** bereit, mit denen Sie Printix in natürlicher Sprache steuern können — vom einfachen _„Welche Drucker haben wir in Düsseldorf?"_ bis zum komplexen _„Zeig mir die 10 teuersten Drucker des letzten Quartals im Vergleich zum Quartal davor"_.

Sie müssen die Tool-Namen **nicht auswendig lernen**. Der Assistent wählt selbstständig das passende Werkzeug anhand Ihrer Frage. Dieses Handbuch gibt Ihnen einen Überblick, _was_ möglich ist, damit Sie wissen, worüber Sie den Assistenten fragen können.

## Wie man dieses Handbuch liest

Jede Kategorie beginnt mit einer kurzen Einleitung, gefolgt von einer Tool-Tabelle und **Beispiel-Dialogen**. Die Dialoge zeigen exakt, wie eine typische Frage an den Assistenten aussieht und welches Tool er intern aufruft. Sie können die Prompts 1:1 übernehmen oder als Inspiration nutzen.

## Inhaltsverzeichnis

1. [System & Selbstdiagnose](#1-system--selbstdiagnose)
2. [Drucker, Sites & Netzwerke](#2-drucker-sites--netzwerke)
3. [Druckjobs & Cloud-Print](#3-druckjobs--cloud-print)
4. [Benutzer, Gruppen & Workstations](#4-benutzer-gruppen--workstations)
5. [Karten & Kartenprofile](#5-karten--kartenprofile)
6. [Reports & Analysen](#6-reports--analysen)
7. [Report-Templates & Scheduling](#7-report-templates--scheduling)
8. [Capture / Workflow-Automation](#8-capture--workflow-automation)
9. [Betrieb, Wartung & Audit](#9-betrieb-wartung--audit)

---

## 1. System & Selbstdiagnose

Diese Tools beantworten die Meta-Fragen: _Wer bin ich? Läuft alles? Welche Rolle habe ich? Was soll ich als Nächstes tun?_ Ideal als Einstieg in eine neue Session — oder wenn etwas unerwartet nicht funktioniert und Sie wissen möchten, **warum**.

| Tool | Zweck |
|------|-------|
| `printix_status` | Health-Check: läuft der Server, ist der Tenant erreichbar, welche API-Versionen. |
| `printix_whoami` | Zeigt den aktuell verbundenen Tenant + eigenen Printix-User. |
| `printix_tenant_summary` | Kompakter Überblick: Anzahl Drucker, User, Sites, Cards, offene Jobs. |
| `printix_explain_error` | Übersetzt einen Printix-Fehlercode oder eine Error-Message in Klartext + Lösungsvorschlag. |
| `printix_suggest_next_action` | Schlägt einen sinnvollen nächsten Schritt anhand eines Kontext-Strings vor. |
| `printix_natural_query` | Nimmt eine natürlichsprachige Frage entgegen und schlägt das passende Reports-Tool vor. |

### Beispiel-Dialoge

**Prompt:** _„Läuft alles bei Printix?"_
Der Assistent ruft `printix_status` auf und meldet Tenant, API-Verbindung und Versionen.

**Prompt:** _„Wer bin ich eigentlich gerade bei Printix angemeldet?"_
`printix_whoami` liefert Tenant-Name, eigene E-Mail und Admin-Status.

**Prompt:** _„Gib mir einen Überblick über meinen Printix-Tenant."_
`printix_tenant_summary` liefert die Kennzahlen in einem Block — perfekt als Gesprächseinstieg.

**Prompt:** _„Was bedeutet der Fehler 'Job submission failed — 403'?"_
`printix_explain_error` erklärt den Code und nennt typische Ursachen (fehlender Scope, Tenant-ID falsch, Token abgelaufen).

---

## 2. Drucker, Sites & Netzwerke

Alles rund um die physische und logische Infrastruktur: Drucker, Queues, Standorte (Sites), Netzwerke und SNMP-Konfigurationen. Lesende wie schreibende Operationen. Die `*_context`-Tools liefern aggregierte Sichten (z. B. „Queue + Printer + letzte Jobs" in einem Aufruf), damit der Assistent nicht mehrere Round-Trips braucht.

| Tool | Zweck |
|------|-------|
| `printix_list_printers` | Listet alle Drucker (mit optionalem Suchbegriff). |
| `printix_get_printer` | Details + Fähigkeiten eines konkreten Druckers. |
| `printix_resolve_printer` | Findet den besten Drucker per Fuzzy-Match (Name + Location + Modell). |
| `printix_network_printers` | Alle Drucker eines Netzwerks oder einer Site. |
| `printix_get_queue_context` | Queue + Printer-Objekt + letzte Jobs in einem Aufruf. |
| `printix_printer_health_report` | Drucker-Status-Übersicht: online, offline, Fehlerzustände. |
| `printix_top_printers` | Top-N Drucker nach Druckvolumen (Tage, Limit, Metrik). |
| `printix_list_sites` | Alle Standorte des Tenants. |
| `printix_get_site` | Details einer Site. |
| `printix_create_site` / `printix_update_site` / `printix_delete_site` | Site-Verwaltung. |
| `printix_site_summary` | Site + Networks + Drucker in einem aggregierten Block. |
| `printix_list_networks` | Netzwerke, optional gefiltert auf eine Site. |
| `printix_get_network` | Details eines Netzwerks. |
| `printix_create_network` / `printix_update_network` / `printix_delete_network` | Netzwerk-Verwaltung. |
| `printix_get_network_context` | Network + zugehörige Site + Drucker in einem Block. |
| `printix_list_snmp_configs` / `printix_get_snmp_config` | SNMP-Konfigurationen. |
| `printix_create_snmp_config` / `printix_delete_snmp_config` | SNMP-Config anlegen/entfernen. |
| `printix_get_snmp_context` | SNMP-Config + betroffene Drucker + Netzwerk in einem Block. |

### Beispiel-Dialoge

**Prompt:** _„Welche Drucker stehen in Düsseldorf und sind von Brother?"_
`printix_resolve_printer("Brother Düsseldorf")` liefert per Token-Fuzzy-Match alle Geräte, bei denen beide Tokens irgendwo in Name/Location/Vendor/Site auftauchen.

**Prompt:** _„Zeig mir alle Drucker im Netzwerk 9cfa4bf0."_
`printix_network_printers(network_id="9cfa4bf0")` löst — falls die API keine direkte Network→Printer-Zuordnung liefert — intern den passenden Site-Scope auf und liefert die relevanten Drucker (`resolution_strategy` im Response zeigt, welcher Weg gegriffen hat).

**Prompt:** _„Mach eine komplette Zusammenfassung der Site DACH."_
`printix_site_summary(site_id=…)` — Site-Meta, alle Networks + Counter, alle Drucker in einem Block.

**Prompt:** _„Welche Drucker sind gerade offline?"_
`printix_printer_health_report` gruppiert nach Status und liefert die Problem-Geräte oben.

---

## 3. Druckjobs & Cloud-Print

Druckjobs einsehen, einreichen, an andere User delegieren. Enthält die produktiven Kurzwege (`quick_print`, `send_to_user`), die typische Mehrschritt-Abläufe (Submit → Upload → Complete) in einem einzigen Aufruf zusammenfassen.

| Tool | Zweck |
|------|-------|
| `printix_list_jobs` | Alle Jobs, optional gefiltert auf eine Queue. |
| `printix_get_job` | Details zu einem Job. |
| `printix_submit_job` | Druckjob einreichen (erster Schritt des 3-Schritt-Submit-Prozesses). |
| `printix_complete_upload` | Upload abschließen und Job freigeben. |
| `printix_delete_job` | Job stornieren. |
| `printix_change_job_owner` | Job-Owner ändern (Delegation). |
| `printix_jobs_stuck` | Jobs, die länger als N Minuten „hängen". |
| `printix_quick_print` | Ein-Schritt-Print: URL + Empfänger → fertig. |
| `printix_send_to_user` | Dokument direkt an einen anderen Benutzer weiterleiten. |

### Beispiel-Dialoge

**Prompt:** _„Schick mir dieses PDF an marcus@firma.de als Secure Print."_
`printix_quick_print(recipient_email="marcus@firma.de", file_url=…, filename="vertrag.pdf")` — submit + upload + complete in einem Aufruf.

**Prompt:** _„Welche Druckjobs hängen seit mehr als 30 Minuten?"_
`printix_jobs_stuck(minutes=30)` listet blockierte Jobs mit Alter und Owner.

**Prompt:** _„Gib den Job 4711 an marcus@firma.de ab, weil ich in den Urlaub fahre."_
`printix_change_job_owner(job_id="4711", new_owner_email="marcus@firma.de")`.

---

## 4. Benutzer, Gruppen & Workstations

Kompletter Lifecycle: anlegen, bearbeiten, deaktivieren, diagnostizieren. Die `user_360`- und `diagnose_user`-Tools sind besonders wertvoll im Helpdesk: sie ziehen User-Stammdaten, Gruppen, Karten, Workstations, SSO-Status und letzte Druck-Aktivität in **einen** Response zusammen.

| Tool | Zweck |
|------|-------|
| `printix_list_users` | Alle User des Tenants, mit Pagination + Rollen-Filter. |
| `printix_get_user` | Details eines Users. |
| `printix_find_user` | Sucht nach E-Mail-Fragment oder Name. |
| `printix_user_360` | 360°-Sicht: User + Karten + Gruppen + Workstations + letzte Jobs. |
| `printix_diagnose_user` | Helpdesk-Diagnose: was funktioniert, was nicht, warum. |
| `printix_create_user` / `printix_delete_user` | User anlegen/löschen. |
| `printix_generate_id_code` | Neuen ID-Code für einen User erzeugen (Self-Service-Token). |
| `printix_onboard_user` / `printix_offboard_user` | Geführtes On- und Offboarding (mehrere Schritte in einem Aufruf). |
| `printix_list_admins` | Alle Admins des Tenants. |
| `printix_permission_matrix` | Matrix: User × Berechtigungen. |
| `printix_inactive_users` | User, die seit N Tagen nicht mehr gedruckt haben. |
| `printix_sso_status` | Prüft SSO-Mapping für eine E-Mail. |
| `printix_list_groups` / `printix_get_group` | Gruppen-Listing / -Details. |
| `printix_create_group` / `printix_delete_group` | Gruppen-Verwaltung. |
| `printix_list_workstations` / `printix_get_workstation` | Workstations-Listing / -Details. |

### Beispiel-Dialoge

**Prompt:** _„Gib mir alles, was du über marcus@firma.de weißt."_
`printix_user_360(query="marcus@firma.de")` liefert die komplette 360°-Sicht.

**Prompt:** _„Warum kann Anna nicht mehr drucken?"_
`printix_diagnose_user(email="anna@firma.de")` prüft Status, SSO, Karten, Gruppen, aktive Blockaden — und gibt eine Diagnose mit Lösungs-Hinweisen zurück.

**Prompt:** _„Welche User sind seit 180 Tagen inaktiv?"_
`printix_inactive_users(days=180)` — Kandidatenliste fürs Offboarding.

**Prompt:** _„Leg einen neuen Mitarbeiter an: peter@firma.de, Peter Meier, Gruppe 'Finance'."_
`printix_onboard_user(...)` führt alle Schritte in der richtigen Reihenfolge aus.

---

## 5. Karten & Kartenprofile

Alles rund um RFID-/Mifare-/HID-Karten: Registrierung, Mapping, Profil-Erkennung, Bulk-Import. Die `decode`/`transform`-Tools sind besonders hilfreich beim Debugging unbekannter Karten-Profile.

| Tool | Zweck |
|------|-------|
| `printix_list_cards` | Karten eines bestimmten Users. |
| `printix_list_cards_by_tenant` | Alle Karten des Tenants (Filter: `all`/`registered`/`orphaned`). |
| `printix_search_card` | Karte per ID oder Kartennummer suchen. |
| `printix_register_card` | Karte einem User zuordnen. |
| `printix_delete_card` | Karten-Zuordnung entfernen. |
| `printix_get_card_details` | Karte + lokales Mapping + Owner-Details in einem Block. |
| `printix_decode_card_value` | Raw-Kartenwert dekodieren (Base64, Hex, YSoft/Konica-Varianten). |
| `printix_transform_card_value` | Kartenwert durch Transformationskette schicken (Hex↔Dezimal, Reverse, Base64, Prefix/Suffix …). |
| `printix_get_user_card_context` | User + alle seine Karten + Profile in einem Block. |
| `printix_list_card_profiles` / `printix_get_card_profile` | Kartenprofile-Listing / -Details. |
| `printix_search_card_mappings` | Lokale Karten-Mapping-DB durchsuchen. |
| `printix_bulk_import_cards` | CSV/JSON-Massenimport (mit Profil + Dry-Run-Modus). |
| `printix_suggest_profile` | Schlägt anhand einer Beispiel-UID das passende Profil vor (Ranking mit Top-10). |
| `printix_card_audit` | Audit-Trail aller Karten-Änderungen für einen User. |
| `printix_find_orphaned_mappings` | Lokale Mappings ohne zugehörigen Printix-User (Cleanup-Kandidaten). |

### Beispiel-Dialoge

**Prompt:** _„Welche Karten hat Marcus?"_
`printix_list_cards` (nach `printix_find_user` für die User-ID) oder kompakter `printix_get_user_card_context`.

**Prompt:** _„Was ist die Karte mit der UID `04:5F:F0:02:AB:3C`?"_
`printix_decode_card_value(card_value="04:5F:F0:02:AB:3C")` erkennt Hex-UID mit Trennzeichen, liefert `decoded_bytes_hex` und `profile_hint: "hex-input"`.

**Prompt:** _„Import mir 500 Karten aus dieser CSV — aber erst mal als Dry-Run."_
`printix_bulk_import_cards(..., dry_run=True)` prüft jede Zeile gegen das ausgewählte Profil und zeigt Vorschau-Werte, ohne etwas in Printix zu schreiben.

**Prompt:** _„Für UID `045FF002` — welches Profil passt?"_
`printix_suggest_profile(sample_uid="045FF002")` liefert Top-10-Profile mit Score + das `best_match`.

---

## 6. Reports & Analysen

Die Reports-Engine läuft gegen ein separates SQL Server-Warehouse. Sie bekommen Kennzahlen, Trends, Anomalien und Ad-hoc-Queries über ein einheitliches Interface. `query_any` ist der universelle Einstieg — die spezialisierten Tools sind schnellere Abkürzungen für gängige Fragen.

| Tool | Zweck |
|------|-------|
| `printix_reporting_status` | Status der Reports-Engine (DB-Verbindung, letzte Nightly-Runs, Preset-Count). |
| `printix_query_any` | Universal: gib ein Preset + Filter, bekomm eine Tabelle. |
| `printix_query_print_stats` | Druckvolumen nach beliebiger Dimension. |
| `printix_query_cost_report` | Druckkosten, optional nach Abteilung/User. |
| `printix_query_top_users` / `printix_query_top_printers` | Top-N mit Zeitfenster. |
| `printix_query_anomalies` | Anomalie-Erkennung (Ausreißer, ungewöhnliche Muster). |
| `printix_query_trend` | Trendlinien über Zeit. |
| `printix_query_audit_log` | Strukturierter Audit-Trail des MCP-Servers selbst (Aktionen, Objekte, Actor). |
| `printix_top_printers` / `printix_top_users` | Kurzform (Tage + Limit + Metrik). |
| `printix_print_trends` | Trend nach Tag/Woche/Monat. |
| `printix_cost_by_department` | Kosten aggregiert pro Abteilung. |
| `printix_compare_periods` | Periode A gegen Periode B stellen. |

### Beispiel-Dialoge

**Prompt:** _„Wer hat letzten Monat am meisten gedruckt?"_
`printix_top_users(days=30, limit=10, metric="pages")`.

**Prompt:** _„Wie sieht der Druck-Trend der letzten 90 Tage aus, monatlich?"_
`printix_print_trends(group_by="month", days=90)`.

**Prompt:** _„Vergleich die letzten 30 Tage mit den 30 Tagen davor — was hat sich geändert?"_
`printix_compare_periods(days_a=30, days_b=30)` liefert Delta-Kennzahlen.

**Prompt:** _„Welche Aktionen hat User X am 15. April im MCP ausgeführt?"_
`printix_query_audit_log(start_date="2026-04-15", end_date="2026-04-15", ...)` — gefiltert auf den Mandanten.

---

## 7. Report-Templates & Scheduling

Wenn Sie eine Analyse regelmäßig brauchen: speichern als Template, einplanen als wiederkehrenden Versand, per E-Mail zustellen lassen. Design-Optionen (Farben, Logos, Layout) werden über `list_design_options` abgefragt; `preview_report` rendert eine Vorschau-PDF ohne tatsächlich zu versenden.

| Tool | Zweck |
|------|-------|
| `printix_save_report_template` | Query + Design als Template speichern. |
| `printix_list_report_templates` | Alle gespeicherten Templates. |
| `printix_get_report_template` | Template-Details. |
| `printix_delete_report_template` | Template löschen. |
| `printix_run_report_now` | Template jetzt einmalig ausführen und zustellen. |
| `printix_send_test_email` | Test-Mail an eine Adresse, um SMTP zu prüfen. |
| `printix_schedule_report` | Template als Cron-Job einplanen. |
| `printix_list_schedules` | Alle aktiven Schedules. |
| `printix_update_schedule` / `printix_delete_schedule` | Schedule ändern/entfernen. |
| `printix_list_design_options` | Welche Farbschemata, Logos, Layout-Varianten stehen zur Verfügung. |
| `printix_preview_report` | Vorschau-PDF eines Reports ohne Versand. |

### Beispiel-Dialoge

**Prompt:** _„Speichere den aktuellen Top-10-User-Report als Template 'Monatlicher Druck-Top10'."_
`printix_save_report_template(...)` speichert Preset + Filter + Design.

**Prompt:** _„Schicke dieses Template jeden ersten Werktag des Monats an management@firma.de."_
`printix_schedule_report(report_id=…, cron="0 8 1 * *", recipients=["management@firma.de"])`.

**Prompt:** _„Zeig mir die Vorschau von Template XY als PDF."_
`printix_preview_report(report_id=…)` — rendert PDF, ohne etwas zu versenden.

---

## 8. Capture / Workflow-Automation

Capture verknüpft eingescannte Dokumente mit Ziel-Systemen (Paperless-ngx, SharePoint, DMS …) über Plugins. Die Tools hier zeigen den Status und die konfigurierten Profile — die eigentliche Plugin-Konfiguration erfolgt in der Web-UI.

| Tool | Zweck |
|------|-------|
| `printix_list_capture_profiles` | Alle konfigurierten Capture-Profile des Tenants. |
| `printix_capture_status` | Status: Server-Port, Webhook-Base-URL, verfügbare Plugins, konfigurierte Profile. |

### Beispiel-Dialoge

**Prompt:** _„Ist Capture aktiv, und welche Plugins habe ich installiert?"_
`printix_capture_status` liefert Plugin-Liste (inkl. paperless_ngx) + Anzahl konfigurierter Profile.

**Prompt:** _„Welche Capture-Profile sind für meinen Tenant aktiv?"_
`printix_list_capture_profiles` — Liste mit Ziel-System, Dateinamen-Pattern und letzten Ausführungen.

---

## 9. Betrieb, Wartung & Audit

Backups, Demo-Daten, Feature-Requests, Audit-Log. Diese Tools sind ein Mix aus Operations (Backup) und Meta (Feature-Tracking).

| Tool | Zweck |
|------|-------|
| `printix_list_backups` | Alle vorhandenen Backups. |
| `printix_create_backup` | Neues Backup der lokalen Konfiguration + DB erzeugen. |
| `printix_demo_setup_schema` | Demo-Schema in der Reports-DB anlegen (Sandbox). |
| `printix_demo_generate` | Synthetische Demo-Daten erzeugen. |
| `printix_demo_rollback` | Demo-Daten wieder entfernen (per Demo-Tag). |
| `printix_demo_status` | Zeigt welche Demo-Sets aktiv sind. |
| `printix_list_feature_requests` / `printix_get_feature_request` | Ticketsystem für Feature-Wünsche. |

### Beispiel-Dialoge

**Prompt:** _„Mach ein Backup, bevor ich was ändere."_
`printix_create_backup` erzeugt ein Zip mit DB + Konfig + Metadaten.

**Prompt:** _„Setze mir eine Demo-Umgebung mit 50 Usern und 500 Jobs auf."_
`printix_demo_setup_schema` (einmalig) + `printix_demo_generate(users=50, jobs=500)`.

**Prompt:** _„Zeig mir alle offenen Feature-Requests."_
`printix_list_feature_requests(status="open")`.

---

## Tipps für produktive AI-Dialoge

1. **Sprechen Sie in Zielen, nicht in Tools.** „Wer druckt zu viel?" ist besser als „ruf query_top_users mit days=30 auf". Der Assistent wählt das richtige Werkzeug.
2. **Liefern Sie Kontext mit.** „Marcus aus der Finance-Abteilung" ist eindeutiger als nur „Marcus".
3. **Nutzen Sie die 360°-Tools.** `printix_user_360`, `printix_get_queue_context`, `printix_site_summary` sparen mehrere Nachfragen.
4. **Bei Fehlern nach der Ursache fragen.** „Warum ist das schiefgegangen?" oder „Erklär mir diesen Fehler" triggert `printix_explain_error` oder `printix_diagnose_user`.
5. **Dry-Run vor Bulk-Operationen.** `printix_bulk_import_cards` hat einen `dry_run=True`-Modus — nutzen Sie ihn.

---

*Dokument generiert aus dem Printix MCP Server v6.7.116 · April 2026*
