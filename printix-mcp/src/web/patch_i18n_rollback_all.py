#!/usr/bin/env python3
"""Patch i18n.py: add demo_btn_rollback_all + demo_confirm_rollback_all to all 12 language sections."""
import re, sys

path = "/addons/printix-mcp-addon/printix-mcp/src/web/i18n.py"
content = open(path).read()

if "demo_btn_rollback_all" in content:
    print("Keys already present — nothing to do")
    sys.exit(0)

# Translations per language (ordered as they appear in i18n.py)
TRANSLATIONS = {
    "de":            ("Alle Demo-Daten löschen",        "Wirklich ALLE Demo-Daten dieses Tenants löschen?"),
    "en":            ("Delete All Demo Data",           "Really delete ALL demo data for this tenant?"),
    "fr":            ("Supprimer toutes les données démo", "Supprimer TOUTES les données démo de ce tenant ?"),
    "it":            ("Elimina tutti i dati demo",      "Eliminare TUTTI i dati demo di questo tenant?"),
    "es":            ("Eliminar todos los datos demo",  "¿Eliminar TODOS los datos demo de este tenant?"),
    "nl":            ("Alle demogegevens verwijderen",  "Echt ALLE demogegevens van deze tenant verwijderen?"),
    "no":            ("Slett alle demodata",            "Vil du virkelig slette ALLE demodata for denne tenanten?"),
    "sv":            ("Ta bort alla demodata",          "Vill du verkligen ta bort ALL demodata för den här klienten?"),
    "bar":           ("Alle Demo-Daten foatschmeißn",   "Wirklich ALLE Demo-Daten von dem Tenant foatschmeißn?"),
    "hessisch":      ("Alle Demo-Daten wegmache",       "Wirklich ALLE Demo-Daten von dem Tenant wegmache?"),
    "oesterreichisch": ("Alle Demo-Daten löschen",      "Wirklich ALLE Demo-Daten des Mandanten löschen?"),
    "schwiizerdütsch": ("Alli Demo-Date lösche",        "Wirklich ALLI Demo-Date vo dem Mandant lösche?"),
}

# Each language section has demo_btn_rollback on one line; insert the two new keys after it
# Pattern: find '        "demo_btn_rollback":  "...",' and append two new lines after
def make_insert(btn_text, confirm_text):
    return (
        f'        "demo_btn_rollback_all":     "{btn_text}",\n'
        f'        "demo_confirm_rollback_all": "{confirm_text}",\n'
    )

# Map language code → insertion lines
# We iterate over all occurrences of demo_btn_rollback in order and pair them with languages
lang_order = ["de","en","fr","it","es","nl","no","sv","bar","hessisch","oesterreichisch","schwiizerdütsch"]

new_content = content
offset = 0
pattern = re.compile(r'        "demo_btn_rollback":  "([^"]+)",\n')
matches = list(pattern.finditer(content))
print(f"Found {len(matches)} occurrences of demo_btn_rollback")

for i, m in enumerate(matches):
    lang = lang_order[i] if i < len(lang_order) else "??"
    btn_text, confirm_text = TRANSLATIONS.get(lang, ("Delete All Demo Data", "Really delete ALL demo data?"))
    insert = make_insert(btn_text, confirm_text)
    # Position in new_content (adjusted by offset)
    end_pos = m.end() + offset
    new_content = new_content[:end_pos] + insert + new_content[end_pos:]
    offset += len(insert)
    print(f"  [{lang}] inserted after line with demo_btn_rollback")

open(path, 'w').write(new_content)
count = new_content.count("demo_btn_rollback_all")
print(f"\nDone! {len(content)} → {len(new_content)} chars, {count} new keys inserted")
