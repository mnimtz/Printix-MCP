"""
Demo Data Generator — Printix BI Datenbank
==========================================
Generiert realistische Demo-Daten für eine eigene Azure SQL-Datenbank.

Features:
  - Kulturell passende Namen in 8 Sprachen (DE, EN, FR, IT, ES, NL, SV, NO)
  - Herstellerbasierte Drucker-Namenskonvention (HP, Xerox, Canon, Ricoh, KM, Kyocera)
  - Realistische Druckvolumen-Verteilung (Saisonalität, Tageszeiten, Duplex/Farbe)
  - Print-, Scan- und Kopieraufträge mit Dateinamen und Capture-Workflows
  - Komplettes Rollback via demo_session_id — alle Demo-Daten löschbar

Schema: Spiegelt die Printix BI-Datenbank exakt, plus demo_session_id-Spalte.
"""

import uuid
import json
import random
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Konstanten: Namen ──────────────────────────────────────────────────────────

NAMES: dict[str, dict[str, list[str]]] = {
    "de": {
        "first": ["Hans","Klaus","Petra","Sabine","Michael","Andrea","Thomas","Maria",
                  "Günther","Ursula","Wolfgang","Monika","Dieter","Brigitte","Frank",
                  "Christine","Bernd","Karin","Jörg","Ute","Rainer","Ingrid","Holger","Silke",
                  "Stefan","Barbara","Martin","Claudia","Andreas","Susanne","Jürgen","Gabriele",
                  "Peter","Birgit","Matthias","Kerstin","Rolf","Heike","Gerhard","Angelika",
                  "Uwe","Elke","Ralf","Marion","Harald","Manuela","Norbert","Nicole","Helmut",
                  "Martina","Volker","Beate","Dirk","Anja","Axel","Tanja","Bernhard","Daniela",
                  "Karl","Simone","Fabian","Julia","Lukas","Lena","Sebastian","Nina","Tobias",
                  "Katharina","Alexander","Sandra","Markus","Stefanie"],
        "last":  ["Müller","Schmidt","Schneider","Fischer","Weber","Meyer","Wagner","Becker",
                  "Schulz","Hoffmann","Schäfer","Koch","Bauer","Richter","Klein","Wolf",
                  "Schröder","Neumann","Schwarz","Zimmermann","Braun","Krüger","Hofmann","Lange",
                  "Schmitt","Werner","Schmitz","Krause","Meier","Lehmann","Schmid","Schulze",
                  "Maier","Köhler","Herrmann","König","Walter","Mayer","Huber","Kaiser","Fuchs",
                  "Peters","Lang","Scholz","Möller","Weiß","Jung","Hahn","Schubert","Vogel",
                  "Friedrich","Keller","Günther","Frank","Berger","Winkler","Roth","Beck",
                  "Lorenz","Baumann","Franke","Albrecht","Schuster","Simon","Ludwig","Böhm",
                  "Winter","Kraus","Martin","Schumacher","Krämer","Vogt","Stein","Jäger","Otto"],
    },
    "en": {
        "first": ["John","Sarah","Michael","Emma","David","Lisa","James","Jennifer","Robert",
                  "Mary","William","Patricia","Richard","Linda","Joseph","Barbara","Thomas",
                  "Elizabeth","Charles","Susan","Daniel","Jessica","Matthew","Ashley",
                  "Christopher","Amanda","Andrew","Melissa","Joshua","Deborah","Kenneth",
                  "Stephanie","Paul","Rebecca","Mark","Laura","Donald","Helen","Steven","Sharon",
                  "Kevin","Cynthia","Brian","Kathleen","George","Amy","Edward","Shirley","Ronald",
                  "Angela","Timothy","Anna","Jason","Brenda","Jeffrey","Pamela","Ryan","Nicole",
                  "Jacob","Samantha","Gary","Katherine","Nicholas","Christine","Eric","Debra",
                  "Jonathan","Rachel","Stephen","Catherine","Larry","Carolyn","Justin","Janet"],
        "last":  ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
                  "Wilson","Taylor","Anderson","Jackson","White","Harris","Martin",
                  "Thompson","Young","Walker","Robinson","Lewis","Clark","Hall","Allen",
                  "Wright","King","Scott","Green","Baker","Adams","Nelson","Carter","Mitchell",
                  "Perez","Roberts","Turner","Phillips","Campbell","Parker","Evans","Edwards",
                  "Collins","Stewart","Morris","Rogers","Reed","Cook","Morgan","Bell","Murphy",
                  "Bailey","Rivera","Cooper","Richardson","Cox","Howard","Ward","Torres",
                  "Peterson","Gray","Ramirez","James","Watson","Brooks","Kelly","Sanders",
                  "Price","Bennett","Wood","Barnes","Ross","Henderson","Coleman","Jenkins"],
    },
    "fr": {
        "first": ["Jean","Marie","Pierre","Sophie","Luc","Isabelle","François","Nathalie",
                  "Philippe","Sylvie","Michel","Catherine","Christophe","Valérie","Nicolas",
                  "Sandrine","Stéphane","Laurence","Patrick","Anne","Julien","Céline",
                  "Olivier","Véronique","Alain","Brigitte","Laurent","Corinne","Éric",
                  "Martine","Thierry","Nicole","Bruno","Chantal","Pascal","Dominique",
                  "Frédéric","Florence","Didier","Christine","Hervé","Monique","Sébastien",
                  "Caroline","Vincent","Hélène","Xavier","Karine","Emmanuel","Emilie","Fabien",
                  "Camille","Antoine","Julie","Alexandre","Delphine","Mathieu","Aurélie",
                  "Guillaume","Stéphanie","Romain","Sarah","Arnaud","Marion","Damien","Audrey",
                  "Cédric","Élodie","Gilles","Charlotte","Thomas","Amélie","Rémy","Manon"],
        "last":  ["Dupont","Martin","Bernard","Dubois","Thomas","Robert","Richard","Petit",
                  "Durand","Leroy","Moreau","Simon","Laurent","Lefebvre","Michel","Garcia",
                  "David","Bertrand","Roux","Vincent","Fournier","Morel","Girard","André",
                  "Mercier","Blanc","Guérin","Boyer","Garnier","Chevalier","Francois","Legrand",
                  "Gauthier","Perrin","Robin","Clément","Morin","Nicolas","Henry","Roussel",
                  "Mathieu","Gautier","Masson","Marchand","Duval","Denis","Dumont","Marie",
                  "Lemaire","Noël","Meyer","Dufour","Meunier","Brun","Blanchard","Giraud",
                  "Joly","Rivière","Lucas","Brunet","Gaillard","Barbier","Arnaud","Martinez",
                  "Gerard","Roche","Renard","Schmitt","Roy","Leroux","Colin","Vidal","Caron"],
    },
    "it": {
        "first": ["Marco","Giulia","Luca","Sara","Andrea","Francesca","Matteo","Chiara",
                  "Davide","Valentina","Alessandro","Laura","Simone","Elena","Federico",
                  "Martina","Riccardo","Paola","Stefano","Giorgia","Antonio","Roberta",
                  "Giuseppe","Silvia","Francesco","Anna","Giovanni","Alessia","Paolo",
                  "Barbara","Roberto","Cristina","Luigi","Claudia","Salvatore","Monica",
                  "Mario","Patrizia","Vincenzo","Rossella","Alberto","Daniela","Fabio","Raffaella",
                  "Massimo","Lucia","Enrico","Manuela","Claudio","Michela","Giorgio","Elisa",
                  "Pietro","Tiziana","Carlo","Sabrina","Lorenzo","Angela","Nicola","Rita",
                  "Emanuele","Letizia","Gianluca","Serena","Alessio","Eleonora","Filippo","Ilaria"],
        "last":  ["Rossi","Ferrari","Russo","Bianchi","Romano","Gallo","Costa","Fontana",
                  "Conti","Esposito","Ricci","Bruno","De Luca","Moretti","Lombardi",
                  "Barbieri","Testa","Serra","Fabbri","Villa","Pellegrini","Marini",
                  "Greco","Mancini","Marino","Rizzo","Lombardo","Giordano","Galli","Leone",
                  "Longo","Gentile","Martinelli","Cattaneo","Morelli","Ferrara","Santoro",
                  "Mariani","Rinaldi","Caruso","Ferri","Sala","Monti","De Santis","Marchetti",
                  "D'Amico","Colombo","Gatti","Parisi","Bellini","Grassi","Benedetti","Giuliani",
                  "Amato","Battaglia","Sanna","Farina","Palumbo","Coppola","Basile","Riva",
                  "Donati","Orlando","Bianco","Valentini","Pagano","Piras","Messina","Cattivelli"],
    },
    "es": {
        "first": ["Carlos","Ana","Miguel","Carmen","José","María","Antonio","Isabel",
                  "Francisco","Laura","Manuel","Marta","Juan","Cristina","David","Elena",
                  "Pedro","Lucía","Alejandro","Patricia","Diego","Sofía","Javier","Raquel",
                  "Jorge","Rosa","Luis","Pilar","Rafael","Dolores","Ángel","Teresa","Fernando",
                  "Nuria","Ramón","Mónica","Jesús","Beatriz","Rubén","Ángela","Sergio","Silvia",
                  "Alberto","Rocío","Óscar","Sonia","Iván","Julia","Álvaro","Alicia","Mario",
                  "Eva","Adrián","Clara","Pablo","Inés","Daniel","Andrea","Víctor","Natalia",
                  "Roberto","Sara","Enrique","Claudia","Gabriel","Paula","Emilio","Victoria","Marcos"],
        "last":  ["García","Martínez","López","Sánchez","González","Pérez","Rodríguez",
                  "Fernández","Torres","Ramírez","Flores","Morales","Ortiz","Vargas","Díaz",
                  "Reyes","Gómez","Molina","Herrera","Silva","Castro","Romero","Navarro",
                  "Jiménez","Álvarez","Moreno","Muñoz","Alonso","Gutiérrez","Ruiz","Hernández",
                  "Serrano","Blanco","Suárez","Castillo","Ortega","Rubio","Sanz","Iglesias",
                  "Nuñez","Medina","Garrido","Santos","Cortés","Lozano","Guerrero","Cano",
                  "Prieto","Méndez","Cruz","Calvo","Gallego","Vidal","León","Márquez","Herrero",
                  "Peña","Cabrera","Campos","Vega","Fuentes","Carrasco","Diez","Caballero","Reyes"],
    },
    "nl": {
        "first": ["Jan","Emma","Pieter","Sophie","Dirk","Anneke","Thomas","Lisa","Joost",
                  "Marieke","Bas","Inge","Tim","Claudia","Martijn","Evelien","Ruben",
                  "Nathalie","Sander","Iris","Lars","Roos","Jeroen","Fleur",
                  "Mark","Linda","Michiel","Esther","Wouter","Annemarie","Erik","Yvonne",
                  "Rick","Saskia","Kees","Monique","Johan","Petra","Bram","Marloes",
                  "Maarten","Wendy","Vincent","Karin","Daan","Femke","Stijn","Hanneke",
                  "Niels","Suzanne","Koen","Judith","Robin","Mirjam","Jeroen","Astrid",
                  "Jasper","Caroline","Joost","Lieke","Tom","Sanne","Freek","Mariska"],
        "last":  ["de Vries","Janssen","van den Berg","Bakker","Peters","Visser","Meijer",
                  "Bos","Mulder","de Boer","Smit","Dekker","van Leeuwen","Dijkstra","van Dijk",
                  "Vermeulen","Kok","Jacobs","Brouwer","de Groot","Willems","van der Meer",
                  "van Beek","Schouten","Hoekstra","van Dam","Verhoeven","de Wit","Prins","Bosch",
                  "Huisman","Peeters","van der Velde","Kuipers","van der Linden","Koster",
                  "Gerritsen","van Veen","van den Broek","Willemsen","Timmermans","Martens",
                  "van Loon","Hendriks","Wolters","de Lange","Koning","van Zanten","Scholten"],
    },
    "sv": {
        "first": ["Erik","Anna","Lars","Maja","Björn","Linnea","Johan","Emma","Mikael",
                  "Lena","Anders","Sofia","Per","Maria","Henrik","Sara","Jonas","Karin",
                  "Stefan","Ingrid","Oskar","Frida","Viktor","Johanna",
                  "Peter","Kerstin","Daniel","Helena","Magnus","Eva","Thomas","Birgitta",
                  "Jan","Ulla","Bengt","Margareta","Kalle","Monika","Axel","Linda",
                  "Fredrik","Cecilia","Gustav","Elsa","Ludvig","Astrid","Rasmus","Alma",
                  "Oliver","Wilma","Isak","Nora","Alexander","Ida","Simon","Alice"],
        "last":  ["Eriksson","Johansson","Andersson","Lindqvist","Nilsson","Larsson",
                  "Svensson","Gustafsson","Pettersson","Persson","Olsson","Bergström",
                  "Holm","Björk","Lindberg","Magnusson","Carlsson","Jakobsson","Hansson","Karlsson",
                  "Jonsson","Lindström","Axelsson","Berglund","Fredriksson","Sandberg","Henriksson",
                  "Forsberg","Sjöberg","Lundberg","Wallin","Engström","Danielsson","Håkansson",
                  "Lund","Bengtsson","Jönsson","Lindgren","Berg","Fransson","Holmberg","Nyström"],
    },
    "no": {
        "first": ["Erik","Ingrid","Lars","Astrid","Ole","Kari","Bjørn","Elin","Tor","Silje",
                  "Per","Anne","Gunnar","Kristin","Svein","Hanne","Trond","Randi","Dag","Marit",
                  "Jan","Berit","Arne","Liv","Rolf","Eli","Knut","Turid","Odd","Ragnhild",
                  "Geir","Sissel","Morten","Trine","Håkon","Linda","Kjell","Grete","Tore","Unni",
                  "Magnus","Mari","Eirik","Nora","Henrik","Ida","Jonas","Emma","Sindre","Ingeborg"],
        "last":  ["Hansen","Johansen","Olsen","Larsen","Andersen","Pedersen","Nilsen",
                  "Kristiansen","Jensen","Karlsen","Johnsen","Haugen","Pettersen","Eriksen",
                  "Berg","Dahl","Halvorsen","Iversen","Moen","Jacobsen","Strand","Lund",
                  "Solberg","Bakken","Svendsen","Martinsen","Rasmussen","Kristoffersen","Jørgensen",
                  "Nygård","Paulsen","Gundersen","Ellingsen","Lie","Mathisen","Knutsen","Aas",
                  "Sæther","Hagen","Antonsen","Ruud","Christensen","Thomassen","Hauge"],
    },
}

