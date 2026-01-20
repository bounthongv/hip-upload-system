"""
Binary String Extractor
Searches for readable strings in binary files to find protocol hints.
"""
import sys
import re

def extract_strings(filename, min_len=4):
    try:
        with open(filename, 'rb') as f:
            data = f.read()
            
        # Find ASCII strings
        # Regex: 4 or more printable characters
        pattern = b'[ -~]{' + str(min_len).encode() + b',}'
        matches = re.findall(pattern, data)
        
        print(f"Strings found in {filename}:")
        print("-" * 40)
        
        keywords = ['connect', 'server', 'handshake', 'welcome', 'push', 'realtime', 'cmd', 'ack', 'nack']
        
        found_keywords = []
        
        for m in matches:
            try:
                s = m.decode('utf-8')
                # Filter for interesting strings
                if any(k in s.lower() for k in keywords):
                    print(f"  {s}")
                    found_keywords.append(s)
            except:
                pass
                
        print("-" * 40)
        print(f"Total strings: {len(matches)}")
        print(f"Keyword matches: {len(found_keywords)}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract_strings(sys.argv[1])
    else:
        print("Usage: python extract_strings.py <file>")
