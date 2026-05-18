import { describe, it, expect } from 'vitest';
import { resolveRelativePath, classifyLink } from './pathUtils.js';

describe('resolveRelativePath', () => {
  it('resolves a sibling file from a root-level file', () => {
    expect(resolveRelativePath('README.md', 'docs/setup.md')).toBe('docs/setup.md');
  });

  it('resolves a sibling file from a nested file', () => {
    expect(resolveRelativePath('docs/guide.md', 'setup.md')).toBe('docs/setup.md');
  });

  it('resolves parent directory traversal', () => {
    expect(resolveRelativePath('docs/guides/intro.md', '../setup.md')).toBe('docs/setup.md');
  });

  it('resolves current directory reference', () => {
    expect(resolveRelativePath('docs/guide.md', './setup.md')).toBe('docs/setup.md');
  });

  it('clamps paths that try to escape above project root', () => {
    expect(resolveRelativePath('README.md', '../../etc/passwd')).toBe('etc/passwd');
  });

  it('clamps deeply nested escape attempts', () => {
    expect(resolveRelativePath('docs/guide.md', '../../../secret.md')).toBe('secret.md');
  });

  it('normalizes backslashes to forward slashes', () => {
    expect(resolveRelativePath('docs\\guide.md', '..\\setup.md')).toBe('setup.md');
  });

  it('handles multiple consecutive .. segments', () => {
    expect(resolveRelativePath('a/b/c/file.md', '../../other.md')).toBe('a/other.md');
  });

  it('handles paths with . in the middle', () => {
    expect(resolveRelativePath('docs/guide.md', './sub/./file.md')).toBe('docs/sub/file.md');
  });

  it('handles root-level file with .. that clamps to root', () => {
    expect(resolveRelativePath('file.md', '../other.md')).toBe('other.md');
  });

  it('result contains no . or .. segments', () => {
    const result = resolveRelativePath('a/b/c.md', './../d/./e/../f.md');
    expect(result).not.toMatch(/(?:^|\/)\.{1,2}(?:\/|$)/);
  });

  it('result does not start with a slash', () => {
    const result = resolveRelativePath('a/b.md', '/absolute.md');
    expect(result).not.toMatch(/^\//);
  });
});

describe('classifyLink', () => {
  it('classifies http:// URLs as absolute', () => {
    expect(classifyLink('http://example.com')).toBe('absolute');
  });

  it('classifies https:// URLs as absolute', () => {
    expect(classifyLink('https://github.com/repo')).toBe('absolute');
  });

  it('classifies relative .md paths as relative-md', () => {
    expect(classifyLink('docs/setup.md')).toBe('relative-md');
  });

  it('classifies ./relative .md paths as relative-md', () => {
    expect(classifyLink('./guide.md')).toBe('relative-md');
  });

  it('classifies ../parent .md paths as relative-md', () => {
    expect(classifyLink('../README.md')).toBe('relative-md');
  });

  it('classifies relative non-.md paths as other-relative', () => {
    expect(classifyLink('docs/image.png')).toBe('other-relative');
  });

  it('classifies files without extension as other-relative', () => {
    expect(classifyLink('Makefile')).toBe('other-relative');
  });

  it('classifies .txt files as other-relative', () => {
    expect(classifyLink('notes.txt')).toBe('other-relative');
  });

  it('does not misclassify .md in the middle of the path', () => {
    expect(classifyLink('docs.md/image.png')).toBe('other-relative');
  });

  it('classifies uppercase .MD as other-relative (case-sensitive)', () => {
    // The design specifies "ending in .md" — case-sensitive
    expect(classifyLink('README.MD')).toBe('other-relative');
  });
});

// --- Property-Based Tests (fast-check) ---
import fc from 'fast-check';

describe('Feature: readme-guide-button, Property 4: Relative path resolution normalizes correctly', () => {
  /**
   * Validates: Requirements 4.1
   *
   * For any current file path and any relative link path (potentially containing
   * `.` and `..` segments), resolveRelativePath SHALL produce a result that:
   * (a) contains no `.` or `..` segments,
   * (b) does not begin with `/` or `\`, and
   * (c) does not escape above the project root (no leading `..`).
   */

  // Generator for path segments (simple alphanumeric names)
  const pathSegment = fc.stringMatching(/^[a-z][a-z0-9_-]{0,7}$/);

  // Generator for a file path like "dir1/dir2/file.md"
  const filePath = fc.tuple(
    fc.array(pathSegment, { minLength: 0, maxLength: 4 }),
    pathSegment
  ).map(([dirs, file]) => [...dirs, `${file}.md`].join('/'));

  // Generator for relative path segments that may include `.` and `..`
  const relativeSegment = fc.oneof(
    pathSegment,
    fc.constant('.'),
    fc.constant('..')
  );

  // Generator for a relative link path like "../docs/./file.md"
  const relativeLinkPath = fc.tuple(
    fc.array(relativeSegment, { minLength: 0, maxLength: 5 }),
    pathSegment
  ).map(([segments, file]) => [...segments, `${file}.md`].join('/'));

  it('result contains no . or .. segments', () => {
    fc.assert(
      fc.property(filePath, relativeLinkPath, (currentFile, relPath) => {
        const result = resolveRelativePath(currentFile, relPath);
        // No segment should be exactly '.' or '..'
        const segments = result.split('/');
        for (const seg of segments) {
          if (seg === '.' || seg === '..') return false;
        }
        return true;
      }),
      { numRuns: 100 }
    );
  });

  it('result does not begin with / or \\', () => {
    fc.assert(
      fc.property(filePath, relativeLinkPath, (currentFile, relPath) => {
        const result = resolveRelativePath(currentFile, relPath);
        return !result.startsWith('/') && !result.startsWith('\\');
      }),
      { numRuns: 100 }
    );
  });

  it('result does not escape above the project root (no leading ..)', () => {
    fc.assert(
      fc.property(filePath, relativeLinkPath, (currentFile, relPath) => {
        const result = resolveRelativePath(currentFile, relPath);
        // The result should not start with '..' segment
        return !result.startsWith('..');
      }),
      { numRuns: 100 }
    );
  });
});

describe('Feature: readme-guide-button, Property 5: Link classification is exhaustive and correct', () => {
  /**
   * Validates: Requirements 4.2, 4.3
   *
   * For any href string, classifyLink SHALL classify it into exactly one category:
   * (a) absolute URL → 'absolute',
   * (b) relative .md → 'relative-md',
   * (c) other relative → 'other-relative'
   */

  // Generator for absolute URLs (http:// or https://)
  const absoluteUrl = fc.oneof(
    fc.webUrl(),
    fc.tuple(
      fc.constantFrom('http://', 'https://'),
      fc.domain(),
      fc.webPath()
    ).map(([protocol, domain, path]) => `${protocol}${domain}${path}`)
  );

  // Generator for relative .md paths
  const pathSegment = fc.stringMatching(/^[a-z][a-z0-9_-]{0,7}$/);

  const relativeMdPath = fc.tuple(
    fc.array(
      fc.oneof(pathSegment, fc.constant('.'), fc.constant('..')),
      { minLength: 0, maxLength: 4 }
    ),
    pathSegment
  ).map(([dirs, file]) => [...dirs, `${file}.md`].join('/'));

  // Generator for other relative paths (not ending in .md, not starting with http(s)://)
  const otherRelativePath = fc.tuple(
    fc.array(pathSegment, { minLength: 0, maxLength: 4 }),
    pathSegment,
    fc.constantFrom('.txt', '.png', '.js', '.html', '.css', '.json', '')
  ).map(([dirs, file, ext]) => [...dirs, `${file}${ext}`].join('/'))
    .filter(p => !p.endsWith('.md') && !p.startsWith('http://') && !p.startsWith('https://'));

  it('classifies absolute URLs as "absolute"', () => {
    fc.assert(
      fc.property(absoluteUrl, (url) => {
        return classifyLink(url) === 'absolute';
      }),
      { numRuns: 100 }
    );
  });

  it('classifies relative .md paths as "relative-md"', () => {
    fc.assert(
      fc.property(relativeMdPath, (path) => {
        return classifyLink(path) === 'relative-md';
      }),
      { numRuns: 100 }
    );
  });

  it('classifies other relative paths as "other-relative"', () => {
    fc.assert(
      fc.property(otherRelativePath, (path) => {
        return classifyLink(path) === 'other-relative';
      }),
      { numRuns: 100 }
    );
  });

  it('every href gets exactly one classification', () => {
    // Generate any string and verify it maps to exactly one of the three categories
    const anyHref = fc.oneof(absoluteUrl, relativeMdPath, otherRelativePath, fc.string({ minLength: 1 }));

    fc.assert(
      fc.property(anyHref, (href) => {
        const result = classifyLink(href);
        const validCategories = ['absolute', 'relative-md', 'other-relative'];
        return validCategories.includes(result);
      }),
      { numRuns: 100 }
    );
  });
});
