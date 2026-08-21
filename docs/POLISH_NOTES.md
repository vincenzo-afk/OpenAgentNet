# Repository Polish & Bug Hunt Notes

## Findings

1. **SQL Injection Vulnerability**: The `DiscoveryService` and `MarketplaceService` were using `sa.text()` with f-strings for JSONB containment checks (`@>`). This has been fixed to use `sa.cast(..., JSONB)`.
2. **Missing Referential Integrity**: SQLAlchemy models were using `Mapped[uuid.UUID]` columns without explicit `ForeignKey` constraints. While app logic handled relationships, the database schema lacked enforcement.
3. **Task Delivery Loop**: Workers were hammering dead endpoints. A 3-attempt cap with a `DEAD_ENDPOINT` failure state was added previously, but further hardening of the worker loops (better error logging, session handling) is identified.
4. **Missing Endpoint**: `GET /v1/agents/me` was added to support dashboard functionality.
5. **Worker Robustness**: Added better error handling and `DeliverPolicy.LAST` for NATS consumers to prevent stale event replay loops.

## Planned Improvements

1. **Add ForeignKey Constraints**: Update all models to use `ForeignKey("table.id")` for all relationship columns.
2. **Add Missing Indexes**: Ensure all foreign keys have indexes for performance.
3. **GitHub Topics**: Update to 20 high-signal topics.
4. **README Refinement**: Apply the 16-section world-class README structure.
5. **CI/CD Hardening**: Ensure CI runs full suite including the new phase checks.
