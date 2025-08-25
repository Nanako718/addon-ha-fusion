# ha base image
ARG BUILD_FROM

# 可配置：从哪拉代码、拉哪个分支/标签
ARG FUSION_REPO=https://github.com/Nanako718/ha-fusion
ARG FUSION_REF=main

# first stage, 不能用 alpine 构建 armv7
FROM node:22 AS builder
WORKDIR /app

# 在线拉你自己的仓库，并构建
RUN git clone --depth 1 --branch ${FUSION_REF} ${FUSION_REPO} . && \
  (npm ci --verbose || npm install --verbose) && \
  npm run build && \
  npm prune --omit=dev && \
  rm -rf ./data/*

# second stage
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