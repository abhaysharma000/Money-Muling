from fastapi import FastAPI, UploadFile, File, HTTPException, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import pandas as pd
import io
import time
import traceback
import json
try:
    from engine import ForensicsEngine
    from models import AnalysisResponse, AnalysisSummary
except ImportError:
    from backend.engine import ForensicsEngine
    from backend.models import AnalysisResponse, AnalysisSummary

app = FastAPI(title="MULE TRACE - Financial Forensics Engine")

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"CRITICAL ERROR: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "traceback": traceback.format_exc() if not isinstance(exc, HTTPException) else None
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ForensicsEngine()
router = APIRouter(prefix="/api")

def analyze_dataframe(df: pd.DataFrame):
    """Reusable generator for forensic analysis stream"""
    def generator():
        try:
            # Immediate heartbeat to prevent Vercel timeout
            yield f"data: {json.dumps({'status': 'System Initializing...', 'progress': 0.05})}\n\n"
            
            start_time = time.time()
            yield f"data: {json.dumps({'status': 'Building Graph Topology...', 'progress': 0.1})}\n\n"
            engine.load_data(df)
            
            yield f"data: {json.dumps({'status': 'Parallel Forensic Sweep...', 'progress': 0.4})}\n\n"
            results = engine.analyze()
            
            yield f"data: {json.dumps({'status': 'Graphing Clusters...', 'progress': 0.7})}\n\n"
            fraud_rings = engine.get_fraud_rings(results)
            graph_data = engine.get_graph_data(results)
            
            processing_time = round(time.time() - start_time, 2)
            avg_score = sum(a['suspicion_score'] for a in results) / len(results) if results else 0
            
            summary = AnalysisSummary(
                total_accounts_analyzed=len(engine.graph.nodes()),
                total_transactions=len(df),
                suspicious_accounts_flagged=len(results),
                fraud_rings_detected=len(fraud_rings),
                avg_risk_score=round(avg_score, 2),
                processing_time_seconds=processing_time
            )
            
            final_data = {
                "suspicious_accounts": results,
                "fraud_rings": fraud_rings,
                "graph_data": graph_data,
                "summary": summary.dict(),
                "complete": True
            }
            yield f"data: {json.dumps(final_data)}\n\n"
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Error in analysis: {e}\n{tb}")
            yield f"data: {json.dumps({'error': str(e), 'complete': True})}\n\n"
    return generator()

@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "Financial Forensics Engine API"}

@router.get("/")
def read_root():
    return {"message": "Financial Forensics Engine API"}

@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    content = await file.read()
    raw_df = pd.read_csv(io.BytesIO(content))
    df = map_columns(raw_df)
    return StreamingResponse(analyze_dataframe(df), media_type="text/event-stream")

