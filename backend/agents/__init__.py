"""
AltairGO AI Agents Layer
─────────────────────────
Five intelligent agents that enhance the deterministic engine:

1. WebScraperAgent     — Gemini-powered web scraping for price data
2. MemoryAgent         — User preference learning from behavioral signals
3. MCPContextAgent     — Live context (weather, events) for Gemini polish
4. TokenOptimizer      — Context compression to reduce Gemini API costs
5. ItineraryQAAgent    — Post-generation quality assurance pipeline
"""

from backend.agents.web_scraper_agent import WebScraperAgent
from backend.agents.memory_agent import MemoryAgent
from backend.agents.mcp_context_agent import MCPContextAgent
from backend.agents.token_optimizer import TokenOptimizer
from backend.agents.itinerary_qa_agent import ItineraryQAAgent
from backend.agents.destination_validator_agent import DestinationValidatorAgent

__all__ = [
    "WebScraperAgent",
    "MemoryAgent",
    "MCPContextAgent",
    "TokenOptimizer",
    "ItineraryQAAgent",
    "DestinationValidatorAgent",
]
