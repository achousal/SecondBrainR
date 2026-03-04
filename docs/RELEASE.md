# Release Process

Main always carries exactly one commit. History is preserved in archive tags.

## Version Scheme

```
vX.Y.Z          -- clean single-commit snapshot (current main)
vX.Y.Z-archive  -- full history before that squash
```

## To bump a version

1. Confirm current version: `git tag -l --sort=-v:refname | head -3`
2. Choose next version number (e.g., v0.7.3 -> v0.8.0)
3. Run:

```bash
# 1. Archive current main
git tag -a vCURRENT-archive -m "vCURRENT archive" HEAD
git push origin vCURRENT-archive

# 2. Orphan-reset main to single commit
git checkout --orphan temp-squash
git commit -m "vNEXT EngramR Knowledge System"
git branch -M main

# 3. Tag and push
git tag -a vNEXT -m "vNEXT EngramR Knowledge System"
git push --force origin main
git push origin vNEXT
```

## Site deployment cleanup

After a version bump, delete previous GitHub Pages deployments to keep only the current one active.

```bash
# List deployments (most recent first)
gh api repos/{owner}/{repo}/deployments --paginate --jq '.[].id'

# Delete old deployments (keep only the latest)
# First set each old deployment to inactive, then delete
gh api repos/{owner}/{repo}/deployments/{id} -X POST -f state=inactive
gh api repos/{owner}/{repo}/deployments/{id} -X DELETE
```

Or use the GitHub UI: Settings > Environments > github-pages > remove old deployments.

After the orphan reset, the deploy workflow re-triggers on the next push that touches `site/**`, deploying a fresh build from the new single commit.

## Shorthand

Tell Claude: "bump to vX.Y.Z" or "new release" -- the process is documented and remembered.

## Tag History

| Tag | Type | Description |
|-----|------|-------------|
| v0.7.1 | archive | First tracked version |
| v0.7.2-archive | archive | Full history before v0.7.3 squash |
| v0.7.3 | release | Current |
