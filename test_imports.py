import sys
import os
import traceback

# Add backend to path specifically
current_dir = os.getcwd()
backend_dir = os.path.join(current_dir, 'backend')
sys.path.append(backend_dir)

print(f"Testing imports from {backend_dir}")

try:
    print("Attempting to import engine...")
    import backend.engine as engine
    print("SUCCESS: backend.engine imported")
except Exception as e:
    print(f"FAILURE: backend.engine failed: {e}")
    traceback.print_exc()

try:
    print("Attempting to import main...")
    import backend.main as main
    print("SUCCESS: backend.main imported")
except Exception as e:
    print(f"FAILURE: backend.main failed: {e}")
    traceback.print_exc()
