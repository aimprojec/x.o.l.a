#!/usr/bin/env python3
"""Usage: python skills.py [--list] [--info NAME] [--run NAME] [--args JSON] [--validate] [--json] # xola-skills: dynamic skills registry and execution engine 🦋"""

import argparse
import ast
import datetime
import enum
import json
import logging
import os
import platform
import re
import shutil
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
VERSION = "1.0.0"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# ANSI color codes for rich CLI terminal rendering
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


# =====================================================================
# 1) Security Permission Tiers
# =====================================================================

class Tier(str, enum.Enum):
    """3-Tier Security Classification for Tool and Skill Permissions."""
    GREEN = "GREEN"    # Auto-execute silently: Read-only safe actions, telemetry, diagnostics
    YELLOW = "YELLOW"  # Auto-execute & write audit log: State mutations, note writing, file patching
    RED = "RED"        # Intercept & require operator approval: Destructive OS actions, deletions, process termination

    def __str__(self) -> str:
        return self.value


# =====================================================================
# 2) Skill Dataclass
# =====================================================================

@dataclass
class Skill:
    """Dynamic Skill specification with keyword matching, security tier, and execution handler."""
    name: str
    tier: Tier = Tier.GREEN
    keywords: List[str] = field(default_factory=list)
    description: str = ""
    handler: Optional[Callable[..., Any]] = None
    category: str = "General"
    prefix_match: bool = False
    args_schema: Dict[str, Any] = field(default_factory=dict)
    mark: str = WATERMARK

    def __post_init__(self):
        # Normalize tier to Tier enum if passed as string
        if isinstance(self.tier, str) and not isinstance(self.tier, Tier):
            try:
                self.tier = Tier(self.tier.upper())
            except ValueError:
                self.tier = Tier.GREEN
        # Ensure keywords are list of strings
        if self.keywords is None:
            self.keywords = []
        self.keywords = [str(k).lower().strip() for k in self.keywords if str(k).strip()]

    def matches(self, user_input: str) -> bool:
        """Check if user query matches this skill's keywords or prefix."""
        if not user_input:
            return False
        cleaned = str(user_input).lower().strip()
        name_lower = self.name.lower()
        if self.prefix_match:
            if cleaned == name_lower or cleaned.startswith(name_lower + " ") or cleaned.startswith(name_lower + "_"):
                return True
            return any(cleaned.startswith(k) for k in self.keywords)
        else:
            if cleaned == name_lower or name_lower in cleaned:
                return True
            return any(k in cleaned for k in self.keywords)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize skill metadata to dictionary (excluding callable handler)."""
        return {
            "name": self.name,
            "tier": self.tier.value if isinstance(self.tier, Tier) else str(self.tier),
            "keywords": self.keywords,
            "description": self.description,
            "category": self.category,
            "prefix_match": self.prefix_match,
            "has_handler": self.handler is not None,
            "args_schema": self.args_schema or {},
            "mark": self.mark,
        }


# =====================================================================
# 3) Skill Registry & Execution Engine
# =====================================================================

class SkillRegistry:
    """Dynamic Extensible Skills Registry with Guardrail Tier Gating and Audit Logging."""

    def __init__(self, name: str = "default", audit_log_path: Optional[str] = None):
        self.name = name
        self._skills: Dict[str, Skill] = {}
        self.audit_log_path = audit_log_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "loop", "skills_audit.log"
        )
        self._logger: Optional[logging.Logger] = None

    @property
    def logger(self) -> logging.Logger:
        """Lazy initialized audit logger."""
        if self._logger is None:
            logger_name = f"xola.skills.{self.name}"
            log = logging.getLogger(logger_name)
            log.setLevel(logging.INFO)
            if not log.handlers and self.audit_log_path:
                try:
                    os.makedirs(os.path.dirname(os.path.abspath(self.audit_log_path)), exist_ok=True)
                    handler = logging.FileHandler(self.audit_log_path, encoding="utf-8")
                    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [TIER-%(message)s]")
                    handler.setFormatter(formatter)
                    log.addHandler(handler)
                except Exception:
                    pass
            self._logger = log
        return self._logger

    def register(self, skill: Skill) -> Skill:
        """Register a new Skill instance into the registry."""
        if not isinstance(skill, Skill):
            raise TypeError(f"Expected Skill instance, got {type(skill).__name__}")
        if not skill.name or not skill.name.strip():
            raise ValueError("Skill name cannot be empty")
        self._skills[skill.name] = skill
        return skill

    def unregister(self, name: str) -> bool:
        """Remove a skill from the registry by name."""
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def get(self, name: str) -> Optional[Skill]:
        """Retrieve skill by exact name."""
        return self._skills.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)

    def list_skills(
        self,
        category: Optional[str] = None,
        tier: Optional[Union[Tier, str]] = None,
    ) -> List[Skill]:
        """List registered skills, optionally filtered by category or tier."""
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category.lower() == category.lower()]
        if tier:
            tier_val = tier.value if isinstance(tier, Tier) else str(tier).upper()
            skills = [
                s for s in skills
                if (s.tier.value if isinstance(s.tier, Tier) else str(s.tier).upper()) == tier_val
            ]
        return sorted(skills, key=lambda s: (s.category, s.name))

    def find_matching_skill(self, query: str) -> Optional[Skill]:
        """Find the best matching skill for a user query string.
        
        Resolution Priority:
          1. Exact name match
          2. Prefix-matching skills
          3. Keyword / substring matching skills
        """
        if not query:
            return None
        clean_q = query.strip().lower()

        # 1. Exact name match
        for skill in self._skills.values():
            if skill.name.lower() == clean_q:
                return skill

        # 2. Prefix-matching skills (higher priority for prompt routing)
        for skill in self._skills.values():
            if skill.prefix_match and skill.matches(query):
                return skill

        # 3. Substring / keyword matches
        for skill in self._skills.values():
            if not skill.prefix_match and skill.matches(query):
                return skill

        return None

    def find_all_matching_skills(self, query: str) -> List[Skill]:
        """Find all skills matching query keywords."""
        if not query:
            return []
        matches = []
        for skill in self._skills.values():
            if skill.matches(query):
                matches.append(skill)
        return matches

    def execute(
        self,
        name_or_query: str,
        args: Optional[Dict[str, Any]] = None,
        auto_approve_red: bool = False,
        audit_log_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch and execute a skill with 3-tier security gating and audit logging."""
        t0 = time.perf_counter()
        tool_args = args if isinstance(args, dict) else {}

        # Resolve skill
        skill = self.get(name_or_query)
        if skill is None:
            skill = self.find_matching_skill(name_or_query)

        if skill is None:
            return {
                "skill": name_or_query,
                "status": "ERROR",
                "tier": "UNKNOWN",
                "error": f"Skill '{name_or_query}' not found in registry",
                "latency_s": round(time.perf_counter() - t0, 4),
                "timestamp": datetime.datetime.now().isoformat(),
                "mark": WATERMARK,
            }

        if skill.handler is None or not callable(skill.handler):
            return {
                "skill": skill.name,
                "status": "ERROR",
                "tier": skill.tier.value if isinstance(skill.tier, Tier) else str(skill.tier),
                "error": f"Skill '{skill.name}' does not have a callable execution handler",
                "latency_s": round(time.perf_counter() - t0, 4),
                "timestamp": datetime.datetime.now().isoformat(),
                "mark": WATERMARK,
            }

        tier_enum = skill.tier if isinstance(skill.tier, Tier) else Tier(str(skill.tier).upper())
        tier_str = tier_enum.value

        # --- Tier GREEN: Auto-execute silently ---
        if tier_enum == Tier.GREEN:
            try:
                if tool_args:
                    output = skill.handler(**tool_args)
                else:
                    try:
                        output = skill.handler()
                    except TypeError:
                        output = skill.handler(**tool_args)
                latency = round(time.perf_counter() - t0, 4)
                return {
                    "skill": skill.name,
                    "status": "SUCCESS",
                    "tier": tier_str,
                    "output": output,
                    "latency_s": latency,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "mark": WATERMARK,
                }
            except Exception as exc:
                latency = round(time.perf_counter() - t0, 4)
                return {
                    "skill": skill.name,
                    "status": "ERROR",
                    "tier": tier_str,
                    "error": str(exc),
                    "latency_s": latency,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "mark": WATERMARK,
                }

        # --- Tier YELLOW: Auto-execute & write audit log ---
        elif tier_enum == Tier.YELLOW:
            try:
                if tool_args:
                    output = skill.handler(**tool_args)
                else:
                    try:
                        output = skill.handler()
                    except TypeError:
                        output = skill.handler(**tool_args)
                latency = round(time.perf_counter() - t0, 4)
                try:
                    self.logger.info(f"YELLOW] Executed '{skill.name}'. Args: {tool_args} | Latency: {latency}s")
                except Exception:
                    pass
                return {
                    "skill": skill.name,
                    "status": "SUCCESS",
                    "tier": tier_str,
                    "output": output,
                    "latency_s": latency,
                    "audited": True,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "mark": WATERMARK,
                }
            except Exception as exc:
                latency = round(time.perf_counter() - t0, 4)
                try:
                    self.logger.error(f"YELLOW] Failed '{skill.name}'. Args: {tool_args} | Error: {exc}")
                except Exception:
                    pass
                return {
                    "skill": skill.name,
                    "status": "ERROR",
                    "tier": tier_str,
                    "error": str(exc),
                    "latency_s": latency,
                    "audited": True,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "mark": WATERMARK,
                }

        # --- Tier RED: Security gate interception ---
        elif tier_enum == Tier.RED:
            approved = False
            if auto_approve_red:
                approved = True
            elif sys.stdin.isatty():
                # Interactive terminal confirmation prompt
                print(f"\n{COLOR_RED}[SECURITY GUARDRAIL - RED TIER INTERCEPT]{COLOR_RESET} 🦋")
                print(f"Autonomous agent requested critical skill: {COLOR_BOLD}'{skill.name}'{COLOR_RESET}")
                print(f"Arguments : {tool_args}")
                print(f"Description: {skill.description}")
                try:
                    choice = input(f"{COLOR_YELLOW}Approve execution of '{skill.name}'? (y/N): {COLOR_RESET}").strip().lower()
                    approved = choice in ("y", "yes")
                except (EOFError, KeyboardInterrupt):
                    approved = False
            else:
                # Non-interactive headless execution without explicit auto_approve_red flag
                from tools.runtime.approvals import authorize_tool
                blocked = authorize_tool("skill." + skill.name, tool_args, high_stakes=True)
                if blocked:
                    return dict(blocked, skill=skill.name, tier=tier_str, mark=WATERMARK)
                approved = True

            if not approved:
                latency = round(time.perf_counter() - t0, 4)
                try:
                    self.logger.warning(f"RED] Execution of '{skill.name}' DENIED by security policy. Args: {tool_args}")
                except Exception:
                    pass
                return {
                    "skill": skill.name,
                    "status": "DENIED",
                    "tier": tier_str,
                    "error": f"Security Guardrail intercepted RED tier skill '{skill.name}'. Execution DENIED.",
                    "latency_s": latency,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "mark": WATERMARK,
                }

            # Authorized execution
            try:
                if tool_args:
                    output = skill.handler(**tool_args)
                else:
                    try:
                        output = skill.handler()
                    except TypeError:
                        output = skill.handler(**tool_args)
                latency = round(time.perf_counter() - t0, 4)
                try:
                    self.logger.warning(f"RED] Authorized execution of '{skill.name}'. Args: {tool_args} | Latency: {latency}s")
                except Exception:
                    pass
                return {
                    "skill": skill.name,
                    "status": "SUCCESS",
                    "tier": tier_str,
                    "output": output,
                    "latency_s": latency,
                    "authorized": True,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "mark": WATERMARK,
                }
            except Exception as exc:
                latency = round(time.perf_counter() - t0, 4)
                try:
                    self.logger.error(f"RED] Authorized '{skill.name}' failed. Args: {tool_args} | Error: {exc}")
                except Exception:
                    pass
                return {
                    "skill": skill.name,
                    "status": "ERROR",
                    "tier": tier_str,
                    "error": str(exc),
                    "latency_s": latency,
                    "authorized": True,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "mark": WATERMARK,
                }

        # Fallthrough safety
        return {
            "skill": skill.name,
            "status": "ERROR",
            "tier": tier_str,
            "error": f"Unknown tier {tier_str}",
            "latency_s": round(time.perf_counter() - t0, 4),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }

    def validate_skills(self) -> Dict[str, Any]:
        """Validate integrity, handler signatures, tier consistency, and schemas of all skills."""
        results = []
        passed_count = 0
        failed_count = 0

        for skill in self._skills.values():
            errors = []
            if not skill.name or not isinstance(skill.name, str):
                errors.append("Invalid or empty skill name")
            if not isinstance(skill.tier, Tier):
                errors.append(f"Invalid tier: {skill.tier}")
            if skill.handler is None or not callable(skill.handler):
                errors.append("Missing callable handler")
            if not skill.description:
                errors.append("Missing description docstring")
            if not skill.keywords:
                errors.append("Missing keyword triggers")

            passed = len(errors) == 0
            if passed:
                passed_count += 1
            else:
                failed_count += 1

            results.append({
                "skill": skill.name,
                "tier": skill.tier.value if isinstance(skill.tier, Tier) else str(skill.tier),
                "category": skill.category,
                "passed": passed,
                "errors": errors,
            })

        all_passed = (failed_count == 0) and (len(self._skills) > 0)
        return {
            "total": len(self._skills),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "all_passed": all_passed,
            "skills": results,
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }

    def clear(self) -> None:
        """Clear all registered skills (useful for isolated unit testing)."""
        self._skills.clear()


