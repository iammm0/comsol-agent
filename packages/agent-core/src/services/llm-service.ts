export interface LlmCompletionRequest {
  backend: string;
  model: string;
  prompt: string;
  apiKey?: string;
  baseUrl?: string;
  ollamaUrl?: string;
}

export interface LlmCompletionResult {
  ok: boolean;
  text: string;
  error?: string;
}

async function callOllama(request: LlmCompletionRequest): Promise<LlmCompletionResult> {
  const base = request.ollamaUrl ?? "http://localhost:11434";
  const response = await fetch(`${base.replace(/\/$/, "")}/api/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: request.model,
      prompt: request.prompt,
      stream: false
    })
  });

  if (!response.ok) {
    return {
      ok: false,
      text: "",
      error: `Ollama request failed: ${response.status}`
    };
  }

  const payload = (await response.json()) as { response?: string };
  return {
    ok: true,
    text: payload.response ?? ""
  };
}

async function callOpenAiCompatible(request: LlmCompletionRequest): Promise<LlmCompletionResult> {
  if (!request.baseUrl || !request.apiKey) {
    return {
      ok: false,
      text: "",
      error: "baseUrl and apiKey are required for OpenAI-compatible backend"
    };
  }

  const response = await fetch(`${request.baseUrl.replace(/\/$/, "")}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${request.apiKey}`
    },
    body: JSON.stringify({
      model: request.model,
      messages: [{ role: "user", content: request.prompt }],
      temperature: 0.2
    })
  });

  if (!response.ok) {
    return {
      ok: false,
      text: "",
      error: `OpenAI-compatible request failed: ${response.status}`
    };
  }

  const payload = (await response.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };

  return {
    ok: true,
    text: payload.choices?.[0]?.message?.content ?? ""
  };
}

export async function completeText(request: LlmCompletionRequest): Promise<LlmCompletionResult> {
  if (request.backend === "ollama") {
    return callOllama(request);
  }

  if (
    request.backend === "openai-compatible" ||
    request.backend === "deepseek" ||
    request.backend === "kimi"
  ) {
    return callOpenAiCompatible(request);
  }

  return {
    ok: false,
    text: "",
    error: `Unsupported backend: ${request.backend}`
  };
}
