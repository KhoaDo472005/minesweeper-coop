#!/usr/bin/env python3
"""Dò mìn đồng đội 2–10 người.

Chạy thử trên máy:   pip install -r requirements.txt && python server.py
Khi deploy (sau nginx/Caddy):   HOST=127.0.0.1 PORT=8000 python server.py

Biến môi trường: HOST (mặc định 0.0.0.0), PORT (mặc định 8000), MAX_ROOMS (mặc định 100)
"""
import base64
import hashlib
import json
import os
import random
import socket
import sys
import time
from pathlib import Path

from aiohttp import web, WSMsgType

ROOT = Path(__file__).parent
SFX_DIR = ROOT / "sfx"

# (rộng, cao, mật độ mìn)
SIZES = {"s": (40, 30, 0.13), "m": (100, 60, 0.14), "l": (200, 120, 0.15)}
MIN_PLAYERS, MAX_PLAYERS = 2, 10
MAX_ROOMS = int(os.environ.get("MAX_ROOMS", "100"))
MSG_PER_SEC = 60  # chống spam: tối đa số tin/giây của mỗi kết nối
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ ký tự dễ nhầm: I, O, 0, 1
ROOMS = {}

# Giá trị ô gửi cho client:
#   0-8   đã mở (số mìn xung quanh)
#   9     chưa mở
#   10-19 cờ của người chơi 0-9
#   20    mìn (khi thua)    21 mìn vừa nổ    22 cờ cắm sai (khi thua)


class Room:
    def __init__(self, code, size, max_players):
        self.code = code
        self.w, self.h, density = SIZES.get(size, SIZES["m"])
        self.n = self.w * self.h
        self.mines_total = int(self.n * density)
        self.max = max(MIN_PLAYERS, min(MAX_PLAYERS, max_players))
        self.slots = [None] * self.max  # mỗi phần tử: (ws, tên) hoặc None
        self.reset()

    def reset(self):
        self.mine = bytearray(self.n)
        self.cnt = bytearray(self.n)
        self.rev = bytearray(self.n)
        self.flag = bytearray(self.n)  # 0 = không, k+1 = cờ của người chơi k
        self.started = False
        self.status = "playing"  # playing | won | lost
        self.opened = 0
        self.boom = -1
        self.boom_name = ""

    # ---------- người chơi ----------
    def names(self):
        return [s[1] if s else None for s in self.slots]

    def count(self):
        return sum(1 for s in self.slots if s)

    def add(self, ws, name):
        for k in range(self.max):
            if self.slots[k] is None:
                self.slots[k] = (ws, name)
                return k
        return -1

    async def broadcast(self, obj, skip=None):
        data = json.dumps(obj, separators=(",", ":"))
        for k, s in enumerate(self.slots):
            if s and k != skip:
                await push_raw(s[0], data)

    # ---------- logic bàn chơi ----------
    def nbrs(self, i):
        x, y = i % self.w, i // self.w
        for dy in (-1, 0, 1):
            ny = y + dy
            if 0 <= ny < self.h:
                for dx in (-1, 0, 1):
                    if dx or dy:
                        nx = x + dx
                        if 0 <= nx < self.w:
                            yield ny * self.w + nx

    def generate(self, first):
        banned = {first, *self.nbrs(first)}  # click đầu luôn an toàn + vùng trống
        cand = [i for i in range(self.n) if i not in banned]
        for i in random.sample(cand, min(self.mines_total, len(cand))):
            self.mine[i] = 1
        for i in range(self.n):
            if self.mine[i]:
                for j in self.nbrs(i):
                    self.cnt[j] += 1

    def open_cell(self, i, changed):
        if self.rev[i] or self.flag[i]:
            return
        if self.mine[i]:
            self.boom = i
            self.status = "lost"
            return
        self.rev[i] = 1
        stack = [i]
        while stack:
            c = stack.pop()
            self.opened += 1
            changed.append(c)
            if self.cnt[c] == 0:
                for j in self.nbrs(c):
                    if not self.rev[j] and not self.flag[j] and not self.mine[j]:
                        self.rev[j] = 1
                        stack.append(j)

    def chord(self, i, changed):
        if self.cnt[i] == 0:
            return
        around = list(self.nbrs(i))
        if sum(1 for j in around if self.flag[j]) != self.cnt[i]:
            return
        for j in around:
            if not self.rev[j] and not self.flag[j]:
                self.open_cell(j, changed)
                if self.status == "lost":
                    return

    def act_open(self, i):
        changed = []
        if not self.started:
            if self.flag[i]:
                return changed
            self.generate(i)
            self.started = True
        if self.rev[i]:
            self.chord(i, changed)
        else:
            self.open_cell(i, changed)
        if self.status == "playing" and self.opened == self.n - self.mines_total:
            self.status = "won"
        return changed

    def act_flag(self, i, player):
        if self.rev[i]:
            return []
        self.flag[i] = 0 if self.flag[i] else player + 1
        return [i]

    def disp(self, i):
        if self.rev[i]:
            return self.cnt[i]
        if self.status == "lost":
            if i == self.boom:
                return 21
            if self.mine[i] and not self.flag[i]:
                return 20
            if self.flag[i] and not self.mine[i]:
                return 22
        elif self.status == "won" and self.mine[i]:
            return 9 + (self.flag[i] or 1)
        return 9 + self.flag[i]

    def snapshot(self, you):
        cells = bytes(self.disp(i) for i in range(self.n))
        return {
            "t": "state",
            "code": self.code,
            "you": you,
            "names": self.names(),
            "w": self.w,
            "h": self.h,
            "mines": self.mines_total,
            "status": self.status,
            "by": self.boom_name,
            "cells": base64.b64encode(cells).decode(),
        }

    async def send_snapshots(self):
        for k, s in enumerate(self.slots):
            if s:
                await push(s[0], self.snapshot(k))