# Global Singleton Skills Registry
GLOBAL_REGISTRY = SkillRegistry(name="global")


# =====================================================================
# 4) Decorator for Dynamic Registration
# =====================================================================

def register_skill(
    name: str,
    tier: Tier = Tier.GREEN,
    keywords: Optional[List[str]] = None,
    description: str = "",
    category: str = "General",
    prefix_match: bool = False,
    args_schema: Optional[Dict[str, Any]] = None,
    registry: Optional[SkillRegistry] = None,
):
    """Decorator to register an extensible skill into the skills registry 🦋."""
    if keywords is None:
        keywords = []

    def decorator(func: Callable[..., Any]):
        doc = description or (func.__doc__ or "").strip().split("\n")[0]
        skill = Skill(
            name=name,
            tier=tier,
            keywords=keywords,
            description=doc,
            handler=func,
            category=category,
            prefix_match=prefix_match,
            args_schema=args_schema or {},
        )
        target_registry = registry if registry is not None else GLOBAL_REGISTRY
        target_registry.register(skill)
        return func

    return decorator


# =====================================================================
# 5) Built-in Core Skills (Target 4 Architecture)
# =====================================================================

@register_skill(
    name="sys_info",
    tier=Tier.GREEN,
    keywords=["sys_info", "system_info", "sysinfo", "specs", "os_info", "diagnostics", "host_metrics"],
    description="System diagnostic telemetry (OS, CPU cores, RAM/disk C: and D: usage, Python runtime, timestamps)",
    category="Diagnostics",
    args_schema={"drive": "Optional drive letter to inspect (e.g. 'C:', 'D:')"},
)
def skill_sys_info(drive: Optional[str] = None) -> Dict[str, Any]:
    """Execute host system information diagnostics 🦋."""
    drives_info = {}
    target_drives = [drive] if drive else (["C:\\", "D:\\"] if sys.platform == "win32" else ["/"])

    for d in target_drives:
        try:
            total, used, free = shutil.disk_usage(d)
            drives_info[d] = {
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb": round(used / (1024 ** 3), 2),
                "free_gb": round(free / (1024 ** 3), 2),
                "percent_used": round((used / total) * 100.0, 1) if total > 0 else 0.0,
            }
        except Exception:
            pass

    return {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "cpu_count": os.cpu_count() or 1,
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "disk": drives_info,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "timestamp_local": datetime.datetime.now().isoformat(),
        "mark": WATERMARK,
    }