# ── Konstanten: Drucker ────────────────────────────────────────────────────────

# (vendor, model_full, code_prefix, is_color)
PRINTER_MODELS: list[tuple[str, str, str, bool]] = [
    ("HP",              "Color LaserJet Pro M479fdw",       "HP-CLJ",  True),
    ("HP",              "LaserJet Enterprise M507dn",        "HP-LJE",  False),
    ("HP",              "LaserJet Pro M404dn",               "HP-LJP",  False),
    ("HP",              "Color LaserJet Enterprise M554dn",  "HP-CLE",  True),
    ("Xerox",           "VersaLink C505",                    "XRX-VLC", True),
    ("Xerox",           "WorkCentre 7845",                   "XRX-WC",  True),
    ("Xerox",           "AltaLink C8170",                    "XRX-ALC", True),
    ("Xerox",           "Phaser 6510",                       "XRX-PH",  True),
    ("Canon",           "imageRUNNER ADVANCE C5560i",        "CNX-iR",  True),
    ("Canon",           "i-SENSYS MF543x",                   "CNX-MF",  True),
    ("Canon",           "MAXIFY GX7050",                     "CNX-MX",  True),
    ("Ricoh",           "MP C3004",                          "RCH-MPC", True),
    ("Ricoh",           "IM C2000",                          "RCH-IMC", True),
    ("Ricoh",           "SP 5310DN",                         "RCH-SP",  False),
    ("Konica Minolta",  "bizhub C450i",                      "KM-BHC",  True),
    ("Konica Minolta",  "bizhub 4702P",                      "KM-BH",   False),
    ("Kyocera",         "TASKalfa 3553ci",                   "KYO-TA",  True),
    ("Kyocera",         "ECOSYS P3145dn",                    "KYO-EC",  False),
    ("Lexmark",         "CX625ade",                          "LXM-CX",  True),
    ("Lexmark",         "MS622de",                           "LXM-MS",  False),
    ("Brother",         "MFC-L9570CDW",                      "BTH-MFC", True),
    ("Sharp",           "MX-3070N",                          "SHP-MX",  True),
]

