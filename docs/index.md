---
layout: page
title: validtr
---

<div class="vh">

<section class="vh-hero">
  <div class="vh-hero-bg" aria-hidden="true"></div>
  <p class="vh-eyebrow">Agentic harness validation</p>
  <h1 class="vh-title">
    Natural language in.<br />
    <span class="vh-accent">Production-grade stack out.</span>
  </h1>
  <p class="vh-sub">
    Describe a task in plain English. validtr recommends the optimal agent
    harness (LLM, framework, MCP servers, skills), provisions it in Docker,
    executes, generates tests, and scores the result. Below the threshold? It
    adjusts the stack and retries.
  </p>
  <div class="vh-actions">
    <a class="vh-btn vh-btn-primary" href="/validtr/getting-started/overview">Get started →</a>
    <a class="vh-btn" href="/validtr/reference/cli">CLI reference</a>
    <a class="vh-btn" href="https://github.com/AdminTurnedDevOps/validtr">GitHub</a>
  </div>

  <div class="vh-shot vh-reveal">
    <div class="vh-frame">
      <div class="vh-frame-bar">
        <span class="vh-dot"></span><span class="vh-dot"></span><span class="vh-dot"></span>
        <span class="vh-frame-url">localhost:4040</span>
      </div>
      <img src="/ui-dashboard.png" alt="validtr Web UI dashboard: describe a task, pick a provider, run validation, and browse scored runs" loading="lazy" />
    </div>
  </div>
</section>

<section class="vh-flow" aria-label="validtr pipeline">
  <div class="vh-flow-head">
    <span class="vh-flow-label">Input</span>
    <span class="vh-flow-label">The validtr pipeline</span>
    <span class="vh-flow-label">Output</span>
  </div>
  <div class="vh-flow-track">
    <div class="vh-io">Plain-English<br />task</div>
    <div class="vh-wire"><span></span></div>
    <div class="vh-stage">
      <div class="vh-step"><b>1</b> Analyze</div>
      <div class="vh-step"><b>2</b> Recommend</div>
      <div class="vh-step"><b>3</b> Provision</div>
      <div class="vh-step"><b>4</b> Execute</div>
      <div class="vh-step"><b>5</b> Test</div>
      <div class="vh-step"><b>6</b> Score</div>
      <div class="vh-retry">↺ retry &lt; threshold</div>
    </div>
    <div class="vh-wire"><span></span></div>
    <div class="vh-io vh-io-out">Validated<br />harness</div>
  </div>
</section>

<section class="vh-demo">
  <p class="vh-eyebrow">See it in action</p>
  <h2 class="vh-h2">From prompt to validated harness</h2>
  <div class="vh-frame vh-frame-video">
    <div class="vh-frame-bar">
      <span class="vh-dot"></span><span class="vh-dot"></span><span class="vh-dot"></span>
      <span class="vh-frame-url">localhost:4040</span>
    </div>
    <video autoplay loop muted playsinline poster="/ui-dashboard-empty.png">
      <source src="/demo-a.mp4" type="video/mp4" />
    </video>
  </div>
</section>

<section class="vh-demo">
  <p class="vh-eyebrow">Scored, end to end</p>
  <h2 class="vh-h2">Every run, scored and projected</h2>
  <div class="vh-frame">
    <div class="vh-frame-bar">
      <span class="vh-dot"></span><span class="vh-dot"></span><span class="vh-dot"></span>
      <span class="vh-frame-url">validtr run</span>
    </div>
    <img src="/cli-output.png" alt="validtr CLI output: best stack found, validation score breakdown, and harness token projection" loading="lazy" />
  </div>
</section>

<section class="vh-bento">
  <a class="vh-card" href="/validtr/reference/recommendation">
    <div class="vh-ico">◈</div>
    <h3>Harness recommendation</h3>
    <p>Web search + MCP registry + skills + LLM reasoning pick the LLM, framework, MCP servers, and skills for each task.</p>
  </a>
  <a class="vh-card" href="/validtr/reference/execution-runtime">
    <div class="vh-ico">▣</div>
    <h3>Containerized execution</h3>
    <p>Each run executes in an isolated, resource-limited Docker container; tests run in a separate sandbox.</p>
  </a>
  <a class="vh-card" href="/validtr/concepts/scoring">
    <div class="vh-ico">◆</div>
    <h3>Test · score · retry</h3>
    <p>Generates tests from the spec, computes a composite score, and iterates until the threshold or attempt limit.</p>
  </a>
  <a class="vh-card" href="/validtr/concepts/pipeline">
    <div class="vh-ico">≣</div>
    <h3>Token &amp; cost projection</h3>
    <p>Projects token usage and cost across Light / Standard / Heavy workflows for the validated harness.</p>
  </a>
</section>

<section class="vh-start">
  <h2 class="vh-start-title">Start here</h2>
  <div class="vh-start-grid">
    <a class="vh-mini" href="/validtr/getting-started/overview">
      <p class="vh-mini-eyebrow">New user path</p>
      <h3>Understand validtr</h3>
      <p>The high-level architecture and workflow before your first run.</p>
    </a>
    <a class="vh-mini" href="/validtr/getting-started/quickstart">
      <p class="vh-mini-eyebrow">Fastest path</p>
      <h3>Run a task in minutes</h3>
      <p>Start the engine, run a task, inspect the scored output with retries.</p>
    </a>
    <a class="vh-mini" href="/validtr/reference/commands/index">
      <p class="vh-mini-eyebrow">CLI guide</p>
      <h3>Browse all commands</h3>
      <p>Docs for <code>run</code>, <code>mcp</code>, <code>config</code>, <code>completion</code>, <code>help</code>.</p>
    </a>
    <a class="vh-mini" href="/validtr/reference/api">
      <p class="vh-mini-eyebrow">Engine API</p>
      <h3>Inspect contracts</h3>
      <p>Endpoints, payload fields, examples, and error behavior.</p>
    </a>
  </div>
</section>

</div>
