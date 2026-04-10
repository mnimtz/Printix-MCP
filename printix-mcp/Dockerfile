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

# Cache-bust: 2026-04-10T15:00 — set_config_from_tenant in sql_client.py (v3.5.1)
COPY src/ /app/

# Copy run script
COPY run.sh /app/run.sh
RUN chmod a+x /app/run.sh

# Expose MCP port and Web-UI port
EXPOSE 8765
EXPOSE 8080

CMD [ "/app/run.sh" ]
