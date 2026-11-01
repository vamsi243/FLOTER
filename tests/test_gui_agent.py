import threading
from unittest.mock import Mock
import pytest
from floter.config import config
from floter.tools.gui_agent import GuiAgent, validate_action
from floter.tools.gui_review import GuiReview
from floter.workers import CancelledError
from floter.tiers.jev_tier import routing_choices, JevActionEnum

ELEMENTS=[{'id':0,'role':'Edit','label':'Search','box':[0,0,.5,.1]},
          {'id':1,'role':'Visual','label':'Mom','box':[0,.2,.5,.3]}]

@pytest.mark.parametrize('action',[
    {'action':'click','element':99,'reason':'missing'},
    {'action':'click','element':True,'reason':'boolean'},
    {'action':'type','element':1,'text':'hello','reason':'visual field'},
    {'action':'type','element':0,'text':'hello\n','reason':'enter'},
    {'action':'click','element':0,'reason':'extra','code':'bad'},
    {'action':'done','evidence':33,'reason':'invented'},
    {'action':'shell','reason':'unsupported'},
])
def test_invalid_model_actions_rejected(action):
    with pytest.raises(ValueError): validate_action(action,ELEMENTS)

def test_plain_text_is_not_key_syntax():
    a={'action':'type','element':0,'text':'{ENTER}','reason':'literal query'}
    assert validate_action(a,ELEMENTS)['text']=='{ENTER}'

def test_reviews_single_use_and_rejection():
    cancel=threading.Event()
    review=GuiReview(lambda ticket: None,cancel)
    def callback(ticket):
        if ticket.get('clear'): return
        assert not review.decide('wrong',True)
        assert review.decide(ticket['token'],False)
        assert not review.decide(ticket['token'],True)
    review.callback=callback
    with pytest.raises(CancelledError): review.ask('click','target')

def test_cancel_interrupts_review():
    cancel=threading.Event()
    review=GuiReview(lambda ticket: cancel.set(),cancel)
    with pytest.raises(CancelledError): review.ask('click','target')

def test_loop_reobserves_after_action_and_preserves_goal():
    desktop=Mock()
    desktop.windows.return_value=[{'handle':123,'title':'WhatsApp','process':'whatsapp.exe'}]
    desktop.observe.return_value={'elements':ELEMENTS}
    reasoner=Mock(local=True)
    reasoner.call.side_effect=[{'window':123},
        {'action':'click','element':1,'reason':'Open Mom'},
        {'action':'done','evidence':1,'reason':'Mom contact panel is visible'}]
    review=Mock(); goal='Open Mom profile in WhatsApp'
    result=GuiAgent(threading.Event(),review,Mock(),desktop,reasoner).run(goal)
    assert result['status']=='success'
    assert desktop.observe.call_count==2
    assert desktop.execute.call_count==1
    assert reasoner.call.call_args.args[1]['goal']==goal
    assert review.call_count==4
    # FLOTER hides only after reviews followed by observation or input.
    assert [c.kwargs.get('hide',True) for c in review.call_args_list]==[False,True,True,False]
    desktop.close.assert_called_once()

def test_routed_app_window_selected_without_model(monkeypatch):
    # "Click on images tab" names no app; another window title mentions FLOTER.
    monkeypatch.setitem(config.WHITELISTED_APPS,'gemini',[])
    desktop=Mock()
    desktop.windows.return_value=[{'handle':1,'title':'FLOTER and 2 more tabs - File Explorer','process':'explorer.exe'},
                                  {'handle':2,'title':'Gemini','process':'gemini.exe'},
                                  {'handle':3,'title':'Google Gemini - Brave','process':'brave.exe'}]
    desktop.observe.return_value={'elements':ELEMENTS}
    monkeypatch.setattr('floter.tools.gui_agent.process_names',lambda target:{'gemini.exe'})
    monkeypatch.setattr('floter.tools.mcp_tools.FastMCPToolRegistry.launch_application',Mock())
    monkeypatch.setattr(GuiAgent,'_wait_for_window',lambda self,d,t: d.windows())
    reasoner=Mock(local=True); reasoner.call.return_value={'action':'ask','reason':'stop after window choice'}
    review=Mock()
    GuiAgent(threading.Event(),review,Mock(),desktop,reasoner).run('Click on images tab.','gemini')
    desktop.bind.assert_called_once_with(2)
    assert 'Gemini (gemini.exe)' in review.call_args_list[1].args[1]
    assert reasoner.call.call_args_list[0].args[2]=='choose the next step'

