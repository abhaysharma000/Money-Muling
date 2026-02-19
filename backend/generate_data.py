import csv
import random
import uuid
from datetime import datetime, timedelta
import argparse

def generate_test_csv(filename="transactions.csv", num_transactions=10000, output_file=None):
    print(f"Generating {num_transactions} transactions...")
    accounts = [f"ACC_{i:04d}" for i in range(1, 1001)]
    
    start_time = datetime(2026, 1, 1)
    
    # Use the provided file-like object or open the filename
    if output_file:
        f = output_file
        should_close = False
    else:
        f = open(filename, 'w', newline='')
        should_close = True
        
    try:
        writer = csv.DictWriter(f, fieldnames=['transaction_id', 'sender_id', 'receiver_id', 'amount', 'timestamp'])
        writer.writeheader()
        
        # 1. Generate some random noise
        for i in range(num_transactions - 200):
            tx_id = f"TX_{i:06d}"
            sender = random.choice(accounts)
            receiver = random.choice(accounts)
            while receiver == sender:
                receiver = random.choice(accounts)
                
            amount = round(random.uniform(10, 5000), 2)
            timestamp = start_time + timedelta(seconds=random.randint(0, 30*24*3600))
            
            writer.writerow({
                "transaction_id": tx_id,
                "sender_id": sender,
                "receiver_id": receiver,
                "amount": amount,
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S")
            })

        # 2. Inject Cycles (length 3 and 4)
        for r in range(5):
            nodes = [f"CYC_{r}_{i}" for i in range(4)]
            for i in range(len(nodes)):
                next_node = nodes[(i + 1) % len(nodes)]
                writer.writerow({
                    "transaction_id": f"TX_CYC_{r}_{i}",
                    "sender_id": nodes[i],
                    "receiver_id": next_node,
                    "amount": 1000,
                    "timestamp": (start_time + timedelta(days=r, hours=i)).strftime("%Y-%m-%d %H:%M:%S")
                })

        # 3. Inject Fan-in (Aggregation)
        target_sink = "SINK_MEGA_01"
        for i in range(50):
            writer.writerow({
                "transaction_id": f"TX_FAN_IN_{i}",
                "sender_id": f"SRCE_{i:03d}",
                "receiver_id": target_sink,
                "amount": 500,
                "timestamp": (start_time + timedelta(days=10, hours=i)).strftime("%Y-%m-%d %H:%M:%S")
            })

        # 4. Inject High Velocity Burst
        burst_acc = "BURST_NODE_X"
        for i in range(50):
            writer.writerow({
                "transaction_id": f"TX_BURST_{i}",
                "sender_id": burst_acc,
                "receiver_id": random.choice(accounts),
                "amount": 50,
                "timestamp": (start_time + timedelta(days=15, minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
            })

    finally:
        if should_close:
            f.close()

    print(f"Successfully generated {num_transactions} transactions")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transactions", type=int, default=10000)
    parser.add_argument("--output", type=str, default="transactions.csv")
    args = parser.parse_args()
    generate_test_csv(args.output, args.transactions)
