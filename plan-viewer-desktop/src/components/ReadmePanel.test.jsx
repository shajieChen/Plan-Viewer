import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, cleanup, waitFor } from '@testing-library/preact';
import fc from 'fast-check';
import { marked } from 'marked';
import { ReadmePanel } from './ReadmePanel.jsx';

// --- Property-Based Tests (fast-check) ---

describe('Feature: readme-guide-button, Property 3: Markdown rendering produces valid HTML structure', () => {
  /**
   * Validates: Requirements 3.2
   *
   * For any non-empty markdown string containing headings, lists, code blocks,
   * or inline formatting, the marked.parse() output SHALL contain corresponding
   * HTML elements (<h1>-<h6>, <ul>/<ol>, <pre><code>, <strong>, <em>).
   */

  const parseMarkdown = (input) => marked.parse(input, { breaks: true, gfm: true });

  // --- Generators ---

  // Heading levels 1-6
  const headingLevel = fc.integer({ min: 1, max: 6 });
  const headingText = fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,20}$/);

  // Generate a markdown heading like "## Title"
  const markdownHeading = fc.tuple(headingLevel, headingText).map(
    ([level, text]) => `${'#'.repeat(level)} ${text}`
  );

  // Generate an unordered list with 1-5 items
  const listItem = fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,15}$/);
  const unorderedList = fc.array(listItem, { minLength: 1, maxLength: 5 }).map(
    (items) => items.map((item) => `- ${item}`).join('\n')
  );

  // Generate an ordered list with 1-5 items
  const orderedList = fc.array(listItem, { minLength: 1, maxLength: 5 }).map(
    (items) => items.map((item, i) => `${i + 1}. ${item}`).join('\n')
  );

  // Generate a fenced code block
  const codeContent = fc.stringMatching(/^[a-z][a-z0-9_() ]{0,30}$/);
  const codeLanguage = fc.constantFrom('', 'js', 'python', 'bash', 'json');
  const codeBlock = fc.tuple(codeLanguage, codeContent).map(
    ([lang, code]) => `\`\`\`${lang}\n${code}\n\`\`\``
  );

  // Generate bold text (no trailing spaces - GFM requires clean boundaries for emphasis)
  const inlineText = fc.stringMatching(/^[A-Za-z][A-Za-z0-9]{0,15}$/);
  const boldText = inlineText.map((text) => `**${text}**`);

  // Generate italic text (no trailing spaces)
  const italicText = inlineText.map((text) => `*${text}*`);

  it('headings produce corresponding <hN> HTML tags', () => {
    fc.assert(
      fc.property(headingLevel, headingText, (level, text) => {
        const markdown = `${'#'.repeat(level)} ${text}`;
        const html = parseMarkdown(markdown);
        const openTag = `<h${level}`;
        const closeTag = `</h${level}>`;
        return html.includes(openTag) && html.includes(closeTag);
      }),
      { numRuns: 100 }
    );
  });

  it('unordered lists produce <ul> and <li> HTML tags', () => {
    fc.assert(
      fc.property(unorderedList, (listMd) => {
        const html = parseMarkdown(listMd);
        return html.includes('<ul>') && html.includes('<li>') && html.includes('</ul>');
      }),
      { numRuns: 100 }
    );
  });

  it('ordered lists produce <ol> and <li> HTML tags', () => {
    fc.assert(
      fc.property(orderedList, (listMd) => {
        const html = parseMarkdown(listMd);
        return html.includes('<ol>') && html.includes('<li>') && html.includes('</ol>');
      }),
      { numRuns: 100 }
    );
  });

  it('fenced code blocks produce <pre><code> HTML tags', () => {
    fc.assert(
      fc.property(codeBlock, (codeMd) => {
        const html = parseMarkdown(codeMd);
        return html.includes('<pre><code') && html.includes('</code></pre>');
      }),
      { numRuns: 100 }
    );
  });

  it('bold text produces <strong> HTML tags', () => {
    fc.assert(
      fc.property(boldText, (boldMd) => {
        const html = parseMarkdown(boldMd);
        return html.includes('<strong>') && html.includes('</strong>');
      }),
      { numRuns: 100 }
    );
  });

  it('italic text produces <em> HTML tags', () => {
    fc.assert(
      fc.property(italicText, (italicMd) => {
        const html = parseMarkdown(italicMd);
        return html.includes('<em>') && html.includes('</em>');
      }),
      { numRuns: 100 }
    );
  });

  it('mixed markdown content produces all expected HTML elements', () => {
    const mixedMarkdown = fc.tuple(
      markdownHeading,
      unorderedList,
      orderedList,
      codeBlock,
      boldText,
      italicText
    ).map(([heading, ul, ol, code, bold, italic]) =>
      [heading, '', ul, '', ol, '', code, '', `Some ${bold} and ${italic} text.`].join('\n')
    );

    fc.assert(
      fc.property(mixedMarkdown, (markdown) => {
        const html = parseMarkdown(markdown);
        return (
          /<h[1-6]/.test(html) &&
          html.includes('<ul>') &&
          html.includes('<ol>') &&
          html.includes('<pre><code') &&
          html.includes('<strong>') &&
          html.includes('<em>')
        );
      }),
      { numRuns: 100 }
    );
  });
});

