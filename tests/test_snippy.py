import base64
import io
from unittest.mock import Mock
import pytest
from PIL import Image
from floter.config import config
from floter.tiers.jev_tier import JevReflexTier, JevActionEnum, JevDecision
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tools.snippy_mcp import save_screenshot

@pytest.mark.parametrize('text', ['take a quick screen shot','quick screenshot','take a screenshot','capture screen','Floter, take a quick screenshot.','Can you please take a quick screen shot?','snippy screenshot','screenshot please'])
def test_screenshot_uses_snippy(text,monkeypatch):
    monkeypatch.setattr(config,'JEV_API_KEY','test-key')
    remote=Mock(return_value=JevDecision(JevActionEnum.SNIPPY_CAPTURE,'full_screen',1,1,True,'Jev remote classification',1))
    monkeypatch.setattr(JevReflexTier,'_call_jev_remote_api',remote)
    snippy=Mock(return_value={'path':'screenshot.png','source':'Snippy MCP'})
    monkeypatch.setattr('floter.tiers.orchestrator.call_snippy',snippy)
    result=FloterOrchestrator().process_query(text)
    assert result['status']=='success'
    assert result['tier']=='Snippy MCP'
    assert snippy.call_args.args[0]=='snippy_take_snip'
    remote.assert_called_once_with(text)

def test_missing_snippy_is_error_no_fallback(monkeypatch):
    monkeypatch.setattr(JevReflexTier,'triage_and_route',Mock(return_value=JevDecision(JevActionEnum.SNIPPY_CAPTURE,'full_screen',1,1,True,'test',1)))
    monkeypatch.setattr('floter.tiers.orchestrator.call_snippy',Mock(side_effect=RuntimeError('Snippy unavailable')))
    fallback=Mock(side_effect=AssertionError('Must not silently substitute another capture tool'))
    monkeypatch.setattr('floter.tools.mcp_tools.FastMCPToolRegistry.snippy_capture',fallback)
    result=FloterOrchestrator().process_query('take a quick screenshot')
    assert result['status']=='error'
    fallback.assert_not_called()

def test_mcp_image_saved(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'SNIPPY_CACHE_DIR',tmp_path)
    buffer=io.BytesIO(); Image.new('RGB',(10,10)).save(buffer,'PNG')
    result=save_screenshot({'content':[{'type':'image','mimeType':'image/png','data':base64.b64encode(buffer.getvalue()).decode()}]})
    from pathlib import Path
    assert Path(result['path']).read_bytes()==buffer.getvalue()

def test_server_pil_repr_is_not_success():
    with pytest.raises(RuntimeError,match='no image bytes'):
        save_screenshot({'content':[{'type':'text','text':'<PIL.Image.Image image mode=RGB size=100x100>'}]})
