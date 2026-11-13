# ⛏️ Co-op Minesweeper

**A real-time multiplayer Minesweeper game where everyone works together on the same board.**

Co-op Minesweeper is a lightweight, browser-based multiplayer Minesweeper game. Create a room, invite your friends, and explore a shared minefield together. Every player sees the same board, shares discoveries, and works toward a common victory.

But be careful: **one wrong step is enough to make the entire team lose!**

## ✨ Features

- **Real-time Multiplayer:** Play together with 2–10 players in a shared game room.
- **Room System:** Create a room and invite others using a 5-character room code or a shareable link.
- **Three Board Sizes:**
  - Small: 40 × 30
  - Medium: 100 × 60
  - Large: 200 × 120
- **Cooperative Gameplay:** All players share the same board state. If anyone hits a mine, everyone loses.
- **Individual Flag Colors:** Each player has a unique flag color, with up to 10 different colors.
- **Live Player Cursors:** See other players' names and cursor positions in real time.
- **Safe First Click:** The first opened cell and its surrounding 8 cells are guaranteed to be mine-free.
- **Flood Fill:** Opening an empty cell automatically reveals connected empty areas.
- **Chord:** Open surrounding cells by clicking an opened numbered cell when the adjacent flags match its number.
- **Responsive Controls:** Supports mouse, keyboard, and touch gestures.
- **Sound Effects & Background Music:** Includes digging, flagging, mass reveal, victory, and game-over sounds.
- **Lightweight:** Built with vanilla HTML, CSS, and JavaScript. No frontend frameworks or build tools required.

## 🎮 Controls

| Action | Mouse / Desktop | Touch Devices |
|---|---|---|
| Open a cell | Left click | Tap in Open mode |
| Place / Remove flag | Right click | Tap in Flag mode |
| Move around | Click and drag | One-finger drag |
| Zoom | Mouse wheel | Two-finger pinch |
| Switch Open / Flag mode | `F` key | ⛏️ / 🚩 button |
| Chord | Click an opened numbered cell | Tap an opened numbered cell |

## 🖥️ Screenshots

<!-- Add screenshots or GIF demonstrations here -->

<!--
![Gameplay](screenshots/gameplay.png)
![Multiplayer](screenshots/multiplayer.png)
-->

## 🛠️ Tech Stack

**Frontend**
- HTML5
- CSS3
- Vanilla JavaScript
- Canvas 2D API
- Web Audio API
- WebSocket API
- Cache Storage API

**Backend**
- Python 3
- aiohttp
- WebSocket

**Deployment**
- Render
- Nginx / Caddy
- systemd
- Cloudflare R2 (optional, for audio hosting)

## 📁 Project Structure

```text
minesweeper-coop/
├── server.py          # Python server and game logic
├── index.html         # Frontend: HTML, CSS, JavaScript, Canvas
├── requirements.txt   # Python dependencies
├── README.md
├── PROJECT_CONTEXT.md # Project handover documentation
├── sfx/               # Sound effects and background music
└── deploy/
    ├── minesweeper.service
    ├── nginx.conf
    └── Caddyfile
```

## 🚀 Getting Started

### Requirements

- Python 3.9+
- pip

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/minesweeper-coop.git
cd minesweeper-coop
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the server

```bash
python server.py
```

### 4. Open the game

Visit:

```text
http://localhost:8000
```

Enter a nickname, create a room, and share the room code with your friends.

**Note:** At least two players must be connected to a room before they can open cells or place flags.

## ⚙️ Configuration

The server supports the following environment variables:

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Server listening address |
| `PORT` | `8000` | Server listening port |
| `MAX_ROOMS` | `100` | Maximum number of concurrent rooms |

Example:

```bash
HOST=0.0.0.0 PORT=8000 MAX_ROOMS=100 python server.py
```

The server also provides a health-check endpoint:

```text
GET /healthz
```

Returns `ok` when the server is running.

## 🏗️ Architecture

Co-op Minesweeper uses a **Server-authoritative architecture**.

The server is responsible for generating mines, calculating adjacent mine counts, processing flood-fill operations, validating player actions, and determining victory or defeat.

The client handles rendering, user input, camera movement, and sound playback.

Communication between clients and the server is handled through WebSockets using JSON messages.

### Game State

Each room maintains its own game state in server memory:

