# 🏔️ MULE TRACE Project Analysis

**Mule Trace** is a high-performance, web-based intelligence platform designed for detecting money muling networks through behavioral graph analytics and temporal windowing.

## 🏗 System Architecture

The application is decoupled into a clear Client-Server architecture:

### Backend (Analytical Engine)
- **Framework**: Python FastAPI
- **Core Technologies**: `NetworkX` (Graph Theory), `Pandas` (Data Processing)
- **Key Modules**:
  - `main.py`: Exposes REST endpoints (`/upload`, `/ai-analyze/{account_id}`, `/generate-demo`) and a WebSocket endpoint (`/ws/live-feed`) for real-time transaction streaming.
  - `engine.py`: Contains the `ForensicsEngine` class which constructs directed graphs and uses vectorized operations to flag accounts.
  - `generate_data.py` (assumed based on imports): Synthesizes mock transaction datasets.
- **Algorithms Implemented**:
  - **Smurfing (Structuring)**: Dynamic sliding 72-hour window detecting $>10$ partners within bursts.
  - **Circular Fund Routing (Carousel)**: Utilizes Johnson's Algorithm (`nx.simple_cycles`) to detect loops of 3-5 hops.
  - **Layered Shell Networks**: Linear chain traversals detecting nested intermediaries with strictly 2-3 total transactions.
  - **Temporal Anomalies**: Flags nodes with high velocity or $>40\%$ nocturnal (11 PM - 5 AM) transaction activity.
  - **Whitelist Logic**: Recognizes high-volume legitimate merchants and consistent payroll pairs.

### Frontend (Visual Intelligence Layer)
- **Framework**: React (Vite)
- **Styling**: Tailwind CSS, employing a premium dark-themed "Forensic Command Center" aesthetic with glassmorphism, pulse animations, and gradient text.
- **Key Libraries**:
  - `vis-network`: For interactive, force-directed graph rendering.
  - `lucide-react`: Professional iconography.
- **Key Components**:
  - `App.jsx`: Main telemetry dashboard, state management (loading states, websocket stream processing), and AI AI Forensic Report UI wrapper. Features a unified command center for file uploads, live streams, and demo data generation.
  - Sub-components (`GraphView`, `StatsDashboard`, `TrendChart`): Manage layout, network clusters, and transaction velocity visualizations.

## 🚀 Key Features

1. **Intelligent Ingestion**: `map_columns` automatically standardizes raw CSV data against a range of common bank statement aliases.
2. **AI Forensic Deep Dive**: A specialized interface providing pseudo-AI narrative summaries of node behavior, classification (e.g., Aggregator vs Isolated Node), and numerical risk assessment.
3. **Live Streaming**: A real-time mode capable of connecting to web sockets to ingest transaction data continuously, rendering clusters as they form.
4. **Risk Scoring Matrix**: Calculates a Suspicion Score (0-100) based on weighted penalties for behaviors like Smurfing (+40) and Nocturnal Activity (+25).

## 📊 Evaluation
The platform demonstrates highly optimized Pandas handling (vectorized ops over `.apply()`), clean separation of concerns, and extensive defensive programming handling streaming responses natively through chunk generators. The user interface leverages modern CSS capabilities to deliver a professional and responsive command-center experience.
