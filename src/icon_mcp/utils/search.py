"""Icon search module - queries iconfont.cn API."""

from __future__ import annotations

import random
import string
import sys
import time
from typing import Any

import httpx

from ..config import ServerConfig
from ..lang import t
from ..models import SearchResult
from .cache import CacheManager


def _generate_search_id() -> str:
    """Generate a unique search ID."""
    rand_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"search_{int(time.time() * 1000)}_{rand_str}"


class IconSearcher:
    """Handles icon search against iconfont.cn API with caching."""

    def __init__(self, config: ServerConfig, cache: CacheManager):
        self.config = config
        self.cache = cache
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.search_timeout_s),
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
            )
        return self._client

    async def search_icons(
        self,
        q: str = "",
        sort_type: str = "updated_at",
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

        # Fetch from API
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
            "ctoken": "null",
        }

        try:
            response = await client.post(self.config.iconfont_api_base, data=form_data)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            raise TimeoutError(t("error.timeout"))
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