- Mine positions
- Adjacent mine counts
- Revealed cells
- Player flags
- Player slots and connections
- Game status

The server sends full board snapshots when players join or a new game starts, then broadcasts only changed cells during normal gameplay to reduce network traffic.

### Multiplayer Synchronization

All players connected to the same room share one authoritative board.

- Opening a cell updates the board for everyone.
- Placing or removing a flag is synchronized instantly.
- Player cursors and names are broadcast in real time.
- A mine hit immediately ends the game for the entire room.

## 🔊 Audio System

The audio system is designed to minimize bandwidth usage.

- Audio files are loaded only when needed.
- Sound effects are decoded and reused through Web Audio API.
- Background music uses the browser Audio API.
- Cache Storage prevents unnecessary downloads.
- Content-based hashes allow long-term browser caching.
- The main HTML response supports ETag and gzip compression.

### External Audio Hosting (Optional)

Audio files can be hosted externally, such as on Cloudflare R2, instead of being served by the Python server.

Configure `SFX_SOURCES` in the `<head>` section of `index.html`:

```javascript
const SFX_SOURCES = {
    bgm: "",
    dig: "",
    mass: "",
    flag: "",
    gameover: "",
    win: ""
};
```

Replace an empty value with the corresponding audio URL.

For example:

```javascript
const SFX_SOURCES = {
    bgm: "https://your-domain.com/sfx/bgm.ogg",
    dig: "https://your-domain.com/sfx/dig.ogg",
    mass: "",
    flag: "",
    gameover: "",
    win: ""
};
```

Empty values use the server-hosted audio files.

**Important:** External audio hosting requires proper CORS configuration. For reliable caching, use long-lived `Cache-Control` headers and change the URL or version query parameter whenever an audio file is replaced.

## 🌐 Deployment

The project can run on any host that supports a persistent Python process and WebSocket connections.

Supported deployment configurations include:

- **Render:** Suitable for simple deployment with environment-based port configuration.
- **Nginx:** Reverse proxy with WebSocket upgrade support.
- **Caddy:** Reverse proxy with automatic HTTPS.
- **systemd:** Process management for Linux servers.

Example deployment configurations are provided in the `deploy/` directory.

When deploying behind a reverse proxy, make sure WebSocket connections to `/ws` are properly forwarded.

The application automatically uses secure WebSockets (`wss://`) when accessed over HTTPS.

## ⚠️ Current Limitations

- **Random Mine Generation:** Boards are generated randomly. Some situations may require guessing; there is currently no guaranteed no-guess generation algorithm.
- **In-memory State:** Room data is stored in RAM and is lost when the server restarts.
- **Single Instance:** The current architecture supports one server process. Multiple workers or instances require shared state management or room-based sticky routing.
- **No Automatic Reconnection:** Players must reload the page and rejoin using the room code after losing their connection.
- **No Authentication:** Anyone with a valid room code can join if the room has available slots.
- **Shared Restart Control:** Any player can restart the game for the entire room.
- **Browser Compatibility:** iPhone/Safari audio playback and touch behavior still require real-device testing.

## 🧪 Testing

The project has been tested with:

- WebSocket client simulations for room creation, joining, player limits, and game synchronization.
- Game logic tests covering cell opening, flags, flood-fill, player disconnections, victory/defeat transitions, and restarts.
- Playwright / Chromium for responsive layout and browser caching behavior.
- JavaScript syntax validation using `node --check`.
- Audio hosting simulations covering CORS behavior and external resource loading.

Some areas still require further testing:

- Real iPhone / Safari compatibility.
- Actual Cloudflare R2 integration.
- Audio playback across different browsers.
- Heavy concurrent traffic and large numbers of rooms.
- A complete real multiplayer victory session.

## 🗺️ Future Improvements

Potential improvements include:

- Implementing a guaranteed no-guess mine generation algorithm.
- Adding automatic WebSocket reconnection.
- Persisting room states across server restarts.
- Supporting horizontal scaling with shared room state.
- Improving binary synchronization for large boards.
- Expanding browser audio compatibility with additional formats.

## 📜 License

No license has been specified yet.

If you intend to make this project open source, consider adding a `LICENSE` file to define how others may use, modify, and distribute the code.

---

**Built with Python, WebSockets, Canvas 2D, and a little teamwork.** ⛏️