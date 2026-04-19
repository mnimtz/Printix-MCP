Platzhalter für app.ico

Bitte ein 256x256 ICO hier ablegen als `app.ico`.
Empfehlung: Printix-Logo oder eigenes Corporate-Icon.

Bis dahin verwendet die csproj-Definition den Eintrag
<ApplicationIcon>Resources\app.ico</ApplicationIcon>
was beim ersten Build einen Warning, aber keinen Fehler wirft.

Für MVP-Tests kann die Zeile in PrintixSend.csproj auskommentiert werden.
