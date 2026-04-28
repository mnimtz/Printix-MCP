ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python 3, pip und FreeTDS ODBC-Treiber für Azure SQL
# Basis-Image ist Debian (definiert in build.yaml).
# tdsodbc registriert FreeTDS automatisch in /etc/odbcinst.ini.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    unixodbc \
    unixodbc-dev \
    tdsodbc \
    freetds-dev \
    freetds-bin \
    # v6.7.28: LibreOffice-core für Web-Upload-Konvertierung (docx/xlsx/pptx/odt → PDF)
    # Nutzt nur das Core-Paket ohne GUI/Java → ~230 MB zusätzlich.
    # Plus 'fonts-dejavu' damit Standard-Dokumente mit Umlauten etc. korrekt rendern.
    libreoffice-core \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    fonts-dejavu \
    # Pillow für Image-to-PDF (PNG/JPG/GIF)
    python3-pil \
    # v6.8.8: Ghostscript für PDF→PCL/PostScript-Konvertierung in den
    # Print-Workflow-Tools (print_self, print_to_recipients, send_to_user
    # etc.). Ohne Konvertierung schickt der Server rohe PDF-Bytes an die
    # Drucker-Queue → Drucker mit reinem PCL-RIP druckt PDF-Source als
    # Klartext (Hieroglyphen). Default-Target-PDL = PCL XL (pxlcolor),
    # universellste moderne Druckersprache.
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Sicherstellen dass FreeTDS korrekt registriert ist (tdsodbc macht das meist automatisch,
# aber wir ergänzen einen expliziten Eintrag als Fallback).
RUN if ! grep -q "\[FreeTDS\]" /etc/odbcinst.ini 2>/dev/null; then \
      DRIVER=$(find /usr/lib -name "libtdsodbc.so*" 2>/dev/null | head -1); \
      if [ -n "$DRIVER" ]; then \
        printf "[FreeTDS]\nDescription=FreeTDS ODBC Driver\nDriver=%s\nSetup=%s\nFileUsage=1\n" \
               "$DRIVER" "$DRIVER" >> /etc/odbcinst.ini; \
      fi; \
    fi

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY src/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt

# 2026-04-10 — v3.7.2: reporting.v_tracking_data/v_jobs/v_jobs_scan Views gefixt
COPY src/ /app/

# v6.7.1: VERSION als Single Source of Truth aus dem Repo-Top-Level nach
# /app/VERSION kopieren. Vorher gab es ein `src/VERSION` (gelöscht in 6.7.0)
# — dadurch hatte das Banner alten Layer-Cache angezeigt. Jetzt eindeutig:
# /app/VERSION = Repo-Top-Level VERSION, von run.sh + app_version.py gelesen.
COPY VERSION /app/VERSION

# Copy run script
COPY run.sh /app/run.sh
RUN chmod a+x /app/run.sh

# Expose MCP port, Web-UI port, and Capture port
EXPOSE 8765
EXPOSE 8080
EXPOSE 8775

CMD [ "/app/run.sh" ]
