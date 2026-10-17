# Day 4 test fixture - the image SandboxExecutor runs commands in by default.
# Alpine plus the handful of coreutils/findutils/grep binaries the generic
# find/grep-based tools need. Nothing else: this container runs with
# --network none, so anything not already baked in cannot be fetched later.
FROM alpine:3.19
RUN apk add --no-cache coreutils findutils grep bash
