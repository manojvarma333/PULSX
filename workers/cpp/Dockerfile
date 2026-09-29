# Builds the C++ worker on Linux (gcc) -- used because no C++ toolchain is available on
# the host this project was authored on. `docker build` is the primary way to compile it.
FROM gcc:13 AS build
RUN apt-get update && apt-get install -y --no-install-recommends cmake git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . .
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --target pulsex_cpp_worker -j

FROM debian:bookworm-slim
COPY --from=build /src/build/pulsex_cpp_worker /usr/local/bin/pulsex_cpp_worker
ENTRYPOINT ["/usr/local/bin/pulsex_cpp_worker"]
