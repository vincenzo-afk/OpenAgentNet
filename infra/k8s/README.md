# Kubernetes deployment

The `openagentnet.yaml` bundle provides a baseline deployment for one OpenAgentNet region. It includes a PostgreSQL StatefulSet, Redis deployment, a three-replica NATS JetStream cluster, three backend replicas, and a migration Job. The NATS cluster uses a headless service so StatefulSet members can form stable routes.

Before applying the bundle, replace the example values in `openagentnet-secrets` with values from a sealed-secret or external-secret workflow. Do not commit production credentials. Replace the backend image with the image built by the project’s release pipeline.

Apply the baseline with:

```bash
kubectl apply -k infra/k8s
kubectl -n openagentnet rollout status statefulset/oan-nats
kubectl -n openagentnet wait --for=condition=complete job/openagentnet-migrations
kubectl -n openagentnet rollout status deployment/openagentnet
```

For a second region, create an overlay that changes `REGION`, `REGISTRY_ID`, `NATS_URL`, and the registry peer endpoint. Connect independent regional NATS clusters through the `leafnodes` block or use a routed super-cluster when operational policy allows it. PostgreSQL and Redis in this baseline are single-region stateful services; use managed multi-region equivalents for production failover.
