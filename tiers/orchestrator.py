"""Single-flight query routing; provider failures never become successes."""
import threading
import json
import re
from floter.workers import CancelledError
from floter.security.plans import ApprovalGate, SkillStore
from floter.tools.snippy_mcp import call_snippy
from floter.tiers.jev_tier import JevReflexTier, JevActionEnum, WEB_ACTIONS, describe_choice, routing_choices
from floter.tiers.gemini_tier import GeminiMultimodalTier
from floter.tiers.hermes_tier import HermesAgentOrchestrator
from floter.tools.mcp_tools import FastMCPToolRegistry
from floter.security.sandbox import GuardrailViolationError


def readable_result(result):
    """Plain text for the result panel; the structured result stays in the return value."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if result.get('analysis'):
            return re.sub(r'\*\*(.+?)\*\*', r'\1', result['analysis'])
        if 'drives' in result:
            return '\n'.join(_drive_summary(drive) for drive in result['drives']) or 'No drives could be read.'
        if result.get('message'):
            return str(result['message'])
    return json.dumps(result, default=str)


def _drive_summary(drive):
    if 'free_bytes' not in drive:
        return f"{drive['drive']} — could not be read"
    free, total = (drive[key] / 1024 ** 3 for key in ('free_bytes', 'total_bytes'))
    count = len(drive['paths'])
    return f"{drive['drive']} — {free:.1f} GB free of {total:.1f} GB ({count} top-level item{'' if count == 1 else 's'})"


class FloterOrchestrator:
    def __init__(self, on_state_change=None, on_log_message=None, on_approval=None, on_completed=None):
        self.on_state_change = on_state_change or (lambda state: None)
        self.on_log_message = on_log_message or (lambda text: None)
        self.on_completed = on_completed or (lambda query, result: None)
        self.jev = JevReflexTier()
        from floter.tools.desktop_actions import NotepadSession, desktop_tools
        self.notepad = NotepadSession()
        self.desktop_tools = desktop_tools(self.notepad)
        from floter.tools.camera import CameraManager
        self.camera = CameraManager(self.on_log_message)
        self.session_context = {}
        self.gemini = GeminiMultimodalTier()
        self.hermes = HermesAgentOrchestrator()
        self._lock = threading.Lock()
        self._closed = False
        self._cancel = threading.Event()
        self.jev.cancel = self._cancel
        self.gemini.cancel = self._cancel
        self.hermes.cancel = self._cancel
        self.approvals = ApprovalGate()
        self.skills = SkillStore()
        self.last_approved_plan = None
        self.on_approval = on_approval or (lambda ticket: None)
        self._thread = None
        from floter.tools.gui_review import GuiReview
        self.gui_review = GuiReview(self.on_approval, self._cancel)

    def cancel_task(self):
        self._cancel.set()

    def shutdown(self):
        self._closed = True
        self._cancel.set()
        self.camera.shutdown()
        self.approvals.reject()
        from floter.tools import omniparser_launcher
        omniparser_launcher.stop()
        from floter.tools import browser_worker
        browser_worker.stop()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(3)

    def process_query_async(self, query):
        if not query.strip() or self._closed:
            return False
        if not self._lock.acquire(blocking=False):
            self.on_log_message("A request is already running.")
            return False
        self._cancel.clear()
        self._thread = threading.Thread(target=self._run, args=(query,), daemon=True)
        self._thread.start()
        return True

    def process_query(self, query):
        if self._closed or not query.strip():
            return {"status": "ignored"}
        if not self._lock.acquire(blocking=False):
            return {"status": "busy"}
        self._cancel.clear()
        return self._run(query)

    def reject_plan(self):
        self.approvals.reject()

    def _propose(self, plan):
        ticket = self.approvals.propose(plan)
        self.on_approval(ticket)
        return {'status':'approval_required', 'plan':ticket['plan']}

    def approve_plan(self, token):
        if token.startswith('gui:'):
            return self.gui_review.decide(token, True)
        if self._closed or not self._lock.acquire(False):
            return False
        try:
            plan = self.approvals.consume(token)
        except Exception:
            self._lock.release()
            raise
        self._thread = threading.Thread(target=self._execute_plan, args=(plan,), daemon=True)
        self._thread.start()
        return True

    def _execute_plan(self, plan):
        completed = 0
        try:
            self.on_state_change('Executing')
            for action in plan['actions']:
                if self._cancel.is_set():
                    raise CancelledError('Plan cancelled')
                if action['tool'] == 'snippy_capture':
                    output = call_snippy('snippy_take_snip', cancel=self._cancel)
                elif action['tool'] == 'inspect_storage':
                    output = FastMCPToolRegistry.inspect_storage_all_drives(cancel=self._cancel, **action['arguments'])
                else:
                    function = getattr(FastMCPToolRegistry, action['tool'])
                    output = function(**action['arguments'])
                self.on_log_message(readable_result(output))
                completed += 1
            self.last_approved_plan = plan
            self.on_state_change('Success')
        except Exception as exc:
            self.on_log_message(f'Plan stopped after {completed} actions: {exc}')
        finally:
            if not self._closed:
                self.on_state_change('Idle')
            self._lock.release()

    def _clarify(self, decision):
        """Without a reasoning provider, ask the user to rephrase instead of guessing."""
        choices = routing_choices()
        ranked = [key for key, _ in sorted(decision.probabilities.items(), key=lambda item: -item[1])
                  if key in choices and key != 'blocked'][:2]
        options = ' or '.join(describe_choice(key, choices) for key in ranked) or 'something else'
        message = (f"I wasn't sure what you meant — did you mean to {options}? "
                   'Please rephrase, for example "open Gmail in Brave" or "search the web for weather in Sydney". '
                   'No action was performed.')
        self.on_log_message(message)
        return {'status':'needs_input','message':message,'tier':'Jev'}

    def _extract_or_full(self, query, purpose):
        """Use Jev to trim filler words; fall back to the full request if Jev is unsure."""
        try:
            return self.jev.extract_argument(query, purpose)
        except CancelledError:
            raise
        except Exception:
            return query

    def _in_floter_browser(self, url):
        from floter.tools import browser_worker
        page = browser_worker.get_worker(self._cancel, self.on_log_message).call(self._cancel, 'goto', url)
        self.session_context['browser_page'] = page['url']
        return {'status':'success','url':page['url'],'browser':"FLOTER's browser"}

    def _open_web(self, query, decision):
        from floter.config import config
        from floter.tools.desktop_actions import site_url, search_url
        from floter.tools.mcp_tools import FastMCPToolRegistry
        browser = decision.browser
        # A named browser keeps the user's own browser; otherwise FLOTER's browser when enabled.
        own = config.BROWSER_AUTOMATION and not browser
        where = "FLOTER's browser" if own else browser.title() if browser else 'your default browser'
        if decision.action == JevActionEnum.WEB_SEARCH:
            topic = self._extract_or_full(query, 'internet search topic, excluding instructions to search and any browser name')
            self._check_cancel()
            self.on_state_change('Executing')
            result = (self._in_floter_browser(search_url(topic)) if own
                      else self.desktop_tools['web_search'].invoke({'query':topic, 'browser':browser}))
            message = f'Searching the web for "{topic}" in {where}.'
        elif decision.action == JevActionEnum.OPEN_OTHER_WEB:
            site = self._extract_or_full(query, 'name or address of the website to open, excluding instructions and any browser name')
            self._check_cancel()
            self.on_state_change('Executing')
            url = site_url(site)
            if url and own:
                result = self._in_floter_browser(url)
                message = f'Opened {url} in {where}.'
            elif url:
                from floter.tools.desktop_actions import open_url
                open_url(url, browser)
                result = {'status':'success','url':url,'browser':browser or 'default browser'}
                message = f'Opened {url} in {where}.'
            else:
                result = (self._in_floter_browser(search_url(site)) if own
                          else self.desktop_tools['web_search'].invoke({'query':site, 'browser':browser}))
                message = f'Searching for the "{site}" website in {where}; pick the right result.'
        else:
            if not decision.target:
                raise ValueError('Classifier omitted the required website')
            self.on_state_change('Executing')
            if decision.target in {'claude','gemini'} and decision.target not in self._whitelisted_apps():
                self.on_log_message('Opening the official '+decision.target+' website. Register the installed app in %USERPROFILE%\.floter\applications.json to use it instead.')
            if own:
                if decision.target not in config.WHITELISTED_URL_MAP:
                    raise GuardrailViolationError('Website is not configured')
                result = self._in_floter_browser(config.WHITELISTED_URL_MAP[decision.target])
            else:
                result = FastMCPToolRegistry.open_website(decision.target, browser)
            message = f'Opened {decision.target} in {where}.'
        if not own:
            self.session_context.pop('browser_page', None)
        self.session_context.update(last_action=decision.action.value, last_target=decision.target,
                                    last_browser=browser, last_request=query[:1000])
        self.on_log_message(message)
        self.on_state_change('Success')
        return {'status':'success','result':result,'message':message,'tier':'Jev / Browser'}

    def _check_cancel(self):
        if self._cancel.is_set():
            raise CancelledError('Request cancelled')

    @staticmethod
    def _whitelisted_apps():
        from floter.config import config
        return config.WHITELISTED_APPS

    def _run(self, query):
        result = self._route_query(query)
        self.on_completed(query, result)
        return result

    def _route_query(self, query):
        try:
            self.on_state_change("Thinking")
            if self._cancel.is_set():
                raise CancelledError('Request cancelled')
            self.jev.context = dict(self.session_context)
            decision = self.jev.triage_and_route(query)
            if self._cancel.is_set():
                raise CancelledError('Request cancelled')
            self.on_log_message(f'Jev: {decision.action.value}; target={decision.target or "none"}; '
                                f'confidence={decision.confidence:.4f}; probability={decision.probability:.4f}; '
                                f'round trip={decision.latency_ms:.0f} ms')
            if not decision.is_safe or decision.action == JevActionEnum.BLOCKED_UNSAFE:
                raise GuardrailViolationError('Jev rejected this request')
            action = decision.action
            # This branch only explains a missing capability; it cannot execute
            # an action and does not require a reasoning-provider key.
            if action == JevActionEnum.UNSUPPORTED_TAB:
                raise ValueError('Closing individual tabs is not supported. You can ask to close the application instead. Configuring Hermes does not add tab controls.')
            threshold = self.jev.WEB_CONFIDENCE_THRESHOLD if action in WEB_ACTIONS else self.jev.CONFIDENCE_THRESHOLD
            confident = decision.confidence >= threshold and decision.probability >= threshold
            navigation = {JevActionEnum.GUI_NAVIGATE, JevActionEnum.BROWSER_NAVIGATE}
            if action in navigation and not confident:
                # Every navigation step is reviewed by the user, so a split between navigation
                # targets (e.g. browser:page vs gui:current) counts as one confident navigation request.
                choices = routing_choices()
                family = sum(p for key, p in decision.probabilities.items()
                             if key in choices and choices[key][0] in navigation)
                confident = family >= self.jev.CONFIDENCE_THRESHOLD
            if not confident and action != JevActionEnum.ESCALATE_TO_HERMES:
                # An uncertain action is never guessed or handed to an advisor that cannot act.
                return self._clarify(decision)
            if action in WEB_ACTIONS:
                return self._open_web(query, decision)
            if action in {JevActionEnum.GUI_NAVIGATE, JevActionEnum.ASSISTANT_PROMPT}:
                from floter.tools.gui_agent import GuiAgent
                self.on_state_change('Reasoning')
                agent = GuiAgent(self._cancel, self.gui_review.ask, self.on_log_message)
                if action == JevActionEnum.ASSISTANT_PROMPT:
                    prompt = self.jev.extract_argument(query, 'exact prompt or question to enter into ' + decision.target + ', excluding instructions to open the assistant')
                    result = agent.run(query, decision.target, prompt=prompt)
                else:
                    result = agent.run(query, decision.target)
                if decision.target:
                    self.session_context.update(last_action='gui', last_target=decision.target)
                self.on_log_message(result['message'])
                if result['status'] == 'success':
                    self.on_state_change('Success')
                return {'status':result['status'],'result':result,'tier':'Jev / GUI navigation'}
            if action == JevActionEnum.BROWSER_NAVIGATE:
                from floter.config import config
                if not config.BROWSER_AUTOMATION:
                    raise ValueError('Browser automation is off. Set BROWSER_AUTOMATION=1 in your .env and restart FLOTER.')
                from floter.tools.browser_agent import BrowserAgent
                self.on_state_change('Reasoning')
                result = BrowserAgent(self._cancel, self.gui_review.ask, self.on_log_message).run(query)
                if result.get('url'):
                    self.session_context.update(last_action='browser', browser_page=result['url'])
                self.on_log_message(result['message'])
                if result['status'] == 'success':
                    self.on_state_change('Success')
                return {'status':result['status'],'result':result,'tier':'Jev / Browser automation'}
            if action == JevActionEnum.CAMERA:
                self.on_state_change('Executing')
                result = self.camera.perform(decision.target)
                self.on_log_message(result['message'])
                self.session_context.update(last_action='camera:' + decision.target, last_target='camera')
                self.on_state_change('Success')
                return {'status':'success', 'result':result, 'tier':'Jev / Camera'}
            if action == JevActionEnum.CLOSE_APP:
                if not decision.target:
                    raise ValueError('Name the application to close')
                from floter.tools.desktop_actions import close_application
                self.on_state_change('Executing')
                result = close_application(decision.target, self.notepad.window_handle if decision.target == 'notepad' else None)
                self.on_log_message(result['message'])
                self.session_context.update(last_action='close', last_target=decision.target)
                self.on_state_change('Success')
                return {'status':'success','result':result,'tier':'Jev'}
            if action == JevActionEnum.PLAN:
                self.hermes.ensure_configured()
                self.on_log_message('Passing this task to Hermes for a proposed plan.')
                response = self.hermes.execute_complex_plan(query, plan_mode=True)
                return self._propose(response['plan'])
            if action == JevActionEnum.TYPE_NOTEPAD:
                argument = self.jev.extract_argument(query, 'literal words to append to Notepad')
                if self._cancel.is_set():
                    raise CancelledError('Request cancelled')
                self.on_state_change('Executing')
                result = self.desktop_tools['type_notepad'].invoke({'text':argument})
                self.session_context.update(last_action='type_notepad', last_request=query[:1000])
                self.on_log_message(readable_result(result))
                self.on_state_change('Success')
                return {'status':'success','result':result,'tier':'Jev / LangChain'}
            if action in {JevActionEnum.RUN_SKILL, JevActionEnum.SAVE_SKILL}:
                # This parses an argument only AFTER Jev has selected the operation.
                # Spoken commands keep case and end punctuation ("Run skill Morning.").
                parts = query.strip().rstrip('.!?').lower().split()
                verb = 'run' if action == JevActionEnum.RUN_SKILL else 'save'
                if len(parts) != 3 or parts[:2] != [verb, 'skill']:
                    raise ValueError(f'Use "{verb} skill <exact-name>" to specify the skill name.')
                skill_name = parts[2]
            if action == JevActionEnum.RUN_SKILL:
                return self._propose(self.skills.load(skill_name))
            if action == JevActionEnum.SAVE_SKILL:
                if self.last_approved_plan is None:
                    raise ValueError('Run an approved plan before saving a skill')
                self.skills.save(skill_name, self.last_approved_plan)
                self.on_log_message('Skill saved. Future runs require approval.')
                return {'status':'success'}
            if action == JevActionEnum.LIST_SKILLS:
                result = self.skills.names()
                self.on_log_message('Saved skills: ' + ', '.join(result) if result else 'No saved skills yet.')
                return {'status':'success','result':result}
            if action == JevActionEnum.SNIPPY_TOOL:
                result = call_snippy(decision.target, cancel=self._cancel)
                self.on_log_message(json.dumps(result)[:12000])
                return {'status':'success','tier':'Snippy MCP','result':result}
            if action == JevActionEnum.INSPECT_STORAGE:
                self.on_state_change("Executing")
                result = FastMCPToolRegistry.inspect_storage_all_drives(cancel=self._cancel)
                self.on_log_message(readable_result(result))
                self.on_state_change("Success")
                return {"status": "success", "result": result, "tier": "Jev"}
            if action == JevActionEnum.ESCALATE_TO_GEMINI:
                self.on_state_change("Reasoning")
                self.on_log_message('Passing this screen-analysis task to Gemini.')
                if not self.gemini.api_key:
                    raise RuntimeError("Configure Gemini before requesting screen analysis")
                screen = FastMCPToolRegistry.snippy_capture("full_screen")
                result = self.gemini.analyze_visual_and_logs(query, image_path=screen)
                tier = "Gemini"
            elif confident and action in {
                JevActionEnum.LAUNCH_APP, JevActionEnum.OPEN_WEB, JevActionEnum.SNIPPY_CAPTURE
            }:
                self.on_state_change("Executing")
                if action == JevActionEnum.SNIPPY_CAPTURE:
                    result = call_snippy("snippy_take_snip", cancel=self._cancel)
                else:
                    if not decision.target:
                        raise ValueError("Classifier omitted the required target")
                    if action == JevActionEnum.OPEN_WEB:
                        if decision.target in {'claude','gemini'}:
                            self.on_log_message('Opening the official '+decision.target+' website. Register the installed app in %USERPROFILE%\\.floter\\applications.json to use it instead.')
                        result = FastMCPToolRegistry.open_website(decision.target)
                    elif decision.target == 'notepad':
                        result = self.notepad.open()
                    else:
                        result = FastMCPToolRegistry.launch_application(decision.target)
                    self.session_context.update(last_action='open', last_target=decision.target)
                tier = "Snippy MCP" if action == JevActionEnum.SNIPPY_CAPTURE else "Jev"
            else:
                self.hermes.ensure_configured()
                self.on_state_change("Reasoning")
                self.on_log_message('Passing this task to Hermes for advice.')
                result = self.hermes.execute_complex_plan(query)
                tier = "Hermes"
            if self._cancel.is_set():
                raise CancelledError("Request cancelled")
            if isinstance(result, dict) and (result.get("error") or result.get("status") == "error"):
                raise RuntimeError(result.get("error", "Provider failed"))
            self.on_log_message(readable_result(result))
            self.on_state_change("Success")
            return {"status": "success", "result": result, "tier": tier}
        except CancelledError:
            return {"status": "cancelled"}
        except Exception as exc:
            self.on_state_change("Blocked")
            self.on_log_message(str(exc))
            return {"status": "blocked" if isinstance(exc, GuardrailViolationError) else "error", "error": str(exc)}
        finally:
            if not self._closed:
                self.on_state_change("Idle")
            self._lock.release()
