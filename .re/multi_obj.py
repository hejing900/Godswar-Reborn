import re, pathlib
text = pathlib.Path("src/Godswar.Server/Domain/World/Content/StarterQuestObjectives.cs").read_text(encoding="utf-8", errors="replace")
entries = re.findall(r"\[(\d+)u\]\s*=\s*\[(.*?)\]\s*,", text, re.S)
multi = []
for qid, body in entries:
    n = body.count("new QuestObjective(")
    if n > 1:
        multi.append((int(qid), n))
total = len(entries)
print(f"整条链里共 {total} 个有击杀目标的任务；其中多目标 {len(multi)} 个：")
for qid, n in sorted(multi):
    print(f"  任务 {qid}: {n} 个目标")