def test_routed_app_with_several_windows_limits_model_choice(monkeypatch):
    desktop=Mock()
    desktop.windows.return_value=[{'handle':1,'title':'Notes','process':'explorer.exe'},
                                  {'handle':2,'title':'Gemini','process':'gemini.exe'},
                                  {'handle':4,'title':'Gemini settings','process':'gemini.exe'}]
    monkeypatch.setattr('floter.tools.gui_agent.process_names',lambda target:{'gemini.exe'})
    monkeypatch.setattr('floter.tools.mcp_tools.FastMCPToolRegistry.launch_application',Mock())
    monkeypatch.setattr(GuiAgent,'_wait_for_window',lambda self,d,t: d.windows())
    reasoner=Mock(local=True); reasoner.call.return_value={'ask':'Which Gemini window?'}
    result=GuiAgent(threading.Event(),Mock(),Mock(),desktop,reasoner).run('Click on images tab.','gemini')
    assert result['status']=='needs_input'
    assert [w['handle'] for w in reasoner.call.call_args.args[1]['windows']]==[2,4]

def test_ambiguous_window_does_not_click():
    desktop=Mock(); desktop.windows.return_value=[]
    reasoner=Mock(local=True); reasoner.call.return_value={'ask':'Which app?'}
    result=GuiAgent(threading.Event(),Mock(),Mock(),desktop,reasoner).run('open profile')
    assert result['status']=='needs_input'
    desktop.execute.assert_not_called()

def test_general_and_named_routes_available():
    choices=routing_choices()
    assert choices['gui:current'][0]==JevActionEnum.GUI_NAVIGATE
    assert choices['gui:notepad'][1]=='notepad'

def test_prompt_handoff_rejects_paraphrasing():
    desktop=Mock()
    desktop.windows.return_value=[{'handle':123,'title':'Claude','process':'claude.exe'}]
    desktop.observe.return_value={'elements':ELEMENTS}
    reasoner=Mock(local=True)
    reasoner.call.side_effect=[{'window':123},{'action':'type','element':0,'text':'changed prompt','reason':'Enter prompt'}]
    with pytest.raises(ValueError,match='prompt changed'):
        GuiAgent(threading.Event(),Mock(),Mock(),desktop,reasoner).run('Open Claude and enter original prompt',prompt='original prompt')
    desktop.execute.assert_not_called()
    desktop.close.assert_called_once()

def test_orchestrator_preserves_compound_goal(monkeypatch):
    from floter.tiers.orchestrator import FloterOrchestrator
    from floter.tiers.jev_tier import JevDecision
    app=FloterOrchestrator()
    app.jev.triage_and_route=Mock(return_value=JevDecision(JevActionEnum.GUI_NAVIGATE,'notepad',.99,1,True,'route',.99))
    agent=Mock(); agent.run.return_value={'status':'needs_input','message':'Which document?'}
    monkeypatch.setattr('floter.tools.gui_agent.GuiAgent',Mock(return_value=agent))
    goal='Open Notepad and find the document settings'
    result=app.process_query(goal)
    agent.run.assert_called_once_with(goal,'notepad')
    assert result['status']=='needs_input'
    assert not app._lock.locked()

@pytest.mark.parametrize('changed_bounds', [True,False])
def test_changed_target_rejected_before_mouse_input(monkeypatch,changed_bounds):
    import time
    from PIL import Image
    from floter.tools.gui_desktop import DesktopSession
    desktop=DesktopSession.__new__(DesktopSession)
    desktop.focus=Mock(); desktop._point_action=Mock()
    rect=Mock(left=0,top=0,right=21 if changed_bounds else 20,bottom=20)
    desktop.bound=Mock(); desktop.bound.rectangle.return_value=rect
    image=Image.new('RGB',(20,20),'white')
    monkeypatch.setattr('PIL.ImageGrab.grab',lambda **kw: Image.new('RGB',(20,20),'black'))
    observation={'time':time.monotonic(),'bounds':(0,0,20,20),'elements':[
        {'id':0,'label':'Target','role':'Visual','box':[0,0,1,1]}],'controls':{},'image':image}
    with pytest.raises(RuntimeError,match='stale'):
        desktop.execute(observation,{'action':'click','element':0})
    desktop._point_action.assert_not_called()
