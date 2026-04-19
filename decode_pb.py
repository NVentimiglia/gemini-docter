import sys

pb_path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\nvent\.gemini\antigravity\conversations\b10e13d2-043f-4d3a-a9fe-3133cb934a5e.pb"

with open(pb_path, "rb") as f:
    data = f.read()

print(f"File size: {len(data)} bytes")
print(f"First 128 bytes (hex): {data[:128].hex()}")
print(f"First 128 bytes (repr): {repr(data[:128])}")

# Check if it starts with valid protobuf tags
first_byte = data[0]
wire_type = first_byte & 0x7
field_number = first_byte >> 3
print(f"\nFirst tag: field={field_number}, wire_type={wire_type}")

# Try to find text content
import re
text_segments = re.findall(b'[\x20-\x7e]{20,}', data[:5000])
print(f"\nFirst text segments found ({len(text_segments)} in first 5KB):")
for seg in text_segments[:10]:
    print(f"  {seg.decode('ascii', errors='replace')[:200]}")

# look for JSON-like structures
json_starts = [i for i in range(min(5000, len(data))) if data[i:i+1] == b'{']
print(f"\nJSON-like starts in first 5KB: {json_starts[:20]}")
