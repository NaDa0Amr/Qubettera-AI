# Week 2 — Intelligent Agent Framework

## Agent Architecture, Personas & Memory

## 1. Overview

This week you will build the **intelligent agent framework** that will power the multi-agent simulation in the following weeks.

The goal is to transform the knowledge infrastructure from Week 1 into a system of configurable AI agents that can:

1. Represent different personas.
2. Maintain memory across interactions.
3. Access external tools.
4. Use the Week 1 retrieval system as a knowledge source.
5. Generate an initial opinion grounded in retrieved evidence.
6. Produce behavior that differs meaningfully between personas.

By the end of the week, you should have a reusable agent framework capable of creating multiple distinct agents from configuration.

These agents will become the participants in the multi-agent discussion system developed in **Week 3**.

---

# 2. Why This Matters

The knowledge infrastructure from Week 1 provides access to information, but information retrieval alone does not create an intelligent participant.

The next step is to build agents that can:

* interpret retrieved information,
* operate according to different perspectives,
* maintain context,
* use tools,
* and form grounded opinions.

In Week 3, multiple instances of these agents will interact with one another in a structured discussion.

The quality of the discussion will therefore depend heavily on the quality and flexibility of the agent framework you build this week.

The objective is not simply to create a chatbot.

You are building a **reusable agent abstraction** that can support many different personas and can later participate in a multi-agent system.

---

# 3. The Problem

Build a configurable AI agent framework capable of representing different personas.

Each agent should be defined by configuration rather than requiring a completely separate implementation.

For example, the same underlying agent framework should be capable of representing:

```text
Agent A
    Different background
    Different stance
    Different communication style

Agent B
    Different background
    Different stance
    Different communication style
```

The underlying implementation should remain reusable.

The exact architecture is your responsibility.

---

# 4. What You Need to Build

Your implementation must provide the following capabilities:

### 4.1 Configurable personas

Agents must be configurable so that multiple agents can have meaningfully different identities, backgrounds, stances, or behavioral characteristics.

### 4.2 Persistent memory

Agents must maintain information across interactions.

### 4.3 Tool access

Agents must have access to tools through a defined mechanism.

### 4.4 Retrieval integration

Agents must be able to access the retrieval system developed in Week 1.

### 4.5 Initial opinion generation

Each configured agent must be able to generate an initial opinion about a selected topic.

The initial opinion must be grounded in information retrieved from the Week 1 knowledge base.

### 4.6 LLM integration

Your framework must use an LLM to generate agent responses and opinions.

You must select and document the provider/model used.

---

# 5. Agent Model

Your implementation should conceptually support an agent with the following capabilities:

```text
                    ┌──────────────────┐
                    │      Agent       │
                    ├──────────────────┤
                    │ Persona          │
                    │ Memory           │
                    │ Tools            │
                    │ LLM              │
                    │ Retrieval        │
                    └──────────────────┘
```

This diagram describes the required **capabilities**, not a required software architecture.

You may implement these components as:

* Classes
* Modules
* Services
* Functions
* Framework abstractions
* Another architecture

The choice is yours.

---

# 6. Persona Configuration

Agents must be configurable.

A persona should contain enough information to produce meaningfully different agent behavior.

Possible persona characteristics include:

* Name
* Background
* Stance
* Communication style
* Expertise
* Priorities
* Other behavioral characteristics

These are examples rather than a mandatory schema.

You should design a persona representation that makes sense for your implementation.

---

## Requirements

Your framework must support:

* At least **two distinct personas**.
* Creating agents from persona configuration.
* Different behavior between the configured agents.
* Reusing the same underlying agent implementation for different personas.

### Acceptance criterion

Given two different persona configurations, the system should produce two agents whose responses demonstrate meaningful differences attributable to their configured personas.

The difference should not simply be the agent's name.

Document how persona information influences the generated behavior.

---

# 7. Memory

Agents need to maintain context across interactions.

