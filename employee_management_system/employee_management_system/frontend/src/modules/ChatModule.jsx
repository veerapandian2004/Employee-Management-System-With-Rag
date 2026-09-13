import { useState, useEffect, useRef } from "react";
import {
  Bot,
  Send,
  User,
  Sparkles,
  Database,
  Clock,
  AlertCircle,
  Plus,
  MessageSquare,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { MarkdownRenderer } from "../components/ui/MarkdownRenderer";
import {
  apiSendChatMessage,
  apiFetchChatHistory,
  apiFetchChatSessions,
  apiCreateChatSession,
  apiDeleteChatSession,
} from "../services/apiService";

export function ChatModule({ currentUser = {} }) {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState("");
  const messagesEndRef = useRef(null);

  // Load user's chat sessions
  const loadSessions = async () => {
    try {
      const sessList = await apiFetchChatSessions();
      if (Array.isArray(sessList)) {
        setSessions(sessList);
        if (sessList.length > 0 && !currentSessionId) {
          setCurrentSessionId(sessList[0].name);
        }
      }
    } catch (err) {
      console.error("Failed loading chat sessions:", err);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  // Load message history for active session
  useEffect(() => {
    async function loadHistory() {
      setInitialLoading(true);
      try {
        if (!currentSessionId) {
          setMessages([
            {
              sender: "assistant",
              text: `Hello ${currentUser.full_name || "there"}! Ask me any question about employees, departments, leave applications, payroll, or attendance. I will generate the exact SQL query and retrieve the results for you.`,
              sources: "SQL Engine",
              timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            },
          ]);
          return;
        }

        const history = await apiFetchChatHistory(currentSessionId);
        if (history && history.length > 0) {
          const formatted = [];
          history.forEach((h) => {
            const userTxt = h.user_message || h.message;
            const asstTxt = h.assistant_message || h.response;
            const timeVal = h.created_at || h.timestamp || h.creation;

            if (h.message_type === "user") {
              if (userTxt) {
                formatted.push({
                  sender: "user",
                  text: userTxt,
                  timestamp: timeVal,
                });
              }
            } else if (
              h.message_type === "assistant" ||
              h.message_type === "sql" ||
              h.message_type === "clarification" ||
              h.message_type === "error"
            ) {
              if (userTxt && (!formatted.length || formatted[formatted.length - 1].text !== userTxt)) {
                formatted.push({
                  sender: "user",
                  text: userTxt,
                  timestamp: timeVal,
                });
              }
              if (asstTxt) {
                formatted.push({
                  sender: "assistant",
                  text: asstTxt,
                  sources: h.sources || (h.message_type === "sql" ? "MariaDB Database" : "EMS Assistant"),
                  timestamp: timeVal,
                });
              }
            } else {
              if (userTxt) {
                formatted.push({
                  sender: "user",
                  text: userTxt,
                  timestamp: timeVal,
                });
              }
              if (asstTxt) {
                formatted.push({
                  sender: "assistant",
                  text: asstTxt,
                  sources: h.sources,
                  timestamp: timeVal,
                });
              }
            }
          });
          setMessages(formatted);
        } else {
          setMessages([
            {
              sender: "assistant",
              text: `Hello ${currentUser.full_name || "there"}! Ask me any question about employees, departments, leave applications, payroll, or attendance.`,
              sources: "SQL Engine",
              timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            },
          ]);
        }
      } catch (err) {
        console.error("Failed loading chat history:", err);
      } finally {
        setInitialLoading(false);
      }
    }
    loadHistory();
  }, [currentSessionId, currentUser.full_name]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleNewChat = async () => {
    // If the active chat is already fresh and empty (no user messages), avoid creating a duplicate session
    const hasUserMessages = messages.some((m) => m.sender === "user");
    if (!hasUserMessages && currentSessionId) {
      return;
    }

    try {
      const newSess = await apiCreateChatSession("New Chat");
      if (newSess && newSess.name) {
        setSessions((prev) => {
          const exists = prev.some((s) => s.name === newSess.name);
          return exists ? prev : [newSess, ...prev];
        });
        setCurrentSessionId(newSess.name);
      } else {
        setCurrentSessionId(null);
      }
      setMessages([
        {
          sender: "assistant",
          text: `New conversation started! How can I assist you today?`,
          sources: "EMS Assistant",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch (err) {
      console.error("Failed to create new chat session:", err);
      setCurrentSessionId(null);
    }
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    try {
      await apiDeleteChatSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.name !== sessionId));
      if (currentSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.name !== sessionId);
        setCurrentSessionId(remaining.length > 0 ? remaining[0].name : null);
      }
    } catch (err) {
      console.error("Failed to delete chat session:", err);
    }
  };

  const handleSend = async (e, textOverride) => {
    if (e) e.preventDefault();
    const textToSend = (textOverride || inputMessage).trim();
    if (!textToSend || loading) return;

    let activeId = currentSessionId;
    if (!activeId) {
      try {
        const newSess = await apiCreateChatSession(
          textToSend.length > 35 ? textToSend.slice(0, 35) + "..." : textToSend
        );
        if (newSess && newSess.name) {
          activeId = newSess.name;
          setCurrentSessionId(activeId);
          setSessions((prev) => {
            const exists = prev.some((s) => s.name === newSess.name);
            return exists ? prev : [newSess, ...prev];
          });
        }
      } catch (err) {
        console.warn("Could not create session document:", err);
      }
    }

    const userMsg = {
      sender: "user",
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputMessage("");
    setLoading(true);
    setError("");

    try {
      const res = await apiSendChatMessage(textToSend, null, activeId);
      const assistantMsg = {
        sender: "assistant",
        text: res.response || "No response received.",
        sources: res.sources || "MariaDB Database",
        timestamp: res.timestamp || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      // Refresh session title
      loadSessions();
    } catch (err) {
      console.error("Chat message error:", err);
      setError("Failed to get response from assistant. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const isEmployee = currentUser?.role === "Employee";
  const promptSuggestions = isEmployee
    ? [
        "Show my employee profile",
        "Show my leave applications",
        "Show my recent salary slips",
        "Show my attendance record",
      ]
    : [
        "Show all active employees",
        "List pending leave requests",
        "Total salary disbursement by month",
        "Count of employees by department",
        "Show employees with salary > 70000",
        "Show today's attendance",
      ];


  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-5xl mx-auto space-y-4 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-gradient-to-r from-indigo-900/90 via-indigo-800/80 to-purple-900/90 text-white shadow-md border border-indigo-700/40">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-indigo-500/30 border border-indigo-400/30 flex items-center justify-center text-white">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold flex items-center space-x-2">
              <span>SQL Query & Database Assistant</span>
              <Badge className="bg-emerald-500/20 text-emerald-200 border-emerald-500/40 text-[10px]">
                Live SQL Grounded
              </Badge>
            </h2>
            <p className="text-xs text-indigo-200">
              Generates accurate MariaDB SQL queries and retrieves live data for your questions
            </p>
          </div>
        </div>

        {/* Action buttons: + New Chat and Toggle Sessions */}
        <div className="flex items-center space-x-2 self-end sm:self-center">
          <Button
            type="button"
            onClick={handleNewChat}
            className="bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 h-8 rounded-lg shadow-sm flex items-center space-x-1.5 cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>New Chat</span>
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="border-indigo-400/40 bg-indigo-950/40 hover:bg-indigo-900/60 text-indigo-100 text-xs h-8 px-2.5 rounded-lg flex items-center space-x-1 cursor-pointer"
            title={sidebarOpen ? "Hide session history" : "Show session history"}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Sessions ({sessions.length})</span>
          </Button>
        </div>
      </div>

      {/* Main Chat Box Container with optional Sessions Sidebar */}
      <div className="flex-1 flex gap-3 overflow-hidden min-h-0">
        {sidebarOpen && (
          <div className="w-56 sm:w-64 flex flex-col rounded-xl border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md shadow-md p-3 shrink-0 animate-in slide-in-from-left-4 duration-200">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 dark:border-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300">
              <span className="flex items-center space-x-1.5">
                <MessageSquare className="h-3.5 w-3.5 text-indigo-500" />
                <span>Conversations</span>
              </span>
              <button
                type="button"
                onClick={handleNewChat}
                className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 text-[11px] flex items-center space-x-0.5 cursor-pointer"
              >
                <Plus className="h-3 w-3" />
                <span>New</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1 pr-1 text-xs">
              {sessions.length === 0 ? (
                <div className="py-8 text-center text-slate-400 text-[11px]">
                  No previous sessions
                </div>
              ) : (
                sessions.map((s) => (
                  <div
                    key={s.name}
                    onClick={() => setCurrentSessionId(s.name)}
                    className={`group flex items-center justify-between p-2 rounded-lg cursor-pointer transition-all ${
                      currentSessionId === s.name
                        ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300 font-medium"
                        : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    }`}
                  >
                    <span className="truncate pr-1 text-[11px]" title={s.title}>
                      {s.title || "Untitled Session"}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => handleDeleteSession(e, s.name)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-600 text-slate-400 transition-opacity cursor-pointer shrink-0"
                      title="Delete chat session"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Main Chat Box Card */}
        <Card className="flex-1 flex flex-col overflow-hidden border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md shadow-lg min-w-0">
        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
          {initialLoading ? (
            <div className="flex items-center justify-center h-full text-slate-400 text-xs space-x-2">
              <span className="h-4 w-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              <span>Loading conversation...</span>
            </div>
          ) : (
            messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex items-start space-x-3 ${
                  m.sender === "user" ? "flex-row-reverse space-x-reverse" : "flex-row"
                }`}
              >
                <div
                  className={`h-8 w-8 rounded-full flex items-center justify-center shrink-0 shadow-xs ${
                    m.sender === "user"
                      ? "bg-indigo-600 text-white font-bold text-xs"
                      : "bg-slate-100 dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 border border-slate-200 dark:border-slate-700"
                  }`}
                >
                  {m.sender === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                </div>

                <div
                  className={`max-w-[85%] rounded-2xl p-4 text-xs sm:text-sm leading-relaxed shadow-xs ${
                    m.sender === "user"
                      ? "bg-indigo-600 text-white rounded-tr-none"
                      : "bg-slate-50 dark:bg-slate-800/80 text-slate-800 dark:text-slate-100 rounded-tl-none border border-slate-200 dark:border-slate-700/60"
                  }`}
                >
                  {m.sender === "assistant" ? (
                    <MarkdownRenderer content={m.text} />
                  ) : (
                    <div className="whitespace-pre-wrap font-sans">{m.text}</div>
                  )}


                  <div
                    className={`mt-2 pt-2 border-t flex items-center justify-between text-[10px] ${
                      m.sender === "user"
                        ? "border-indigo-500/50 text-indigo-200"
                        : "border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500"
                    }`}
                  >
                    <span className="flex items-center space-x-1">
                      {m.sender === "assistant" && m.sources && (
                        <>
                          <Database className="h-3 w-3 text-indigo-500 shrink-0" />
                          <span>Sources: {m.sources}</span>
                        </>
                      )}
                    </span>
                    <span className="flex items-center space-x-1">
                      <Clock className="h-2.5 w-2.5" />
                      <span>{m.timestamp}</span>
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}

          {loading && (
            <div className="flex items-start space-x-3">
              <div className="h-8 w-8 rounded-full bg-slate-100 dark:bg-slate-800 text-indigo-600 flex items-center justify-center shrink-0 border border-slate-200 dark:border-slate-700">
                <Bot className="h-4 w-4" />
              </div>
              <div className="p-3.5 rounded-2xl rounded-tl-none bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-500 flex items-center space-x-2">
                <span className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
                <span className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse delay-100" />
                <span className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse delay-200" />
                <span className="text-[11px] text-slate-400">Consulting MariaDB database & policy files...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Prompt Suggestions */}
        <div className="px-4 py-2 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex flex-wrap gap-1.5">
          <span className="text-[11px] text-slate-400 font-medium self-center mr-1 flex items-center">
            <Sparkles className="h-3 w-3 text-indigo-500 mr-1" /> Quick questions:
          </span>
          {promptSuggestions.map((prompt, i) => (
            <button
              key={i}
              onClick={() => handleSend(null, prompt)}
              className="text-[11px] px-2.5 py-1 rounded-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:border-indigo-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors cursor-pointer"
            >
              {prompt}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-3 sm:p-4 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          {error && (
            <div className="mb-2 p-2 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-400 text-xs flex items-center space-x-2">
              <AlertCircle className="h-3.5 w-3.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSend} className="flex items-center space-x-2">
            <Input
              placeholder="Ask a database question (e.g. 'Show employees in Engineering', 'Pending leaves')..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              className="flex-1 text-xs sm:text-sm bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700"
              disabled={loading}
            />
            <Button
              type="submit"
              disabled={loading || !inputMessage.trim()}
              className="bg-indigo-600 hover:bg-indigo-700 text-white shrink-0 px-4 cursor-pointer"
            >
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </Card>
    </div>
    </div>
  );
}
