# ConvoMate

Real-time customer support call monitoring with live transcription, sentiment detection, escalation tracking, and agent coaching.

## Overview

ConvoMate is an MVP for an agent-assist product. It listens to a live phone call streamed from Twilio, transcribes speech with Deepgram, analyzes the latest customer utterance with an LLM, and pushes live updates to a dashboard.

The current system is best described as:

- a live caller sentiment monitor
- an escalation detector
- a real-time coaching assistant for the support agent

It is not yet a full call-center platform. It does not currently manage a true two-leg customer-agent bridge, separate speakers reliably, or automate downstream actions like CRM updates or refunds.

## Core Workflow

1. A caller dials your Twilio number.
2. Twilio requests `/twiml` from the backend.
3. The backend returns TwiML instructing Twilio to open a media stream to `/media-stream`.
4. The backend forwards incoming audio frames to Deepgram for speech-to-text.
5. For each finalized transcript segment, the backend:
   - stores recent context
   - runs sentiment and escalation analysis
   - generates a coaching suggestion
6. The backend broadcasts transcript and analysis events to the frontend over `/ws`.
7. The dashboard updates in real time with transcript, sentiment, escalation state, and agent guidance.

## Features

- Live phone call ingestion via Twilio Media Streams
- Real-time speech transcription via Deepgram
- LLM-powered sentiment classification
- Escalation risk detection
- Live coaching suggestions for the support agent
- Browser dashboard with transcript and metrics
- Demo simulation mode without Twilio
- REST endpoint for direct text testing
- Render deployment support

## Architecture

```text
Caller
  -> Twilio Voice Number
  -> POST /twiml
  -> WebSocket /media-stream
  -> Deepgram speech-to-text
  -> LLM analysis
  -> WebSocket /ws
  -> Dashboard
```

## Tech Stack

- FastAPI
- Twilio Media Streams
- Deepgram
- Groq
- Plain HTML/CSS/JavaScript dashboard
- Render for deployment

## Project Structure

```text
ConvoMate/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── routers/
│   │   ├── analyze.py
│   │   ├── frontend_ws.py
│   │   └── twilio_ws.py
│   └── services/
│       ├── context.py
│       ├── deepgram.py
│       └── groq.py
├── frontend/
│   ├── app.js
│   ├── index.html
│   └── style.css
├── render.yaml
└── README.md
```

## Environment Variables

Create a local `.env` in the project root.

Required:

- `DEEPGRAM_API_KEY`
- `GROQ_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `AGENT_PHONE_NUMBER`
- `PUBLIC_URL`

Optional:

- `GROQ_MODEL`
- `HOST`
- `PORT`
- `CONTEXT_BUFFER_SIZE`
- `MIN_TRANSCRIPT_LENGTH`

Example values are in `backend/.env.example`.

## Local Setup

### 1. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r backend/requirements.txt
```

### 3. Configure `.env`

Fill in your Deepgram, Groq, Twilio, and `PUBLIC_URL` values.

For local Twilio testing, `PUBLIC_URL` should be your ngrok HTTPS URL.

### 4. Start the backend

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## How To Open The Frontend

You have two ways to use the dashboard:

### Local file mode

Open `frontend/index.html` directly in your browser.

### Backend-served dashboard

Once the backend is running, open:

```text
http://localhost:8000/dashboard/
```

This is also the recommended path for Render deployment.

## How To Test The MVP

### Option 1: Demo mode

Open the dashboard and click `Start Simulation`.

This exercises:

- transcript rendering
- sentiment updates
- escalation banner logic
- coaching suggestions
- dashboard state management

This is the fastest way to confirm the UI works end to end without telephony.

### Option 2: REST analysis test

Use the `/analyze` endpoint to test text classification directly.

```powershell
Invoke-WebRequest -Method POST `
  -Uri http://127.0.0.1:8000/analyze `
  -ContentType "application/json" `
  -Body '{"text":"I am frustrated with this delay","reset_context":true}'
```

