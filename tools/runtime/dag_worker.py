"""Isolated DAG tool worker; stdout is a single JSON result. 🦋"""
import contextlib
import io
import json
import sys


def execute(action, args):
    if action == 'echo':
        return {'status': 'SUCCESS', 'text': args.get('text', '')}
    from jarvis.brain import AutonomousBrain, BrainPlan
    aliases = {'system.health': ('sentinel', None), 'guard.audit': ('guard', 'guard'),
               'audit': ('guard', 'guard'), 'voice.speak': ('voice', None)}
    kind, skill = aliases.get(action, ('hands', action) if action.startswith('hands.') else ('skill', action))
    return AutonomousBrain().execute_plan(BrainPlan(prompt=action, action=kind, skill=skill, args=args)).to_dict()


def main():
    payload = json.loads(sys.stdin.read())
    from tools.runtime.approvals import SCOPE
    token = SCOPE.set(payload.get('scope', 'dag'))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            result = execute(payload['action'], payload.get('args', {}))
    except Exception as exc:
        result = {'status': 'ERROR', 'error': str(exc)}
    finally:
        SCOPE.reset(token)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