Implement a memory mechanism that allows an agent to retain relevant information from previous interactions.

The exact implementation is up to you.

Possible approaches include:

* Conversation history
* Structured memory
* Summarized memory
* Persistent storage
* Vector-based memory
* Another appropriate mechanism

You may use an existing framework or build your own.

---

## Requirements

Your agent must be able to:

1. Receive an interaction.
2. Store or otherwise retain relevant information.
3. Receive a later interaction.
4. Use information from the earlier interaction when generating its response.

### Acceptance criterion

Demonstrate that an agent can remember information introduced during an earlier interaction and use it appropriately in a later interaction.

Your demonstration should clearly distinguish between:

```text
Interaction 1
    Information introduced

Interaction 2
    Agent uses information from Interaction 1
```

Document the memory strategy you selected and its limitations.

---

# 8. Tool System

Agents must have access to tools through a defined mechanism.

A tool represents an external capability that the agent can invoke when needed.

Examples could include:

* Knowledge retrieval
* Search
* Calculation
* Data lookup
* Another domain-specific operation

The Week 1 retrieval system should be treated as one of the important tools available to the agent.

---

## Requirements

Your framework must:

* Define how tools are represented.
* Allow an agent to access tools.
* Allow the agent to invoke an appropriate tool when needed.
* Return the tool result to the agent.
* Make the tool result available to the agent's reasoning/generation process.

The exact tool architecture is your choice.

---

## Tool design

You should document:

* How tools are registered.
* How tools are described to the agent.
* How tool inputs are represented.
* How tool outputs are represented.
* How tool errors are handled.

---

## Acceptance criterion

Demonstrate an agent successfully invoking at least one tool and using the returned information in its response.

The Week 1 retrieval system should be integrated as a usable knowledge-access mechanism.

---

# 9. Week 1 Retrieval Integration

The agents must be able to use the retrieval system developed during Week 1.

The retrieval system should be treated as a dependency rather than duplicated inside this repository.

The agent should be capable of:

```text
User / Task
     │
     ▼
   Agent
     │
     ▼
Retrieval Request
     │
     ▼
Week 1 Knowledge Infrastructure
     │
     ▼
Relevant Sources / Chunks
     │
     ▼
   Agent
     │
     ▼
Grounded Response
```

The exact integration mechanism is your choice.

You may use:

* A Python interface
* An HTTP API
* Another documented service interface
* Another appropriate integration mechanism

Do not duplicate the entire Week 1 ingestion pipeline inside this repository.

---

## Acceptance criterion

Given a topic or question, an agent must be able to:

1. Identify or receive the topic.
2. Access relevant information through the Week 1 retrieval system.
3. Use retrieved information when forming its response.
4. Preserve source information where appropriate.

---

# 10. Initial Opinion Generation

The most important output of this week is the agent's **initial opinion**.

For each configured persona, the system should be able to generate an initial opinion about a selected topic.

The opinion must be grounded in the knowledge retrieved from Week 1.

---

## Required behavior

Given:

```text
Topic
+
Persona configuration
+
Knowledge available through Week 1
```

the system should produce:

```text
Initial opinion
+
Supporting retrieved information / sources
```

---

## Requirements

At least two distinct personas must generate initial opinions about the same topic.

The opinions should demonstrate meaningful differences resulting from their persona configurations.

Each opinion must be grounded in at least one relevant retrieved source.

---

## Acceptance criteria

You should be able to demonstrate:

### Persona A

```text
Topic
    ↓
Retrieval
    ↓
Relevant evidence
    ↓
Agent A
    ↓
Initial opinion
```

### Persona B

```text
Topic
    ↓
Retrieval
    ↓
Relevant evidence
    ↓
Agent B
    ↓
Initial opinion
```

The two agents should not simply produce identical responses with different names.

---

# 11. LLM Provider and Model

You must select an LLM provider and model for your agents.

Possible providers include:

