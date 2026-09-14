import type { ReactNode } from "react";

/**
 * A small, dependency-free renderer for the subset of Markdown the backend
 * actually produces (headings, bold, bullet lists, checklists, hr,
 * blockquotes). Builds React elements directly rather than dangerously
 * injecting HTML -- there's no untrusted-content risk here (the backend is
 * the only author of these docs), but building elements is just as easy
 * and avoids the whole class of injection risk for free, so there's no
 * reason to reach for dangerouslySetInnerHTML.
 */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*|`(.+?)`/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = regex.exec(text))) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    if (match[1] !== undefined) {
      nodes.push(<strong key={`${keyPrefix}-b-${i++}`}>{match[1]}</strong>);
    } else if (match[2] !== undefined) {
      nodes.push(
        <code key={`${keyPrefix}-c-${i++}`} className="md-inline-code">
          {match[2]}
        </code>,
      );
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

export function MiniMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let listBuffer: string[] = [];
  let key = 0;

  const flushList = () => {
    if (listBuffer.length === 0) return;
    blocks.push(
      <ul className="md-list" key={`ul-${key++}`}>
        {listBuffer.map((item, i) => {
          const checklist = /^\[( |x)\]\s+/.exec(item);
          if (checklist) {
            const checked = checklist[1] === "x";
            const rest = item.slice(checklist[0].length);
            return (
              <li key={i} className="md-checklist-item">
                <input type="checkbox" checked={checked} readOnly /> {renderInline(rest, `li-${i}`)}
              </li>
            );
          }
          return <li key={i}>{renderInline(item, `li-${i}`)}</li>;
        })}
      </ul>,
    );
    listBuffer = [];
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^-{3,}$/.test(line.trim())) {
      flushList();
      blocks.push(<hr className="md-hr" key={`hr-${key++}`} />);
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      flushList();
      const level = heading[1].length;
      const content = renderInline(heading[2], `h-${key}`);
      const Tag = (`h${Math.min(level + 1, 6)}` as unknown) as keyof JSX.IntrinsicElements;
      blocks.push(
        <Tag className={`md-heading md-h${level}`} key={`h-${key++}`}>
          {content}
        </Tag>,
      );
      continue;
    }
    const listItem = /^[-*]\s+(.*)$/.exec(line);
    if (listItem) {
      listBuffer.push(listItem[1]);
      continue;
    }
    flushList();
    if (line.trim() === "") {
      continue;
    }
    blocks.push(
      <p className="md-paragraph" key={`p-${key++}`}>
        {renderInline(line, `p-${key}`)}
      </p>,
    );
  }
  flushList();

  return <div className="mini-markdown">{blocks}</div>;
}
