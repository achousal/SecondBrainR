# Literature Backend Reference

Supported literature search backends, their env vars, and routing rules. Used by Turn 5 of the interview to guide the user's choices.

---

## Backends

| Backend | Env Var (required) | Env Var (optional) | Content Type |
|---------|-------------------|-------------------|--------------|
| pubmed | NCBI_EMAIL | NCBI_API_KEY | Biomedical, clinical |
| arxiv | (none) | (none) | Physics, CS, math, quant-bio |
| semantic_scholar | (none) | S2_API_KEY | Cross-domain academic |
| openalex | OPENALEX_API_KEY | (none) | Cross-domain, open metadata |
| web-search | (none) | (none) | General fallback |

## Enrichment Services

| Service | Env Var | Purpose |
|---------|---------|---------|
| crossref | LITERATURE_ENRICHMENT_EMAIL | DOI metadata, citation counts |
| unpaywall | LITERATURE_ENRICHMENT_EMAIL | Open access PDF links |

## Routing Rules

The `config_overrides.research` section defines a 3-tier routing:

1. **primary** -- first backend tried for /literature searches
2. **fallback** -- used when primary returns no results or errors
3. **last_resort** -- always "web-search" as final fallback

The `config_overrides.literature.sources` list defines which backends are available (not routing order).

## Domain Recommendations

| Domain Type | Recommended Primary | Recommended Sources |
|------------|--------------------|--------------------|
| Biomedical/clinical | pubmed | [pubmed, semantic_scholar, openalex] |
| Physics/engineering | arxiv | [arxiv, semantic_scholar, openalex] |
| Social science | openalex | [openalex, semantic_scholar] |
| Computer science | semantic_scholar | [arxiv, semantic_scholar, openalex] |
| Interdisciplinary | semantic_scholar | [pubmed, arxiv, semantic_scholar, openalex] |

## Env Var Descriptions (for profile.yaml generation)

```yaml
NCBI_EMAIL: "Required by NCBI API policy -- use your institutional email"
NCBI_API_KEY: "NCBI EUTILS for 10 req/s -- https://www.ncbi.nlm.nih.gov/account/settings/"
OPENALEX_API_KEY: "OpenAlex API key -- https://openalex.org/"
S2_API_KEY: "Semantic Scholar higher rate limits -- https://www.semanticscholar.org/product/api"
LITERATURE_ENRICHMENT_EMAIL: "For CrossRef polite pool + Unpaywall TOS -- your institutional email"
```