* OpenAI
* Anthropic
* Google
* Local/open-source models
* Another appropriate provider

The provider itself is not prescribed.

Your choice should consider:

* Response quality
* Cost
* Latency
* Context window
* Tool-calling capabilities
* Availability
* Hardware requirements
* Reliability

---

## Requirements

Document:

```text
Provider:
Model:
Reason for selection:
Important configuration:
```

If you use an API-based provider:

* Do not commit API keys.
* Store credentials through environment variables or another secure configuration mechanism.
* Document the required environment variables.

---

# 12. Prompt Design

Your agent behavior will depend significantly on prompt design.

You are responsible for designing the prompts necessary to:

* Establish persona behavior.
* Provide task instructions.
* Incorporate retrieved context.
* Incorporate memory.
* Handle tool results.
* Generate the initial opinion.

The exact prompt structure is your choice.

---

## Requirements

Your documentation should explain:

* How persona information reaches the model.
* How retrieved context reaches the model.
* How memory is incorporated.
* How tool results are incorporated.
* Any important prompt-design decisions.

Do not hard-code behavior for the individual personas in a way that prevents the framework from supporting new personas.

The goal is a **general agent framework**, not two manually scripted agents.

---

# 13. Agent Architecture

You are free to choose the architecture of your agent framework.

Possible approaches include:

* Custom implementation
* LangChain
* Another agent framework
* A lightweight LLM wrapper
* Another architecture you can justify

Framework choice is not the goal of the assignment.

The important question is:

> Can your architecture support configurable agents with memory, tools, retrieval, and distinct behavior?

---

## Architecture documentation

Your documentation should include a simple architecture diagram showing the major components and their relationships.

For example:

```text
                    ┌───────────────┐
                    │   Persona     │
                    └───────┬───────┘
                            │
                            ▼
┌─────────────┐      ┌───────────────┐
│   Memory    │◄────►│     Agent     │
└─────────────┘      └───────┬───────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
              ┌──────────┐      ┌──────────┐
              │  Tools   │      │ Retrieval│
              └──────────┘      └─────┬────┘
                                      │
                                      ▼
                              Week 1 Knowledge
```

This is an example only.

Your actual architecture should reflect your implementation.

---

# 14. Constraints

The following requirements are mandatory.

### Required

* At least two configurable personas.
* Reusable agent implementation.
* Persistent memory across interactions.
* Tool access.
* Week 1 retrieval integration.
* LLM-powered generation.
* Initial opinion generation.
* At least one retrieved source supporting each initial opinion.
* Documentation of architecture and major design decisions.
* No secrets committed to the repository.

### Not prescribed

The following are intentionally left open:

* Agent class structure.
* Persona schema.
* Memory implementation.
* Tool framework.
* LLM provider.
* LLM model.
* Prompt architecture.
* Agent framework.
* Internal directory structure.
* Communication protocol.

---

# 15. Suggested Repository Structure

The repository intentionally contains minimal scaffolding.

A possible starting structure is:

```text
.
├── README.md
├── .gitignore
├── .env.example
├── requirements.txt
│
├── personas/
│   └── .gitkeep
│
├── prompts/
│   └── .gitkeep
│
├── docs/
│   └── .gitkeep
│
├── src/
│   └── .gitkeep
│
├── tests/
│   └── .gitkeep
│
└── outputs/
    └── .gitkeep
```

This structure is only a starting point.

You may reorganize the repository according to your architecture.

For example, you may introduce components for:

* agents
* memory
* tools
* retrieval
* configuration
* providers
* evaluation
* experiments

Do not feel obligated to follow the suggested structure if another organization is more appropriate.

---

# 16. Configuration

Your repository should include an example environment configuration:

```text
.env.example
```

Do not commit:

* API keys
* Passwords
* Database credentials
* Private tokens
* Other secrets

If Week 1's retrieval system requires database credentials or service configuration, document how your Week 2 system connects to it.

---

# 17. Testing Requirements

