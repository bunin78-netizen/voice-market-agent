"""Интеграция с Solana: публичный JSON-RPC, без ключей.

Даёт агенту три вещи, которых раньше не было:
  * состояние сети — слот, эпоха, версия узла, пропускная способность;
  * баланс кошелька в SOL;
  * последние транзакции кошелька (без разбора инструкций — только факты).

Используются публичные RPC-эндпоинты, поэтому ключи и аккаунты не нужны.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import requests

ENDPOINTS = (
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
)
TIMEOUT = 15
LAMPORTS_PER_SOL = 1_000_000_000


class SolanaError(RuntimeError):
    pass


def rpc(method: str, params: list | None = None) -> object:
    """JSON-RPC с перебором публичных эндпоинтов."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    last = ""
    for url in ENDPOINTS:
        try:
            r = requests.post(url, json=payload, timeout=TIMEOUT)
            if r.status_code != 200:
                last = f"{url} → {r.status_code}"
                continue
            data = r.json()
            if "error" in data:
                raise SolanaError(str(data["error"])[:200])
            return data.get("result")
        except SolanaError:
            raise
        except Exception as e:  # noqa: BLE001 — пробуем следующий узел
            last = f"{url} → {type(e).__name__}"
    raise SolanaError(f"узлы Solana недоступны ({last})")


def looks_like_address(value: str) -> bool:
    """Грубая проверка: base58, 32–44 символа."""
    v = (value or "").strip()
    if not 32 <= len(v) <= 44:
        return False
    alphabet = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    return all(c in alphabet for c in v)


@dataclass
class NetworkStatus:
    version: str = ""
    slot: int = 0
    epoch: int = 0
    epoch_progress: float = 0.0
    tps: float = 0.0
    slot_time: float = 0.0
    healthy: bool = True
    extra: dict = field(default_factory=dict)

    def as_text(self) -> str:
        return (
            f"Сеть Solana: версия узла {self.version}, слот {self.slot:,}, "
            f"эпоха {self.epoch} ({self.epoch_progress:.0f}% пройдено). "
            f"Пропускная способность около {self.tps:.0f} транзакций в секунду, "
            f"среднее время слота {self.slot_time:.2f} секунды. Сеть отвечает нормально."
        ).replace(",", " ")


def network_status() -> NetworkStatus:
    st = NetworkStatus()
    try:
        version = rpc("getVersion") or {}
        st.version = version.get("solana-core", "?")
    except SolanaError:
        st.healthy = False
        raise

    try:
        st.slot = int(rpc("getSlot") or 0)
    except SolanaError:
        pass

    try:
        epoch = rpc("getEpochInfo") or {}
        st.epoch = int(epoch.get("epoch", 0))
        idx, total = epoch.get("slotIndex"), epoch.get("slotsInEpoch")
        if idx and total:
            st.epoch_progress = idx / total * 100
    except SolanaError:
        pass

    try:
        samples = rpc("getRecentPerformanceSamples", [5]) or []
        if samples:
            tps = [s.get("numTransactions", 0) / max(s.get("samplePeriodSecs", 1), 1) for s in samples]
            st.tps = sum(tps) / len(tps)
            st.slot_time = sum(s.get("samplePeriodSecs", 0) for s in samples) / max(sum(s.get("numSlots", 1) for s in samples), 1)
    except SolanaError:
        pass

    return st


@dataclass
class WalletInfo:
    address: str
    sol: float
    lamports: int

    def as_text(self) -> str:
        return f"На кошельке {self.address} сейчас {self.sol:.4f} SOL."


def balance(address: str) -> WalletInfo:
    addr = (address or "").strip()
    if not looks_like_address(addr):
        raise SolanaError(f"«{addr}» не похоже на адрес Solana (нужно 32–44 символа base58)")
    res = rpc("getBalance", [addr]) or {}
    lamports = int(res.get("value", 0))
    return WalletInfo(address=addr, sol=lamports / LAMPORTS_PER_SOL, lamports=lamports)


def recent_transactions(address: str, limit: int = 5) -> list[dict]:
    addr = (address or "").strip()
    if not looks_like_address(addr):
        raise SolanaError(f"«{addr}» не похоже на адрес Solana")
    limit = max(1, min(int(limit or 5), 20))
    res = rpc("getSignaturesForAddress", [addr, {"limit": limit}]) or []
    out = []
    for item in res:
        out.append({
            "signature": item.get("signature", "")[:16] + "…",
            "slot": item.get("slot"),
            "failed": bool(item.get("err")),
            "block_time": item.get("blockTime"),
        })
    return out


def activity_text(address: str, limit: int = 5) -> str:
    txs = recent_transactions(address, limit)
    if not txs:
        return f"У кошелька {address} в истории пока нет транзакций."
    ok = sum(1 for t in txs if not t["failed"])
    last = txs[0]
    return (
        f"Последние {len(txs)} транзакций кошелька {address}: успешных {ok}, "
        f"неудачных {len(txs) - ok}. Самая свежая — в слоте {last['slot']}"
        + (" (прошла)" if not last["failed"] else " (с ошибкой)")
        + "."
    )
