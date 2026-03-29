import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from backend import services

# Test normalization and cost lookup
test_models = [
    "google/nano-banana-2",
    "nano-banana-2",
    "google/nano-banana-pro",
    "nano-banana-pro",
    "google/nano-banana",
    "nano-banana"
]

print("--- Testing Model Costs ---")
for m in test_models:
    norm = services.normalize_model_id(m)
    cost = services.get_model_cost(m)
    print(f"Input: {m:25} | Normalized: {norm:20} | Cost: {cost}")

print("\n--- Testing Environment Loading ---")
print(f"AVAILABLE_MODELS from env/fallback: {os.getenv('AVAILABLE_MODELS')[:50]}...")
