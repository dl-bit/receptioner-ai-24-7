# ==============================================================================
# Dockerfile pentru rularea Chatwoot Community Edition (Open-Source)
# pe Render.com (512 MB Free Tier) & Hugging Face Spaces (16 GB Free Tier)
# Include:
# 1. Optimizări agresive Ruby GC / jemalloc pentru încadrare în <380 MB RAM
# 2. Initializer Rails pentru rularea job-urilor (Webhooks, Mesaje) in-process (:async)
#    fără a necesita un al doilea container plătit de Sidekiq Worker!
# ==============================================================================
FROM chatwoot/chatwoot:latest

USER root

ENV NODE_ENV=production \
    RAILS_ENV=production \
    INSTALLATION_ENV=docker \
    DEFAULT_LOCALE=ro \
    ENABLE_ACCOUNT_SIGNUP=true \
    RAILS_LOG_TO_STDOUT=true \
    POSTGRES_PORT=5432 \
    USE_IN_PROCESS_ASYNC_JOBS=true \
    WEB_CONCURRENCY=0 \
    RAILS_MAX_THREADS=3 \
    MALLOC_ARENA_MAX=2 \
    RUBY_GC_HEAP_GROWTH_FACTOR=1.05 \
    RUBY_GC_MALLOC_LIMIT=16777216 \
    RUBY_GC_OLDMALLOC_LIMIT=16777216

RUN mkdir -p /app/storage /app/tmp/pids /app/config/initializers && \
    chmod -R 777 /app/storage /app/tmp /app/log && \
    printf 'if ENV["USE_IN_PROCESS_ASYNC_JOBS"] == "true"\n  Rails.application.config.active_job.queue_adapter = :async\n  Rails.logger.info("==> [Render Free Mode] ActiveJob queue_adapter set to :async (in-process webhooks & jobs)")\nend\n' > /app/config/initializers/zz_render_free_async.rb && \
    printf '#!/bin/sh\nset -e\nexport POSTGRES_PORT="${POSTGRES_PORT:-5432}"\nrm -f /app/tmp/pids/server.pid\necho "==> Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."\nuntil pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USERNAME}"; do\n  sleep 2\ndone\necho "==> Preparing Chatwoot PostgreSQL database..."\nbundle exec rails db:chatwoot_prepare\necho "==> Starting Chatwoot Community Edition server on port ${PORT:-3000}..."\nexec bundle exec puma -C config/puma.rb -p "${PORT:-3000}"\n' > /app/start_render.sh && \
    chmod +x /app/start_render.sh

EXPOSE 3000

ENTRYPOINT ["/app/start_render.sh"]
