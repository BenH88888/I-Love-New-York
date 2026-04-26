/**
 * Chat component — only rendered when USE_LLM = True in routes.py.
 *
 * Shows a message history and a chat input bar at the bottom.
 * When the backend returns a search_term event, it calls onSearchTerm
 * to update the search bar and results above.
 */
import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
  modifiedQuery?: string;
}

interface ChatProps {
  onSearchTerm: (query: string) => void;
  baseModel: string;
  useSVD: boolean;
}

export default function Chat({ onSearchTerm, baseModel, useSVD }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setLoading(true);

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", modifiedQuery: undefined },
    ]);

    abortRef.current = new AbortController();

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, baseModel: baseModel, useSVD:useSVD }),
        signal: abortRef.current.signal,
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const raw = line.slice(5).trim();
          if (raw === "[DONE]") {
            setLoading(false);
            continue;
          }

          let payload: any;
          try {
            payload = JSON.parse(raw);
          } catch {
            continue;
          }

          if (payload.modified_query) {
            onSearchTerm(payload.modified_query);

            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  modifiedQuery: payload.modified_query,
                };
              }
              return updated;
            });
          }

          if (payload.content) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + payload.content,
                };
              }
              return updated;
            });
          }

          if (payload.error) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: "Sorry, something went wrong. Please try again.",
                };
              }
              return updated;
            });
            setLoading(false);
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: "Connection error. Please try again.",
            };
          }
          return updated;
        });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
  <div className="chat-shell-inner">
    


      {messages.length > 0 && (
      <div id="messages">
      

      {messages.map((msg, i) => (
        <div key={i} className={`msg-row ${msg.role === "user" ? "user" : ""}`}>
          <div className={`msg-avatar ${msg.role === "user" ? "user-av" : "ai-av"}`}>
            {msg.role === "user" ? "👤" : "✨"}
          </div>
          <div className={`bubble ${msg.role === "user" ? "user" : "ai"}`}>
            {msg.role === "assistant" && msg.modifiedQuery && (
              <div className="rag-tag">
                🔍 IR: {msg.modifiedQuery}
              </div>
            )}
            <p>{msg.content}</p>
            {msg.role === "assistant" && msg.content === "" && loading && i === messages.length - 1 && (
              <div className="loading-indicator visible">
                <div className="loading-dot" />
                <div className="loading-dot" />
                <div className="loading-dot" />
              </div>
            )}
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />
      </div>
    )}
    

    <div className="chat-bar">
      <div className="input-wrap">
        <input
          placeholder="Ask about places in New York..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          disabled={loading}
        />
      </div>
      <button className="send-btn" onClick={sendMessage} disabled={loading}>
        ➤
      </button>
    </div>
  </div>

  );
}