FLOOR_CODES  = ["EG", "OG1", "OG2", "OG3", "KG", "DG"]
DEPARTMENTS  = ["IT", "HR", "FIN", "MKT", "VTR", "LOG", "MGT", "PRD", "QM", "EKF", "RD"]
PAPER_SIZES  = ["A4"] * 80 + ["A3"] * 10 + ["Letter"] * 8 + ["A5"] * 2   # weighted
MONTH_FACTORS = {1:0.95, 2:1.00, 3:1.05, 4:1.05, 5:1.00, 6:0.90,
                 7:0.80, 8:0.55, 9:1.05, 10:1.10, 11:1.00, 12:0.65}

# ── Konstanten: Dateinamen ─────────────────────────────────────────────────────

_PRINT_TEMPLATES = [
    "Rechnung_{nr:04d}.pdf",
    "Angebot_Kunde_{nr:03d}.pdf",
    "Lieferschein_{nr:05d}.pdf",
    "Bestellung_{nr:04d}.pdf",
    "Protokoll_Meeting_{date}.pdf",
    "Vertrag_{nr:03d}.pdf",
    "KV_Projekt_{nr:03d}.pdf",
    "Mahnschreiben_{nr:03d}.pdf",
    "Praesentation_Produkt.pptx",
    "Jahresbericht_{year}.pdf",
    "Budget_{year}_Q{q}.xlsx",
    "Report_Q{q}_{year}.xlsx",
    "Vertriebsbericht_KW{kw:02d}.pdf",
    "Handbuch_v{maj}.{min}.pdf",
    "Schulungsunterlage_{nr:02d}.pdf",
    "Zertifikat_{nr:03d}.pdf",
    "Reisekostenabrechnung_{date}.xlsx",
    "Projektplan_{nr:03d}.pdf",
]

_SCAN_TEMPLATES = [
    "SCAN_{date}_{time}.pdf",
    "Eingang_Rechnung_{date}.pdf",
    "Posteingang_{date}.pdf",
    "Lieferschein_Eingang_{nr:04d}.pdf",
    "Beleg_{date}.pdf",
    "Vertrag_Scan_{date}.pdf",
    "Personalakte_Eingang.pdf",
    "Brief_Eingang_{date}.pdf",
    "Zertifikat_Eingang_{date}.pdf",
]

# ── Sensible Dateinamen (v3.8.0) ──────────────────────────────────────────────
# Diese Templates enthalten bewusst Schlüsselwörter aus den 6 Keyword-Sets des
# "Sensible Dokumente"-Reports (HR, Finanzen, Vertraulich, Gesundheit, Recht, PII),
# damit Demo-Datasets Treffer für den Compliance-Scan liefern. Anteil in den
# Print-/Scan-Jobs: ~8 % (siehe _filename_print/_filename_scan).
_SENSITIVE_PRINT_TEMPLATES = [
    # HR
    "Gehaltsabrechnung_{year}_{mo:02d}.pdf",
    "Lohnabrechnung_{user}_{mo:02d}_{year}.pdf",
    "Arbeitsvertrag_{user}.pdf",
    "Kuendigung_Entwurf_{nr:03d}.pdf",
    "Personalakte_{user}.pdf",
    "Bewerbung_{user}_CV.pdf",
    # Finanzen
    "Kreditkartenabrechnung_{year}_{mo:02d}.pdf",
    "IBAN_Liste_Kunden_{year}.xlsx",
    "Kontoauszug_{year}_{mo:02d}.pdf",
    "Steuererklaerung_{year}.pdf",
    "Bilanz_Entwurf_{year}.xlsx",
    # Vertraulich / Confidential
    "VERTRAULICH_Strategie_{year}.pdf",
    "Confidential_Board_Meeting_{date}.pdf",
    "NDA_{kunde}_{nr:03d}.pdf",
    "Geheim_MA_Deal_{nr:03d}.pdf",
    # Gesundheit / Health
    "Krankmeldung_{user}_{date}.pdf",
    "Arztbrief_{user}.pdf",
    "AU_Bescheinigung_{nr:04d}.pdf",
    # Recht / Legal
    "Klageschrift_{nr:03d}.pdf",
    "Anwaltsschreiben_{kunde}.pdf",
    "Gerichtsbeschluss_{nr:04d}.pdf",
    "Mahnbescheid_{nr:04d}.pdf",
    # PII
    "Personalausweis_Kopie_{user}.pdf",
    "Reisepass_Scan_{user}.pdf",
    "SVN_Liste_{year}.xlsx",
]

_SENSITIVE_SCAN_TEMPLATES = [
    "SCAN_Personalausweis_{date}.pdf",
    "SCAN_Reisepass_{date}.pdf",
    "SCAN_Gehaltsabrechnung_{date}.pdf",
    "SCAN_Arbeitsvertrag_{date}.pdf",
    "SCAN_Krankmeldung_{date}.pdf",
    "SCAN_Arztbrief_{date}.pdf",
    "SCAN_Kontoauszug_{date}.pdf",
    "SCAN_NDA_Vertraulich_{date}.pdf",
    "SCAN_Anwaltsschreiben_{date}.pdf",
    "SCAN_Personalakte_{date}.pdf",
    "SCAN_Kreditkarte_Beleg_{date}.pdf",
    "SCAN_VERTRAULICH_{date}.pdf",
]

# Wahrscheinlichkeit, mit der ein Dateiname aus dem sensiblen Pool gezogen wird.
_SENSITIVE_RATIO = 0.08

CAPTURE_WORKFLOWS = [
    "Posteingang digitalisieren",
    "Rechnungen Buchhaltung",
    "HR Personalakte",
    "Verträge Archiv",
    "Lieferscheine Lager",
    "Eingangspost Büro",
    "Qualitätsdoku QM",
    "Kundenkorrespondenz",
    "Behördenpost",
    "Projektdokumentation",
    "Finanzdokumente",
    "Einkauf Bestellungen",
]

# ── Azure SQL Schema ───────────────────────────────────────────────────────────

