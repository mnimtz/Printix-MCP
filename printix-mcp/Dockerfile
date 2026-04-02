ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python 3 and pip
RUN apk add --no-cache python3 py3-pip

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY src/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt

# Copy application source
COPY src/ /app/

# Copy run script
COPY run.sh /app/run.sh
RUN chmod a+x /app/run.sh

# Expose MCP SSE port
EXPOSE 8765

CMD [ "/app/run.sh" ]
