# Rebuild for the CPU architecture selected by the CE team. Pin base-image
# digests in deployment records; the tag here is intentionally readable.
FROM debian:bookworm-slim AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ make libgmp-dev python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY Makefile ./
COPY src/ ./src/
COPY *.py ./
COPY tests/ ./tests/
RUN make -j2 bin/cf_worker && make test

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 libgmp10 libgmpxx4ldbl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /build/bin/cf_worker /app/bin/cf_worker
COPY campaign.py run_task.py parameter_space.py verify.py run_task.sh container_entrypoint.sh /app/
RUN chmod 0755 /app/run_task.sh /app/container_entrypoint.sh /app/bin/cf_worker \
    && mkdir -p /local/input /local/output
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/container_entrypoint.sh"]
