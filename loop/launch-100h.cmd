@echo off
rem 🦋 X.O.L.A. Long Horizon 100-Hour Runner (10 chained 10-hour segments)
rem Each segment resumes the same mission; logs append, so a crash never
rem loses prior segments. Kill with Ctrl+C — progress stays in the logs.
setlocal enabledelayedexpansion
set PYTHONUTF8=1
set PYTHONPATH=D:\alox\LongHorizon-Harness\src
cd /d D:\alox

for /L %%i in (1,1,10) do (
  echo === 100H SEGMENT %%i/10 START %date% %time% === >> D:\alox\xola\loop\lh-100h.log
  python -m lh_harness run --task "Segment %%i of 10 of a 100-hour run. Read D:\alox\xola\loop\mission.md and execute it end to end. Per mission: analyse hermes, agy, opencode, deepseek-harness (reports to D:\alox\xola\reports\), create new agents in D:\alox\xola\agents\, loop every later round through scout/guard/memory, verify everything with real tool output, never stop early. Review D:\alox\xola\memory\ and D:\alox\xola\loop\lh-100h.log first and resume from the latest state instead of restarting." --manager-agent opencode --manager-model opencode/deepseek-v4-flash-free --executor-agent agy --executor-model gemini-3.7-flash-high --auditor-agent opencode --auditor-model opencode/deepseek-v4-flash-free --max-rounds 200 --cli-executor-timeout 1800 --workspace D:\alox >> D:\alox\xola\loop\lh-100h.log 2>> D:\alox\xola\loop\lh-100h.err.log
  echo === 100H SEGMENT %%i/10 DONE %date% %time% === >> D:\alox\xola\loop\lh-100h.log
)
echo === 100H RUN COMPLETE %date% %time% === >> D:\alox\xola\loop\lh-100h.log
endlocal
