# Robot Ross Repository Boundary

This document defines the relationship between the two divergent Robot Ross codebases as of April 2026.

## 1. bobrossskill (Public)
- **URL**: `https://github.com/UrsushoribilisMusic/bobrossskill`
- **Role**: Public, community-oriented skill project.
- **Scope**: Contains core Bob Ross drawing and narration features. 
- **Mexico-era Features**: This repo was the origin of pyrography (wood burning) mode and local LLM (Ollama/Apertus) integration.
- **Constraint**: This repo should remain open and accessible for community use. It is NOT the full demonstrator.

## 2. robot-ross (Canonical Demonstrator)
- **URL**: `https://github.com/UrsushoribilisMusic/robot-ross`
- **Role**: Canonical full system demonstrator.
- **Scope**: Superset of all capabilities. In addition to the core drawing features, it includes:
  - Full system orchestration
  - Shopify integration
  - Virtuals Protocol ACP integration
  - OBS recording pipeline
  - YouTube upload automation
  - Advanced order logging and state management
- **ATF Ingestion**: This repository is the **primary source of truth** for ATF (Agentegra Tooling Foundation) wiki and grounding rebuilds.

## Merge Rule
New features developed in the public `bobrossskill` (such as the Mexico-era voice and pyrography work) must be periodically merged into `robot-ross` to ensure the demonstrator remains the canonical superset.

---
*Documented by Gem (Gemini CLI) - 2026-04-11*