SCHEMA_STATEMENTS: list[str] = [
    # demo schema
    """
    IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'demo')
        EXEC('CREATE SCHEMA demo')
    """,
    # networks
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='networks' AND schema_id=SCHEMA_ID('demo'))
    CREATE TABLE demo.networks (
        id              NVARCHAR(100) NOT NULL,
        tenant_id       NVARCHAR(100) NOT NULL,
        name            NVARCHAR(255) NOT NULL,
        demo_session_id NVARCHAR(100) NULL,
        CONSTRAINT PK_networks PRIMARY KEY (id)
    )
    """,
    # users
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='users' AND schema_id=SCHEMA_ID('demo'))
    CREATE TABLE demo.users (
        id              NVARCHAR(100) NOT NULL,
        tenant_id       NVARCHAR(100) NOT NULL,
        email           NVARCHAR(255) NOT NULL,
        name            NVARCHAR(255) NOT NULL,
        department      NVARCHAR(255) NULL,
        demo_session_id NVARCHAR(100) NULL,
        CONSTRAINT PK_users PRIMARY KEY (id)
    )
    """,
    # printers
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='printers' AND schema_id=SCHEMA_ID('demo'))
    CREATE TABLE demo.printers (
        id              NVARCHAR(100) NOT NULL,
        tenant_id       NVARCHAR(100) NOT NULL,
        name            NVARCHAR(255) NOT NULL,
        model_name      NVARCHAR(255) NULL,
        vendor_name     NVARCHAR(255) NULL,
        network_id      NVARCHAR(100) NULL,
        location        NVARCHAR(255) NULL,
        demo_session_id NVARCHAR(100) NULL,
        CONSTRAINT PK_printers PRIMARY KEY (id)
    )
    """,
    # jobs
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='jobs' AND schema_id=SCHEMA_ID('demo'))
    CREATE TABLE demo.jobs (
        id              NVARCHAR(100) NOT NULL,
        tenant_id       NVARCHAR(100) NOT NULL,
        color           BIT          NOT NULL DEFAULT 0,
        duplex          BIT          NOT NULL DEFAULT 0,
        page_count      INT          NOT NULL DEFAULT 1,
        paper_size      NVARCHAR(50) NULL,
        printer_id      NVARCHAR(100) NULL,
        submit_time     DATETIME2    NULL,
        tenant_user_id  NVARCHAR(100) NULL,
        filename        NVARCHAR(500) NULL,
        demo_session_id NVARCHAR(100) NULL,
        CONSTRAINT PK_jobs PRIMARY KEY (id)
    )
    """,
    # tracking_data  (IDENTITY — kein id im INSERT)
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='tracking_data' AND schema_id=SCHEMA_ID('demo'))
    CREATE TABLE demo.tracking_data (
        id               BIGINT IDENTITY(1,1) NOT NULL,
        job_id           NVARCHAR(100) NOT NULL,
        tenant_id        NVARCHAR(100) NOT NULL,
        page_count       INT          NOT NULL DEFAULT 1,
        color            BIT          NOT NULL DEFAULT 0,
        duplex           BIT          NOT NULL DEFAULT 0,
        print_time       DATETIME2    NOT NULL,
        printer_id       NVARCHAR(100) NULL,
        print_job_status NVARCHAR(50) NOT NULL DEFAULT 'PRINT_OK',
        demo_session_id  NVARCHAR(100) NULL,
        CONSTRAINT PK_tracking_data PRIMARY KEY (id)
    )
    """,
    # jobs_scan
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='jobs_scan' AND schema_id=SCHEMA_ID('demo'))
    CREATE TABLE demo.jobs_scan (
        id              NVARCHAR(100) NOT NULL,
        tenant_id       NVARCHAR(100) NOT NULL,
        printer_id      NVARCHAR(100) NULL,
        tenant_user_id  NVARCHAR(100) NULL,
        scan_time       DATETIME2    NOT NULL,
        page_count      INT          NOT NULL DEFAULT 1,
        color           BIT          NOT NULL DEFAULT 0,
        workflow_name   NVARCHAR(500) NULL,
        filename        NVARCHAR(500) NULL,
        demo_session_id NVARCHAR(100) NULL,
        CONSTRAINT PK_jobs_scan PRIMARY KEY (id)
    )
    """,
    # v3.8.0 — idempotente Migration: filename-Spalte nachrüsten für bestehende Installationen
    """
    IF NOT EXISTS (
        SELECT 1 FROM sys.columns
        WHERE object_id = OBJECT_ID('demo.jobs_scan') AND name = 'filename'
    )
        ALTER TABLE demo.jobs_scan ADD filename NVARCHAR(500) NULL
    """,
    # jobs_copy
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='jobs_copy' AND schema_id=SCHEMA_ID('demo'))
    CREATE TABLE demo.jobs_copy (
        id              NVARCHAR(100) NOT NULL,
        tenant_id       NVARCHAR(100) NOT NULL,
        printer_id      NVARCHAR(100) NULL,
        tenant_user_id  NVARCHAR(100) NULL,
        copy_time       DATETIME2    NOT NULL,
        demo_session_id NVARCHAR(100) NULL,
        CONSTRAINT PK_jobs_copy PRIMARY KEY (id)
    )
    """,
    # jobs_copy_details
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='jobs_copy_details' AND schema_id=SCHEMA_ID('demo'))
    CREATE TABLE demo.jobs_copy_details (
        id              NVARCHAR(100) NOT NULL,
        job_id          NVARCHAR(100) NOT NULL,
        page_count      INT          NOT NULL DEFAULT 1,
        paper_size      NVARCHAR(50) NULL,
        duplex          BIT          NOT NULL DEFAULT 0,
        color           BIT          NOT NULL DEFAULT 0,
        demo_session_id NVARCHAR(100) NULL,
        CONSTRAINT PK_jobs_copy_details PRIMARY KEY (id)
    )
    """,
    # demo_sessions  (Rollback-Tracking)
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='demo_sessions' AND schema_id=SCHEMA_ID('demo'))
    CREATE TABLE demo.demo_sessions (
        session_id      NVARCHAR(100) NOT NULL,
        tenant_id       NVARCHAR(100) NOT NULL,
        demo_tag        NVARCHAR(100) NOT NULL,
        created_at      DATETIME2    NOT NULL,
        params_json     NVARCHAR(MAX) NULL,
        status          NVARCHAR(50) NOT NULL DEFAULT 'active',
        user_count      INT NOT NULL DEFAULT 0,
        printer_count   INT NOT NULL DEFAULT 0,
        network_count   INT NOT NULL DEFAULT 0,
        print_job_count INT NOT NULL DEFAULT 0,
        scan_job_count  INT NOT NULL DEFAULT 0,
        copy_job_count  INT NOT NULL DEFAULT 0,
        CONSTRAINT PK_demo_sessions PRIMARY KEY (session_id)
    )
    """,
    # Indexes
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_td_tenant_time' AND object_id=OBJECT_ID('demo.tracking_data'))
        CREATE INDEX IX_td_tenant_time ON demo.tracking_data (tenant_id, print_time)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_td_demo' AND object_id=OBJECT_ID('demo.tracking_data'))
        CREATE INDEX IX_td_demo ON demo.tracking_data (demo_session_id)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_jobs_tenant' AND object_id=OBJECT_ID('demo.jobs'))
        CREATE INDEX IX_jobs_tenant ON demo.jobs (tenant_id, submit_time)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_users_tenant' AND object_id=OBJECT_ID('demo.users'))
        CREATE INDEX IX_users_tenant ON demo.users (tenant_id, email)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_printers_network' AND object_id=OBJECT_ID('demo.printers'))
        CREATE INDEX IX_printers_network ON demo.printers (tenant_id, network_id)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_scan_tenant' AND object_id=OBJECT_ID('demo.jobs_scan'))
        CREATE INDEX IX_scan_tenant ON demo.jobs_scan (tenant_id, scan_time)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_copy_tenant' AND object_id=OBJECT_ID('demo.jobs_copy'))
        CREATE INDEX IX_copy_tenant ON demo.jobs_copy (tenant_id, copy_time)
    """,
    # ── Reporting Schema & Views ───────────────────────────────────────────────
    # Erstellt reporting-Schema mit VIEWs die echte + Demo-Daten kombinieren.
    # Demo-Daten erscheinen nur wenn aktive Demo-Sessions für den Tenant existieren.
    """
    IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'reporting')
        EXEC('CREATE SCHEMA reporting')
    """,
    """
    CREATE OR ALTER VIEW reporting.v_tracking_data AS
    -- dbo.tracking_data.id = uniqueidentifier, demo.tracking_data.id = bigint
    -- → beide explizit auf NVARCHAR(36) casten, damit UNION ALL kompatibel wird.
    SELECT CAST(id AS NVARCHAR(36)) AS id, job_id, tenant_id, page_count, color, duplex,
           print_time, printer_id, print_job_status
    FROM dbo.tracking_data
    UNION ALL
    SELECT CAST(id AS NVARCHAR(36)) AS id, job_id, tenant_id, page_count, color, duplex,
           print_time, printer_id, print_job_status
    FROM demo.tracking_data
    WHERE EXISTS (
        SELECT 1 FROM demo.demo_sessions ds
        WHERE ds.tenant_id = demo.tracking_data.tenant_id AND ds.status = 'active'
    )
    """,
    # v_jobs wird via dynamischem SQL erstellt — siehe _create_v_jobs_view() unten.
    # Grund: dbo.jobs hat in manchen Printix-BI-Datenbanken KEINE `name`-Spalte.
    # Ein statisches CREATE VIEW mit CAST(name ...) AS filename scheitert dann
    # still, und der Compliance-Report „Sensible Dokumente" liefert 0 Treffer
    # weil weder die View noch der Fallback Demo-Daten einschließt.
    "-- v_jobs: see _create_v_jobs_view()",
    """
    CREATE OR ALTER VIEW reporting.v_users AS
    SELECT id, tenant_id, email, name, department
    FROM dbo.users
    UNION ALL
    SELECT id, tenant_id, email, name, department
    FROM demo.users
    WHERE EXISTS (
        SELECT 1 FROM demo.demo_sessions ds
        WHERE ds.tenant_id = demo.users.tenant_id AND ds.status = 'active'
    )
    """,
    """
    CREATE OR ALTER VIEW reporting.v_printers AS
    SELECT id, tenant_id, name, model_name, vendor_name, network_id, location
    FROM dbo.printers
    UNION ALL
    SELECT id, tenant_id, name, model_name, vendor_name, network_id, location
    FROM demo.printers
    WHERE EXISTS (
        SELECT 1 FROM demo.demo_sessions ds
        WHERE ds.tenant_id = demo.printers.tenant_id AND ds.status = 'active'
    )
    """,
    """
    CREATE OR ALTER VIEW reporting.v_networks AS
    SELECT id, tenant_id, name
    FROM dbo.networks
    UNION ALL
    SELECT id, tenant_id, name
    FROM demo.networks
    WHERE EXISTS (
        SELECT 1 FROM demo.demo_sessions ds
        WHERE ds.tenant_id = demo.networks.tenant_id AND ds.status = 'active'
    )
    """,
    """
    CREATE OR ALTER VIEW reporting.v_jobs_scan AS
    -- v3.8.0: filename ergänzt für den Compliance-Report "Sensible Dokumente".
    -- dbo.jobs_scan führt (soweit bekannt) keinen Dateinamen — daher NULL-Fallback.
    -- demo.jobs_scan hat seit v3.8.0 eine filename-Spalte (idempotente Migration).
    SELECT id, tenant_id, printer_id, tenant_user_id, scan_time,
           page_count, color,
           CAST(NULL AS NVARCHAR(500)) AS filename
    FROM dbo.jobs_scan
    UNION ALL
    SELECT id, tenant_id, printer_id, tenant_user_id, scan_time,
           page_count, color, filename
    FROM demo.jobs_scan
    WHERE EXISTS (
        SELECT 1 FROM demo.demo_sessions ds
        WHERE ds.tenant_id = demo.jobs_scan.tenant_id AND ds.status = 'active'
    )
    """,
    """
    CREATE OR ALTER VIEW reporting.v_jobs_copy AS
    SELECT id, tenant_id, printer_id, tenant_user_id, copy_time
    FROM dbo.jobs_copy
    UNION ALL
    SELECT id, tenant_id, printer_id, tenant_user_id, copy_time
    FROM demo.jobs_copy
    WHERE EXISTS (
        SELECT 1 FROM demo.demo_sessions ds
        WHERE ds.tenant_id = demo.jobs_copy.tenant_id AND ds.status = 'active'
    )
    """,
    """
    CREATE OR ALTER VIEW reporting.v_jobs_copy_details AS
    SELECT d.id, d.job_id, d.page_count, d.paper_size, d.duplex, d.color
    FROM dbo.jobs_copy_details d
    UNION ALL
    SELECT d.id, d.job_id, d.page_count, d.paper_size, d.duplex, d.color
    FROM demo.jobs_copy_details d
    WHERE EXISTS (
        SELECT 1 FROM demo.jobs_copy jc
        JOIN demo.demo_sessions ds ON ds.tenant_id = jc.tenant_id AND ds.status = 'active'
        WHERE jc.id = d.job_id
    )
    """,
]


