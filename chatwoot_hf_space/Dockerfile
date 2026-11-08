# ==============================================================================
# Dockerfile pentru rularea Chatwoot Community Edition (Open-Source)
# pe Hugging Face Spaces (2 vCPU, 16 GB RAM 100% Gratuit, Port 7860)
# Conectat la PostgreSQL (Supabase / Neon / Render) + Redis (Upstash / Render)
# ==============================================================================
FROM chatwoot/chatwoot:latest

USER root

ENV NODE_ENV=production \
    RAILS_ENV=production \
    INSTALLATION_ENV=docker \
    DEFAULT_LOCALE=ro \
    ENABLE_ACCOUNT_SIGNUP=true \
    RAILS_LOG_TO_STDOUT=true \
    PORT=7860

RUN mkdir -p /app/storage /app/tmp/pids && \
    chmod -R 777 /app/storage /app/tmp /app/log

EXPOSE 7860

ENTRYPOINT ["docker/entrypoints/rails.sh"]
CMD ["sh", "-c", "bundle exec rails db:chatwoot_prepare && bundle exec rails s -p 7860 -b 0.0.0.0"]
