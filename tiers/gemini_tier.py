import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, List

from floter.config import config, model_chain
from floter.workers import request_json, CancelledError
from floter.security.sandbox import SafeFileSystem

class GeminiMultimodalTier:
    """
    Tier B: Google Gemini 1.5 (Multimodal Vision & Fast Synthesis)
    Inspects visual context from Snippy, summarizes logs, and structures reports.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.cancel = None
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model or config.GEMINI_MODEL
        self.vision_model = config.GEMINI_VISION_MODEL or self.model

    def analyze_visual_and_logs(
        self, 
        prompt: str, 
        image_path: Optional[str] = None, 
        logs: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Multimodal inference combining screen capture and log context to produce
        synthesized findings and structured report data.
        """
        combined_text = prompt
        if logs:
            combined_text += "\n\n=== RECENT LOG EXTRACTS ===\n"
            for log in logs[:5]:
                combined_text += f"\nFile: {log.get('name')}\nContent Snippet:\n{log.get('content')[:2000]}\n"

        # If API key is available, call Gemini API
        if self.api_key:
            return self._call_gemini_api(combined_text, image_path)

        raise RuntimeError("Set GEMINI_API_KEY and Gemini model IDs to enable visual analysis")

    def _call_gemini_api(self, text_prompt: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        target_model = self.vision_model if image_path else self.model
        if not target_model:
            raise RuntimeError("Set GEMINI_MODEL / GEMINI_VISION_MODEL to a supported model ID")
        contents_parts = [{"text": text_prompt}]

        if image_path and Path(image_path).exists():
            img_bytes = Path(image_path).read_bytes()
            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            contents_parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": b64_img
                }
            })

        payload = {
            "contents": [{"parts": contents_parts}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        failure = None
        # A busy or failing model hands over to the next configured fallback.
        for model in model_chain(target_model, config.GEMINI_FALLBACK_MODELS):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key}
                )
                res_data = request_json(req, 12.0, self.cancel)
                candidates = res_data.get("candidates", [])
                if not candidates:
                    raise ValueError("Gemini returned no usable response")
                text_out = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                try:
                    result = json.loads(text_out)
                    if not isinstance(result, dict):
                        raise ValueError("Expected a JSON object")
                    return result
                except json.JSONDecodeError:
                    return {"analysis": text_out, "rows": []}
            except CancelledError:
                raise
            except Exception as exc:
                failure = exc
        raise RuntimeError("Gemini request failed; check model, credentials and connection") from failure