# ── Schema Setup ──────────────────────────────────────────────────────────────

def _create_v_jobs_view() -> None:
    """
    Erstellt reporting.v_jobs dynamisch — prüft ob dbo.jobs eine `name`-Spalte hat.

    Das Printix-BI-Schema (v2025.4) hat in dbo.jobs KEIN `name`/`filename`-Feld.
    Manche ältere oder erweiterte Installationen haben es aber. Die View muss in
    beiden Fällen funktionieren, damit der Compliance-Report „Sensible Dokumente"
    die Demo-Dateinamen findet.
    """
    from .sql_client import execute_script, query_fetchone

    # Prüfe ob dbo.jobs.name existiert
    try:
        r = query_fetchone(
            "SELECT COUNT(*) AS cnt FROM sys.columns "
            "WHERE object_id = OBJECT_ID('dbo.jobs') AND name = 'name'"
        )
        has_name = bool((r or {}).get("cnt", 0) > 0)
    except Exception:
        has_name = False

    if has_name:
        filename_expr = "CAST(name AS NVARCHAR(500)) AS filename"
    else:
        filename_expr = "CAST(NULL AS NVARCHAR(500)) AS filename"

    sql = f"""
    CREATE OR ALTER VIEW reporting.v_jobs AS
    -- v4.0.0: dbo.jobs-Spalte dynamisch ermittelt (name oder NULL-Fallback).
    -- Wird für den Compliance-Report "Sensible Dokumente" (query_sensitive_documents)
    -- benötigt, der per LIKE im Dateinamen nach Schlüsselwörtern sucht.
    SELECT id, tenant_id, color, duplex, page_count, paper_size,
           printer_id, submit_time, tenant_user_id,
           {filename_expr}
    FROM dbo.jobs
    UNION ALL
    SELECT id, tenant_id, color, duplex, page_count, paper_size,
           printer_id, submit_time, tenant_user_id, filename
    FROM demo.jobs
    WHERE EXISTS (
        SELECT 1 FROM demo.demo_sessions ds
        WHERE ds.tenant_id = demo.jobs.tenant_id AND ds.status = 'active'
    )
    """
    execute_script([sql])


def setup_schema() -> dict:
    """
    Erstellt alle erforderlichen Tabellen und Indexes in der konfigurierten Azure SQL.
    Idempotent — bereits existierende Objekte werden nicht verändert.
    """
    from .sql_client import execute_script
    from .query_tools import invalidate_view_cache
    errors = []
    created = []
    for stmt in SCHEMA_STATEMENTS:
        label = stmt.strip().split("\n")[0].strip()[:80]
        if label.startswith("-- v_jobs:"):
            # Dynamische View-Erstellung statt statischem Statement
            try:
                _create_v_jobs_view()
                created.append("CREATE OR ALTER VIEW reporting.v_jobs (dynamic)")
            except Exception as e:
                errors.append({"statement": "CREATE VIEW reporting.v_jobs", "error": str(e)})
            continue
        try:
            execute_script([stmt])
            created.append(label)
        except Exception as e:
            errors.append({"statement": label, "error": str(e)})

    # View-Cache zurücksetzen damit neue reporting-Views sofort genutzt werden
    invalidate_view_cache()

    return {
        "success":  len(errors) == 0,
        "executed": len(created),
        "errors":   errors,
        "message":  "Schema bereit." if not errors else f"{len(errors)} Fehler beim Setup.",
    }


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _uid() -> str:
    return str(uuid.uuid4())