This is useful for checking whether sentiment and suggestion logic behave as expected without Twilio or Deepgram in the loop.

### Option 3: Live Twilio call

1. Start the backend.
2. Expose it with ngrok:

```powershell
ngrok http 8000
```

3. Set `.env`:

```text
PUBLIC_URL=https://your-ngrok-url
```

4. Restart the backend after changing `.env`.
5. In the Twilio console, point your number's incoming voice webhook to:

```text
https://your-ngrok-url/twiml
```

6. Open the dashboard.
7. Call the Twilio number and speak.

Expected result:

- the terminal logs Twilio and Deepgram activity
- the dashboard shows live transcript updates
- sentiment and coaching update after final transcript chunks

## How To Validate The Product

The MVP can validate:

- Twilio audio ingestion
- transcription quality
- basic sentiment classification
- escalation detection
- usefulness of live coaching suggestions

The MVP cannot fully validate:

- true speaker separation
- actual agent quality scoring
- a realistic two-leg customer-agent conversation inside Twilio

Best practical tests:

1. One person speaks scripted emotional phrases to verify sentiment accuracy.
2. One person roleplays both customer and agent with pauses.
3. Two people speak into the same live call audio path for a more realistic test.

## Dashboard Behavior

The dashboard shows:

- current call state
- transcript feed
- current sentiment
- escalation status
- call duration
- transcript segment count
- latest coaching suggestion
- sentiment history

It also supports a scripted simulation mode for demoing the product without live telephony.

## API Endpoints

### `GET /`

Returns service metadata and important URLs.

### `GET /health`

Health check endpoint.

### `POST /twiml`

Returns TwiML instructing Twilio to connect the call audio stream to `/media-stream`.

### `WS /media-stream`

Receives Twilio Media Streams audio payloads and drives the transcription and analysis pipeline.

### `WS /ws`

Pushes transcript and analysis events to the dashboard.

### `POST /analyze`

Analyzes direct text input without a live call.

Request body:

```json
{
  "text": "I am extremely frustrated with this service!",
  "reset_context": true
}
```

Example response:

```json
{
  "transcript": "I am extremely frustrated with this service!",
  "sentiment": "Frustrated",
  "escalation": "Yes",
  "suggestion": "Acknowledge the frustration clearly, apologize, and offer the fastest concrete next step."
}
```

### `GET /docs`

Swagger UI for exploring the API.

### `GET /dashboard/`

Serves the browser dashboard through FastAPI.

## Deployment On Render

This repo includes `render.yaml` for deployment.

### Render flow

1. Push this repo to GitHub.
2. Create a new Blueprint deploy in Render using the repo.
3. Let Render detect `render.yaml`.
4. Set these secret environment variables in Render:
   - `DEEPGRAM_API_KEY`
   - `GROQ_API_KEY`
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `PUBLIC_URL`
5. Set `PUBLIC_URL` to your Render service URL, for example:

```text
https://convomate-backend.onrender.com
```

### After deploy

- backend health: `https://your-render-url/health`
- dashboard: `https://your-render-url/dashboard/`
- Twilio webhook: `https://your-render-url/twiml`

In the Twilio console, update your number to call:

```text
https://your-render-url/twiml
```

## Failure Modes To Expect

- If Twilio cannot reach `/media-stream`, the call will not stream correctly.
- If Deepgram cannot connect, the dashboard will show a call error and no transcript will appear.
- If Groq is unreachable, the app falls back to local heuristic analysis.
- If the dashboard is open from a local file while the backend is down, simulation mode still works.

## Current Limitations

- No robust customer vs agent speaker separation
- No real call bridging between customer and support agent
- No persistence layer for transcripts or analytics
- No auth or multi-tenant support
- No CRM or ticketing integrations

## Suggested Next Steps

1. Add speaker diarization or channel separation.
2. Add robust speaker separation or diarization.
3. Add persisted call logs and evaluation history.
4. Add an automated test suite around `/analyze`.
5. Implement a proper Twilio bridged call flow for agent/customer testing.
