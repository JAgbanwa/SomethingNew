FROM debian:bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends g++ make libgmp-dev python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY Makefile ej375.py ./
COPY src/ ./src/
COPY tests/ ./tests/
RUN make all && make test

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 libgmp10 libgmpxx4ldbl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /build/bin/ /app/bin/
COPY ej375.py /app/
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
STOPSIGNAL SIGTERM
ENTRYPOINT ["python3", "/app/ej375.py", "run"]
CMD ["--task", "/local/input/task.json", "--output-dir", "/local/output"]
