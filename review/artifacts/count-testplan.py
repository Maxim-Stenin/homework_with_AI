import re, sys, io, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
p = r"C:\Users\msten\Downloads\TestTask review new session\qa\test-plan.md"
txt = open(p, encoding="utf-8").read()
rows = re.findall(r"^\|\s*(TC-\d+)\s*\|\s*([ПНГ])\s*\|(.*)$", txt, re.M)
print("строк TC:", len(rows))
ids = [r[0] for r in rows]
print("уникальных ID:", len(set(ids)))
dup = [i for i, c in collections.Counter(ids).items() if c > 1]
print("дубликаты:", dup)
nums = sorted(int(i.split("-")[1]) for i in set(ids))
print("диапазон:", nums[0], "..", nums[-1])
print("пропуски:", [n for n in range(nums[0], nums[-1] + 1) if n not in set(nums)])
types = collections.Counter(r[1] for r in rows)
print("типы:", dict(types))
neg = types["Н"] + types["Г"]
print(f"Н+Г = {neg} из {len(rows)} = {neg/len(rows)*100:.1f}%")
st = collections.Counter()
for _, _, rest in rows:
    for mark in ("✅", "❌", "⚠️", "⛔"):
        if mark in rest:
            st[mark] += 1
            break
    else:
        st["?"] += 1
print("статусы:", dict(st))
