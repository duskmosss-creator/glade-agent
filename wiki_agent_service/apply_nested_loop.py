"""
Script to cleanly replace get_agent_response function with nested loop version
"""

# Read the old file
with open('wiki_agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find where get_agent_response starts and ends
start_line = None
end_line = None

for i, line in enumerate(lines):
    if line.strip().startswith('def get_agent_response('):
        start_line = i
    if start_line is not None and line.strip() == 'return final_answer':
        end_line = i + 1  # Include the return line
        break

if start_line is None or end_line is None:
    print(f"ERROR: Could not find function boundaries")
    print(f"Start: {start_line}, End: {end_line}")
    exit(1)

print(f"Found get_agent_response from line {start_line+1} to {end_line}")

# Read the new implementation
with open('C:/wikipedia/off-grid-agent/wiki_nested_implementation.py', 'r', encoding='utf-8') as f:
    new_impl = f.read()

# Extract just the function (skip the module docstring at top)
new_lines = new_impl.split('\n')
func_start = None
for i, line in enumerate(new_lines):
    if line.strip().startswith('def get_agent_response('):
        func_start = i
        break

if func_start is None:
    print("ERROR: Could not find function in new implementation")
    exit(1)

new_function = '\n'.join(new_lines[func_start:]) + '\n'

# Replace the old function with the new one
output_lines = lines[:start_line] + [new_function] + lines[end_line:]

# Write the result
with open('wiki_agent.py', 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print(f"✓ Replaced lines {start_line+1}-{end_line} with nested loop implementation")
print(f"✓ New file has {len(output_lines)} lines")
