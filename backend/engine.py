import networkx as nx
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Set

class ForensicsEngine:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.df = None
        self.suspicious_accounts = {}
        self.fraud_rings = {}

    def load_data(self, df: pd.DataFrame, progress_callback=None):
        """Construct graph and prepare data for analysis efficiently"""
        if progress_callback: progress_callback("Loading data and building graph...", 0.1)
        
        self.df = df.copy()
        
        # Hyper-Defensive Numeric Conversion
        if 'amount' in self.df.columns:
            if self.df['amount'].dtype == object:
                self.df['amount'] = self.df['amount'].astype(str).str.replace(r'[$,]', '', regex=True)
            self.df['amount'] = pd.to_numeric(self.df['amount'], errors='coerce').fillna(0).astype(float)
        
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'], errors='coerce')
        self.df['sender_id'] = self.df['sender_id'].astype(str).fillna("unknown")
        self.df['receiver_id'] = self.df['receiver_id'].astype(str).fillna("unknown")
        
        self.graph.clear()
        
        # Optimized Graph Construction - Explicitly select numeric columns for agg
        try:
            edge_data = self.df.groupby(['sender_id', 'receiver_id']).agg({
                'amount': 'sum',
                'transaction_id': 'count'
            }).reset_index()
        except Exception as e:
            # Fallback if agg fails: ensure amount is float and try again
            self.df['amount'] = self.df['amount'].astype(float)
            edge_data = self.df.groupby(['sender_id', 'receiver_id']).agg({
                'amount': 'sum',
                'transaction_id': 'count'
            }).reset_index()
        
        self.graph = nx.from_pandas_edgelist(
            edge_data, 'sender_id', 'receiver_id', 
            ['amount', 'transaction_id'], 
            create_using=nx.DiGraph()
        )
        
        # Rename attributes for consistency with existing code
        for u, v, d in self.graph.edges(data=True):
            d['total_amount'] = float(d.pop('amount'))
            d['count'] = int(d.pop('transaction_id'))
        
        if progress_callback: progress_callback("Graph constructed.", 0.2)

    def detect_smurfing(self, progress_callback=None) -> Dict[str, Dict]:
        """Detect Fan-in/Fan-out patterns using vectorized sliding windows (Pandas Rolling)"""
        if progress_callback: progress_callback("Analyzing smurfing (Vectorized)...", 0.6)
        smurfing_results = {}
        if self.df is None or self.df.empty:
            return smurfing_results
            
        window_size = '72h'
        
        # Create a temporary sorted DF for rolling analysis
        temp_df = self.df.sort_values('timestamp').dropna(subset=['timestamp'])
        
        if temp_df.empty:
            return smurfing_results
        
        # 1. Vectorized Fan-In (Many to One)
        # Group by receiver, use rolling 72h window to count unique senders
        # Note: nunique() isn't directly available in rolling, so we use a custom apply if needed
        # or a more efficient trick: count unique senders in the window
        
        # Use a numeric proxy for rolling count of unique senders if possible, 
        # but nunique in rolling is tricky. We'll use a more robust approach.
        # Check if sender_id can be mapped to int for the rolling operation
        sender_map = {id: i for i, id in enumerate(temp_df['sender_id'].unique())}
        temp_df['sender_idx'] = temp_df['sender_id'].map(sender_map)
        
        in_counts = temp_df.set_index('timestamp').groupby('receiver_id')['sender_idx'].rolling(window_size).apply(lambda x: len(set(x)), raw=True)
        flagged_in = in_counts[in_counts >= 10].index.get_level_values(0).unique()
        
        for receiver in flagged_in:
            smurfing_results.setdefault(str(receiver), {"patterns": set(), "explanation": []})
            smurfing_results[str(receiver)]["patterns"].add("fan_in")
            smurfing_results[str(receiver)]["explanation"].append("Fan-in Aggregation: 10+ distinct senders within a 72-hour window (Vectorized Match).")

        # 2. Vectorized Fan-Out (One to Many)
        receiver_map = {id: i for i, id in enumerate(temp_df['receiver_id'].unique())}
        temp_df['receiver_idx'] = temp_df['receiver_id'].map(receiver_map)

        out_counts = temp_df.set_index('timestamp').groupby('sender_id')['receiver_idx'].rolling(window_size).apply(lambda x: len(set(x)), raw=True)
        flagged_out = out_counts[out_counts >= 10].index.get_level_values(0).unique()

        for sender in flagged_out:
            smurfing_results.setdefault(str(sender), {"patterns": set(), "explanation": []})
            smurfing_results[str(sender)]["patterns"].add("fan_out")
            smurfing_results[str(sender)]["explanation"].append("Fan-out Dispersal: 10+ distinct receivers within a 72-hour window (Vectorized Match).")
                    
        return smurfing_results

    def identify_legitimate_entities(self, progress_callback=None) -> Set[str]:
        """Detect high-volume merchants and regular payroll accounts using robust vectorized heuristics"""
        if progress_callback: progress_callback("Filtering legitimate entities...", 0.3)
        legitimate = set()
        
        # 1. Advanced Merchant/Hub detection (Vectorized)
        receivers = self.df.groupby('receiver_id')
        unique_senders = receivers['sender_id'].nunique()
        candidate_merchants = unique_senders[unique_senders >= 50].index
        
        for merchant in candidate_merchants:
            group = self.df[self.df['receiver_id'] == merchant]
            # Check for "trap" merchants: consistent volume, not bursty
            daily_counts = group.resample('d', on='timestamp').size()
            if daily_counts.std() < daily_counts.mean() * 0.7:
                legitimate.add(str(merchant))

        # 2. Payroll detection (Stability Check)
        recurring = self.df.groupby(['sender_id', 'receiver_id']).size()
        candidate_pairs = recurring[recurring >= 3].index
        
        for sender, receiver in candidate_pairs:
            group = self.df[(self.df['sender_id'] == sender) & (self.df['receiver_id'] == receiver)]
            # Check for monthly cadence
            times = sorted(group['timestamp'])
            diffs = pd.Series(times).diff().dt.days.dropna()
            if (diffs >= 25).all() and (diffs <= 35).all():
                # Amount Stability Check: < 5% variance
                amounts = group['amount']
                if amounts.std() < amounts.mean() * 0.05:
                    legitimate.add(str(receiver))
                    
        return legitimate

    def detect_bursts(self) -> Dict[str, bool]:
        """Detect accounts with unusual transaction bursts (Vectorized)"""
        bursts = {}
        # Only analyze active nodes
        node_activity = self.df.groupby('sender_id').size()
        active_nodes = node_activity[node_activity > 5].index
        
        for node in active_nodes:
            node_tx = self.df[self.df['sender_id'] == node]
            windowed = node_tx.resample('1h', on='timestamp').size()
            if not windowed.empty and windowed.max() > windowed.mean() + 3 * windowed.std() + 5:
                bursts[str(node)] = True
        return bursts

    def analyze(self, progress_callback=None) -> Dict:
        """Run suite of detection patterns in PARALLEL to ensure < 30s performance"""
        from concurrent.futures import ThreadPoolExecutor
        
        legitimate = self.identify_legitimate_entities(progress_callback)
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            if progress_callback: progress_callback("Executing Parallel Forensic Sweep...", 0.5)
            
            future_smurfing = executor.submit(self.detect_smurfing)
            future_bursts = executor.submit(self.detect_bursts)
            future_shells = executor.submit(self.detect_shell_chains)
            
            # Cycles are slow, so we prune the graph first
            susp_nodes = [n for n in self.graph.nodes() if n not in legitimate]
            # Further prune for cycles: only nodes with degree > 1 can be in a cycle
            cycle_candidates = [n for n in susp_nodes if self.graph.degree(n) > 1]
            subgraph = self.graph.subgraph(cycle_candidates)
            future_cycles = executor.submit(lambda: list(nx.simple_cycles(subgraph)))
            
            smurfing = future_smurfing.result()
            bursts = future_bursts.result()
            shell_chains = future_shells.result()
            cycles = future_cycles.result()

        scores = {}
        tags = {}
        explanations = {}
        
        # 1. Smurfing
        for node, data in smurfing.items():
            if node in legitimate: continue
            scores[node] = scores.get(node, 0) + 40
            tags.setdefault(node, set()).update(data["patterns"])
            explanations.setdefault(node, []).extend(data["explanation"])

        # 2. Cycles
        for cycle in cycles:
            l = len(cycle)
            if 3 <= l <= 5:
                for node in cycle:
                    scores[node] = scores.get(node, 0) + (25 * (6-l))
                    tags.setdefault(node, set()).add(f"cycle_length_{l}")
                    explanations.setdefault(node, []).append(f"Involved in a {l}-step circular fund routing loop.")

        # 3. Shell Chains
        for chain in shell_chains:
            l = len(chain)
            for node in chain:
                if node in legitimate: continue
                scores[node] = scores.get(node, 0) + 20
                tags.setdefault(node, set()).add("shell_chain")
                # Deduplicate: only keep highest hop count info to avoid clutter
                curr_ex = [ex for ex in explanations.get(node, []) if "layered shell network" in ex]
                if not curr_ex:
                    explanations.setdefault(node, []).append(f"Part of a {l}-hop layered shell network.")
                else:
                    # Update if this chain is longer
                    old_len = int(curr_ex[0].split("-hop")[0].split(" ")[-1])
                    if l > old_len:
                        explanations[node].remove(curr_ex[0])
                        explanations[node].append(f"Part of a {l}-hop layered shell network.")

        # 4. Bursts & Night Activity
        for node, is_burst in bursts.items():
            if node in legitimate: continue
            
            node_tx = self.df[(self.df['sender_id'] == node) | (self.df['receiver_id'] == node)]
            night_tx = node_tx[node_tx['timestamp'].dt.hour.isin([23, 0, 1, 2, 3, 4])]
            night_pct = (len(night_tx) / len(node_tx)) * 100 if len(node_tx) > 5 else 0
            
            if night_pct > 40: # High threshold for automatic flagging
                scores[node] = scores.get(node, 0) + 25
                tags.setdefault(node, set()).add("nocturnal_activity")
                explanations.setdefault(node, []).append(f"Suspicious nocturnal pattern: {night_pct:.1f}% of volume during 23:00-05:00.")

            if is_burst and node not in tags:
                scores[node] = scores.get(node, 0) + 15
                tags.setdefault(node, set()).add("high_velocity")
                explanations.setdefault(node, []).append("Detected unusual transaction burst frequency.")

        # Compile Results
        results = []
        for node, score in scores.items():
            if score > 0:
                # Collect last 10 transactions for frontend charts
                node_tx = self.df[(self.df['sender_id'] == node) | (self.df['receiver_id'] == node)].sort_values('timestamp', ascending=False).head(10)
                tx_list = [
                    {
                        "transaction_id": str(row['transaction_id']),
                        "sender_id": str(row['sender_id']),
                        "receiver_id": str(row['receiver_id']),
                        "amount": float(row['amount']),
                        "timestamp": row['timestamp'].strftime("%Y-%m-%d %H:%M:%S") if hasattr(row['timestamp'], 'strftime') else str(row['timestamp'])
                    } for _, row in node_tx.iterrows()
                ]

                results.append({
                    "account_id": node,
                    "suspicion_score": float(round(min(100.0, float(score)), 2)),
                    "detected_patterns": sorted(list(tags.get(node, []))),
                    "explanation": " ".join(dict.fromkeys(explanations.get(node, []))),
                    "is_legitimate_hub": node in legitimate,
                    "ring_id": "",
                    "recent_transactions": tx_list
                })
        
        return sorted(results, key=lambda x: x['suspicion_score'], reverse=True)

    def detect_shell_chains(self, min_hops=4) -> List[List[str]]:
        """Detect linear chains through low-activity nodes (Vectorized Count)"""
        counts = pd.concat([self.df['sender_id'], self.df['receiver_id']]).value_counts()
        chains = []
        for node in [n for n in self.graph.nodes() if self.graph.out_degree(n) == 1]:
            path = [node]
            curr = node
            while True:
                succs = list(self.graph.successors(curr))
                if not succs: break
                nxt = succs[0]
                if nxt in path: break
                nxt_activity = counts.get(nxt, 0)
                if 2 <= nxt_activity <= 3 and self.graph.out_degree(nxt) == 1:
                    path.append(nxt)
                    curr = nxt
                else:
                    path.append(nxt)
                    break
            if len(path) >= min_hops:
                chains.append(path)
        return chains

    def get_fraud_rings(self, suspicious_accounts: List[Dict]) -> List[Dict]:
        """Group suspicious nodes into rings based on connectivity"""
        suspicious_nodes = {acc['account_id'] for acc in suspicious_accounts}
        subgraph = self.graph.subgraph(suspicious_nodes).to_undirected()
        components = list(nx.connected_components(subgraph))
        
        rings = []
        for i, nodes in enumerate(components):
            if len(nodes) < 2: continue
            ring_id = f"RING_{i+1:03d}"
            ring_scores = [a['suspicion_score'] for a in suspicious_accounts if a['account_id'] in nodes]
            pattern_types = set()
            for node in nodes:
                acc = next((a for a in suspicious_accounts if a['account_id'] == node), None)
                if acc:
                    acc['ring_id'] = ring_id
                    for p in acc['detected_patterns']:
                        if 'cycle' in p: pattern_types.add('cycle')
                        elif 'fan' in p: pattern_types.add('smurfing')
                        elif 'shell' in p: pattern_types.add('shell-chain')
            
            avg_score = sum(ring_scores) / len(ring_scores) if ring_scores else 0
            rings.append({
                "ring_id": ring_id,
                "member_accounts": sorted(list(nodes)),
                "pattern_type": ", ".join(sorted(list(pattern_types))) if pattern_types else "unclassified",
                "risk_score": float(round(avg_score, 2))
            })
        return sorted(rings, key=lambda x: x['risk_score'], reverse=True)

    def get_graph_data(self, suspicious_accounts: List[Dict]) -> Dict:
        """Extract nodes and edges for visualization (Optimized)"""
        node_ids = {acc['account_id'] for acc in suspicious_accounts}
        # Include direct neighbors
        neighbors = set()
        for node in node_ids:
            neighbors.update(self.graph.successors(node))
            neighbors.update(self.graph.predecessors(node))
        all_relevant = node_ids.union(neighbors)
        
        nodes = []
        for node_id in all_relevant:
            acc = next((a for a in suspicious_accounts if a['account_id'] == node_id), None)
            total_tx = self.graph.degree(node_id)
            nodes.append({
                "id": node_id,
                "label": node_id,
                "risk_score": acc['suspicion_score'] if acc else 0,
                "tags": acc['detected_patterns'] if acc else [],
                "total_transactions": total_tx,
                "is_legitimate": acc['is_legitimate_hub'] if acc else False,
                "ring_id": acc.get('ring_id', "") if acc else ""
            })

        edges = []
        for u, v, data in self.graph.subgraph(all_relevant).edges(data=True):
            edges.append({
                "from_node": u, "to_node": v,
                "label": f"${data['total_amount']:.0f}",
                "value": data['total_amount']
            })
        return {"nodes": nodes, "edges": edges}


