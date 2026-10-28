# IR Agent — AI-Powered Cybersecurity Incident Response

An AI-powered cybersecurity incident response agent designed to investigate security alerts, analyze logs, identify Indicators of Compromise (IOCs), assess severity, and recommend appropriate containment actions through a controlled, human-approved process.

The project demonstrates how agentic AI can support security operations while maintaining strict safeguards against prompt injection, unauthorized actions, and attacks targeting critical assets.

## Project Overview

Security teams often need to investigate alerts from multiple sources, correlate evidence, determine the severity of an incident, and decide how to respond. This project explores how an AI agent can assist with these tasks while keeping security-critical decisions under human control.

The agent investigates one incident at a time using synthetic security logs, asset inventory information, and simulated threat intelligence. Based on the available evidence, it produces an incident assessment and may request a containment action, such as disabling a compromised account, isolating a host, or blocking a suspicious IP address.

**Key principle:** The AI agent can investigate and recommend actions, but dangerous containment operations are simulated and subject to explicit human approval and code-enforced security restrictions.

## Key Features

- **AI-driven incident investigation:** Analyzes security alerts and gathers relevant evidence using available tools.
- **IOC extraction:** Identifies indicators such as suspicious IP addresses, affected hosts, and potentially compromised accounts.
- **Severity classification:** Assesses incidents and supports prioritization based on the collected evidence.
- **MCP integration:** Retrieves incident logs through a Model Context Protocol (MCP) server.
- **Human-in-the-loop approval:** Requires explicit approval before executing simulated containment actions.
- **Protected asset enforcement:** Blocks actions targeting protected assets, even when approval is granted.
- **Prompt injection defense:** Tests resistance to malicious instructions embedded in attacker-controlled log fields.
- **Evaluation and testing:** Includes synthetic incident datasets, automated graders, security tests, and evaluation configurations.
- **Browser interface:** Provides a web-based interface powered by FastAPI for interacting with the agent.

## Technology Stack

- **Python** — Core agent logic, security controls, evaluation, and testing.
- **FastAPI** — Backend API and browser interface.
- **HTML, CSS, and JavaScript** — Frontend interface.
- **MCP (Model Context Protocol)** — Structured access to incident logs through a dedicated server.
- **OpenRouter or Ollama** — Configurable model providers supporting the required tool-calling capabilities.
- **pytest** — Automated testing of security controls and agent behavior.
- **uv** — Python dependency and environment management.
- **JSONL** — Structured agent execution traces.

## System Architecture

The project follows an agentic architecture in which the model selects investigation steps based on the alert and the evidence gathered.

1. **Incident input:** The agent receives an incident identifier.
2. **Context and instructions:** The agent follows the role, workflow, output requirements, and security rules defined in `AGENTS.md`.
3. **Evidence collection:** It calls permitted tools to inspect logs and obtain relevant investigation data.
4. **Analysis:** It correlates the evidence, extracts IOCs, and determines the likely severity and incident type.
5. **Action authorization:** Requests for dangerous actions pass through a dedicated authorization layer.
6. **Human approval:** Containment requests require explicit approval.
7. **Security enforcement:** Protected assets cannot be targeted, regardless of the model's recommendation or approval response.
8. **Results and traces:** The agent returns its assessment and records execution traces for analysis and evaluation.

The investigation is dynamic: the next tool call depends on the alert and the evidence returned. Security-critical authorization rules remain deterministic and enforced in code rather than relying on the model alone.

## Security Design

The project explores the security risks that arise when an AI system can access private information, process untrusted content, and request actions.

### Security controls

- Tool allowlisting to restrict available operations.
- Human approval gates for dangerous containment tools.
- Code-enforced protected asset rules.
- A bounded agent execution budget.
- Context management and truncation of tool results.
- Execution traces for investigation and debugging.
- Synthetic data and mocked containment operations.

### Prompt Injection Testing

The project includes adversarial incidents containing malicious instructions embedded in attacker-controlled fields, such as HTTP user-agent values.

These scenarios attempt to manipulate the agent into requesting unauthorized operations, including host isolation, account disabling, and IP blocking.

The security tests compare behavior with and without the defense layer. The intended security guarantee is that the authorization layer rejects actions against protected assets independently of the model's behavior.

**Safety scope:** All incident data is synthetic, and dangerous containment actions are mocked. The project does not perform real host isolation, account disabling, or network blocking.

