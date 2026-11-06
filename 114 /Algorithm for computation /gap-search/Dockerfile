# CE114 gap-search image. Rebuild for the CPU architecture selected by the CE team and pin
# the base-image digest in deployment records. The build runs the full test suite.
FROM debian:bookworm-slim AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ make libgmp-dev python3 python3-numpy \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY Makefile ./
COPY src/ ./src/
COPY *.py ./
COPY tests/ ./tests/
RUN make all && make test

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 libgmp10 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /build/bin/ /app/bin/
COPY gap_common.py gap_campaign.py run_gap_task.py collect_gap.py audit_gap.py to_d.py container_entrypoint.sh /app/
RUN chmod 0755 /app/container_entrypoint.sh /app/bin/gap_worker && mkdir -p /local/input /local/output
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/container_entrypoint.sh"]
