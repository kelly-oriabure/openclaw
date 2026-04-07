FROM coollabsio/openclaw:2026.3.8

# Fix Xiaomi baseUrl (built-in has wrong default URL)
RUN find /opt/openclaw/app/dist -name "*.js" -exec sed -i \
    -e 's|https://api\.xiaomimimo\.com/anthropic|https://token-plan-sgp.xiaomimimo.com/anthropic|g' \
    -e 's|https://api\.xiaomimimo\.com/v1|https://token-plan-sgp.xiaomimimo.com/v1|g' \
    {} + \
    && echo "Xiaomi baseUrl patched successfully"

RUN apt-get update \
    && apt-get install -y curl gnupg nano git build-essential wget unzip \
    # Playwright/Chromium dependencies
    libnss3 libatk-bridge2.0-0 libxcomposite1 libxrandr2 libasound2 \
    libpangocairo-1.0-0 libatspi2.0-0 libgtk-3-0 libgbm1 libdrm2 libxshmfence1 \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y gh \
    && gh --version \
    # Install Playwright properly then install Chromium browser
    && npm install -g @playwright/test \
    && npx playwright install chromium \
    # Clean up apt cache and npm cache
    && rm -rf /var/lib/apt/lists/* /root/.npm