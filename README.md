# Bin Day

A simple self-hosted web app that shows which bins to put out each week, based on the live Ipswich Borough Council collection schedule. Designed to look great on an iPhone home screen and on an e-ink display.

## Features

- Pulls the real council schedule daily — bank holidays and Christmas changes are handled automatically
- Shows urgency: **"Put out tonight!"**, "Put out tomorrow night", "Next collection in X days"
- Colour mode for phones/tablets, e-ink mode (`?theme=eink`) for e-ink displays
- Runs in Docker on a Raspberry Pi or any home server

## Finding your Council ID

1. Go to [app.ipswich.gov.uk/bin-collection](https://app.ipswich.gov.uk/bin-collection)
2. Search for your street
3. Look at the URL — the number at the end is your ID:
   ```
   https://app.ipswich.gov.uk/bin-collection/months/771
                                                       ^^^
                                                   your ID
   ```

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/YOURUSERNAME/bin-day.git
cd bin-day
```

**2. Create your `.env` file**
```bash
cp .env.example .env
```
Edit `.env` and set your council ID:
```
COUNCIL_ID=771
```

**3. Start the container**
```bash
docker compose up -d
```

The app runs at `http://localhost:5000` (or replace `localhost` with your Pi's IP address).

## Adding to your iPhone home screen

1. Open Safari and go to `http://<your-pi-ip>:5000`
2. Tap the **Share** button → **Add to Home Screen**
3. Name it **Bin Day** → tap **Add**

## E-ink display

Add `?theme=eink` to the URL for a high-contrast black-and-white layout suited to e-ink screens:

```
http://<your-pi-ip>:5000?theme=eink
```

## Updating

```bash
git pull
docker compose up -d --build
```

## Bins supported

| Colour | Type |
|--------|------|
| ⬛ Black | General waste |
| 🔲 Grey (small) | Food waste caddy |
| 🟫 Brown | Garden waste |
| 🟦 Blue | Plastics |
| 🟩 Green lid | Paper & card |
