FROM --platform=linux/amd64 citusdata/citus:latest

COPY worker-node/wait-for-manager.sh /wait-for-manager.sh
COPY worker-node/wait-for-db-init.sh /wait-for-db-init.sh
COPY worker-node/update-pg-hba.sh /update-pg-hba.sh
COPY worker-node/worker-entrypoint.sh /worker-entrypoint.sh

RUN chmod +x /wait-for-manager.sh \
    && chmod +x /wait-for-db-init.sh \
    && chmod +x /update-pg-hba.sh \
    && chmod +x /worker-entrypoint.sh

CMD ["bash", "/worker-entrypoint.sh"]