def _pick_name(languages: list[str], rng: random.Random) -> tuple[str, str, str]:
    """Gibt (first, last, lang) aus einer zufälligen der gewählten Sprachen zurück."""
    lang = rng.choice(languages)
    if lang not in NAMES:
        lang = "de"
    bank = NAMES[lang]
    return rng.choice(bank["first"]), rng.choice(bank["last"]), lang


def _ascii_slug(s: str) -> str:
    """
    Wandelt Diakritika um und entfernt alles außer Buchstaben/Ziffern.
      'Günther' -> 'guenther'
      "D'Amico" -> 'damico'
      'de Vries' -> 'devries'
    """
    replacements = {"ä":"ae","ö":"oe","ü":"ue","ß":"ss","á":"a","à":"a","â":"a",
                    "é":"e","è":"e","ê":"e","ë":"e","í":"i","ì":"i","î":"i","ï":"i",
                    "ó":"o","ò":"o","ô":"o","ú":"u","ù":"u","û":"u","ñ":"n","ç":"c",
                    "ø":"o","å":"a","æ":"ae","Ä":"ae","Ö":"oe","Ü":"ue","É":"e","È":"e",
                    "Á":"a","À":"a","Í":"i","Ó":"o","Ú":"u","Ñ":"n","Ç":"c"}
    for k, v in replacements.items():
        s = s.replace(k, v)
    return "".join(c for c in s.lower() if c.isalnum())


def _email(first: str, last: str, domain: str) -> str:
    """
    Erzeugt eine saubere E-Mail-Adresse:
      'Günther Schröder' -> 'guenther.schroeder@domain'
      'Jean-Luc' 'de Vries' -> 'jeanluc.devries@domain'
    """
    return f"{_ascii_slug(first)}.{_ascii_slug(last)}@{domain}"


def _working_days(start: datetime, end: datetime) -> list[datetime]:
    """Gibt alle Werktage (Mo-Fr) zwischen start und end zurück."""
    days, cur = [], start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def _random_time(day: datetime, rng: random.Random) -> datetime:
    """
    Zufällige Uhrzeit mit realistischer Verteilung:
    Spitzen 9-11 Uhr (35 %) und 13-15 Uhr (30 %).
    """
    segments = [(570, 660, 35), (780, 900, 30), (450, 570, 10),
                (660, 780, 10), (900, 1110, 15)]
    total = sum(w for _, _, w in segments)
    pick  = rng.randint(1, total)
    cumul = 0
    for s_min, e_min, w in segments:
        cumul += w
        if pick <= cumul:
            minute = rng.randint(s_min, e_min - 1)
            break
    else:
        minute = 540
    return day.replace(hour=minute // 60, minute=minute % 60,
                       second=rng.randint(0, 59), microsecond=0)


def _page_count(rng: random.Random) -> int:
    """Log-normalverteilte Seitenanzahl: Median ~3, max ~200."""
    pages = int(math.exp(rng.gauss(1.1, 0.85)))
    return max(1, min(200, pages))


