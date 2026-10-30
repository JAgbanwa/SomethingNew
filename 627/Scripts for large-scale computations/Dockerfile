# CE627 d-first worker image. Rebuild for the CPU architecture selected by the
# CE team and pin the base-image digest in deployment records.
FROM debian:bookworm-slim AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ make libgmp-dev python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY Makefile ./
COPY src/ ./src/
COPY *.py ./
COPY tests/ ./tests/
RUN make all && make test

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 libgmp10 libgmpxx4ldbl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /build/bin/ /app/bin/
COPY common627.py run_task.py make_campaign.py collect.py verify_hits.py container_entrypoint.sh /app/
RUN chmod 0755 /app/container_entrypoint.sh /app/bin/thue627_worker \
    && mkdir -p /local/input /local/output
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/container_entrypoint.sh"]
