@echo off
rem 🦋 X.O.L.A. Long Horizon 10-Hour Runner
set PYTHONUTF8=1
set PYTHONPATH=D:\alox\LongHorizon-Harness\src
cd /d D:\alox
python -m lh_harness run --task "Read D:\alox\xola\loop\mission.md and execute it end to end. 10-hour budget. Per mission: analyse hermes, agy, opencode, deepseek-harness (reports to D:\alox\xola\reports\), create new agents in D:\alox\xola\agents\, loop every later round through scout/guard/memory, verify everything with real tool output, never stop early." --manager-agent opencode --manager-model opencode/deepseek-v4-flash-free --executor-agent agy --executor-model gemini-3.7-flash-high --auditor-agent opencode --auditor-model opencode/deepseek-v4-flash-free --max-rounds 200 --cli-executor-timeout 1800 --workspace D:\alox >> D:\alox\xola\loop\lh-10h.log 2>> D:\alox\xola\loop\lh-10h.err.log

