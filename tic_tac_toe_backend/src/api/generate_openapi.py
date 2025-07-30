import json
import os

from src.api.main import app

# Get the OpenAPI schema
openapi_schema = app.openapi()

# Write to file
output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'interfaces')
output_dir = os.path.abspath(output_dir)
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "openapi.json")

with open(output_path, "w") as f:
    json.dump(openapi_schema, f, indent=2)
