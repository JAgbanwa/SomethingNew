# Primitive-375 search image. Rebuild for the CPU architecture selected by CE and pin
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
COPY gap_common.py gap_campaign.py band_campaign.py benchmark375.py pack_ce.py run_gap_task.py run_ce_bundle.py collect_gap.py collect_campaign.py audit_gap.py container_entrypoint.sh /app/
COPY src/gap_worker.cpp /app/src/gap_worker.cpp
RUN chmod 0755 /app/container_entrypoint.sh /app/bin/gap_worker && mkdir -p /local/input /local/output
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/container_entrypoint.sh"]