Your implementation should contain tests or reproducible checks for the major capabilities.

At minimum, demonstrate the following.

### Persona test

Two persona configurations produce meaningfully different behavior.

### Memory test

Information from an earlier interaction can be used in a later interaction.

### Tool test

An agent can invoke a tool and use its result.

### Retrieval test

The agent can successfully access Week 1 retrieval.

### Opinion test

At least two personas can generate grounded initial opinions about the same topic.

The exact testing framework is your choice.

The tests should focus on **behavior**, not internal implementation details.

---

# 18. Acceptance Criteria

The week is considered complete when all of the following are satisfied.

## Persona system

* [ ] At least two distinct personas are implemented.
* [ ] Personas are configurable.
* [ ] The same underlying agent framework can support different personas.
* [ ] Persona differences produce meaningful behavioral differences.

## Memory

* [ ] The agent maintains information across interactions.
* [ ] A later interaction can use information from an earlier interaction.
* [ ] The memory strategy is documented.
* [ ] Known memory limitations are documented.

## Tools

* [ ] A tool interface/mechanism exists.
* [ ] At least one tool can be invoked successfully.
* [ ] Tool results can influence agent output.
* [ ] Tool registration/invocation is documented.

## Retrieval

* [ ] The Week 1 retrieval system is integrated.
* [ ] Agents can query the knowledge base.
* [ ] Retrieved information can be incorporated into generation.
* [ ] Source information is preserved where appropriate.

## Initial opinions

* [ ] At least two personas generate opinions about the same topic.
* [ ] Each opinion is grounded in retrieved information.
* [ ] At least one supporting source is associated with each opinion.
* [ ] Persona differences are reflected in the resulting opinions.

## LLM

* [ ] An LLM provider/model has been selected.
* [ ] The choice is documented.
* [ ] Credentials are handled securely.
* [ ] The model can successfully generate agent responses.

## Architecture

* [ ] The overall architecture is documented.
* [ ] Major design decisions are explained.
* [ ] The framework can support additional personas without rewriting the entire agent implementation.

## Reproducibility

* [ ] Setup instructions are complete.
* [ ] Dependencies are documented.
* [ ] Required environment variables are documented.
* [ ] A reviewer can reproduce the core demonstration.

---

# 19. Expected Deliverables

At the end of the week, your repository should contain:

### 1. Agent framework

A reusable implementation capable of creating configurable agents.

### 2. Persona configurations

At least two meaningfully different personas.

### 3. Memory system

A working mechanism for retaining information across interactions.

### 4. Tool system

A mechanism allowing agents to invoke external capabilities.

### 5. Retrieval integration

Working integration with the Week 1 knowledge infrastructure.

### 6. Initial opinions

Grounded initial opinions from at least two personas discussing the same topic.

### 7. Architecture documentation

A clear explanation of your implementation and major design decisions.

### 8. Demonstration

A reproducible demonstration showing:

```text
Persona
   ↓
Agent
   ↓
Retrieve Knowledge
   ↓
Use Memory / Tools
   ↓
Generate Initial Opinion
```

---

# 20. Documentation Requirements

Your README and supporting documentation should allow another developer to understand your system without reading every source file.

At minimum document:

## Architecture

Explain the major components and how they interact.

## Persona design

Explain:

* Persona representation.
* How persona information affects behavior.
* How new personas can be added.

## Memory

Explain:

* What is stored.
* Where it is stored.
* How it is retrieved.
* How long it persists.
* Important limitations.

## Tools

Explain:

* How tools are defined.
* How tools are registered.
* How agents invoke them.
* How results are returned.

## Retrieval

Explain:

* How the Week 1 system is accessed.
* What the retrieval interface expects.
* What the agent receives from retrieval.

## LLM

Explain:

* Provider.
* Model.
* Important configuration.
* Why it was selected.

## Prompt design

Explain the major decisions behind your prompts.

## Limitations

Document known weaknesses and areas you would improve with additional time.

