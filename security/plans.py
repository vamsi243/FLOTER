"""Strict, immutable, single-use approval tickets for model-proposed actions."""
import json
import re
import secrets
import threading
import time
from pathlib import Path
from jsonschema import Draft202012Validator
from floter.config import config
from floter.security.sandbox import GuardrailViolationError, SafeFileSystem

def action_schema(name, properties):
    return {'type':'object', 'additionalProperties':False, 'required':['tool','arguments'],
            'properties': {'tool': {'const':name}, 'arguments': {'type':'object', 'additionalProperties':False,
                           'required':list(properties), 'properties':properties}}}

TEXT = {'type':'string','maxLength':20000}
FILENAME = {'type':'string','minLength':1,'maxLength':120,'pattern':r'^[A-Za-z0-9][A-Za-z0-9 _.-]*\.(txt|md)$'}
PLAN_SCHEMA = {'$schema':'https://json-schema.org/draft/2020-12/schema', 'type':'object',
    'additionalProperties':False, 'required':['version','summary','actions'], 'properties': {
        'version':{'const':1}, 'summary':{'type':'string','minLength':1,'maxLength':300},
        'actions': {'type':'array','minItems':1,'maxItems':8,'items':{'oneOf':[
            action_schema('launch_application',{'target':{'type':'string','minLength':1,'maxLength':50}}),
            action_schema('snippy_capture',{'region':{'const':'full_screen'}}),
            action_schema('generate_notepad_document',{'file_name':FILENAME,'content':TEXT}),
            action_schema('write_notepad',{'file_name':FILENAME,'content':TEXT}),
            action_schema('inspect_storage', {'time_budget': {'type':'number','minimum':1,'maximum':30}, 'max_entries_per_drive': {'type':'integer','minimum':1,'maximum':10000}}),
        ]}}}}

def validate_plan(plan):
    try:
        encoded = json.dumps(plan, allow_nan=False)
        if len(encoded) > 100000:
            raise ValueError('Plan exceeds size limit')
        clean = json.loads(encoded)
        Draft202012Validator(PLAN_SCHEMA).validate(clean)
        for action in clean['actions']:
            if action['tool'] == 'launch_application':
                if action['arguments']['target'] not in {*config.WHITELISTED_APPS, *config.WHITELISTED_URL_MAP}:
                    raise ValueError('Unknown application')
        return clean
    except Exception as exc:
        raise GuardrailViolationError('Plan contains unsupported actions or invalid parameters') from exc

class ApprovalGate:
    def __init__(self, ttl=300):
        self.ttl = ttl
        self._pending = None
        self._mutex = threading.Lock()

    def propose(self, plan):
        encoded = json.dumps(validate_plan(plan), ensure_ascii=False, sort_keys=True)
        token = secrets.token_urlsafe(24)
        with self._mutex:
            self._pending = (token, encoded, time.monotonic()+self.ttl)
        return {'token':token,'plan':json.loads(encoded)}

    def reject(self):
        with self._mutex:
            self._pending = None

    def consume(self, token):
        with self._mutex:
            pending = self._pending
            if not pending or not secrets.compare_digest(pending[0], token):
                raise GuardrailViolationError('No matching approval request')
            self._pending = None
        if time.monotonic() >= pending[2]:
            raise GuardrailViolationError('Approval expired; request the plan again')
        return validate_plan(json.loads(pending[1]))

class SkillStore:
    def __init__(self, directory=None):
        self.directory = Path(directory or (config.HOME_DIR / '.floter' / 'skills'))

    def _path(self, name):
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', name):
            raise ValueError('Skill names use lowercase letters, numbers, underscores and hyphens')
        return self.directory / (name+'.json')

    def save(self, name, plan):
        SafeFileSystem.write_new_text(self._path(name), json.dumps(validate_plan(plan), indent=2))

    def load(self, name):
        path = self._path(name)
        if path.is_symlink() or path.stat().st_size > 100000:
            raise GuardrailViolationError('Invalid skill file')
        return validate_plan(json.loads(path.read_text(encoding='utf-8')))

    def names(self):
        return sorted(p.stem for p in self.directory.glob('*.json'))[:100]
