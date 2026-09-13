import { useState } from "react";
import { Copy, Check, Terminal } from "lucide-react";

export function MarkdownRenderer({ content = "" }) {
  if (!content) return null;

  // Split by fenced code blocks: ```[lang] ... ```
  const parts = [];
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({
        type: "text",
        content: content.slice(lastIndex, match.index),
      });
    }
    parts.push({
      type: "code",
      language: match[1] || "sql",
      code: match[2].trim(),
    });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    parts.push({
      type: "text",
      content: content.slice(lastIndex),
    });
  }

  return (
    <div className="space-y-3 text-xs sm:text-sm leading-relaxed overflow-hidden">
      {parts.map((part, index) => {
        if (part.type === "code") {
          return <CodeBlock key={index} code={part.code} language={part.language} />;
        }
        return <TextOrTableBlock key={index} text={part.content} />;
      })}
    </div>
  );
}

function CodeBlock({ code, language }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = code;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const highlightSQL = (text) => {
    const keywords = [
      "SELECT", "FROM", "WHERE", "AND", "OR", "JOIN", "LEFT JOIN", "RIGHT JOIN",
      "INNER JOIN", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "AS", "DESC",
      "ASC", "LIKE", "IN", "IS NULL", "IS NOT NULL", "SUM", "AVG", "COUNT",
      "MIN", "MAX", "ROUND", "CURDATE\\(\\)", "NOT"
    ];
    const regex = new RegExp(`\\b(${keywords.join("|")})\\b`, "gi");

    const segments = [];
    let cur = 0;
    let m;
    while ((m = regex.exec(text)) !== null) {
      if (m.index > cur) {
        segments.push(text.slice(cur, m.index));
      }
      segments.push(
        <span key={m.index} className="text-cyan-400 font-bold dark:text-cyan-300">
          {m[0].toUpperCase()}
        </span>
      );
      cur = m.index + m[0].length;
    }
    if (cur < text.length) {
      segments.push(text.slice(cur));
    }
    return segments;
  };

  return (
    <div className="my-2 rounded-xl overflow-hidden border border-slate-700/80 bg-slate-950 text-slate-100 shadow-md font-mono text-xs">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-900/90 border-b border-slate-800 text-[11px] text-slate-400">
        <div className="flex items-center space-x-1.5 font-semibold text-indigo-300">
          <Terminal className="h-3.5 w-3.5 text-indigo-400" />
          <span>{language ? language.toUpperCase() : "SQL"} Query</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center space-x-1 px-2 py-0.5 rounded-md hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer"
          title="Copy query to clipboard"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span className="text-[10px] text-emerald-400 font-semibold">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span className="text-[10px]">Copy SQL</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto whitespace-pre leading-relaxed text-slate-200">
        <code>{highlightSQL(code)}</code>
      </pre>
    </div>
  );
}

function TextOrTableBlock({ text }) {
  if (!text || !text.trim()) return null;

  const lines = text.split("\n");
  const blocks = [];
  let currentTable = null;
  let textBuffer = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith("|") && line.endsWith("|")) {
      if (textBuffer.length > 0) {
        blocks.push({ type: "prose", content: textBuffer.join("\n") });
        textBuffer = [];
      }
      if (!currentTable) {
        currentTable = [];
      }
      currentTable.push(line);
    } else {
      if (currentTable) {
        blocks.push({ type: "table", lines: currentTable });
        currentTable = null;
      }
      textBuffer.push(lines[i]);
    }
  }

  if (currentTable) {
    blocks.push({ type: "table", lines: currentTable });
  }
  if (textBuffer.length > 0) {
    blocks.push({ type: "prose", content: textBuffer.join("\n") });
  }

  return (
    <>
      {blocks.map((b, idx) => {
        if (b.type === "table") {
          return <MarkdownTable key={idx} lines={b.lines} />;
        }
        return <ProseParagraph key={idx} text={b.content} />;
      })}
    </>
  );
}

function MarkdownTable({ lines }) {
  if (!lines || lines.length < 2) return null;

  const parseRow = (line) => {
    return line
      .slice(1, -1)
      .split("|")
      .map((cell) => cell.trim());
  };

  const header = parseRow(lines[0]);
  const dataRows = lines.slice(2).map(parseRow);

  return (
    <div className="my-2.5 overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 shadow-2xs">
      <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800 text-left text-xs font-sans">
        <thead className="bg-slate-50 dark:bg-slate-800/80">
          <tr>
            {header.map((col, idx) => (
              <th
                key={idx}
                className="px-3 py-2 font-semibold text-slate-700 dark:text-slate-200 capitalize tracking-wider"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
          {dataRows.map((row, rIdx) => (
            <tr
              key={rIdx}
              className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors"
            >
              {row.map((cell, cIdx) => (
                <td key={cIdx} className="px-3 py-1.5 text-slate-600 dark:text-slate-300 font-mono text-[11px]">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProseParagraph({ text }) {
  if (!text || !text.trim()) return null;

  const renderInline = (str) => {
    const parts = [];
    let remaining = str;
    let keyIdx = 0;

    while (remaining.length > 0) {
      const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
      const codeMatch = remaining.match(/`([^`]+)`/);
      const italicMatch = remaining.match(/\*([^*]+)\*/);

      let firstMatch = null;
      let matchType = null;

      if (boldMatch && (!firstMatch || boldMatch.index < firstMatch.index)) {
        firstMatch = boldMatch;
        matchType = "bold";
      }
      if (codeMatch && (!firstMatch || codeMatch.index < firstMatch.index)) {
        firstMatch = codeMatch;
        matchType = "code";
      }
      if (italicMatch && (!firstMatch || italicMatch.index < firstMatch.index)) {
        firstMatch = italicMatch;
        matchType = "italic";
      }

      if (firstMatch) {
        if (firstMatch.index > 0) {
          parts.push(remaining.slice(0, firstMatch.index));
        }
        if (matchType === "bold") {
          parts.push(
            <strong key={keyIdx++} className="font-semibold text-slate-900 dark:text-slate-100">
              {firstMatch[1]}
            </strong>
          );
        } else if (matchType === "code") {
          parts.push(
            <code
              key={keyIdx++}
              className="px-1.5 py-0.5 mx-0.5 rounded-md bg-slate-200 dark:bg-slate-700/80 font-mono text-[11px] text-indigo-600 dark:text-indigo-300"
            >
              {firstMatch[1]}
            </code>
          );
        } else if (matchType === "italic") {
          parts.push(
            <em key={keyIdx++} className="italic text-slate-500 dark:text-slate-400">
              {firstMatch[1]}
            </em>
          );
        }
        remaining = remaining.slice(firstMatch.index + firstMatch[0].length);
      } else {
        parts.push(remaining);
        break;
      }
    }

    return parts;
  };

  const lines = text.split("\n");
  return (
    <div className="space-y-1">
      {lines.map((l, idx) => {
        const trimmed = l.trim();
        if (!trimmed) return <div key={idx} className="h-1" />;
        if (trimmed.startsWith("• ") || trimmed.startsWith("- ")) {
          return (
            <div key={idx} className="flex items-start space-x-2 ml-1">
              <span className="text-indigo-500 font-bold">•</span>
              <span>{renderInline(trimmed.slice(2))}</span>
            </div>
          );
        }
        return <div key={idx}>{renderInline(l)}</div>;
      })}
    </div>
  );
}

