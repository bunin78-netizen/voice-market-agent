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


# ------------------------------------------------------------------ токены

KNOWN_MINTS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "So11111111111111111111111111111111111111112": "SOL (обёрнутый)",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "mSOL",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
}
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def token_balances(address: str, limit: int = 6) -> list[dict]:
    """SPL-токены на кошельке (только ненулевые балансы)."""
    addr = (address or "").strip()
    if not looks_like_address(addr):
        raise SolanaError(f"«{addr}» не похоже на адрес Solana")
    res = rpc("getTokenAccountsByOwner",
              [addr, {"programId": TOKEN_PROGRAM}, {"encoding": "jsonParsed"}]) or {}
    out = []
    for item in res.get("value", []):
        try:
            info = item["account"]["data"]["parsed"]["info"]
            amount = info["tokenAmount"]["uiAmount"] or 0
        except (KeyError, TypeError):
            continue
        if amount <= 0:
            continue
        mint = info.get("mint", "")
        out.append({
            "mint": mint,
            "symbol": KNOWN_MINTS.get(mint, mint[:6] + "…"),
            "amount": round(float(amount), 6),
        })
    out.sort(key=lambda t: -t["amount"])
    return out[:limit]


def tokens_text(address: str) -> str:
    sol = balance(address)
    tokens = token_balances(address)
    head = f"На кошельке {address}: {sol.sol:.4f} SOL"
    if not tokens:
        return head + ". Токенов SPL нет."
    parts = ", ".join(f"{t['amount']:g} {t['symbol']}" for t in tokens)
    return head + f" и токены: {parts}."


# ------------------------------------------------------------------ Solana Pay

def pay_url(recipient: str, amount: float | None = None, mint: str | None = None,
            label: str = "Voice Market Agent", message: str = "") -> str:
    """Ссылка Solana Pay: пользователь платит из своего кошелька, ключи у нас не хранятся."""
    addr = (recipient or "").strip()
    if not looks_like_address(addr):
        raise SolanaError(f"«{addr}» не похоже на адрес Solana")
    params = []
    if label:
        params.append("label=" + requests.utils.quote(label))
    if message:
        params.append("message=" + requests.utils.quote(message))
    if mint:
        if not looks_like_address(mint):
            raise SolanaError("некорректный mint токена")
        params.append("spl-token=" + mint)
    if amount is not None and amount > 0:
        params.append(f"amount={amount:g}")
    base = f"solana:{addr}"
    return base + ("?" + "&".join(params) if params else "")


def qr_png(data: str, path) -> str:
    """QR-код ссылки Solana Pay — картинкой, чтобы отсканировать телефоном."""
    import qrcode  # локальный импорт: нужен только здесь
    img = qrcode.make(data)
    img.save(str(path))
    return str(path)


# ------------------------------------------------------------------ обмен (Jupiter)

JUPITER = "https://lite-api.jup.ag/swap/v1/quote"
SWAP_MINTS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "WSOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
}
DECIMALS = {"SOL": 9, "USDC": 6, "USDT": 6, "JUP": 6, "BONK": 5}


def resolve_mint(token: str) -> str:
    t = (token or "").strip().upper()
    if t in SWAP_MINTS:
        return SWAP_MINTS[t]
    if looks_like_address(token):
        return token.strip()
    raise SolanaError(f"не знаю токен «{token}» (есть SOL, USDC, USDT, JUP, BONK)")


def swap_quote(from_token: str, to_token: str, amount: float) -> dict:
    """Котировка обмена через Jupiter — без ключей и без исполнения."""
    src, dst = resolve_mint(from_token), resolve_mint(to_token)
    decimals = DECIMALS.get((from_token or "").upper(), 9)
    raw = int(amount * (10 ** decimals))
    r = requests.get(JUPITER, params={
        "inputMint": src, "outputMint": dst, "amount": raw, "slippageBps": 50,
    }, timeout=TIMEOUT)
    if r.status_code != 200:
        raise SolanaError(f"Jupiter ответил {r.status_code}")
    data = r.json()
    out_decimals = DECIMALS.get((to_token or "").upper(), 6)
    out_amount = int(data.get("outAmount", 0)) / (10 ** out_decimals)
    rate = out_amount / amount if amount else 0
    return {
        "from": from_token.upper(), "to": to_token.upper(), "amount": amount,
        "out_amount": round(out_amount, 6), "rate": round(rate, 6),
        "price_impact_pct": data.get("priceImpactPct", "0"),
        "execute_url": f"https://jup.ag/swap/{from_token.upper()}-{to_token.upper()}",
    }


def swap_text(from_token: str, to_token: str, amount: float) -> str:
    q = swap_quote(from_token, to_token, amount)
    return (f"Обмен {amount:g} {q['from']} даст примерно {q['out_amount']:g} {q['to']} "
            f"(курс {q['rate']:g}, влияние на цену {q['price_impact_pct']}). "
            f"Исполнение — в кошельке или через jup.ag, ключи я не трогаю.")