## Evaluation and Testing

The evaluation dataset contains 15 synthetic incidents across five categories:

- Account takeover
- Phishing
- Beaconing activity
- False positives
- Prompt injection

Automated graders assess aspects such as severity classification, IOC extraction, requested action, target selection, and resistance to injected instructions.

Two configurations are provided:

- **Configuration A:** Minimal agent instructions.
- **Configuration B:** Full instructions and security guidance from `AGENTS.md`.

Both configurations use the same harness so their behavior can be compared under consistent conditions.

Evaluation results should be added to this README after running the evaluation scripts. No performance improvement is claimed until supported by measured results.

## Project Structure

```text
agent/          Agent loop, harness, and supporting logic
data/           Synthetic incident logs and investigation data
evals/          Evaluation tasks, graders, and evaluation runner
mcp_server/     MCP server for incident log access
security/       Attack scenarios and security testing
tests/          Automated security and behavior tests
traces/         Agent execution traces
web/            Browser frontend
.env.example    Example environment configuration
gen_data.py     Synthetic incident data generator
smoke_test.py   Model connectivity and tool-calling smoke test
webapp.py       FastAPI web application
pyproject.toml  Project dependencies and configuration
uv.lock         Locked dependency versions
```

## Getting Started

### Prerequisites

- Python version compatible with the project dependencies.
- [uv](https://docs.astral.sh/uv/)
- An Ollama installation with a compatible model, or an OpenRouter API key.
- A model that supports the tool/function-calling behavior required by the agent.

### Installation

Clone the repository and enter the project directory:

```bash
git clone https://github.com/uiiv0/AI-Incident-Response-Agent.git
cd AI-Incident-Response-Agent
uv sync
```

Create a local environment file.

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**

```bash
cp .env.example .env
```

Edit `.env` to configure the model provider and the required credentials or endpoint. Keep API keys private and never commit `.env`.

### Run the Checks

Check model connectivity and tool calling:

```bash
uv run python smoke_test.py
```

Run the automated tests:

```bash
uv run pytest -q
```

Generate the synthetic incident dataset if needed:

```bash
uv run python gen_data.py
```

Run an example incident investigation:

```bash
uv run python -m agent.cli INC-001 --prompt B
```

Run the evaluation:

```bash
uv run python -m evals.run_eval --configs A B --k 2
```

Run the prompt injection scenario without the defense layer:

```bash
uv run python -m security.attack --undefended
```

Run the defended scenario:

```bash
uv run python -m security.attack
```

Some commands require a configured, reachable model. Review the project configuration and command output when troubleshooting.

### Launch the Web Interface

Start the FastAPI application:

```bash
uv run uvicorn webapp:app --reload
```

Open the following address in your browser:

http://127.0.0.1:8000

The browser interface communicates with the Python backend. API credentials remain on the server and should not be exposed in frontend code.

## Data Privacy and Responsible Use

All data included in this project is synthetic. In real incident response environments, logs may contain personal information, internal IP addresses, usernames, email addresses, and other sensitive data.

Before deploying a similar system in production, organizations should assess data residency requirements, minimize sensitive fields, enforce access controls, define retention policies, and ensure that model-provider configurations comply with applicable organizational and regulatory requirements, including relevant Saudi data protection requirements where applicable.

This project is a research and learning implementation, not a production-ready incident response platform.

## Learning Reference

This project is informed by concepts explored in SDAIA Academy's agentic AI learning materials:

- [SDAIA Academy — Agentic AI](https://github.com/SDAIAAcademy/agentic-ai)
- [SDAIA Academy — Agentic AI Day 5 Slides](https://sdaiaacademy.github.io/agentic-ai/slides/day5.html#1)

The project is an independent implementation for educational purposes and is not an official SDAIA Academy product.

## Future Improvements

- Add measured evaluation results and compare configurations A and B.
- Document the model provider and inference environment used in experiments.
- Add reproducible attack-versus-defense results and example traces.
- Improve evidence correlation and investigation reporting.
- Expand the synthetic dataset and evaluation coverage.

## Author

This project was developed as part of the Advanced Agentic AI Systems Engineering Program at SDAIA Academy, as a practical application of agentic AI concepts. It applies these concepts to building an intelligent agent for cybersecurity incident investigation, security log analysis, tool orchestration, and the implementation of human approval mechanisms and security controls.
