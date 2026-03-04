/** TOC scroll-spy: highlights the active heading in the right-rail TOC. */
function initTocSpy(): void {
  const tocLinks = document.querySelectorAll<HTMLAnchorElement>(".toc-link");
  if (tocLinks.length === 0) return;

  const headingEls: HTMLElement[] = [];
  tocLinks.forEach((link) => {
    const slug = link.dataset.tocSlug;
    if (!slug) return;
    const el = document.getElementById(slug);
    if (el) headingEls.push(el);
  });

  if (headingEls.length === 0) return;

  let activeSlug = "";

  function setActive(slug: string): void {
    if (slug === activeSlug) return;
    activeSlug = slug;
    tocLinks.forEach((link) => {
      link.classList.toggle("toc-active", link.dataset.tocSlug === slug);
    });
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          setActive(entry.target.id);
          break;
        }
      }
    },
    { rootMargin: "-80px 0px -60% 0px", threshold: 0 },
  );

  headingEls.forEach((el) => observer.observe(el));
}

document.addEventListener("DOMContentLoaded", initTocSpy);