@register_skill(
    name="file_patch",
    tier=Tier.YELLOW,
    keywords=["file_patch", "patch_file", "apply_patch", "edit_file", "replace_content", "patch"],
    description="Safe structured file patcher, line replacer, and file mutator with backup support",
    category="Filesystem",
    args_schema={
        "path": "Target file path to modify (required)",
        "target_content": "Exact substring to find and replace (for mode='replace')",
        "replacement_content": "Replacement text to substitute",
        "content": "Content string for mode='overwrite', 'append', or 'prepend'",
        "mode": "Operation mode: 'replace', 'overwrite', 'append', 'prepend' (default: 'replace')",
        "create_backup": "Boolean to create .bak copy before modifying (default: False)",
    },
)
def skill_file_patch(
    path: str,
    target_content: Optional[str] = None,
    replacement_content: Optional[str] = None,
    content: Optional[str] = None,
    mode: str = "replace",
    create_backup: bool = False,
) -> Dict[str, Any]:
    """Apply safe structured mutations and replacements to a target file 🦋."""
    if not path:
        raise ValueError("Parameter 'path' is required for file_patch")

    abs_path = os.path.abspath(path)
    file_exists = os.path.exists(abs_path)

    if mode in ("replace", "append", "prepend") and not file_exists:
        raise FileNotFoundError(f"File not found: {abs_path}")

    existing_content = ""
    if file_exists:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            existing_content = f.read()

        if create_backup:
            backup_path = f"{abs_path}.bak"
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(existing_content)

    new_content = existing_content
    changes_count = 0

    mode_clean = mode.lower().strip()
    if mode_clean == "replace":
        if target_content is None or replacement_content is None:
            raise ValueError("Parameters 'target_content' and 'replacement_content' required for mode='replace'")
        if target_content not in existing_content:
            return {
                "status": "NO_MATCH",
                "path": abs_path,
                "changes_count": 0,
                "message": f"Target content substring was not found in {os.path.basename(abs_path)}",
                "mark": WATERMARK,
            }
        changes_count = existing_content.count(target_content)
        new_content = existing_content.replace(target_content, replacement_content)

    elif mode_clean == "overwrite":
        if content is None:
            raise ValueError("Parameter 'content' is required for mode='overwrite'")
        new_content = content
        changes_count = 1

    elif mode_clean == "append":
        if content is None:
            raise ValueError("Parameter 'content' is required for mode='append'")
        new_content = existing_content + ("\n" if existing_content and not existing_content.endswith("\n") else "") + content
        changes_count = 1

    elif mode_clean == "prepend":
        if content is None:
            raise ValueError("Parameter 'content' is required for mode='prepend'")
        new_content = content + ("\n" if not content.endswith("\n") else "") + existing_content
        changes_count = 1

    else:
        raise ValueError(f"Unsupported file_patch mode '{mode}'. Use 'replace', 'overwrite', 'append', or 'prepend'.")

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return {
        "status": "SUCCESS",
        "path": abs_path,
        "mode": mode_clean,
        "changes_count": changes_count,
        "bytes_written": len(new_content.encode("utf-8")),
        "lines_count": len(new_content.splitlines()),
        "mark": WATERMARK,
    }


