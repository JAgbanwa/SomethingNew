# Rebuild for the CPU architecture selected by the CE team. Pin base-image
# digests in deployment records; the tag here is intentionally readable.
FROM debian:bookworm-slim AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ make libgmp-dev python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY Makefile Dockerfile ./
COPY src/ ./src/
COPY *.py ./
COPY tests/ ./tests/
COPY examples/ ./examples/
RUN make -j2 all && make test

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 libgmp10 libgmpxx4ldbl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /build/bin/ /app/bin/
COPY campaign.py run_task.py parameter_space.py q_sieve.py verify.py run_task.sh container_entrypoint.sh /app/
COPY xy_campaign.py xy_common.py run_xy_task.py collect_xy.py verify_xy.py /app/
COPY cube_campaign.py /app/
COPY aq_traversal.py /app/
# d-first half-chart engine (D_FIRST.md): python3 /app/run_d_task.py --task ... --output-dir ...
COPY dfirst_common.py d_campaign.py run_d_task.py collect_d.py verify_d.py /app/
RUN chmod 0755 /app/run_task.sh /app/container_entrypoint.sh /app/bin/cf_worker /app/bin/xy_cf_worker /app/bin/dthue_worker \
    && mkdir -p /local/input /local/output
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/container_entrypoint.sh"]
