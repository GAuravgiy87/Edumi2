import sys

def check_js_braces(js_code):
    stack = []
    in_string = False
    string_char = ''
    in_regex = False
    in_line_comment = False
    in_block_comment = False
    escape = False

    for i, char in enumerate(js_code):
        if in_line_comment:
            if char == '\n':
                in_line_comment = False
            continue
            
        if in_block_comment:
            if char == '*' and i + 1 < len(js_code) and js_code[i+1] == '/':
                in_block_comment = False
            continue
            
        if escape:
            escape = False
            continue
            
        if char == '\\':
            escape = True
            continue
            
        if in_string:
            if char == string_char:
                in_string = False
            continue
            
        # In actual code
        if char in ['\"', '\'', '\`']:
            in_string = True
            string_char = char
            continue
            
        if char == '/' and i + 1 < len(js_code):
            next_char = js_code[i+1]
            if next_char == '/':
                in_line_comment = True
                continue
            elif next_char == '*':
                in_block_comment = True
                continue
                
        if char == '{':
            stack.append(i)
        elif char == '}':
            if not stack:
                # Calculate line number
                lines = js_code[:i].split('\n')
                print(f'Unexpected }} at line {len(lines)}')
                return False
            stack.pop()
            
    if stack:
        lines = js_code[:stack[-1]].split('\n')
        print(f'Missing closing }} for brace at line {len(lines)}')
        return False
        
    print('All braces match perfectly!')
    return True

with open('test_script.js', 'r', encoding='utf-8') as f:
    js = f.read()

check_js_braces(js)
