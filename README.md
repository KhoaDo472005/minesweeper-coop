# Dò mìn đồng đội (2–10 người)

Server Python (aiohttp + WebSocket) + client Canvas thuần, không cần build.

```
minesweeper-coop/
├── server.py
├── index.html
├── requirements.txt
├── sfx/            ← âm thanh (xem bên dưới)
└── deploy/         ← mẫu cấu hình systemd, nginx, Caddy
```

## Chạy thử trên máy

```bash
pip install -r requirements.txt
python server.py            # mở http://localhost:8000
```

## Triển khai lên VPS / hosting mini có tên miền phụ

Yêu cầu: máy chủ Linux chạy được tiến trình Python lâu dài và cho phép WebSocket.
(Shared hosting kiểu cPanel thường **không** chạy được: cần VPS hoặc dịch vụ như Railway/Fly/Render.)

1. Trỏ bản ghi DNS `A` của tên miền phụ (vd `mine.example.com`) về IP máy chủ.
2. Chép thư mục này lên máy chủ, ví dụ `/opt/minesweeper`:
   ```bash
   cd /opt/minesweeper
   python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
   ```
3. Chạy nền bằng systemd: sửa đường dẫn trong `deploy/minesweeper.service`, rồi
   ```bash
   sudo cp deploy/minesweeper.service /etc/systemd/system/
   sudo systemctl enable --now minesweeper
   ```
4. Đặt reverse proxy trước (chọn một):
   - **Caddy** (ngắn nhất, tự lấy HTTPS): dùng `deploy/Caddyfile`.
   - **nginx**: dùng `deploy/nginx.conf`, rồi `sudo certbot --nginx -d mine.example.com`.
5. Mở `https://mine.example.com`. Trang tự dùng `wss://` khi chạy HTTPS.

Server chỉ lắng nghe `127.0.0.1:8000` khi có `HOST=127.0.0.1` (đã đặt trong file service), nên bên ngoài chỉ vào được qua proxy.

Biến môi trường: `HOST` (mặc định `0.0.0.0`), `PORT` (mặc định `8000`), `MAX_ROOMS` (mặc định `100`).
Kiểm tra sống: `GET /healthz` trả `ok`.

## Âm thanh (`./sfx`)

| Tên file (không tính đuôi) | Phát khi |
|---|---|
| `bgm` | nhạc nền, lặp liên tục khi đang chơi |
| `dig` | mở một ô số |
| `mass` | mở vùng trống (bung nhiều ô) |
| `flag` | cắm hoặc gỡ cờ |
| `gameover` | có người dẫm mìn |
| `win` *(tuỳ chọn)* | thắng ván |

Đuôi hỗ trợ: `.ogg`, `.mp3`, `.m4a`, `.wav` (ưu tiên theo thứ tự này). Thay file bằng bản của bạn là xong,
không cần sửa code; chỉ cần tải lại trang. Các file hiện có là bản tổng hợp tự động để chạy thử.
Nên dùng `.ogg`/`.mp3` mono, nhạc nền vài trăm KB là đủ nhẹ.

Người chơi có nút 🔊 (hiệu ứng) và 🎵 (nhạc nền) trên thanh trên cùng, lựa chọn được nhớ trong trình duyệt.

## Ghi chú

- Chủ phòng chọn số người tối đa (2–10) khi tạo phòng. Ván chỉ bắt đầu khi có ít nhất 2 người; người khác vào thêm giữa chừng được.
- Ai dẫm mìn thì cả phòng thua (chơi hợp tác), tên người đó hiện trên thông báo.
- Mỗi kết nối bị giới hạn 60 tin/giây, server giới hạn số phòng cùng lúc bằng `MAX_ROOMS`.
