"""Example usage of the medical chatbot API.

Run the FastAPI server first:
    uvicorn app.main:app --reload --port 8000

Then run this script:
    python example_usage.py
"""

import httpx
import asyncio
from typing import Dict, Any


async def chat(session_id: str, message: str) -> Dict[str, Any]:
    """Send a chat message and get response.

    Args:
        session_id: Unique session identifier
        message: User message

    Returns:
        API response as dictionary
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/chat",
            json={"session_id": session_id, "message": message},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


async def example_emotional_support():
    """Example: Emotional support conversation."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Emotional Support Conversation")
    print("=" * 70 + "\n")

    session_id = "example-emotional-1"

    # First message
    print("👤 User: I'm feeling really anxious today\n")
    response1 = await chat(session_id, "I'm feeling really anxious today")
    print(f"🤖 Agent ({response1['agent']}): {response1['message']}\n")

    # Follow-up
    print("👤 User: It's been hard to focus on anything\n")
    response2 = await chat(session_id, "It's been hard to focus on anything")
    print(f"🤖 Agent ({response2['agent']}): {response2['message']}\n")


async def example_medical_information():
    """Example: Medical information retrieval."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Medical Information Query")
    print("=" * 70 + "\n")

    session_id = "example-medical-1"

    # First message
    print("👤 User: What is Sertraline used for?\n")
    response1 = await chat(session_id, "What is Sertraline used for?")
    print(f"🤖 Agent ({response1['agent']}): {response1['message']}\n")

    # Follow-up
    print("👤 User: What are the common side effects?\n")
    response2 = await chat(session_id, "What are the common side effects?")
    print(f"🤖 Agent ({response2['agent']}): {response2['message']}\n")


async def example_medication_comparison():
    """Example: Comparing multiple medications."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Medication Comparison")
    print("=" * 70 + "\n")

    session_id = "example-comparison-1"

    # Ask about multiple medications
    print("👤 User: Can you compare Sertraline and Bupropion?\n")
    response = await chat(session_id, "Can you compare Sertraline and Bupropion?")
    print(f"🤖 Agent ({response['agent']}): {response['message']}\n")


async def example_session_persistence():
    """Example: Demonstrating session persistence."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Session Persistence (Multi-turn)")
    print("=" * 70 + "\n")

    session_id = "example-persist-1"

    messages = [
        "Tell me about antidepressants",
        "Which ones are SSRIs?",
        "What about their side effects?",
        "How long do they take to work?",
    ]

    for i, msg in enumerate(messages, 1):
        print(f"👤 User (message {i}): {msg}\n")
        response = await chat(session_id, msg)
        print(f"🤖 Agent ({response['agent']}): {response['message'][:200]}...\n")
        await asyncio.sleep(1)  # Slight delay between messages


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("Medical Chatbot API - Example Usage")
    print("=" * 70)
    print("\nMake sure the FastAPI server is running:")
    print("  uvicorn app.main:app --reload --port 8000\n")

    try:
        # Check if server is running
        async with httpx.AsyncClient() as client:
            health = await client.get("http://localhost:8000/health", timeout=5.0)
            health.raise_for_status()
            print("✅ Server is running!\n")

        # Run examples
        await example_emotional_support()
        await example_medical_information()
        await example_medication_comparison()
        await example_session_persistence()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70 + "\n")

    except httpx.ConnectError:
        print("❌ Error: Cannot connect to server.")
        print("Please start the server first:")
        print("  uvicorn app.main:app --reload --port 8000\n")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