@register_skill(
    name="code_ast_metrics",
    tier=Tier.GREEN,
    keywords=["code_ast_metrics", "ast_metrics", "ast_analyze", "code_metrics", "python_metrics", "ast"],
    description="Python AST static analyzer extracting functions, classes, imports, LOC, and syntax validity",
    category="CodeAnalysis",
    args_schema={
        "path": "Target Python source file path to analyze",
        "code": "Direct Python code string to parse (if path not provided)",
    },
)
def skill_code_ast_metrics(
    path: Optional[str] = None,
    code: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze Python code or file using standard library ast parser 🦋."""
    if not path and not code:
        raise ValueError("Either 'path' or 'code' parameter must be provided")

    source_code = code or ""
    source_name = "<string>"

    if path:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"File not found: {abs_path}")
        source_name = abs_path
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            source_code = f.read()

    lines = source_code.splitlines()
    loc = len(lines)
    comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
    blank_lines = sum(1 for line in lines if not line.strip())
    code_lines = loc - comment_lines - blank_lines

    try:
        tree = ast.parse(source_code, filename=source_name)
    except SyntaxError as syn_err:
        return {
            "source": source_name,
            "valid_syntax": False,
            "syntax_error": {
                "msg": syn_err.msg,
                "line": syn_err.lineno,
                "offset": syn_err.offset,
                "text": (syn_err.text or "").strip(),
            },
            "loc": loc,
            "mark": WATERMARK,
        }

    functions = []
    classes = []
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_async = isinstance(node, ast.AsyncFunctionDef)
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "args_count": len(node.args.args),
                "is_async": is_async,
                "has_docstring": ast.get_docstring(node) is not None,
            })
        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "bases_count": len(node.bases),
                "has_docstring": ast.get_docstring(node) is not None,
            })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    return {
        "source": source_name,
        "valid_syntax": True,
        "loc": loc,
        "code_lines": code_lines,
        "comment_lines": comment_lines,
        "blank_lines": blank_lines,
        "functions_count": len(functions),
        "classes_count": len(classes),
        "imports_count": len(imports),
        "functions": functions,
        "classes": classes,
        "imports": sorted(list(set(imports))),
        "module_docstring": ast.get_docstring(tree) is not None,
        "mark": WATERMARK,
    }


@register_skill(
    name="http_probe",
    tier=Tier.GREEN,
    keywords=["http_probe", "curl", "url_probe", "http_get", "fetch_url", "ping_url", "http"],
    description="Zero-dependency HTTP GET/HEAD URL prober and latency inspector using stdlib urllib",
    category="Network",
    args_schema={
        "url": "Target URL to probe (required)",
        "method": "HTTP method: GET or HEAD (default: 'GET')",
        "timeout": "Timeout in seconds (default: 10.0)",
        "headers": "Optional dictionary of custom request headers",
        "max_body_bytes": "Maximum response body bytes to capture (default: 2048)",
    },
)
def skill_http_probe(
    url: str,
    method: str = "GET",
    timeout: float = 10.0,
    headers: Optional[Dict[str, str]] = None,
    max_body_bytes: int = 2048,
) -> Dict[str, Any]:
    """Probe an HTTP/HTTPS endpoint and inspect headers, status, and latency 🦋."""
    if not url:
        raise ValueError("Parameter 'url' is required for http_probe")

    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"http://{clean_url}"

    req_headers = {
        "User-Agent": f"Xola-Skills-Prober/{VERSION} (Pure Stdlib; +https://github.com/alox/xola)",
    }
    if headers and isinstance(headers, dict):
        req_headers.update(headers)

    t0 = time.perf_counter()
    method_upper = method.upper().strip()

    try:
        req = urllib.request.Request(clean_url, headers=req_headers, method=method_upper)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.status
            reason = resp.reason
            raw_body = resp.read(max_body_bytes)
            latency = round(time.perf_counter() - t0, 4)

            resp_headers = dict(resp.headers.items())
            body_snippet = raw_body.decode("utf-8", errors="replace")

            return {
                "status": "UP",
                "http_status": status_code,
                "reason": reason,
                "url": clean_url,
                "method": method_upper,
                "latency_s": latency,
                "headers": resp_headers,
                "body_snippet": body_snippet[:500],
                "content_length": len(raw_body),
                "mark": WATERMARK,
            }
    except urllib.error.HTTPError as http_err:
        latency = round(time.perf_counter() - t0, 4)
        return {
            "status": "HTTP_ERROR",
            "http_status": http_err.code,
            "reason": http_err.reason,
            "url": clean_url,
            "latency_s": latency,
            "error": str(http_err),
            "mark": WATERMARK,
        }
    except urllib.error.URLError as url_err:
        latency = round(time.perf_counter() - t0, 4)
        return {
            "status": "DOWN",
            "url": clean_url,
            "latency_s": latency,
            "error": str(url_err.reason),
            "mark": WATERMARK,
        }
    except Exception as exc:
        latency = round(time.perf_counter() - t0, 4)
        return {
            "status": "ERROR",
            "url": clean_url,
            "latency_s": latency,
            "error": str(exc),
            "mark": WATERMARK,
        }


@register_skill(
    name="text_format",
    tier=Tier.GREEN,
    keywords=["text_format", "format_text", "slugify", "prettify", "wrap_text", "json_format", "table"],
    description="Text transformation utilities (wrap, slugify, truncate, json_pretty, markdown_table)",
    category="Utilities",
    args_schema={
        "text": "Input text or JSON string to format (required)",
        "action": "Transformation action: 'wrap', 'slugify', 'truncate', 'json_pretty', 'table', 'upper', 'lower' (default: 'wrap')",
        "width": "Maximum line width for wrap action (default: 80)",
        "max_len": "Maximum length for truncate action (default: 100)",
        "indent": "Indentation spaces for json_pretty (default: 2)",
    },
)
def skill_text_format(
    text: str,
    action: str = "wrap",
    width: int = 80,
    max_len: int = 100,
    indent: int = 2,
) -> Dict[str, Any]:
    """Transform and format text strings 🦋."""
    if text is None:
        raise ValueError("Parameter 'text' is required for text_format")

    action_clean = action.lower().strip()
    result_text = ""

    if action_clean == "wrap":
        result_text = textwrap.fill(text, width=width)

    elif action_clean == "slugify":
        clean = re.sub(r"[^\w\s-]", "", text).strip().lower()
        result_text = re.sub(r"[-\s]+", "-", clean)

    elif action_clean == "truncate":
        if len(text) <= max_len:
            result_text = text
        else:
            result_text = text[:max_len - 3] + "..."

    elif action_clean == "json_pretty":
        try:
            parsed = json.loads(text) if isinstance(text, str) else text
            result_text = json.dumps(parsed, indent=indent, ensure_ascii=False)
        except Exception as e:
            raise ValueError(f"Failed to parse input as JSON: {e}")

    elif action_clean == "upper":
        result_text = text.upper()

    elif action_clean == "lower":
        result_text = text.lower()

    elif action_clean == "table":
        # Formats list of dicts or CSV lines into markdown table
        try:
            items = json.loads(text) if isinstance(text, str) and text.strip().startswith(("[", "{")) else None
            if isinstance(items, list) and items and isinstance(items[0], dict):
                headers = list(items[0].keys())
                header_line = "| " + " | ".join(headers) + " |"
                sep_line = "| " + " | ".join("---" for _ in headers) + " |"
                data_lines = []
                for item in items:
                    data_lines.append("| " + " | ".join(str(item.get(h, "")) for h in headers) + " |")
                result_text = "\n".join([header_line, sep_line] + data_lines)
            else:
                result_text = text
        except Exception:
            result_text = text

    else:
        raise ValueError(f"Unknown text_format action '{action}'. Supported: wrap, slugify, truncate, json_pretty, table, upper, lower")

    return {
        "action": action_clean,
        "input_len": len(text),
        "output_len": len(result_text),
        "output": result_text,
        "mark": WATERMARK,
    }


# =====================================================================
# 6) Terminal Rendering & Reporting
# =====================================================================

def render_skills_list(skills: List[Skill], registry_name: str = "global") -> str:
    """Render formatted ANSI/plain text list of skills."""
    lines = [
        f"🦋 X.O.L.A. Skills Registry [{registry_name}] — {len(skills)} Registered Skill(s) 🦋",
        "=" * 76,
        f"{'Skill Name':<20} | {'Tier':<8} | {'Category':<14} | {'Description'}",
        "-" * 76,
    ]

    for s in skills:
        tier_val = s.tier.value if isinstance(s.tier, Tier) else str(s.tier)
        tier_tag = f"[{tier_val}]"
        desc_snip = s.description[:30] + "..." if len(s.description) > 30 else s.description
        lines.append(f"{s.name:<20} | {tier_tag:<8} | {s.category:<14} | {desc_snip}")

    lines.append("=" * 76)
    return "\n".join(lines)


def render_skill_info(skill: Skill) -> str:
    """Render detailed information view for a single skill."""
    tier_val = skill.tier.value if isinstance(skill.tier, Tier) else str(skill.tier)
    keywords_str = ", ".join(skill.keywords) if skill.keywords else "(none)"
    schema_str = json.dumps(skill.args_schema, indent=2) if skill.args_schema else "(none)"

    lines = [
        f"🦋 X.O.L.A. Skill Inspector: '{skill.name}' 🦋",
        "=" * 72,
        f"Name         : {skill.name}",
        f"Security Tier: [{tier_val}]",
        f"Category     : {skill.category}",
        f"Prefix Match : {'Enabled' if skill.prefix_match else 'Disabled'}",
        f"Keywords     : {keywords_str}",
        f"Description  : {skill.description}",
        f"Handler      : {'Callable Registered' if skill.handler else 'None'}",
        "-" * 72,
        "Argument Schema:",
        schema_str,
        "=" * 72,
    ]
    return "\n".join(lines)


def render_execution_result(res: Dict[str, Any]) -> str:
    """Render structured terminal report for skill execution result."""
    status = res.get("status", "UNKNOWN")
    skill_name = res.get("skill", "unknown")
    tier = res.get("tier", "UNKNOWN")
    latency = res.get("latency_s", 0.0)

    lines = [
        f"🦋 X.O.L.A. Skill Execution: {skill_name} [{status}] 🦋",
        "=" * 72,
        f"Skill   : {skill_name}",
        f"Status  : {status}",
        f"Tier    : [{tier}]",
        f"Latency : {latency:.4f}s",
    ]

    if "error" in res:
        lines.append(f"Error   : {res['error']}")
    if "output" in res:
        lines.append("-" * 72)
        lines.append("Execution Output:")
        out = res["output"]
        if isinstance(out, (dict, list)):
            lines.append(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            lines.append(str(out))

    lines.append("=" * 72)
    return "\n".join(lines)


def render_validation_report(val: Dict[str, Any]) -> str:
    """Render terminal report for registry validation."""
    total = val.get("total", 0)
    passed = val.get("passed_count", 0)
    failed = val.get("failed_count", 0)
    all_passed = val.get("all_passed", False)
    status_tag = "[ALL PASSED]" if all_passed else "[FAILURES DETECTED]"

    lines = [
        f"🦋 X.O.L.A. Skills Registry Validation {status_tag} 🦋",
        "=" * 72,
        f"Total Skills Checked : {total}",
        f"Passed Integrity     : {passed}",
        f"Failed Checks        : {failed}",
        "-" * 72,
    ]

    for s_info in val.get("skills", []):
        st = "[PASS]" if s_info.get("passed") else "[FAIL]"
        lines.append(f"  • {st} {s_info.get('skill'):<20} | Tier: {s_info.get('tier'):<7} | Cat: {s_info.get('category')}")
        for err in s_info.get("errors", []):
            lines.append(f"      ↳ ERROR: {err}")

    lines.append("=" * 72)
    return "\n".join(lines)


# =====================================================================
# 7) Standalone CLI Entrypoint
# =====================================================================

def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for skills registry tool."""
    parser = argparse.ArgumentParser(
        prog="skills",
        description="xola-skills — Dynamic Skills Registry & Execution Engine 🦋",
        epilog="Usage: python skills.py [--list] [--info NAME] [--run NAME] [--args JSON] [--validate] [--json]",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all registered skills in the registry",
    )
    parser.add_argument(
        "--info", "-i",
        metavar="NAME",
        help="Display detailed metadata and schema for specific skill",
    )
    parser.add_argument(
        "--run", "-r",
        metavar="NAME",
        help="Execute specified skill by name or keyword query",
    )
    parser.add_argument(
        "--args", "-a",
        default="{}",
        help="JSON string or file path containing arguments for skill execution",
    )
    parser.add_argument(
        "--query", "-q",
        metavar="QUERY",
        help="Find and inspect matching skill for given query string",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate integrity, schemas, and handlers of all registered skills",
    )
    parser.add_argument(
        "--category", "-c",
        default=None,
        help="Filter skills list by category",
    )
    parser.add_argument(
        "--tier", "-t",
        default=None,
        help="Filter skills list by security tier (GREEN, YELLOW, RED)",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve RED tier skills for autonomous non-interactive runs",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON format",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    return parser


def parse_args_payload(args_input: str) -> Dict[str, Any]:
    """Parse JSON string or file path into arguments dictionary."""
    if not args_input or args_input.strip() == "{}":
        return {}
    raw = args_input.strip()
    # Check if path to existing file
    if os.path.isfile(raw):
        with open(raw, "r", encoding="utf-8") as f:
            return json.loads(f.read())
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in --args parameter: {exc}")


def main() -> None:
    """Main CLI entrypoint router."""
    parser = build_parser()
    args = parser.parse_args()

    # Default action if no arguments provided: list skills
    if not (args.list or args.info or args.run or args.query or args.validate):
        args.list = True

    try:
        # Action 1: Validate registry
        if args.validate:
            val_res = GLOBAL_REGISTRY.validate_skills()
            if args.json:
                print(json.dumps(val_res, indent=2))
            else:
                print(render_validation_report(val_res))
            sys.exit(0 if val_res.get("all_passed") else 1)

        # Action 2: Inspect specific skill info
        elif args.info:
            skill = GLOBAL_REGISTRY.get(args.info) or GLOBAL_REGISTRY.find_matching_skill(args.info)
            if not skill:
                err_payload = {
                    "status": "ERROR",
                    "error": f"Skill '{args.info}' not found in registry",
                    "mark": WATERMARK,
                }
                if args.json:
                    print(json.dumps(err_payload, indent=2))
                else:
                    print(f"🦋 ERROR: Skill '{args.info}' not found in registry", file=sys.stderr)
                sys.exit(1)

            if args.json:
                print(json.dumps(skill.to_dict(), indent=2))
            else:
                print(render_skill_info(skill))
            sys.exit(0)

        # Action 3: Find by query
        elif args.query:
            skill = GLOBAL_REGISTRY.find_matching_skill(args.query)
            if not skill:
                err_payload = {
                    "status": "NO_MATCH",
                    "query": args.query,
                    "error": f"No skill found matching query '{args.query}'",
                    "mark": WATERMARK,
                }
                if args.json:
                    print(json.dumps(err_payload, indent=2))
                else:
                    print(f"🦋 No skill found matching query '{args.query}'", file=sys.stderr)
                sys.exit(1)

            if args.json:
                print(json.dumps(skill.to_dict(), indent=2))
            else:
                print(render_skill_info(skill))
            sys.exit(0)

        # Action 4: Run skill
        elif args.run:
            payload_args = parse_args_payload(args.args)
            exec_res = GLOBAL_REGISTRY.execute(
                name_or_query=args.run,
                args=payload_args,
                auto_approve_red=args.auto_approve,
            )
            if args.json:
                print(json.dumps(exec_res, indent=2, ensure_ascii=False))
            else:
                print(render_execution_result(exec_res))
            sys.exit(0 if exec_res.get("status") == "SUCCESS" else 1)

        # Action 5: List skills (default)
        elif args.list:
            skills = GLOBAL_REGISTRY.list_skills(category=args.category, tier=args.tier)
            if args.json:
                payload = {
                    "command": "skills",
                    "action": "list",
                    "total": len(skills),
                    "skills": [s.to_dict() for s in skills],
                    "timestamp": datetime.datetime.now().isoformat(),
                    "mark": WATERMARK,
                }
                print(json.dumps(payload, indent=2))
            else:
                print(render_skills_list(skills))
            sys.exit(0)

    except KeyboardInterrupt:
        print(f"\nOperation cancelled by operator {WATERMARK}", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        err_payload = {
            "status": "ERROR",
            "error": str(exc),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }
        if args.json:
            print(json.dumps(err_payload, indent=2))
        else:
            print(f"🦋 ERROR in xola-skills: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
