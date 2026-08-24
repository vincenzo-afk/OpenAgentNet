from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_compose_postgres_image_includes_pgvector():
    compose = (REPO_ROOT / "infra/docker/docker-compose.dev.yml").read_text()
    assert "image: pgvector/pgvector:pg15" in compose


def test_kubernetes_postgres_image_includes_pgvector():
    manifest = (REPO_ROOT / "infra/k8s/openagentnet.yaml").read_text()
    assert "image: pgvector/pgvector:pg16" in manifest


def test_semantic_memory_migration_enables_vector_extension():
    migration = (REPO_ROOT / "backend/alembic/versions/016_memory_embeddings.py").read_text()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "Vector(1536)" in migration