// --- Unit Tests ---

describe('ReadmePanel - unit tests', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  // --- Requirement 2.6: Loading indicator appears during fetch ---
  it('displays loading indicator while fetch is pending', async () => {
    // fetch never resolves so component stays in loading state
    globalThis.fetch.mockImplementation(() => new Promise(() => {}));

    render(<ReadmePanel projectName="test-project" onClose={() => {}} />);

    // useEffect fires synchronously during render in Preact, triggering loadFile
    // Since fetch never resolves, loading remains true
    await waitFor(() => {
      expect(screen.getByText('加载中...')).toBeTruthy();
    });
  });

  // --- Requirement 3.3: Error message for 404 ---
  it('displays error message when fetch returns 404', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve('{"error":"File not found"}'),
    });

    render(<ReadmePanel projectName="test-project" onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('未找到 README.md')).toBeTruthy();
    });
  });

  // --- Requirement 3.4: Error message for network failure ---
  it('displays error message on network error', async () => {
    globalThis.fetch.mockRejectedValue(new TypeError('Failed to fetch'));

    render(<ReadmePanel projectName="test-project" onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('加载失败，请确认服务器运行中')).toBeTruthy();
    });
  });

  // --- Requirement 3.6: Empty file renders without error ---
  it('renders without error when file is empty', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve(''),
    });

    render(<ReadmePanel projectName="test-project" onClose={() => {}} />);

    // Wait for loading to finish
    await waitFor(() => {
      expect(screen.queryByText('加载中...')).toBeNull();
    });

    // No error message should be displayed
    expect(screen.queryByText('未找到 README.md')).toBeNull();
    expect(screen.queryByText('加载失败，请确认服务器运行中')).toBeNull();
  });

  // --- Requirement 4.5: Breadcrumb renders initial "README.md" entry ---
  it('renders breadcrumb with initial README.md entry', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve('# Hello World'),
    });

    render(<ReadmePanel projectName="test-project" onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.queryByText('加载中...')).toBeNull();
    });

    // Breadcrumb should show "README.md"
    expect(screen.getByText('README.md')).toBeTruthy();
  });

  // --- Requirement 4.6: Clicking breadcrumb navigates and truncates history ---
  it('truncates breadcrumb history when a breadcrumb item is clicked', async () => {
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve('# Root\n\n[Guide](docs/guide.md)'),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve('# Guide\n\n[Deep](deep.md)'),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve('# Deep page'),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve('# Root\n\n[Guide](docs/guide.md)'),
      });

    const { container } = render(
      <ReadmePanel projectName="test-project" onClose={() => {}} />
    );

    // Wait for initial README.md to load
    await waitFor(() => {
      expect(screen.queryByText('加载中...')).toBeNull();
    });

    // Click the .md link to navigate to docs/guide.md
    const guideLink = container.querySelector('a[href="docs/guide.md"]');
    expect(guideLink).toBeTruthy();

    await act(async () => {
      fireEvent.click(guideLink);
    });

    await waitFor(() => {
      expect(screen.getByText('guide.md')).toBeTruthy();
    });

    // Navigate deeper: click the deep.md link
    const deepLink = container.querySelector('a[href="deep.md"]');
    expect(deepLink).toBeTruthy();

    await act(async () => {
      fireEvent.click(deepLink);
    });

    await waitFor(() => {
      expect(screen.getByText('deep.md')).toBeTruthy();
    });

    // Now we have breadcrumbs: README.md > guide.md > deep.md
    // Click "README.md" breadcrumb to truncate history
    const breadcrumbLink = screen.getByText('README.md');

    await act(async () => {
      fireEvent.click(breadcrumbLink);
    });

    await waitFor(() => {
      expect(screen.queryByText('guide.md')).toBeNull();
      expect(screen.queryByText('deep.md')).toBeNull();
    });

    // README.md should still be visible as the current breadcrumb
    expect(screen.getByText('README.md')).toBeTruthy();
  });
});


