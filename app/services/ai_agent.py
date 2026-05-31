import asyncio
import json
import logging
import time
from typing import Any
from urllib import error, parse, request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class AgentResult:
    text: str
    tool_calls_made: list[str]

class AIAssistantAgent:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model.removeprefix("models/").strip("/")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def get_tools_schema(self) -> list[dict[str, Any]]:
        return [{
            "functionDeclarations": [
                {
                    "name": "list_targets",
                    "description": "List all available publishing destinations for the user. Returns a dict with 'targets' (raw list), 'display_all' (pre-formatted text showing all destinations), and 'display_telegram_only' (pre-formatted text showing only Telegram channels/groups). When showing results to the user, you MUST copy the display_all or display_telegram_only text exactly as-is without any modification or renaming.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {},
                    }
                },
                {
                    "name": "save_user_preference",
                    "description": "Permanently save a user preference, rule, or instruction.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "key": {"type": "STRING", "description": "Short key name for the preference"},
                            "value": {"type": "STRING", "description": "The detailed preference value"}
                        },
                        "required": ["key", "value"]
                    }
                },
                {
                    "name": "forget_user_preference",
                    "description": "Delete a previously saved user preference.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "key": {"type": "STRING", "description": "The key of the preference to delete"}
                        },
                        "required": ["key"]
                    }
                },
                {
                    "name": "publish_post",
                    "description": "Immediately publish a post to a destination. Use target_id to specify the destination: 'facebook' for Facebook Page, or a Telegram chat identifier (e.g. '-100xxx' or '@username') for a Telegram channel/group. If target_id is not provided, defaults to Facebook.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "text": {"type": "STRING", "description": "The text content of the post"},
                            "target_id": {"type": "STRING", "description": "Destination identifier. 'facebook' for Facebook Page, or the Telegram chat ID/username for a Telegram channel or group. If omitted, defaults to 'facebook'."},
                            "include_ai_image": {"type": "BOOLEAN", "description": "Whether to generate and attach an AI image"},
                            "image_prompt": {"type": "STRING", "description": "Detailed prompt for the AI image if include_ai_image is true"}
                        },
                        "required": ["text"]
                    }
                },
                {
                    "name": "schedule_future_post",
                    "description": "Schedule a post to be published at a specific future date and time. Use target_id to specify the destination: 'facebook' for Facebook Page, or a Telegram chat identifier for a Telegram channel/group.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "text": {"type": "STRING", "description": "The text content of the post"},
                            "datetime_str": {"type": "STRING", "description": "The target datetime in format YYYY-MM-DD HH:MM:SS"},
                            "target_id": {"type": "STRING", "description": "Destination identifier. 'facebook' for Facebook Page, or the Telegram chat ID/username. If omitted, defaults to 'facebook'."},
                            "include_ai_image": {"type": "BOOLEAN", "description": "Whether to generate an AI image for this post"},
                            "image_prompt": {"type": "STRING", "description": "Detailed prompt for the image"}
                        },
                        "required": ["text", "datetime_str"]
                    }
                }
            ]
        }]

    async def chat(self, system_prompt: str, chat_history: list[dict[str, Any]], new_message: str, callbacks: dict[str, Any]) -> AgentResult:
        """
        chat_history format: [{"role": "user", "parts": [{"text": "hi"}]}, {"role": "model", "parts": [{"text": "hello"}]}]
        callbacks: dictionary of async functions corresponding to tool names.
        """
        history = list(chat_history)
        history.append({"role": "user", "parts": [{"text": new_message}]})

        url = f"{self.base_url}/{self.model}:generateContent?key={parse.quote(self.api_key, safe='')}"
        
        tool_calls_made = []
        
        for _ in range(5):  # Max 5 recursive tool calls per turn
            payload = {
                "systemInstruction": {"role": "system", "parts": [{"text": system_prompt}]},
                "contents": history,
                "tools": self.get_tools_schema(),
                "generationConfig": {"temperature": 0.7}
            }
            
            req = request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            
            try:
                response_body = await asyncio.to_thread(self._make_request, req)
                if not response_body:
                    return AgentResult("I encountered a network error while processing.", tool_calls_made)
                    
                resp_json = json.loads(response_body)
                candidates = resp_json.get("candidates", [])
                if not candidates:
                    return AgentResult("I received an empty response from the AI.", tool_calls_made)
                    
                message = candidates[0].get("content", {})
                parts = message.get("parts", [])
                
                # Check for function calls
                function_calls = [p.get("functionCall") for p in parts if "functionCall" in p]
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                
                history.append(message)  # Append assistant's response to history
                
                if not function_calls:
                    # No more tools to call, return the final text
                    return AgentResult("".join(text_parts), tool_calls_made)
                
                # Execute function calls
                function_responses = []
                for fc in function_calls:
                    name = fc.get("name")
                    args = fc.get("args", {})
                    tool_calls_made.append(name)
                    
                    if name in callbacks:
                        try:
                            # Execute the registered python callback
                            result = await callbacks[name](**args)
                            func_resp = {"result": result}
                        except Exception as e:
                            logger.error(f"Tool {name} failed: {e}")
                            func_resp = {"error": str(e)}
                    else:
                        func_resp = {"error": "Tool not found"}
                        
                    function_responses.append({
                        "functionResponse": {
                            "name": name,
                            "response": func_resp
                        }
                    })
                
                # Append tool results to history as the 'user' role returning the data
                history.append({
                    "role": "user",
                    "parts": function_responses
                })
                
            except Exception as e:
                logger.error(f"Agent loop error: {e}")
                return AgentResult(f"I encountered an internal error: {str(e)}", tool_calls_made)

        return AgentResult("I reached the maximum number of tool calls and had to stop.", tool_calls_made)

    def _make_request(self, req: request.Request) -> str | None:
        for attempt in range(3):
            try:
                # Rebuild request for retries since the body stream is consumed
                retry_req = request.Request(
                    req.full_url,
                    data=req.data,
                    headers=dict(req.headers),
                    method=req.method,
                )
                with request.urlopen(retry_req, timeout=45.0) as response:
                    return response.read(65536).decode("utf-8", errors="replace")
            except error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                logger.error(f"Gemini API Error {e.code} (attempt {attempt+1}): {body}")
                if e.code in (503, 429) and attempt < 2:
                    time.sleep(2 * (attempt + 1))  # 2s, 4s backoff
                    continue
                return None
            except (error.URLError, TimeoutError) as e:
                logger.error(f"Gemini API Request Failed (attempt {attempt+1}): {e}")
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
        return None
