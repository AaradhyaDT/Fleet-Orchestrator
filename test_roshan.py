import sys

def main():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    
    t = int(input_data[0])
    idx = 1
    out = []
    
    for _ in range(t):
        n = int(input_data[idx])
        c = input_data[idx + 1]
        s = input_data[idx + 2]
        idx += 3
        
        all_c = True
        for ch in s:
            if ch != c:
                all_c = False
                break
        
        if all_c:
            out.append("0")
            continue
        
        found = False
        for x in range(1, n + 1):
            ok = True
            for mult in range(x, n + 1, x):
                if s[mult - 1] != c:
                    ok = False
                    break
            if ok:
                out.append("1")
                out.append(str(x))
                found = True
                break
        
        if not found:
            out.append("2")
            out.append(f"{n - 1} {n}")
            
    print("\n".join(out))

if __name__ == '__main__':
    main()
