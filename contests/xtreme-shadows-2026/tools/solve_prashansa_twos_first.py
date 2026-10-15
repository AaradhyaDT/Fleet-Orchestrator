import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    t = int(input_data[0])
    idx = 1
    out = []
    for _ in range(t):
        n = int(input_data[idx])
        k = int(input_data[idx + 1])
        x = int(input_data[idx + 2])
        idx += 3
        
        if x != 1:
            out.append("YES")
            out.append(str(n))
            out.append("".join("1 " for _ in range(n)))
        elif n % 2 == 0 and k >= 2:
            out.append("YES")
            out.append(str(n // 2))
            out.append("".join("2 " for _ in range(n // 2)))
        elif n % 2 == 1 and k >= 3 and n >= 3:
            out.append("YES")
            out.append(str(n // 2))
            # Put 2s first, then 3 at the end!
            res = "".join("2 " for _ in range(n // 2 - 1)) + "3 "
            out.append(res)
        else:
            out.append("NO")
            
    print("\n".join(out))

if __name__ == '__main__':
    solve()
