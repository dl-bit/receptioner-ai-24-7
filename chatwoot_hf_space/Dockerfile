# ==============================================================================
# Dockerfile pentru rularea Chatwoot Community Edition (Open-Source)
# pe Render.com & Hugging Face Spaces (inclusiv migrare automată DB la pornire)
# ==============================================================================
FROM chatwoot/chatwoot:latest

USER root

ENV NODE_ENV=production \
    RAILS_ENV=production \
    INSTALLATION_ENV=docker \
    DEFAULT_LOCALE=ro \
    ENABLE_ACCOUNT_SIGNUP=true \
    RAILS_LOG_TO_STDOUT=true

RUN mkdir -p /app/storage /app/tmp/pids && \
    chmod -R 777 /app/storage /app/tmp /app/log && \
    printf '#!/bin/sh\nset -e\nrm -f /app/tmp/pids/server.pid\necho "==> Preparing Chatwoot PostgreSQL database..."\nbundle exec rails db:chatwoot_prepare\necho "==> Starting Chatwoot Community Edition server on port ${PORT:-3000}..."\nexec bundle exec rails s -p "${PORT:-3000}" -b 0.0.0.0\n' > /app/start_render.sh && \
    chmod +x /app/start_render.sh

EXPOSE 3000

ENTRYPOINT ["docker/entrypoints/rails.sh"]
CMD ["/app/start_render.sh"]
