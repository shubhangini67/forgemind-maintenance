"use client";

import Link from "next/link";

interface Props {
  content: string;
  className?: string;
}

function parseInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const pattern = /(\*\*(.*?)\*\*|\[([^\]]+)\]\(([^)]+)\))/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let idx = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(<span key={`${keyPrefix}-t-${idx++}`}>{text.slice(last, match.index)}</span>);
    }
    if (match[2] !== undefined) {
      nodes.push(
        <strong key={`${keyPrefix}-b-${idx++}`} className="font-semibold text-tata-ink">
          {match[2]}
        </strong>
      );
    } else if (match[3] !== undefined && match[4] !== undefined) {
      const label = match[3];
      const href = match[4];
      const isInternal = href.startsWith("/");
      if (isInternal) {
        nodes.push(
          <Link
            key={`${keyPrefix}-l-${idx++}`}
            href={href}
            className="font-medium text-tata-blue underline decoration-tata-blue/40 underline-offset-2 transition hover:text-tata-blue-dark hover:decoration-tata-blue"
          >
            {label}
          </Link>
        );
      } else {
        nodes.push(
          <a
            key={`${keyPrefix}-a-${idx++}`}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-tata-blue underline decoration-tata-blue/40 underline-offset-2 transition hover:text-tata-blue-dark"
          >
            {label}
          </a>
        );
      }
    }
    last = match.index + match[0].length;
  }

  if (last < text.length) {
    nodes.push(<span key={`${keyPrefix}-t-${idx}`}>{text.slice(last)}</span>);
  }
  return nodes.length ? nodes : [<span key={`${keyPrefix}-empty`}>{text}</span>];
}

export function MarkdownRenderer({ content, className = "" }: Props) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line) {
      elements.push(<div key={i} className="h-2" />);
      i++;
      continue;
    }
    if (/^## (.+)/.test(line)) {
      elements.push(
        <h3 key={i} className="mt-3 mb-1 text-sm font-bold text-tata-blue">
          {line.replace(/^## /, "")}
        </h3>
      );
      i++;
      continue;
    }
    if (/^### (.+)/.test(line)) {
      elements.push(
        <h4 key={i} className="mt-2 mb-1 text-sm font-semibold text-tata-ink/80">
          {line.replace(/^### /, "")}
        </h4>
      );
      i++;
      continue;
    }
    if (/^\d+[.)]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+[.)]\s/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+[.)]\s/, ""));
        i++;
      }
      elements.push(
        <ol key={`ol-${i}`} className="my-2 space-y-1">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-tata-ink/80">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-tata-blue-pale text-xs font-medium text-tata-blue">
                {idx + 1}
              </span>
              <span>{parseInline(item, `ol-${idx}`)}</span>
            </li>
          ))}
        </ol>
      );
      continue;
    }
    if (/^[-*•]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*•]\s/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*•]\s/, ""));
        i++;
      }
      elements.push(
        <ul key={`ul-${i}`} className="my-2 space-y-1.5">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-tata-ink/80">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-tata-blue" />
              <span>{parseInline(item, `ul-${idx}`)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }
    if (/^[-=]>\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-=]>\s/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-=]>\s/, ""));
        i++;
      }
      elements.push(
        <ul key={`arr-${i}`} className="my-2 space-y-1">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-tata-ink/70">
              <span className="text-tata-blue">›</span>
              <span>{parseInline(item, `arr-${idx}`)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }
    // Standalone link line → render as a prominent CTA button
    const ctaMatch = line.match(/^\[([^\]]+)\]\(([^)]+)\)\s*$/);
    if (ctaMatch) {
      const label = ctaMatch[1];
      const href = ctaMatch[2];
      const isInternal = href.startsWith("/");
      const cls =
        "my-1.5 inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-tata-blue to-[#0078d4] px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition hover:shadow-md";
      elements.push(
        isInternal ? (
          <Link key={i} href={href} className={cls}>
            {label}
            <span aria-hidden>→</span>
          </Link>
        ) : (
          <a key={i} href={href} target="_blank" rel="noopener noreferrer" className={cls}>
            {label}
            <span aria-hidden>↗</span>
          </a>
        )
      );
      i++;
      continue;
    }

    elements.push(
      <p key={i} className="text-sm leading-relaxed text-tata-ink/80">
        {parseInline(line, `p-${i}`)}
      </p>
    );
    i++;
  }

  return <div className={`space-y-0.5 ${className}`}>{elements}</div>;
}
