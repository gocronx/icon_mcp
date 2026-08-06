"""Icon search module - queries iconfont.cn API with retry and connection pooling."""

from __future__ import annotations

import random
import string
import sys
import time
from typing import Any

import httpx

from ..config import ServerConfig
from ..lang import t
from .cache import CacheManager

__all__ = ["IconSearcher"]

# Retry configuration
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 0.5  # seconds; will double each retry
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Search ID generation
_SEARCH_ID_RAND_LENGTH = 8
_SEARCH_ID_CHARSET = string.ascii_lowercase + string.digits


def _generate_search_id() -> str:
    """Generate a unique search ID."""
    rand_str = "".join(random.choices(_SEARCH_ID_CHARSET, k=_SEARCH_ID_RAND_LENGTH))
    return f"search_{int(time.time() * 1000)}_{rand_str}"


class IconSearcher:
    """Handles icon search against iconfont.cn API with caching, retry, and connection pooling."""

    def __init__(self, config: ServerConfig, cache: CacheManager):
        self.config = config
        self.cache = cache
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=float(self.config.search_timeout_s),
                    write=10.0,
                    pool=5.0,
                ),
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30.0,
                ),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": "https://www.iconfont.cn/",
                    "Origin": "https://www.iconfont.cn",
                },
                http2=True,
            )
        return self._client

    async def _request_with_retry(
        self, client: httpx.AsyncClient, url: str, data: dict[str, str]
    ) -> httpx.Response:
        """Execute a POST request with exponential backoff retry on transient errors."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.post(url, data=data)

                # Retry on transient HTTP status codes
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    if attempt < _MAX_RETRIES - 1:
                        wait = _RETRY_BACKOFF_BASE * (2 ** attempt)
                        print(
                            f"  Retry {attempt + 1}/{_MAX_RETRIES} after HTTP {response.status_code}, "
                            f"waiting {wait:.1f}s...",
                            file=sys.stderr,
                        )
                        import asyncio
                        await asyncio.sleep(wait)
                        continue

                return response

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF_BASE * (2 ** attempt)
                    print(
                        f"  Retry {attempt + 1}/{_MAX_RETRIES} after timeout, "
                        f"waiting {wait:.1f}s...",
                        file=sys.stderr,
                    )
                    import asyncio
                    await asyncio.sleep(wait)
                    continue
                raise

            except (httpx.ConnectError, httpx.ReadError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF_BASE * (2 ** attempt)
                    print(
                        f"  Retry {attempt + 1}/{_MAX_RETRIES} after connection error, "
                        f"waiting {wait:.1f}s...",
                        file=sys.stderr,
                    )
                    import asyncio
                    await asyncio.sleep(wait)
                    continue
                raise

        # Should not reach here, but just in case
        if last_exc:
            raise last_exc
        raise RuntimeError("Unexpected retry loop exit")

    async def search_icons(
        self,
        q: str = "",
        sort_type: str = "recommend",
        page: int = 1,
        page_size: int = 100,
        s_type: str = "",
        from_collection: int = -1,
        fills: str = "",
    ) -> dict[str, Any]:
        """Search icons from iconfont.cn.

        Returns a dict with search_id, icons, count, web_url, and instructions.
        """
        # Validate params
        if not isinstance(page, int) or page < 1:
            raise ValueError(t("search.invalidPage"))
        if not isinstance(page_size, int) or page_size < 1 or page_size > 100:
            raise ValueError(t("search.invalidPageSize"))

        # Check cache
        cache_key = f"search_{q}_{sort_type}_{page}_{page_size}_{s_type}_{from_collection}_{fills}"
        cached = self.cache.get_icon(cache_key)
        if cached is not None:
            return cached

        # Fetch from API with retry
        client = await self._get_client()
        form_data = {
            "q": q,
            "sortType": sort_type,
            "page": str(page),
            "pageSize": str(page_size),
            "sType": s_type,
            "fromCollection": str(from_collection),
            "fills": fills,
            "t": str(int(time.time() * 1000)),
            # Note: ctoken is hardcoded to "null". If iconfont.cn starts
            # requiring a valid token, this will need updating.
            "ctoken": "null",
        }

        try:
            response = await self._request_with_retry(
                client, self.config.iconfont_api_base, form_data
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            raise TimeoutError(t("error.timeout"))
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"{t('search.searchFailed')}: HTTP {e.response.status_code}"
            )
        except Exception as e:
            raise RuntimeError(f"{t('search.searchFailed')}: {e}")

        if data.get("code") != 200:
            raise RuntimeError(
                f"{t('search.searchFailed')}: API returned code {data.get('code')}"
            )

        # Extract icons
        icons_data = data.get("data", {}).get("icons", [])
        total_count = data.get("data", {}).get("count", 0)

        # Generate search ID and build result
        search_id = _generate_search_id()

        result = {
            "search_id": search_id,
            "query": q,
            "count": len(icons_data),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "icons": icons_data,
            "instructions": [
                f"1. {t('search.browseAndSelect')}",
                f"2. {t('search.clickSelect')}",
                f"3. {t('search.sendToClient')}",
                f"4. {t('search.autoReturn')}",
            ],
        }

        # Cache the result
        self.cache.set_icon(cache_key, result)
        self.cache.set_search(search_id, {
            "query": q,
            "page": page,
            "page_size": page_size,
            "icons": icons_data,
            "total_count": total_count,
            "timestamp": time.time(),
        })

        print(
            t("search.foundIcons", {"count": len(icons_data)}),
            file=sys.stderr,
        )

        return result

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