# ---------- tiện ích ----------
async def push_raw(ws, data):
    try:
        await ws.send_str(data)
    except Exception:
        pass


async def push(ws, obj):
    await push_raw(ws, json.dumps(obj, separators=(",", ":")))


def new_code():
    while True:
        code = "".join(random.choices(ALPHABET, k=5))
        if code not in ROOMS:
            return code


def clean_name(s):
    s = " ".join(str(s or "").split())[:16]
    return s or "Người chơi"


def parse_max(v):
    try:
        return max(MIN_PLAYERS, min(MAX_PLAYERS, int(v)))
    except (TypeError, ValueError):
        return MIN_PLAYERS


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# ---------- âm thanh (thư mục ./sfx) ----------
SFX_NAMES = ("bgm", "dig", "mass", "flag", "gameover", "win")  # win là tuỳ chọn
SFX_EXTS = (".ogg", ".mp3", ".m4a", ".wav")  # ưu tiên định dạng nhẹ
SFX_MIME = {".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav"}


def sfx_files():
    out = {}
    for name in SFX_NAMES:
        for ext in SFX_EXTS:
            p = SFX_DIR / (name + ext)
            if p.is_file():
                out[name] = p
                break
    return out


_ver_cache = {}


def sfx_version(p):
    """Mã băng theo NỘI DUNG file (không theo ngày sửa): deploy lại mà file không đổi thì
    người chơi vẫn dùng bản đã lưu trong trình duyệt, file đổi thì URL đổi."""
    st = p.stat()
    key = (str(p), st.st_mtime_ns, st.st_size)
    v = _ver_cache.get(key)
    if v is None:
        v = _ver_cache[key] = hashlib.md5(p.read_bytes()).hexdigest()[:8]
    return v


def sfx_manifest():
    return {n: f"/sfx/{p.name}?v={sfx_version(p)}" for n, p in sfx_files().items()}


async def api_sfx(request):
    return web.json_response(sfx_manifest(), headers={"Cache-Control": "no-cache"})


async def sfx_file(request):
    name = request.match_info["name"]
    for p in sfx_files().values():
        if p.name == name:
            # URL có ?v=<mã băm nội dung> nên cache dài hạn được
            return web.FileResponse(p, headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "Content-Type": SFX_MIME.get(p.suffix, "application/octet-stream"),
            })
    raise web.HTTPNotFound()


# ---------- HTTP / WebSocket ----------
_index = {"key": None, "body": b"", "etag": ""}


def build_index():
    """Nhúng danh sách âm thanh thẳng vào trang (đỡ một lượt gọi API), dựng lại khi file đổi."""
    manifest = sfx_manifest()
    page = ROOT / "index.html"
    key = (page.stat().st_mtime_ns, tuple(sorted(manifest.items())))
    if _index["key"] != key:
        html = page.read_text(encoding="utf-8")
        html = html.replace("/*SFX*/null", json.dumps(manifest, separators=(",", ":")), 1)
        body = html.encode("utf-8")
        _index.update(key=key, body=body, etag='"' + hashlib.md5(body).hexdigest()[:16] + '"')
    return _index