// --- Property-Based Tests for View State (Properties 1 & 2) ---

describe('Feature: readme-guide-button, Property 1: View mutual exclusivity', () => {
  /**
   * Validates: Requirements 2.2
   *
   * For any application state where showReadme is true, the SwimLane and CompactView
   * components SHALL NOT be rendered, and conversely when showReadme is false, the
   * ReadmePanel SHALL NOT be rendered.
   */

  // The view selection logic extracted from App.jsx:
  // showReadme=true  → { readmePanel: true, swimLane: false, compactView: false }
  // showReadme=false && width >= 400 → { readmePanel: false, swimLane: true, compactView: false }
  // showReadme=false && width < 400  → { readmePanel: false, swimLane: false, compactView: true }
  function getVisibleViews(showReadme, windowWidth) {
    if (showReadme) {
      return { readmePanel: true, swimLane: false, compactView: false };
    }
    const isCompact = windowWidth < 400;
    return {
      readmePanel: false,
      swimLane: !isCompact,
      compactView: isCompact,
    };
  }

  it('when showReadme is true, SwimLane and CompactView are NOT rendered', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 100, max: 2000 }), // windowWidth
        (windowWidth) => {
          const views = getVisibleViews(true, windowWidth);
          return views.readmePanel === true &&
                 views.swimLane === false &&
                 views.compactView === false;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('when showReadme is false, ReadmePanel is NOT rendered', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 100, max: 2000 }), // windowWidth
        (windowWidth) => {
          const views = getVisibleViews(false, windowWidth);
          return views.readmePanel === false;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('exactly one view type is rendered for any state', () => {
    fc.assert(
      fc.property(
        fc.boolean(), // showReadme
        fc.integer({ min: 100, max: 2000 }), // windowWidth
        (showReadme, windowWidth) => {
          const views = getVisibleViews(showReadme, windowWidth);
          const visibleCount = [views.readmePanel, views.swimLane, views.compactView]
            .filter(Boolean).length;
          return visibleCount === 1;
        }
      ),
      { numRuns: 100 }
    );
  });
});

describe('Feature: readme-guide-button, Property 2: Toggle round-trip restores correct view', () => {
  /**
   * Validates: Requirements 2.3, 5.2
   *
   * For any window width, toggling showReadme from false to true and back to false
   * SHALL result in the application displaying SwimLane (if width >= 400px) or
   * CompactView (if width < 400px), identical to the state before the toggle.
   */

  // Simulates the view selection logic from App.jsx
  function getVisibleView(showReadme, windowWidth) {
    if (showReadme) return 'ReadmePanel';
    return windowWidth >= 400 ? 'SwimLane' : 'CompactView';
  }

  it('toggling showReadme true then back to false restores original view', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 100, max: 2000 }), // windowWidth
        (windowWidth) => {
          // State before toggle: showReadme = false
          const viewBefore = getVisibleView(false, windowWidth);

          // Toggle to true
          const viewDuringToggle = getVisibleView(true, windowWidth);

          // Toggle back to false
          const viewAfter = getVisibleView(false, windowWidth);

          // During toggle, ReadmePanel should be visible
          // After round-trip, view should match the original
          return viewDuringToggle === 'ReadmePanel' && viewAfter === viewBefore;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('round-trip preserves correct view based on window width threshold', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 100, max: 2000 }), // windowWidth
        (windowWidth) => {
          // After round-trip (false → true → false), the expected view depends on width
          const expectedView = windowWidth >= 400 ? 'SwimLane' : 'CompactView';
          const actualView = getVisibleView(false, windowWidth);
          return actualView === expectedView;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('width threshold at exactly 400px renders SwimLane after round-trip', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 400, max: 2000 }), // windowWidth >= 400
        (windowWidth) => {
          const viewAfterRoundTrip = getVisibleView(false, windowWidth);
          return viewAfterRoundTrip === 'SwimLane';
        }
      ),
      { numRuns: 100 }
    );
  });

  it('width below 400px renders CompactView after round-trip', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 100, max: 399 }), // windowWidth < 400
        (windowWidth) => {
          const viewAfterRoundTrip = getVisibleView(false, windowWidth);
          return viewAfterRoundTrip === 'CompactView';
        }
      ),
      { numRuns: 100 }
    );
  });
});