---

# 21. Reviewer Reproduction

Your README must contain exact commands for reproducing the core demonstration.

A reviewer should be able to:

1. Install dependencies.
2. Configure the environment.
3. Connect to the Week 1 retrieval system.
4. Create/load the personas.
5. Run the agent.
6. Generate initial opinions.
7. Verify the retrieved evidence.
8. Demonstrate memory.
9. Demonstrate tool usage.

Your actual commands depend on your implementation.

For example:

```bash
# Install dependencies
...

# Configure environment
...

# Start required services
...

# Run the agent demonstration
...

# Run tests
...
```

Replace the placeholders with the actual commands used by your project.

---

# 22. Final Demonstration

Your final demonstration should show the system working rather than simply showing source code.

At minimum demonstrate:

### Step 1 — Create agents

Create at least two agents using different persona configurations.

### Step 2 — Provide a topic

Give both agents the same topic.

### Step 3 — Retrieve knowledge

Show that the agents can access relevant information from the Week 1 knowledge infrastructure.

### Step 4 — Generate opinions

Generate an initial opinion for each persona.

### Step 5 — Show grounding

Show the retrieved source(s) supporting the opinions.

### Step 6 — Demonstrate memory

Show that an agent can retain and use information from a previous interaction.

### Step 7 — Demonstrate a tool

Show an agent successfully invoking a tool and using the result.

---

# 23. Design Decisions

A major part of this week's work is learning to make architectural decisions.

You should be prepared to justify:

### Why this LLM?

What made your selected model/provider appropriate?

### Why this memory design?

Why does your memory mechanism fit the expected use case?

### Why this tool architecture?

How can your framework support additional tools later?

### Why this persona representation?

How does it enable meaningful behavioral differences?

### Why this agent architecture?

Why did you choose your framework or custom implementation?

### How does the system scale?

What would happen if the project needed:

* 10 agents?
* 50 agents?
* More tools?
* More personas?
* Longer interactions?

You don't need to solve all of these problems now.

You should, however, be able to identify the architectural limitations of your current design.

---
# 24. Learning Resources

The following resources support the concepts and implementation tasks in this week. **Required** resources should be studied as part of the week's work; optional resources provide additional explanations or alternative implementation approaches.

## Required Resources

### OpenRouter API Integration in Python

**Study time:** ~30 minutes

https://www.datacamp.com/tutorial/openrouter

**Relevant to:**

* Researching LLM provider options.
* Understanding OpenRouter integration.
* Implementing LLM access within the agent framework.

This resource provides a practical integration pattern for using OpenRouter from Python.

---

### Using Ollama with Python — Function Calling

**Study time:** ~25 minutes

https://cohorte.co/blog/using-ollama-with-python-step-by-step-guide

**Relevant to:**

* Researching LLM provider options.
* Understanding local-model function calling.
* Designing the agent architecture.

This is particularly relevant if you choose Ollama for cost or latency reasons.

---

### Beginner's Tutorial for Claude API Python

**Study time:** Not specified in the source document.

**Relevant to:**

* Researching LLM provider options.
* Implementing tools.

The Week 2 resource-to-checkpoint mapping identifies this as a **required** resource, although the source section does not provide its URL or study-time estimate.

---

### LangChain Deep Agent Memory Docs

**Study time:** ~30 minutes

https://docs.langchain.com/oss/python/deepagents/memory

**Relevant to:**

* Implementing agent memory.
* Understanding concrete memory patterns for agents.

This resource directly supports the agent-memory implementation task.

---

## Optional Resources

### LangChain and OpenRouter Setup

**Study time:** ~20 minutes

https://medium.com/@vinod.work/langchain-and-openrouter-in-python-90cfc16050b5

**Relevant to:**

* Implementing tools.
* Integrating LangChain with OpenRouter.

This is a supplementary integration walkthrough if you choose to use LangChain with OpenRouter.

---

### AI Agents Explained — Arabic Video