def etag_match(header, etag):
    if not header:
        return False
    tags = [t.strip() for t in header.split(",")]  # nginx có thể đổi thành dạng yếu W/"..."
    return "*" in tags or etag in tags or "W/" + etag in tags


async def index(request):
    page = build_index()
    headers = {"ETag": page["etag"], "Cache-Control": "no-cache"}  # luôn hỏi lại, nhưng chỉ tốn 304
    if etag_match(request.headers.get("If-None-Match"), page["etag"]):
        return web.Response(status=304, headers=headers)
    resp = web.Response(body=page["body"], content_type="text/html", charset="utf-8", headers=headers)
    resp.enable_compression()  # gzip: ~22 KB còn khoảng 6 KB
    return resp


async def healthz(request):
    return web.Response(text="ok")


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=2048)
    await ws.prepare(request)
    room, me = None, -1
    win_start, win_cnt = time.monotonic(), 0
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            now = time.monotonic()
            if now - win_start >= 1:
                win_start, win_cnt = now, 0
            win_cnt += 1
            if win_cnt > MSG_PER_SEC:
                continue
            try:
                m = json.loads(msg.data)
            except ValueError:
                continue
            if not isinstance(m, dict):
                continue
            t = m.get("t")

            # --- chưa vào phòng ---
            if room is None:
                if t == "create":
                    if len(ROOMS) >= MAX_ROOMS:
                        await push(ws, {"t": "err", "msg": "Máy chủ đang đầy phòng, thử lại sau nhé"})
                        continue
                    code = new_code()
                    room = ROOMS[code] = Room(code, m.get("size"), parse_max(m.get("max")))
                    me = room.add(ws, clean_name(m.get("name")))
                    await push(ws, room.snapshot(me))
                elif t == "join":
                    r = ROOMS.get(str(m.get("code", "")).strip().upper())
                    if not r:
                        await push(ws, {"t": "err", "msg": "Không tìm thấy phòng này"})
                        continue
                    k = r.add(ws, clean_name(m.get("name")))
                    if k < 0:
                        await push(ws, {"t": "err", "msg": f"Phòng đã đủ {r.max}/{r.max} người"})
                        continue
                    room, me = r, k
                    await push(ws, room.snapshot(me))
                    await room.broadcast({"t": "players", "names": room.names()}, skip=me)
                continue

            # --- đã ở trong phòng ---
            if t in ("open", "flag", "cur"):
                x, y = m.get("x"), m.get("y")
                if not (
                    type(x) is int and type(y) is int
                    and 0 <= x < room.w and 0 <= y < room.h
                ):
                    continue
                if t == "cur":
                    await room.broadcast({"t": "cur", "p": me, "x": x, "y": y}, skip=me)
                    continue
                if room.status != "playing":
                    continue
                if room.count() < MIN_PLAYERS:
                    await push(ws, {"t": "err", "msg": "Chờ thêm người vào phòng đã"})
                    continue
                i = y * room.w + x
                changed = room.act_open(i) if t == "open" else room.act_flag(i, me)
                if room.status == "lost":
                    room.boom_name = room.slots[me][1] if room.slots[me] else ""
                if room.status != "playing":
                    await room.send_snapshots()
                elif changed:
                    flat = []
                    for c in changed:
                        flat += [c, room.disp(c)]
                    await room.broadcast({"t": "d", "c": flat})
            elif t == "restart":
                room.reset()
                await room.send_snapshots()
    finally:
        if room is not None:
            room.slots[me] = None
            if not any(room.slots):
                ROOMS.pop(room.code, None)
            else:
                await room.broadcast({"t": "players", "names": room.names()})
    return ws


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8000"))
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/sfx", api_sfx)
    app.router.add_get("/sfx/{name}", sfx_file)
    app.router.add_get("/healthz", healthz)
    print("=" * 52)
    print(f"  Dò mìn đồng đội — đang chạy ở {host}:{port}")
    if host in ("0.0.0.0", "::"):
        print(f"  Trên máy bạn:   http://localhost:{port}")
        print(f"  Trong mạng LAN: http://{lan_ip()}:{port}")
    print("  Âm thanh:", ", ".join(sfx_files()) or "(chưa có file nào trong ./sfx)")
    print("=" * 52)
    web.run_app(app, host=host, port=port, print=None)


if __name__ == "__main__":
    main()
