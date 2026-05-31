import asyncio
import os
from app.services.ai_agent import AIAssistantAgent

async def test_gemini():
    # First, let's see if the key is in environment variables directly
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("GEMINI_API_KEY is not in OS environment variables.")
        # Try loading from dotenv if they have it somewhere else, or maybe it's passed differently
        from app.core.config import load_settings
        settings = load_settings()
        api_key = settings.gemini_api_key
        
    if not api_key:
        print("Could not find Gemini API Key in settings either!")
        return
        
    print(f"Found Gemini API Key: {api_key[:5]}...{api_key[-4:]}")
    
    print("Testing Gemini API...")
    agent = AIAssistantAgent(api_key=api_key, model="gemini-2.5-flash-lite")
    
    # Send a simple message without tools just to test connection
    history = []
    
    # We use empty callbacks for the test
    result = await agent.chat("You are a helpful assistant.", history, "Hello, are you online?", {})
    
    print("Response from Gemini:")
    print(result.text)

if __name__ == "__main__":
    asyncio.run(test_gemini())