def _filename_print(rng: random.Random, ts: datetime,
                    user: Optional[dict] = None) -> str:
    # v3.8.0 — mit Wahrscheinlichkeit _SENSITIVE_RATIO aus dem sensiblen Pool
    if rng.random() < _SENSITIVE_RATIO:
        tpl = rng.choice(_SENSITIVE_PRINT_TEMPLATES)
    else:
        tpl = rng.choice(_PRINT_TEMPLATES)
    user_slug = _ascii_slug(user["name"]) if user and user.get("name") else "mitarbeiter"
    return tpl.format(
        nr=rng.randint(1, 9999), date=ts.strftime("%Y-%m-%d"),
        year=ts.year, q=((ts.month - 1) // 3) + 1, mo=ts.month,
        kw=ts.isocalendar()[1], maj=rng.randint(1, 5), min=rng.randint(0, 9),
        kunde=rng.choice(["ABC","XYZ","Mustermann","Musterfrau","Omega","Alpha","Beta"]),
        thema=rng.choice(["Produkt","Service","Vertrieb","Marketing","IT","HR"]),
        user=user_slug,
    )


def _filename_scan(rng: random.Random, ts: datetime) -> str:
    # v3.8.0 — mit Wahrscheinlichkeit _SENSITIVE_RATIO aus dem sensiblen Pool
    if rng.random() < _SENSITIVE_RATIO:
        tpl = rng.choice(_SENSITIVE_SCAN_TEMPLATES)
    else:
        tpl = rng.choice(_SCAN_TEMPLATES)
    return tpl.format(
        nr=rng.randint(1, 9999), date=ts.strftime("%Y%m%d"),
        time=ts.strftime("%H%M%S"),
    )


# ── Daten-Generierung ─────────────────────────────────────────────────────────

def _gen_users(
    tenant_id: str, user_count: int, languages: list[str],
    session_id: str, rng: random.Random, email_domain: str,
) -> list[dict]:
    """
    Generiert Benutzer nach dem Schema 'Vorname Nachname'.

    Kollisionsbehandlung: Wenn derselbe 'Vorname Nachname' doppelt auftritt,
    wird ein Mittelinitial (A./B./C./...) eingefügt — so bleiben Anzeige-Name
    UND E-Mail-Adresse eindeutig und lesbar, statt dass nur die Mail-Adresse
    mit einer zufälligen Zahl ergänzt wird (was vorher 'komische Schreibweisen'
    erzeugt hat).
    """
    users: list[dict] = []
    seen_names_exact: set[str] = set()   # vollständiger Anzeigename (inkl. Initial)
    seen_base_counts: dict[str, int] = {}  # "Vorname Nachname" -> Anzahl bisher
    seen_emails: set[str] = set()

    attempts = 0
    max_attempts = max(user_count * 15, 100)
    while len(users) < user_count and attempts < max_attempts:
        attempts += 1
        first, last, _ = _pick_name(languages, rng)

        base_name = f"{first} {last}"
        count = seen_base_counts.get(base_name, 0)

        if count == 0:
            display_name = base_name
            email = _email(first, last, email_domain)
        else:
            # Mittelinitial einfügen: 'Hans A. Müller', 'Hans B. Müller', ...
            # count=1 -> A, count=2 -> B, ... Email: 'hans.a.mueller@...'
            initial = chr(ord('A') + ((count - 1) % 26))
            display_name = f"{first} {initial}. {last}"
            email = (
                f"{_ascii_slug(first)}.{initial.lower()}."
                f"{_ascii_slug(last)}@{email_domain}"
            )

        # Fallback: sehr unwahrscheinliche Kollision -> skippen, neu ziehen
        if display_name in seen_names_exact or email in seen_emails:
            continue

        seen_base_counts[base_name] = count + 1
        seen_names_exact.add(display_name)
        seen_emails.add(email)
        users.append({
            "id":              _uid(),
            "tenant_id":       tenant_id,
            "email":           email,
            "name":            display_name,
            "department":      rng.choice(DEPARTMENTS),
            "demo_session_id": session_id,
        })
    return users


def _gen_networks(
    tenant_id: str, sites: list[str], session_id: str,
) -> list[dict]:
    return [
        {"id": _uid(), "tenant_id": tenant_id, "name": s, "demo_session_id": session_id}
        for s in sites
    ]


def _gen_printers(
    tenant_id: str, printer_count: int, networks: list[dict],
    session_id: str, rng: random.Random,
) -> list[dict]:
    printers = []
    used_names: set[str] = set()
    models = rng.choices(PRINTER_MODELS, k=printer_count)
    for i, (vendor, model, prefix, _is_color) in enumerate(models):
        net = networks[i % len(networks)]
        floor = rng.choice(FLOOR_CODES)
        seq   = i + 1
        name  = f"[DEMO] {prefix}-{floor}-{seq:02d}"
        if name in used_names:
            name = f"[DEMO] {prefix}-{floor}-{seq:02d}b"
        used_names.add(name)
        printers.append({
            "id":              _uid(),
            "tenant_id":       tenant_id,
            "name":            name,
            "model_name":      model,
            "vendor_name":     vendor,
            "network_id":      net["id"],
            "location":        f"{net['name']} / {floor}",
            "demo_session_id": session_id,
        })
    return printers


def _gen_print_jobs(
    tenant_id: str, users: list[dict], printers: list[dict],
    working_days: list[datetime], jobs_per_user_day: float,
    session_id: str, rng: random.Random,
) -> tuple[list[tuple], list[tuple]]:
    jobs_rows: list[tuple] = []
    tracking_rows: list[tuple] = []

    user_weights = [rng.uniform(0.3, 2.5) for _ in users]

    for day in working_days:
        month_factor = MONTH_FACTORS.get(day.month, 1.0)
        for user, weight in zip(users, user_weights):
            n_jobs = max(0, int(rng.gauss(jobs_per_user_day * weight * month_factor, 1.0)))
            for _ in range(n_jobs):
                ts      = _random_time(day, rng)
                pages   = _page_count(rng)
                color   = 1 if rng.random() < 0.30 else 0
                duplex  = 1 if rng.random() < 0.60 else 0
                paper   = rng.choice(PAPER_SIZES)
                printer = rng.choice(printers)
                fname   = _filename_print(rng, ts, user)
                job_id  = _uid()

                jobs_rows.append((
                    job_id, tenant_id, color, duplex, pages, paper,
                    printer["id"], ts, user["id"], fname, session_id,
                ))
                tracking_rows.append((
                    job_id, tenant_id, pages, color, duplex, ts,
                    printer["id"], "PRINT_OK", session_id,
                ))

    return jobs_rows, tracking_rows


def _gen_scan_jobs(
    tenant_id: str, users: list[dict], printers: list[dict],
    working_days: list[datetime], session_id: str, rng: random.Random,
) -> list[tuple]:
    rows: list[tuple] = []
    for day in working_days:
        month_factor = MONTH_FACTORS.get(day.month, 1.0)
        for user in users:
            if rng.random() > (0.33 * month_factor):
                continue
            ts    = _random_time(day, rng)
            pages = rng.randint(1, 20)
            color = 1 if rng.random() < 0.15 else 0
            rows.append((
                _uid(), tenant_id, rng.choice(printers)["id"], user["id"],
                ts, pages, color,
                rng.choice(CAPTURE_WORKFLOWS),
                _filename_scan(rng, ts),
                session_id,
            ))
    return rows


def _gen_copy_jobs(
    tenant_id: str, users: list[dict], printers: list[dict],
    working_days: list[datetime], session_id: str, rng: random.Random,
) -> tuple[list[tuple], list[tuple]]:
    copy_rows: list[tuple]   = []
    detail_rows: list[tuple] = []
    for day in working_days:
        month_factor = MONTH_FACTORS.get(day.month, 1.0)
        for user in users:
            if rng.random() > (0.25 * month_factor):
                continue
            ts      = _random_time(day, rng)
            job_id  = _uid()
            pages   = rng.randint(1, 30)
            color   = 1 if rng.random() < 0.20 else 0
            duplex  = 1 if rng.random() < 0.50 else 0
            paper   = rng.choice(PAPER_SIZES)
            copy_rows.append((
                job_id, tenant_id, rng.choice(printers)["id"],
                user["id"], ts, session_id,
            ))
            detail_rows.append((
                _uid(), job_id, pages, paper, duplex, color, session_id,
            ))
    return copy_rows, detail_rows


# ── Bulk-Insert Helfer ────────────────────────────────────────────────────────

def _bulk_insert(sql: str, rows: list, batch_size: int = 2000) -> int:
    from .sql_client import execute_many
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        total += execute_many(sql, batch)
    return total


# ── Öffentliche API ───────────────────────────────────────────────────────────

def generate_demo_dataset(
    tenant_id: str,
    user_count: int = 15,
    printer_count: int = 6,
    queue_count: int = 2,
    months: int = 12,
    languages: Optional[list[str]] = None,
    sites: Optional[list[str]] = None,
    demo_tag: str = "",
    jobs_per_user_day: float = 3.0,
    seed: Optional[int] = None,
    preset: str = "custom",
) -> dict:
    """
    Generiert ein vollständiges Demo-Dataset und schreibt es in die konfigurierte Azure SQL.
    """
    from .sql_client import execute_write

    user_count       = max(1, min(200, user_count))
    printer_count    = max(1, min(50, printer_count))
    months           = max(1, min(36, months))
    languages        = [l for l in (languages or ["de"]) if l in NAMES] or ["de"]
    sites            = sites or ["Hauptsitz", "Niederlassung"]
    demo_tag         = demo_tag.strip() or f"DEMO_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    # Stabile Demo-Domain — RFC 2606 .example TLD ist eindeutig als Demo erkennbar
    # und vermeidet das frühere "demo-demo2026...invalid"-Doppelpräfix.
    email_domain     = "printix-demo.example"

    rng        = random.Random(seed)
    session_id = f"{demo_tag}_{_uid()[:8]}"
    now        = datetime.now()
    end_dt     = now.replace(hour=23, minute=59, second=59, microsecond=0)
    start_dt   = (now - timedelta(days=months * 30)).replace(
                     hour=0, minute=0, second=0, microsecond=0)

    logger.info("Demo-Generator gestartet: session=%s tenant=%s user=%d printer=%d months=%d",
                session_id, tenant_id, user_count, printer_count, months)

    users    = _gen_users(tenant_id, user_count, languages, session_id, rng, email_domain)
    networks = _gen_networks(tenant_id, sites, session_id)
    printers = _gen_printers(tenant_id, printer_count, networks, session_id, rng)
    wdays    = _working_days(start_dt, end_dt)

    logger.info("Werktage im Zeitraum: %d", len(wdays))

    jobs_rows, tracking_rows = _gen_print_jobs(
        tenant_id, users, printers, wdays, jobs_per_user_day, session_id, rng)
    scan_rows = _gen_scan_jobs(tenant_id, users, printers, wdays, session_id, rng)
    copy_rows, copy_detail_rows = _gen_copy_jobs(
        tenant_id, users, printers, wdays, session_id, rng)

    logger.info("Datenmenge: %d Druckjobs | %d Scans | %d Kopien",
                len(jobs_rows), len(scan_rows), len(copy_rows))

    errors = []

    _bulk_insert(
        "INSERT INTO demo.networks (id,tenant_id,name,demo_session_id) VALUES (?,?,?,?)",
        [(n["id"], n["tenant_id"], n["name"], n["demo_session_id"]) for n in networks],
    )
    _bulk_insert(
        "INSERT INTO demo.users (id,tenant_id,email,name,department,demo_session_id) VALUES (?,?,?,?,?,?)",
        [(u["id"], u["tenant_id"], u["email"], u["name"], u["department"], u["demo_session_id"])
         for u in users],
    )
    _bulk_insert(
        "INSERT INTO demo.printers (id,tenant_id,name,model_name,vendor_name,network_id,location,demo_session_id) VALUES (?,?,?,?,?,?,?,?)",
        [(p["id"], p["tenant_id"], p["name"], p["model_name"], p["vendor_name"],
          p["network_id"], p["location"], p["demo_session_id"]) for p in printers],
    )
    _bulk_insert(
        "INSERT INTO demo.jobs (id,tenant_id,color,duplex,page_count,paper_size,printer_id,submit_time,tenant_user_id,filename,demo_session_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        jobs_rows,
    )
    _bulk_insert(
        "INSERT INTO demo.tracking_data (job_id,tenant_id,page_count,color,duplex,print_time,printer_id,print_job_status,demo_session_id) VALUES (?,?,?,?,?,?,?,?,?)",
        tracking_rows,
    )
    if scan_rows:
        _bulk_insert(
            "INSERT INTO demo.jobs_scan (id,tenant_id,printer_id,tenant_user_id,scan_time,page_count,color,workflow_name,filename,demo_session_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            scan_rows,
        )
    if copy_rows:
        _bulk_insert(
            "INSERT INTO demo.jobs_copy (id,tenant_id,printer_id,tenant_user_id,copy_time,demo_session_id) VALUES (?,?,?,?,?,?)",
            copy_rows,
        )
        _bulk_insert(
            "INSERT INTO demo.jobs_copy_details (id,job_id,page_count,paper_size,duplex,color,demo_session_id) VALUES (?,?,?,?,?,?,?)",
            copy_detail_rows,
        )

    params_json = json.dumps({
        "user_count": user_count, "printer_count": printer_count,
        "queue_count": queue_count,
        "months": months, "languages": languages, "sites": sites,
        "jobs_per_user_day": jobs_per_user_day, "seed": seed,
        "start": start_dt.isoformat(), "end": end_dt.isoformat(),
        "preset": preset,
    })
    execute_write(
        "INSERT INTO demo.demo_sessions "
        "(session_id,tenant_id,demo_tag,created_at,params_json,status,"
        "user_count,printer_count,network_count,print_job_count,scan_job_count,copy_job_count) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (session_id, tenant_id, demo_tag, now, params_json, "active",
         len(users), len(printers), len(networks),
         len(jobs_rows), len(scan_rows), len(copy_rows)),
    )

    logger.info("Demo-Datensatz fertig: session=%s", session_id)

    return {
        "session_id":    session_id,
        "demo_tag":      demo_tag,
        "period":        f"{start_dt.date()} – {end_dt.date()}",
        "working_days":  len(wdays),
        "users":         len(users),
        "printers":      len(printers),
        "networks":      len(networks),
        "print_jobs":    len(jobs_rows),
        "scan_jobs":     len(scan_rows),
        "copy_jobs":     len(copy_rows),
        "errors":        errors,
        "status":        "ok" if not errors else "partial",
        "rollback_cmd":  f'printix_demo_rollback(demo_tag="{demo_tag}")',
    }


