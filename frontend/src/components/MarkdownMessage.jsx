import React, { useMemo } from 'react';
import { marked } from 'marked';

// Configure marked with GitHub Flavored Markdown and line breaks
marked.setOptions({
  gfm: true,
  breaks: true,
});

/**
 * Renders Markdown text with clean typography, styled lists, bold weights, and code blocks.
 */
export default function MarkdownMessage({ content, isUser = false }) {
  const html = useMemo(() => {
    if (!content) return '';
    try {
      return marked.parse(content);
    } catch (err) {
      console.warn('Markdown parsing fallback:', err);
      return content;
    }
  }, [content]);

  if (isUser) {
    return <div style={{ whiteSpace: 'pre-wrap' }}>{content}</div>;
  }

  return (
    <div
      className="markdown-content"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
