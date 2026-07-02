FROM coollabsio/openclaw:2026.5.20
# Or use coollabsio/openclaw:2026.5.22 if you want the current image.

ARG PLAYWRIGHT_VERSION=1.60.0

ENV DEBIAN_FRONTEND=noninteractive \
  PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
  ca-certificates curl nano wget unzip; \
  install -d -m 0755 /etc/apt/keyrings /etc/apt/sources.list.d; \
  curl -fsSL -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  https://cli.github.com/packages/githubcli-archive-keyring.gpg; \
  chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg; \
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  > /etc/apt/sources.list.d/github-cli.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends gh; \
  NPM_CONFIG_PREFIX=/usr/local npm install -g "@playwright/test@${PLAYWRIGHT_VERSION}"; \
  playwright install --with-deps chromium; \
  gh --version; \
  playwright --version; \
  rm -rf /var/lib/apt/lists/* /root/.npm

COPY skills /defaults/skills
COPY init-skills.sh /usr/local/bin/init-skills.sh
RUN chmod +x /usr/local/bin/init-skills.sh

ENTRYPOINT ["/usr/local/bin/init-skills.sh"]
CMD ["openclaw", "gateway"]