def rollback_demo(tenant_id: str, demo_tag: str) -> dict:
    """
    Löscht alle Demo-Daten mit dem angegebenen demo_tag.
    """
    from .sql_client import execute_write, query_fetchall

    sessions = query_fetchall(
        "SELECT session_id FROM demo.demo_sessions WHERE tenant_id=? AND demo_tag=?",
        (tenant_id, demo_tag),
    )
    session_ids = [s["session_id"] for s in sessions]
    if not session_ids:
        return {"deleted": {}, "sessions_found": 0, "message": f"Keine Sessions für Tag '{demo_tag}' gefunden."}

    deleted: dict[str, int] = {}
    tables_ordered = [
        "demo.jobs_copy_details",
        "demo.jobs_copy",
        "demo.jobs_scan",
        "demo.tracking_data",
        "demo.jobs",
        "demo.printers",
        "demo.users",
        "demo.networks",
        "demo.demo_sessions",
    ]
    for sid in session_ids:
        for tbl in tables_ordered:
            col = "session_id" if tbl == "demo.demo_sessions" else "demo_session_id"
            try:
                n = execute_write(f"DELETE FROM {tbl} WHERE {col}=?", (sid,))
                deleted[tbl] = deleted.get(tbl, 0) + n
            except Exception as e:
                logger.warning("Rollback-Fehler %s session %s: %s", tbl, sid, e)

    total = sum(deleted.values())
    logger.info("Rollback abgeschlossen: %d Zeilen gelöscht für tag=%s", total, demo_tag)
    return {
        "deleted":        deleted,
        "sessions_found": len(session_ids),
        "total_deleted":  total,
        "demo_tag":       demo_tag,
        "status":         "ok",
    }


def rollback_demo_all(tenant_id: str) -> dict:
    """
    Löscht ALLE Demo-Daten für den Tenant (alle Tags/Sessions).
    Nützlich wenn man ohne bestehende Sessions alles bereinigen möchte.
    """
    from .sql_client import execute_write, query_fetchall

    try:
        sessions = query_fetchall(
            "SELECT session_id, demo_tag FROM demo.demo_sessions WHERE tenant_id=?",
            (tenant_id,),
        )
    except Exception as e:
        return {"deleted": {}, "sessions_found": 0, "total_deleted": 0, "status": "ok",
                "message": f"Keine Demo-Tabellen gefunden ({e})"}

    tables_ordered = [
        "demo.jobs_copy_details",
        "demo.jobs_copy",
        "demo.jobs_scan",
        "demo.tracking_data",
        "demo.jobs",
        "demo.printers",
        "demo.users",
        "demo.networks",
        "demo.demo_sessions",
    ]
    deleted: dict = {}
    for tbl in tables_ordered:
        if tbl == "demo.demo_sessions":
            try:
                n = execute_write("DELETE FROM demo.demo_sessions WHERE tenant_id=?", (tenant_id,))
                deleted[tbl] = deleted.get(tbl, 0) + n
            except Exception as e:
                import logging; logging.getLogger(__name__).warning("Rollback-All %s: %s", tbl, e)
        else:
            col = "demo_session_id"
            try:
                n = execute_write(
                    f"DELETE FROM {tbl} WHERE {col} IN "
                    "(SELECT session_id FROM demo.demo_sessions WHERE tenant_id=?)",
                    (tenant_id,),
                )
                deleted[tbl] = deleted.get(tbl, 0) + n
            except Exception as e:
                import logging; logging.getLogger(__name__).warning("Rollback-All %s: %s", tbl, e)

    total = sum(deleted.values())
    import logging; logging.getLogger(__name__).info(
        "Rollback-All: %d Zeilen gelöscht für tenant_id=%s", total, tenant_id)
    return {
        "deleted":        deleted,
        "sessions_found": len(sessions),
        "total_deleted":  total,
        "status":         "ok",
    }


def get_demo_status(tenant_id: str) -> dict:
    """
    Gibt eine Übersicht aller aktiven Demo-Sessions für den Tenant zurück.
    """
    from .sql_client import query_fetchall
    try:
        sessions = query_fetchall(
            # Perf v3.7.8: TOP 20 begrenzt die Round-Trip-Dauer bei Azure SQL
            # (die Demo-Seite zeigt sowieso nur die neuesten Sessions).
            "SELECT TOP 20 session_id,demo_tag,created_at,status,"
            "user_count,printer_count,network_count,"
            "print_job_count,scan_job_count,copy_job_count,params_json "
            "FROM demo.demo_sessions WHERE tenant_id=? ORDER BY created_at DESC",
            (tenant_id,),
        )
    except Exception as e:
        return {"error": f"demo.demo_sessions Tabelle nicht gefunden — bitte zuerst printix_demo_setup_schema ausführen. ({e})"}

    total_jobs = sum((s.get("print_job_count") or 0) for s in sessions)
    total_rows = sum(
        (s.get("print_job_count") or 0) + (s.get("scan_job_count") or 0) +
        (s.get("copy_job_count") or 0) for s in sessions
    )
    return {
        "sessions":          sessions,
        "session_count":     len(sessions),
        "total_print_jobs":  total_jobs,
        "total_demo_rows":   total_rows,
        "hint":              "Rollback: printix_demo_rollback(demo_tag='TAG')",
    }