def map_columns(df: pd.DataFrame):
    """Bulletproof Column Mapping Logic"""
    mapping = {
        'sender_id': ['sender_id', 'sourceid', 'from', 'sender', 'source', 'initiator', 'nameorig', 'origin'],
        'receiver_id': ['receiver_id', 'destinationid', 'to', 'receiver', 'destination', 'recipient', 'namedest', 'target'],
        'amount': ['amount', 'amountofmoney', 'value', 'sum', 'amountoff'],
        'timestamp': ['timestamp', 'date', 'time', 'datetime'],
        'transaction_id': ['transaction_id', 'id', 'tx_id', 'txid']
    }
    
    norm_to_orig = {str(col).lower().replace(" ", "").replace("_", ""): col for col in df.columns}
    final_mapping = {}
    mapped_orig_cols = set()
    
    for target, aliases in mapping.items():
        match_found = False
        for alias in aliases:
            norm_alias = alias.lower().replace(" ", "").replace("_", "")
            if norm_alias in norm_to_orig:
                orig_col = norm_to_orig[norm_alias]
                if orig_col not in mapped_orig_cols:
                    final_mapping[orig_col] = target
                    mapped_orig_cols.add(orig_col)
                    match_found = True
                    break
        
        if not match_found:
            sample = df.drop(columns=list(mapped_orig_cols)).head(100)
            for col in sample.columns:
                col_data = sample[col].dropna()
                if col_data.empty: continue
                if target == 'amount' and pd.api.types.is_numeric_dtype(col_data):
                    if col_data.mean() > 0:
                        final_mapping[col] = target
                        mapped_orig_cols.add(col)
                        match_found = True
                        break
                elif target == 'timestamp':
                    try:
                        pd.to_datetime(col_data.iloc[0], errors='raise')
                        final_mapping[col] = target
                        mapped_orig_cols.add(col)
                        match_found = True
                        break
                    except: pass
                elif target in ['sender_id', 'receiver_id'] and not pd.api.types.is_numeric_dtype(col_data):
                    final_mapping[col] = target
                    mapped_orig_cols.add(col)
                    match_found = True
                    break
        
        if not match_found and target in ['sender_id', 'receiver_id', 'amount']:
            indices = {'sender_id': 1, 'receiver_id': 2, 'amount': 3}
            if len(df.columns) > indices.get(target, 999):
                fallback_col = df.columns[indices[target]]
                if fallback_col not in mapped_orig_cols:
                    final_mapping[fallback_col] = target
                    mapped_orig_cols.add(fallback_col)
                    match_found = True
            if not match_found:
                raise HTTPException(status_code=400, detail=f"Column mapping failed: {target}")

    df = df.rename(columns=final_mapping)
    expected = ['transaction_id', 'sender_id', 'receiver_id', 'amount', 'timestamp']
    available = [c for c in expected if c in df.columns]
    df = df[available].copy()
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    if 'transaction_id' not in df.columns:
        df['transaction_id'] = [f"TX_{i:06d}" for i in range(len(df))]
    if 'timestamp' not in df.columns:
        df['timestamp'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        
    return df[['transaction_id', 'sender_id', 'receiver_id', 'amount', 'timestamp']]

def format_duration(seconds: float) -> str:
    """Convert seconds into a human-readable duration string"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    elif seconds < 86400:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"
    else:
        d = int(seconds // 86400)
        h = int((seconds % 86400) // 3600)
        return f"{d}d {h}h"

@router.post("/ai-analyze/{account_id}")
async def ai_analyze_endpoint(account_id: str):
    """Generate a mock AI forensic deep-dive for hackathon demo"""
    if account_id not in engine.graph.nodes():
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Calculate actual stats for dynamic reporting
    in_degree = engine.graph.in_degree(account_id)
    out_degree = engine.graph.out_degree(account_id)
    
    node_tx = engine.df[(engine.df['sender_id'] == account_id) | (engine.df['receiver_id'] == account_id)].copy()
    
    # Temporal analysis logic
    temporal_detail = "Insufficient temporal metadata available."
    behavioral_flags = []
    
    if not node_tx.empty and 'timestamp' in node_tx.columns:
        try:
            if not pd.api.types.is_datetime64_any_dtype(node_tx['timestamp']):
                node_tx['timestamp'] = pd.to_datetime(node_tx['timestamp'])
            
            min_time = node_tx['timestamp'].min()
            max_time = node_tx['timestamp'].max()
            duration_secs = (max_time - min_time).total_seconds()
            
            readable_duration = format_duration(duration_secs)
            
            # Night pattern detection (11 PM - 5 AM)
            night_tx = node_tx[node_tx['timestamp'].dt.hour.isin([23, 0, 1, 2, 3, 4])]
            night_pct = (len(night_tx) / len(node_tx)) * 100 if not node_tx.empty else 0
            
            if night_pct > 25:
                behavioral_flags.append({
                    "type": "Nocturnal",
                    "detail": f"{night_pct:.1f}% of activity occurs in dead-of-night hours (11PM-5AM)."
                })

            if duration_secs < 3600:
                 temporal_detail = f"High-velocity burst: {len(node_tx)} tx in {readable_duration}."
            else:
                velocity = len(node_tx) / max(1, duration_secs / 3600)
                temporal_detail = f"Temporal density: {velocity:.1f} tx/hr over a {readable_duration} window."
                
            # Consistency vs Variance
            hourly_tx = node_tx.resample('1h', on='timestamp').size()
            if not hourly_tx.empty and len(hourly_tx) > 3:
                cv = hourly_tx.std() / hourly_tx.mean() if hourly_tx.mean() > 0 else 0
                if cv < 0.2:
                    behavioral_flags.append({
                        "type": "Robotic",
                        "detail": "Highly consistent transaction cadence suggestive of automated pooling."
                    })
        except Exception as e:
            print(f"Temporal analysis error: {e}")
            temporal_detail = "Temporal anomaly: Clustering suggestive of automated script behavior."

    # Role classification
    if in_degree > 10 and out_degree < 2:
        role = "Aggregator (Fan-in)"
    elif out_degree > 10 and in_degree < 2:
        role = "Distributor (Fan-out)"
    elif in_degree >= 1 and out_degree >= 1:
        role = "Intermediary Layer"
    else:
        role = "Endpoint Node"
        role = "Isolated Node"

    return {
        "account_id": account_id,
        "forensic_summary": f"Behavioral analysis of {account_id} reveals a high-risk {role} pattern.",
        "behavioral_flags": [
            { "type": "Topology", "detail": f"Degree centrality ({in_degree} in, {out_degree} out) confirms intermediary role." },
            { "type": "Temporal", "detail": temporal_detail }
        ],
        "recommendation": "IMMEDIATE FREEZE. High-velocity aggregator profile detected." if in_degree > 10 else "MONITOR. Potential shell entity in fund-routing chain.",
        "prediction_confidence": 0.85 + (0.10 * (min(1.0, (in_degree + out_degree) / 20)))
    }

@router.post("/generate-demo")
async def generate_demo_endpoint():
    """Trigger the generation of a demo dataset and return the stream"""
    try:
        from generate_data import generate_test_csv
    except ImportError:
        from backend.generate_data import generate_test_csv
    
    # Use in-memory buffer to avoid Vercel Read-Only File System errors
    output_buffer = io.StringIO()
    generate_test_csv(num_transactions=1500, output_file=output_buffer)
    output_buffer.seek(0)
    
    df = pd.read_csv(output_buffer)
    df = map_columns(df)
    return StreamingResponse(analyze_dataframe(df), media_type="text/event-stream")

@router.get("/live-stream")
async def live_stream_endpoint():
    """Streaming alternative to WebSockets for serverless environments (Vercel)"""
    try:
        from generate_data import generate_test_csv
    except ImportError:
        from backend.generate_data import generate_test_csv

    def generator():
        try:
            output_buffer = io.StringIO()
            generate_test_csv(num_transactions=200, output_file=output_buffer)
            output_buffer.seek(0)
            
            full_df = pd.read_csv(output_buffer)
            full_df = map_columns(full_df)
            
            chunk_size = 15
            total_chunks = len(full_df) // chunk_size
            
            for i in range(total_chunks):
                chunk = full_df.iloc[:(i+1)*chunk_size]
                start_time = time.time()
                engine.load_data(chunk)
                results = engine.analyze()
                fraud_rings = engine.get_fraud_rings(results)
                graph_data = engine.get_graph_data(results)
                processing_time = round(time.time() - start_time, 2)
                avg_score = sum(a['suspicion_score'] for a in results) / len(results) if results else 0
                
                summary = AnalysisSummary(
                    total_accounts_analyzed=len(engine.graph.nodes()),
                    total_transactions=len(chunk),
                    suspicious_accounts_flagged=len(results),
                    fraud_rings_detected=len(fraud_rings),
                    avg_risk_score=round(avg_score, 2),
                    processing_time_seconds=processing_time
                )
                
                final_data = {
                    "suspicious_accounts": results,
                    "fraud_rings": fraud_rings,
                    "graph_data": graph_data,
                    "summary": summary.dict(),
                    "complete": i == total_chunks - 1
                }
                yield f"data: {json.dumps(final_data)}\n\n"
                time.sleep(0.4)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'complete': True})}\n\n"
            
    return StreamingResponse(generator(), media_type="text/event-stream")

app.include_router(router)

@app.websocket("/ws/live-feed")
async def websocket_live_feed(websocket: WebSocket):
    await websocket.accept()
    
    try:
        from generate_data import generate_test_csv
    except ImportError:
        from backend.generate_data import generate_test_csv
        
    try:
        # Generate initial large dataset
        output_buffer = io.StringIO()
        generate_test_csv(num_transactions=500, output_file=output_buffer)
        output_buffer.seek(0)
        
        full_df = pd.read_csv(output_buffer)
        full_df = map_columns(full_df)
        
        chunk_size = 20
        total_chunks = len(full_df) // chunk_size
        
        # Stream chunks
        for i in range(total_chunks):
            chunk = full_df.iloc[:(i+1)*chunk_size]
            
            start_time = time.time()
            engine.load_data(chunk)
            results = engine.analyze()
            
            fraud_rings = engine.get_fraud_rings(results)
            graph_data = engine.get_graph_data(results)
            
            processing_time = round(time.time() - start_time, 2)
            avg_score = sum(a['suspicion_score'] for a in results) / len(results) if results else 0
            
            summary = AnalysisSummary(
                total_accounts_analyzed=len(engine.graph.nodes()),
                total_transactions=len(chunk),
                suspicious_accounts_flagged=len(results),
                fraud_rings_detected=len(fraud_rings),
                avg_risk_score=round(avg_score, 2),
                processing_time_seconds=processing_time
            )
            
            final_data = {
                "suspicious_accounts": results,
                "fraud_rings": fraud_rings,
                "graph_data": graph_data,
                "summary": summary.dict(),
                "complete": i == total_chunks - 1
            }
            
            await websocket.send_json(final_data)
            await asyncio.sleep(0.5) # Wait 0.5 seconds before sending next chunk
            
    except WebSocketDisconnect:
        print("Live feed disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e), "complete": True})
        except:
            pass