**Study time:** ~25 minutes

https://www.youtube.com/watch?v=VzMkFbWt7Uc

**Relevant to:**

* Understanding AI agent concepts.
* Designing the agent architecture.

This provides a bilingual conceptual overview of agents and can be useful before beginning implementation.

---

### Building AI Agents from Scratch — English Video

**LangChain Full Crash Course - AI Agents in Python**

**Study time:** ~40 minutes

**Relevant to:**

* Designing the agent architecture.
* Creating agent personas.

This is a supplementary step-by-step build-along resource for the architecture and persona tasks.

---

## Resource-to-Task Mapping

| Resource                                         | Relevant Task(s)                              | Required? |
| ------------------------------------------------ | --------------------------------------------- | --------- |
| OpenRouter API Integration in Python             | Research providers; Implement tools           | Yes       |
| Using Ollama with Python (Function Calling)      | Research providers; Design agent architecture | Yes       |
| Beginner's Tutorial for Claude API Python        | Research providers; Implement tools           | Yes       |
| LangChain Deep Agent Memory Docs                 | Implement agent memory                        | Yes       |
| LangChain and OpenRouter Setup                   | Implement tools                               | Optional  |
| AI Agents Explained (Arabic, Video)              | Design agent architecture                     | Optional  |
| Building AI Agents from Scratch (English, Video) | Design agent architecture; Create personas    | Optional  |

The resource-to-checkpoint mapping above follows the mapping provided in the Week 2 source document.
---
# 25. Handoff to Week 3

Week 3 will use the agents created during this week as participants in a multi-agent discussion.

Your Week 2 implementation should therefore make it possible for another component to:

1. Create/load an agent.
2. Provide it with a task or message.
3. Allow it to access its persona.
4. Allow it to access its memory.
5. Allow it to use available tools.
6. Allow it to access the Week 1 knowledge infrastructure.
7. Receive a generated response.

The exact interface is your choice.

However, document it clearly.

At minimum explain:

```text
Agent creation:
    How is an agent configured?

Input:
    What does an agent receive?

Output:
    What does an agent return?

Memory:
    How is conversation state maintained?

Tools:
    How are tools exposed?

Retrieval:
    How is the Week 1 knowledge base accessed?
```

The Week 3 discussion system should not need to understand your internal implementation.

---

# 26. Engineering Mindset

There is intentionally no single correct implementation for this week.

A strong solution should demonstrate that you understand the difference between:

```text
Persona
    ≠
Prompt
```

and:

```text
Agent
    ≠
LLM API call
```

A useful agent framework should provide a reusable abstraction around:

```text
Persona
   +
Memory
   +
Tools
   +
Knowledge
   +
LLM
   =
Agent
```

The exact way you implement this is up to you.

Do not optimize for building the largest framework possible.

Prefer an architecture that is:

* Clear
* Reusable
* Testable
* Extensible
* Reasonably simple
* Appropriate for the project's requirements

---

# 26. Definition of Done

You are done when you can demonstrate the following end-to-end flow:

```text
                  ┌─────────────────┐
                  │ Persona Config  │
                  └────────┬────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Agent    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
          ┌────────┐  ┌─────────┐  ┌──────────┐
          │ Memory │  │  Tools  │  │ Retrieval│
          └────────┘  └─────────┘  └────┬─────┘
                                        │
                                        ▼
                                Week 1 Knowledge
                                        │
                                        ▼
                                  Relevant Evidence
                                        │
                                        ▼
                                  ┌───────────┐
                                  │    LLM    │
                                  └─────┬─────┘
                                        │
                                        ▼
                                Initial Opinion
```

At minimum, your demonstration should show:

* Two distinct personas.
* Persistent memory.
* Tool usage.
* Week 1 retrieval.
* Grounded initial opinions.
* Meaningful behavioral differences between personas.

Your completed framework will become the foundation for the **multi-agent discussion system in Week 3**.
