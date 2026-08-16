import { useEffect, useMemo, useRef, useState } from "react";
import Editor, { type Monaco } from "@monaco-editor/react";
import type { editor as MonacoEditorNS } from "monaco-editor";
import { ChevronDown, ChevronRight, FileCode, Folder } from "lucide-react";

import { Badge } from "../../components/common/Badge";
import { GlassPanel } from "../../components/common/GlassPanel";
import { api } from "../../services/api";
import { useReviewStore } from "../../store/reviewStore";
import type { PRFile } from "../../types/domain";

export interface ExplorerTarget {
  file: string;
  line: number | null;
}

interface Props {
  target?: ExplorerTarget | null;
}

interface TreeNode {
  name: string;
  path: string;
  file?: PRFile;
  children: Map<string, TreeNode>;
}

function buildTree(files: PRFile[]): TreeNode {
  const root: TreeNode = { name: "", path: "", children: new Map() };
  for (const f of files) {
    const parts = f.filename.split("/");
    let node = root;
    let pathSoFar = "";
    parts.forEach((part, i) => {
      pathSoFar = pathSoFar ? `${pathSoFar}/${part}` : part;
      let child = node.children.get(part);
      if (!child) {
        child = { name: part, path: pathSoFar, children: new Map() };
        node.children.set(part, child);
      }
      if (i === parts.length - 1) child.file = f;
      node = child;
    });
  }
  return root;
}

const _LANG_BY_EXT: Record<string, string> = {
  py: "python",
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  json: "json",
  md: "markdown",
  sql: "sql",
  yaml: "yaml",
  yml: "yaml",
  html: "html",
  css: "css",
  toml: "ini",
};

function languageFor(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return _LANG_BY_EXT[ext] ?? "plaintext";
}

function FileTree({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: TreeNode;
  depth: number;
  selected: string | null;
  onSelect: (path: string) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const entries = Array.from(node.children.values()).sort((a, b) => {
    const aDir = a.children.size > 0 && !a.file;
    const bDir = b.children.size > 0 && !b.file;
    if (aDir !== bDir) return aDir ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div>
      {entries.map((entry) => {
        const isDir = entry.children.size > 0 && !entry.file;
        if (isDir) {
          return (
            <div key={entry.path}>
              <button
                onClick={() => setCollapsed((c) => !c)}
                className="flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs text-slate-300 hover:bg-mission-panel/60"
                style={{ paddingLeft: 8 + depth * 14 }}
              >
                {collapsed ? <ChevronRight className="h-3 w-3 shrink-0" /> : <ChevronDown className="h-3 w-3 shrink-0" />}
                <Folder className="h-3.5 w-3.5 shrink-0 text-mission-muted" />
                <span className="min-w-0 flex-1 truncate">{entry.name}</span>
              </button>
              {!collapsed && (
                <FileTree node={entry} depth={depth + 1} selected={selected} onSelect={onSelect} />
              )}
            </div>
          );
        }
        const f = entry.file!;
        return (
          <button
            key={entry.path}
            onClick={() => onSelect(f.filename)}
            className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs transition-colors ${
              selected === f.filename ? "bg-mission-accent/10 text-mission-accent" : "text-slate-300 hover:bg-mission-panel/60"
            }`}
            style={{ paddingLeft: 8 + depth * 14 }}
          >
            <FileCode className="h-3.5 w-3.5 shrink-0" />
            <span className="min-w-0 flex-1 truncate">{entry.name}</span>
            <Badge tone={f.status === "added" ? "ok" : f.status === "removed" ? "danger" : "info"}>
              {f.status.slice(0, 1).toUpperCase()}
            </Badge>
          </button>
        );
      })}
    </div>
  );
}

export function CodeExplorerPage({ target }: Props) {
  const reviewId = useReviewStore((s) => s.reviewId);
  const [files, setFiles] = useState<PRFile[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editorRef = useRef<MonacoEditorNS.IStandaloneCodeEditor | null>(null);
  const decorationsRef = useRef<MonacoEditorNS.IEditorDecorationsCollection | null>(null);

  useEffect(() => {
    if (!reviewId) {
      setFiles([]);
      setSelected(null);
      return;
    }
    api
      .getFiles(reviewId)
      .then(setFiles)
      .catch((err) => setError(String(err)));
  }, [reviewId]);

  useEffect(() => {
    if (target?.file) setSelected(target.file);
  }, [target]);

  useEffect(() => {
    if (!reviewId || !selected) {
      setContent(null);
      return;
    }
    setLoading(true);
    setError(null);
    api
      .getFileContent(reviewId, selected)
      .then((res) => setContent(res.content))
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [reviewId, selected]);

  function highlightTarget() {
    const ed = editorRef.current;
    if (!ed || !target?.line || target.file !== selected) return;
    ed.revealLineInCenter(target.line);
    decorationsRef.current?.clear();
    decorationsRef.current = ed.createDecorationsCollection([
      {
        range: { startLineNumber: target.line, startColumn: 1, endLineNumber: target.line, endColumn: 1 },
        options: {
          isWholeLine: true,
          className: "explorer-target-line",
        },
      },
    ]);
  }

  useEffect(() => {
    highlightTarget();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content, target, selected]);

  const tree = useMemo(() => buildTree(files), [files]);

  if (!reviewId) {
    return (
      <GlassPanel title="Code Explorer">
        <p className="text-xs text-mission-muted">Trigger a review to browse its changed files.</p>
      </GlassPanel>
    );
  }

  return (
    <div className="grid h-[calc(100vh-140px)] grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
      <div className="glass-panel overflow-y-auto p-3">
        <div className="mono-label mb-2">Changed Files</div>
        <FileTree node={tree} depth={0} selected={selected} onSelect={setSelected} />
        {files.length === 0 && <p className="text-xs text-mission-muted">No files.</p>}
      </div>

      <div className="glass-panel flex flex-col overflow-hidden p-0">
        <div className="border-b border-mission-border px-3 py-2 text-xs text-mission-muted">
          {selected ?? "Select a file"}
        </div>
        <div className="flex-1 overflow-hidden">
          {loading && <p className="p-4 text-xs text-mission-muted">Loading...</p>}
          {error && <p className="p-4 text-xs text-mission-danger">{error}</p>}
          {!loading && !error && selected && content !== null && (
            <Editor
              height="100%"
              language={languageFor(selected)}
              value={content}
              theme="vs-dark"
              options={{ readOnly: true, minimap: { enabled: false }, fontSize: 12, scrollBeyondLastLine: false }}
              onMount={(editorInstance: MonacoEditorNS.IStandaloneCodeEditor, _monaco: Monaco) => {
                editorRef.current = editorInstance;
                highlightTarget();
              }}
            />
          )}
          {!loading && !error && !selected && (
            <p className="p-4 text-xs text-mission-muted">Select a file from the list to view it.</p>
          )}
        </div>
      </div>
    </div>
  );
}
