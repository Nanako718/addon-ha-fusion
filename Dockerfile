# ha base image（由 config.yaml 的 build_from 注入）
ARG BUILD_FROM

# 你的仓库与分支/标签（确认这里的分支名与仓库一致）
ARG FUSION_REPO=https://github.com/Nanako718/ha-fusion
ARG FUSION_REF=main

# -------- Stage 1: build --------
FROM node:22 AS builder
WORKDIR /app

# 安装 git 和 CA 证书（否则 git clone 很容易失败）
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 可视化检查变量，方便排错
RUN echo "FUSION_REPO=${FUSION_REPO} FUSION_REF=${FUSION_REF}"

# 拉你自己的仓库，并构建
RUN git clone --depth 1 --branch "${FUSION_REF}" "${FUSION_REPO}" . && \
    (npm ci --verbose || npm install --verbose --no-audit --no-fund) && \
    npm run build && \
    npm prune --omit=dev && \
    rm -rf ./data/*

# -------- Stage 2: runtime --------
FROM $BUILD_FROM
WORKDIR /rootfs

COPY --from=builder /app/build ./build
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/server.js .
COPY --from=builder /app/package.json .

COPY run.sh /

RUN apk add --no-cache nodejs-current && \
    ln -s /rootfs/data /data && \
    chmod a+x /run.sh

ENV PORT=8099 \
    NODE_ENV=production \
    ADDON=true

CMD [ "/run.sh" ]