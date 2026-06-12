import asyncio

import asyncpg
import boto3
import httpx
import redis

from fixmate.core.settings import settings


async def main() -> None:
    conn = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    print("postgres OK", await conn.fetchval("select version()"))
    await conn.close()
    print("redis OK" if redis.from_url(settings.redis_url).ping() else "redis FAIL")
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    s3.list_buckets()
    print("minio OK")
    r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
    models = [m["name"] for m in r.json().get("models", [])]
    print("ollama OK, models:", models)
    for required in (settings.ollama_generation_model, settings.ollama_embedding_model):
        if not any(required in m for m in models):
            print(f"  MISSING model {required} — run: ollama pull {required}")


asyncio.run(main())
